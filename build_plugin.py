#!/usr/bin/env python3
"""
nanoTracker Plugin Builder
Packages a plugin source directory into a .ntins (instrument) or .ntsfx (fx) archive.

Usage:
    python build_plugin.py <plugin_dir>
    python build_plugin.py <plugin_dir> --out <output_dir>
    python build_plugin.py <plugin_dir> --name "My Plugin 1.0.0"

Requirements: Python 3.8+ (stdlib only — no pip dependencies)
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path


# ── Validation ────────────────────────────────────────────────────────────────

SUPPORTED_SCHEMA_VERSIONS = {1, 2}
VALID_TYPES = {"instrument", "fx"}
VALID_VOICE_STEALING = {"oldest", "quietest", "none"}
VALID_OSC_TYPES = {"sine", "square", "sawtooth", "triangle", "noise"}
VALID_FX_NODE_TYPES = {
    "gain", "delay", "biquad", "compressor", "convolver",
    "panner", "waveshaper", "worklet",
    # v2 additions
    "mixer", "splitter", "merger", "oscillator", "constant",
    "analyser", "lfo", "envelope",
}
VALID_CURVE_TYPES = {"sigmoid", "clip", "fold"}
VALID_FILTER_TYPES = {"lowpass", "highpass", "bandpass", "notch", "allpass", "peaking", "lowshelf", "highshelf"}
VALID_CONTROL_TYPES = {
    "knob", "slider", "toggle", "select", "number", "waveform_view",
    # v2 additions
    "xy_pad", "envelope_editor", "meter", "label", "group",
}

# Files to exclude from the archive
EXCLUDE_PATTERNS = {
    ".DS_Store", "Thumbs.db", "__pycache__", ".git",
    "*.pyc", "*.pyo", "build_plugin.py",
}


class ValidationError(Exception):
    pass


def err(msg: str) -> None:
    raise ValidationError(msg)


def require_str(obj: dict, key: str, where: str) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v.strip():
        err(f"{where}.{key} must be a non-empty string")
    return v


def opt_str(obj: dict, key: str, fallback: str = "") -> str:
    v = obj.get(key, fallback)
    return v if isinstance(v, str) else fallback


def opt_number(obj: dict, key: str, fallback: float = 0.0) -> float:
    v = obj.get(key, fallback)
    if not isinstance(v, (int, float)):
        err(f"'{key}' must be a number, got {type(v).__name__}")
    return float(v)


def opt_bool(obj: dict, key: str, fallback: bool = False) -> bool:
    v = obj.get(key, fallback)
    if not isinstance(v, bool):
        err(f"'{key}' must be a boolean")
    return v


def validate_manifest(manifest: dict) -> str:
    """Validates manifest block, returns plugin type."""
    if not isinstance(manifest, dict):
        err("manifest must be an object")
    require_str(manifest, "name", "manifest")
    require_str(manifest, "version", "manifest")
    plugin_type = require_str(manifest, "type", "manifest")
    if plugin_type not in VALID_TYPES:
        err(f"manifest.type must be one of {VALID_TYPES}, got '{plugin_type}'")
    name = manifest["name"]
    if len(name) > 64:
        err(f"manifest.name is too long ({len(name)} chars, max 64)")
    return plugin_type


def validate_parameters(params: list) -> None:
    if not isinstance(params, list):
        err("parameters must be an array")
    for i, p in enumerate(params):
        loc = f"parameters[{i}]"
        if not isinstance(p, dict):
            err(f"{loc} must be an object")
        require_str(p, "key", loc)
        require_str(p, "label", loc)
        mn = opt_number(p, "min", 0)
        mx = opt_number(p, "max", 1)
        df = opt_number(p, "default", 0)
        opt_number(p, "step", 0.01)
        if mn >= mx:
            err(f"{loc}: min ({mn}) must be less than max ({mx})")
        if not (mn <= df <= mx):
            print(f"  WARNING: {loc}.default ({df}) is outside [{mn}, {mx}]")


def validate_ui(ui: dict) -> None:
    if not isinstance(ui, dict):
        err("ui must be an object")
    layout = ui.get("layout", "flex")
    if layout not in {"grid", "flex"}:
        err(f"ui.layout must be 'grid' or 'flex', got '{layout}'")
    controls = ui.get("controls", [])
    if not isinstance(controls, list):
        err("ui.controls must be an array")
    for i, c in enumerate(controls):
        loc = f"ui.controls[{i}]"
        if not isinstance(c, dict):
            err(f"{loc} must be an object")
        ctrl_type = c.get("type", "knob")
        if ctrl_type not in VALID_CONTROL_TYPES:
            err(f"{loc}.type must be one of {VALID_CONTROL_TYPES}, got '{ctrl_type}'")


def validate_instrument_dsp(dsp: dict, source_files: set) -> None:
    if not isinstance(dsp, dict):
        err("dsp must be an object")
    processor_name = dsp.get("processorName")
    if processor_name is not None and not isinstance(processor_name, str):
        err("dsp.processorName must be a string or null")
    voices = dsp.get("voices", 8)
    if not isinstance(voices, int) or not (1 <= voices <= 32):
        err(f"dsp.voices must be an integer 1–32, got {voices!r}")
    vs = opt_str(dsp, "voiceStealing", "oldest")
    if vs not in VALID_VOICE_STEALING:
        err(f"dsp.voiceStealing must be one of {VALID_VOICE_STEALING}")

    oscs = dsp.get("oscillators", [])
    if not isinstance(oscs, list):
        err("dsp.oscillators must be an array")
    for i, o in enumerate(oscs):
        loc = f"dsp.oscillators[{i}]"
        ot = o.get("type", "sine")
        if ot not in VALID_OSC_TYPES:
            err(f"{loc}.type must be one of {VALID_OSC_TYPES}")
        mix = opt_number(o, "mix", 1.0)
        if not (0.0 <= mix <= 1.0):
            err(f"{loc}.mix must be 0–1")

    samples = dsp.get("samples", [])
    if not isinstance(samples, list):
        err("dsp.samples must be an array")
    for i, s in enumerate(samples):
        loc = f"dsp.samples[{i}]"
        if not isinstance(s, dict):
            err(f"{loc} must be an object")
        file_path = require_str(s, "file", loc)
        if file_path not in source_files:
            print(f"  WARNING: {loc}.file '{file_path}' not found in source directory")
        kr = s.get("keyRange", {})
        vr = s.get("velocityRange", {})
        lo, hi = opt_number(kr, "lo", 0), opt_number(kr, "hi", 127)
        if lo > hi:
            err(f"{loc}.keyRange: lo ({lo}) > hi ({hi})")
        lo, hi = opt_number(vr, "lo", 0), opt_number(vr, "hi", 127)
        if lo > hi:
            err(f"{loc}.velocityRange: lo ({lo}) > hi ({hi})")
        start_offset = opt_number(s, "startOffset", 0.0)
        duration = opt_number(s, "duration", 0.0)
        if start_offset < 0:
            err(f"{loc}.startOffset must be >= 0")
        if duration < 0:
            err(f"{loc}.duration must be >= 0 (0 = play to end)")

    env = dsp.get("envelope", {})
    if not isinstance(env, dict):
        err("dsp.envelope must be an object")
    for field in ("attack", "decay", "release"):
        v = opt_number(env, field, 0.01)
        if v < 0:
            err(f"dsp.envelope.{field} must be >= 0")
    sustain = opt_number(env, "sustain", 0.8)
    if not (0.0 <= sustain <= 1.0):
        err(f"dsp.envelope.sustain must be 0–1")

    filt = dsp.get("filter")
    if filt is not None:
        if not isinstance(filt, dict):
            err("dsp.filter must be an object or null")
        ft = opt_str(filt, "type", "lowpass")
        if ft not in VALID_FILTER_TYPES:
            err(f"dsp.filter.type must be one of {VALID_FILTER_TYPES}")


def validate_fx_dsp(dsp: dict, source_files: set) -> None:
    if not isinstance(dsp, dict):
        err("dsp must be an object")
    nodes = dsp.get("nodes", [])
    if not isinstance(nodes, list):
        err("dsp.nodes must be an array")
    node_ids = {"input", "output"}
    for i, n in enumerate(nodes):
        loc = f"dsp.nodes[{i}]"
        if not isinstance(n, dict):
            err(f"{loc} must be an object")
        node_id = require_str(n, "id", loc)
        if node_id in node_ids:
            err(f"{loc}.id '{node_id}' is reserved — choose a different id")
        node_ids.add(node_id)
        node_type = require_str(n, "type", loc)
        if node_type not in VALID_FX_NODE_TYPES:
            err(f"{loc}.type must be one of {VALID_FX_NODE_TYPES}")
        if node_type == "convolver":
            impulse = n.get("impulse")
            if impulse and impulse not in source_files:
                print(f"  WARNING: {loc}.impulse '{impulse}' not found in source directory")
        if node_type == "waveshaper":
            curve = n.get("curve")
            if curve and curve not in VALID_CURVE_TYPES:
                err(f"{loc}.curve must be one of {VALID_CURVE_TYPES}")

    conns = dsp.get("connections", [])
    if not isinstance(conns, list):
        err("dsp.connections must be an array")
    for i, c in enumerate(conns):
        loc = f"dsp.connections[{i}]"
        require_str(c, "from", loc)
        require_str(c, "to", loc)
        if c["from"] not in node_ids:
            print(f"  WARNING: {loc}.from '{c['from']}' not in known node ids")
        if c["to"] not in node_ids:
            print(f"  WARNING: {loc}.to '{c['to']}' not in known node ids")


def validate_loop_presets(presets: list) -> None:
    if not isinstance(presets, list):
        err("loopPresets must be an array")
    for i, p in enumerate(presets):
        loc = f"loopPresets[{i}]"
        if not isinstance(p, dict):
            err(f"{loc} must be an object")
        require_str(p, "name", loc)
        steps = p.get("steps", [])
        if not isinstance(steps, list):
            err(f"{loc}.steps must be an array")
        for j, s in enumerate(steps):
            sloc = f"{loc}.steps[{j}]"
            if not isinstance(s, dict):
                err(f"{sloc} must be an object")
            pad = opt_number(s, "padIndex", 0)
            if pad < 0:
                err(f"{sloc}.padIndex must be >= 0")
            vol = opt_number(s, "volume", 100)
            if not (0 <= vol <= 100):
                err(f"{sloc}.volume must be 0–100")


def validate_plugin_json(data: dict, source_files: set) -> tuple[str, str]:
    """
    Validates entire plugin.json.
    Returns (plugin_type, suggested_filename_stem).
    """
    schema_version = data.get("schemaVersion")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        err(
            f"Unsupported schemaVersion: {schema_version!r}. "
            f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )

    manifest = data.get("manifest", {})
    plugin_type = validate_manifest(manifest)

    params = data.get("parameters", [])
    validate_parameters(params)

    ui = data.get("ui", {"layout": "flex", "controls": []})
    validate_ui(ui)

    dsp = data.get("dsp")
    if dsp is None:
        err("dsp block is required")

    if plugin_type == "instrument":
        validate_instrument_dsp(dsp, source_files)
        loop_presets = data.get("loopPresets", [])
        if loop_presets:
            validate_loop_presets(loop_presets)
    else:
        validate_fx_dsp(dsp, source_files)

    # Check script.js vs processorName consistency
    processor_name = dsp.get("processorName")
    has_script = "script.js" in source_files
    if processor_name and not has_script:
        print(f"  WARNING: processorName is set to '{processor_name}' but script.js is not present")
    if has_script and not processor_name:
        print("  WARNING: script.js is present but processorName is null — worklet will not be registered")

    name = manifest["name"]
    version = manifest["version"]
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    stem = f"{safe_name}_{version}"
    return plugin_type, stem


# ── File collection ───────────────────────────────────────────────────────────

def should_exclude(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return True
    if name in {"__pycache__", ".git", ".gitignore", "build_plugin.py", "llm.txt"}:
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    return False


def collect_files(source_dir: Path) -> list[Path]:
    """Returns relative paths of all files to package."""
    result = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and not should_exclude(path):
            result.append(path)
    return result


# ── Build ─────────────────────────────────────────────────────────────────────

def build_plugin(source_dir: Path, output_dir: Path, name_override: str | None = None) -> Path:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()

    print(f"  Source : {source_dir}")
    print(f"  Output : {output_dir}")
    print()

    # Read plugin.json
    plugin_json_path = source_dir / "plugin.json"
    if not plugin_json_path.exists():
        err(f"plugin.json not found in {source_dir}")

    with open(plugin_json_path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            err(f"plugin.json is not valid JSON: {e}")

    # Collect files first (so validation can check referenced paths)
    all_files = collect_files(source_dir)
    source_file_set = {str(p.relative_to(source_dir)) for p in all_files}

    print("  Validating plugin.json ...")
    plugin_type, stem = validate_plugin_json(data, source_file_set)
    print("  Validation passed.")
    print()

    ext = ".ntins" if plugin_type == "instrument" else ".ntsfx"
    filename = (name_override or stem) + ext
    output_path = output_dir / filename

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Packaging {len(all_files)} file(s) ...")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for abs_path in all_files:
            rel = abs_path.relative_to(source_dir)
            zf.write(abs_path, arcname=str(rel))
            size_kb = abs_path.stat().st_size / 1024
            print(f"    + {rel}  ({size_kb:.1f} KB)")

    total_kb = output_path.stat().st_size / 1024
    print()
    print(f"  Built: {output_path.name}  ({total_kb:.1f} KB)")
    return output_path


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package a nanoTracker plugin source directory into .ntins or .ntsfx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_plugin.py ./my-reverb
  python build_plugin.py ./my-reverb --out ./dist
  python build_plugin.py ./my-reverb --name "SpaceVerb_1.0.0"
        """,
    )
    parser.add_argument(
        "source",
        metavar="PLUGIN_DIR",
        help="Directory containing plugin.json and plugin assets",
    )
    parser.add_argument(
        "--out",
        metavar="OUTPUT_DIR",
        default=None,
        help="Directory to write the archive to (default: same as PLUGIN_DIR)",
    )
    parser.add_argument(
        "--name",
        metavar="FILENAME_STEM",
        default=None,
        help="Override output filename (without extension)",
    )

    args = parser.parse_args()
    source_dir = Path(args.source)

    if not source_dir.exists():
        print(f"ERROR: source directory does not exist: {source_dir}", file=sys.stderr)
        return 1
    if not source_dir.is_dir():
        print(f"ERROR: source path is not a directory: {source_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.out) if args.out else source_dir.parent

    print("nanoTracker Plugin Builder")
    print("=" * 40)
    try:
        build_plugin(source_dir, output_dir, name_override=args.name)
    except ValidationError as e:
        print(f"\nValidation error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
