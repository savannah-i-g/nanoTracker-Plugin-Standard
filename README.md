# nanoTracker Plugin Builder

A zero-dependency command-line tool for packaging [nanoTracker](https://federated.industries/tracker) plugins. Point it at a source directory, and it validates your `plugin.json` and bundles everything into a ready-to-load archive.

---

## Contents

- [Quick Start](#quick-start)
- [Plugin Types](#plugin-types)
- [Archive Structure](#archive-structure)
- [plugin.json Reference](#pluginjson-reference)
  - [Manifest](#manifest)
  - [Parameters](#parameters)
  - [UI Controls](#ui-controls)
  - [Instrument DSP](#instrument-dsp)
  - [Sample Zones](#sample-zones)
  - [Loop Presets](#loop-presets)
  - [FX DSP](#fx-dsp)
- [AudioWorklet (script.js)](#audioworklet-scriptjs)
- [Build Tool](#build-tool)
- [Examples](#examples)
- [Common Mistakes](#common-mistakes)
- [Reference Tables](#reference-tables)

---

## Quick Start

```bash
# Package a plugin source directory
python3 build_plugin.py ./my-plugin

# Write the archive to a specific output directory
python3 build_plugin.py ./my-plugin --out ./dist

# Override the output filename
python3 build_plugin.py ./my-plugin --name "MyPlugin_1.0.0"
```

**Requirements:** Python 3.8 or later. No external packages needed — uses the standard library only.

The output extension (`.ntins` or `.ntsfx`) is determined automatically from `manifest.type` in your `plugin.json`.

---

## Plugin Types

| Type | Extension | Purpose |
|---|---|---|
| **Instrument** | `.ntins` | Polyphonic voices triggered by tracker note events. Supports sample playback, oscillators, ADSR envelopes, and filters. |
| **FX** | `.ntsfx` | Audio effect that slots into any FX Mixer channel. Defined as a declarative Web Audio node graph. |

Both types are **ZIP archives** renamed with the appropriate extension. Load them in nanoTracker via the **PLG** button in the menu bar.

---

## Archive Structure

```
my-plugin.ntins
├── plugin.json          Required — all configuration and preset data
├── script.js            Optional — AudioWorklet processor (audio thread only)
├── samples/             Optional — WAV or FLAC audio files
│   ├── kick.wav
│   └── snare.wav
└── assets/              Optional — PNG/SVG graphics
```

> **Security note:** `script.js` is loaded exclusively as an AudioWorklet processor via a Blob `ObjectURL`. It is never `eval()`-ed or imported as general JavaScript. Worklet processors run in the browser's audio rendering thread with no DOM or network access.

---

## plugin.json Reference

Every plugin begins with the same top-level envelope:

```json
{
  "schemaVersion": 2,
  "manifest": { },
  "parameters": [ ],
  "dsp": { },
  "ui": { },
  "loopPresets": [ ],
  "presets": [ ]
}
```

`loopPresets` is for instrument plugins only. `parameters`, `ui`, and `presets` are optional but recommended.

**Schema versions:** Both `1` and `2` are supported. All v2 fields are optional — a schema v1 plugin loads identically in a v2 host. Set `"schemaVersion": 2` to use new features (modulation, expanded node types, presets, etc.).

---

### Manifest

```json
"manifest": {
  "name":        "My Plugin",
  "version":     "1.0.0",
  "type":        "instrument",
  "author":      "Your Name",
  "description": "One-line description"
}
```

| Field | Required | Notes |
|---|---|---|
| `name` | Yes | Max 64 characters. Forms the plugin ID alongside `version`. |
| `version` | Yes | Semver recommended (`1.0.0`). |
| `type` | Yes | `"instrument"` or `"fx"`. Determines the archive extension. |
| `author` | No | — |
| `description` | No | Shown in the Plugins panel. |

The plugin's runtime ID is `plugin:Name@version` — this is what gets stored in `.ftrk` save files.

---

### Parameters

Parameters are the interface between the tracker's automation system and your plugin's DSP.

```json
"parameters": [
  {
    "key":             "envelope.attack",
    "label":           "ATTACK",
    "min":             0.001,
    "max":             4.0,
    "default":         0.01,
    "step":            0.001,
    "unit":            "s",
    "displayDecimals": 3
  }
]
```

| Field | Required | Notes |
|---|---|---|
| `key` | Yes | Dot-path for instruments (`envelope.attack`). `nodeId.audioParam` for FX (`wet.gain`). |
| `label` | Yes | ALL-CAPS, ≤8 chars for best display. |
| `min` / `max` | Yes | `min` must be strictly less than `max`. |
| `default` | Yes | Should be within `[min, max]`. |
| `step` | Yes | Increment for dragging/scrolling. |
| `unit` | No | `"s"`, `"Hz"`, `"%"`, `"dB"`, `"ms"`, or `""`. |
| `displayDecimals` | No | Integer. Controls LCD digit precision. |
| `group` | No | **v2.** UI grouping category string (e.g. `"FILTER"`, `"ENVELOPE"`). |
| `curve` | No | **v2.** Value mapping: `"linear"` (default), `"exponential"`, or `"logarithmic"`. Exponential bunches values toward the bottom (good for frequency); logarithmic bunches toward the top. |

**Convention:** Wet/dry parameters use the `0–100` range (the host divides by 100 internally before setting the `AudioParam`). Time parameters always use seconds.

---

### UI Controls

```json
"ui": {
  "layout": "grid",
  "controls": [
    { "type": "knob",          "parameter": "envelope.attack",  "label": "ATK"   },
    { "type": "slider",        "parameter": "filter.frequency", "label": "CUTOFF" },
    { "type": "waveform_view", "sampleIndex": 0,                "label": "WAVE"  }
  ]
}
```

| Control type | Best for | Notes |
|---|---|---|
| `knob` | Continuous params | 270° rotary dial. |
| `slider` | Continuous params | Vertical or horizontal fader. |
| `toggle` | Boolean params | ON/OFF button. |
| `select` | Discrete enum values | Dropdown. Requires `"options": ["A", "B", "C"]`. |
| `number` | Precise numeric entry | LCD click-to-edit field. |
| `waveform_view` | Sample/analyser preview | Use `"sampleIndex"` (static) or `"analyserNode"` (live). |
| `xy_pad` | **v2.** 2D control | Requires `"parameterX"` and `"parameterY"`. |
| `envelope_editor` | **v2.** ADSR visual | Draggable breakpoints. Set `"parameter": "envelope"` for the prefix group. |
| `meter` | **v2.** Level meter | Requires `"analyserNode"` (ID of an analyser DSP node). |
| `label` | **v2.** Static text | Display-only. Set `"label": "YOUR TEXT"`. |
| `group` | **v2.** Container | Nests `"children": [...]` with `"style": "row"` or `"column"`. |

`layout` is either `"grid"` (even columns) or `"flex"` (left-to-right wrap).

#### v2 UI-level fields

```json
"ui": {
  "layout": "flex",
  "accentColor": "#ff6600",
  "minWidth": 300,
  "minHeight": 200,
  "controls": [ ]
}
```

| Field | Notes |
|---|---|
| `accentColor` | **v2.** CSS colour for plugin accent theming (knob highlights, waveform colour). |
| `minWidth` / `minHeight` | **v2.** Pixel hints for the plugin UI panel. |

#### v2 control fields

| Field | Applies to | Notes |
|---|---|---|
| `options` | `select` | Array of option label strings. Parameter value = selected index. |
| `parameterX` / `parameterY` | `xy_pad` | Parameter keys for X and Y axes. |
| `analyserNode` | `waveform_view`, `meter` | ID of an `analyser` node in the DSP graph. |
| `children` | `group` | Nested array of controls. |
| `style` | `group` | `"row"` or `"column"` flex direction. |
| `width` / `height` | `waveform_view`, `xy_pad`, `meter`, `envelope_editor` | Pixel size hints. |

All numeric displays automatically use nanoTracker's LCD ghost-digit style.

---

### Instrument DSP

```json
"dsp": {
  "processorName": null,
  "voices":        16,
  "voiceStealing": "oldest",
  "oscillators": [
    { "type": "sawtooth", "detune": -10, "mix": 0.5 },
    { "type": "sawtooth", "detune":  10, "mix": 0.5 }
  ],
  "samples": [ ],
  "envelope": {
    "attack":  0.005,
    "decay":   0.1,
    "sustain": 0.8,
    "release": 0.3
  },
  "filter": {
    "type":      "lowpass",
    "frequency": 8000,
    "Q":         1.0
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `processorName` | `string \| null` | AudioWorklet processor name. `null` = use the built-in engine. |
| `voices` | `integer 1–32` | Maximum simultaneous voices. |
| `voiceStealing` | `string` | `"oldest"`, `"quietest"`, or `"none"`. |
| `oscillators` | `array` | Mixed into each voice before the sample. |
| `samples` | `array` | Sample zones. See [Sample Zones](#sample-zones). |
| `envelope` | `object` | ADSR applied to every voice. `sustain` is `0.0–1.0`. |
| `filter` | `object \| null` | One-pole filter post-oscillator. `null` to disable. |
| `filters` | **v2.** `array` | Additional filter stages chained in series after `filter`. |
| `envelopes` | **v2.** `array` | Named multi-stage envelopes (beyond the main ADSR). |
| `lfos` | **v2.** `array` | Per-voice LFOs for modulation. |
| `modRoutes` | **v2.** `array` | Modulation routing (same format as FX `modRoutes`). |
| `unison` | **v2.** `object` | `{ "count": 7, "detune": 30, "stereoSpread": 0.8 }`. 1-8 sub-voices. |
| `portamento` | **v2.** `object` | `{ "time": 0.06, "mode": "legato" }`. `"always"` or `"legato"`. |
| `noiseType` | **v2.** `string` | `"white"`, `"pink"`, or `"brown"` noise generator. |

**Oscillator types:** `sine`, `square`, `sawtooth`, `triangle`, `noise`

**v2 oscillator fields:** `fmTarget` (index of target oscillator for FM synthesis), `fmDepth` (modulation depth in Hz).

**Filter types:** `lowpass`, `highpass`, `bandpass`, `notch`, `allpass`, `peaking`, `lowshelf`, `highshelf`

**v2 LFO definition:**
```json
{ "id": "lfo1", "shape": "sine", "rate": 5, "depth": 200 }
```

**v2 Envelope definition:**
```json
{ "id": "filterEnv", "stages": [{ "target": 1, "time": 0.01 }, { "target": 0.3, "time": 0.2 }], "loop": false }
```

**v2 Modulation route (instruments):** Same format as FX. Built-in sources: `"velocity"`, `"note"`.
```json
{ "source": "lfo1", "target": "filter.frequency", "depth": 500 }
{ "source": "velocity", "target": "filter.frequency", "depth": 2000 }
```

When `processorName` is `null`, the host's built-in polyphonic scheduler handles note events using `AudioBufferSourceNode` with ADSR gain ramps. This covers most use cases. Only add a `script.js` when you need custom DSP that can't be expressed declaratively.

#### v2 Tracker Integration

Plugin instruments are a first-class tracker concept. When assigned to an instrument slot via the **INS** panel, they respond to all tracker note and effect commands:

| Effect | Plugin Behavior |
|---|---|
| 0xx Arpeggio | Rapid pitch changes via `setPitch` (no envelope re-trigger) |
| 1xx/2xx Portamento | Smooth pitch glide via `setPitch` |
| 3xx Tone porta | Pitch glide to target note |
| 4xx Vibrato | Periodic pitch modulation |
| 7xx Tremolo | Periodic volume modulation |
| Cxx Set volume | Direct gain change |
| E9x Retrigger | `noteOff` + `noteOn` |

Worklet processors receive two additional message types:
- `{ type: "setPitch", frequency: Hz, time: audioTime }` — pitch control from effect commands
- `{ type: "setGain", gain: 0-1, time: audioTime }` — volume control from effect commands

---

### Sample Zones

```json
"samples": [
  {
    "file":          "samples/bass_c2.wav",
    "rootKey":       36,
    "keyRange":      { "lo": 24, "hi": 48 },
    "velocityRange": { "lo":  0, "hi": 127 },
    "loop":          false,
    "loopStart":     0.0,
    "loopEnd":       0.0,
    "startOffset":   0.0,
    "duration":      0.0
  }
]
```

| Field | Notes |
|---|---|
| `file` | Path relative to the archive root (e.g. `"samples/kick.wav"`). |
| `rootKey` | MIDI note at which the sample plays at original pitch. |
| `keyRange` | MIDI note range (`lo`–`hi`) this zone handles. |
| `velocityRange` | Velocity range (`lo`–`hi`, 0–127) for velocity switching. |
| `loop` | Enable loop between `loopStart` and `loopEnd`. |
| `loopStart` / `loopEnd` | Loop points in seconds. `loopEnd: 0` = end of buffer. |
| `startOffset` | Seconds into the buffer where playback begins. |
| `duration` | Seconds to play. `0` = play to end of buffer. |

**`startOffset` and `duration` enable non-destructive slicing.** A single audio file can back many zones with different offsets — no need to pre-chop samples into individual files.

```
// Eight equal slices from a 2-bar loop at 140 BPM (eighth-note grid)
step = 60 / 140 / 2  // ≈ 0.2143 s

zone[0]: startOffset=0.0000, duration=0.2143, rootKey=36
zone[1]: startOffset=0.2143, duration=0.2143, rootKey=37
zone[2]: startOffset=0.4286, duration=0.2143, rootKey=38
// ...
```

Zone selection per note event: the host picks the first zone whose `keyRange` contains the played note and whose `velocityRange` contains the played velocity.

---

### Loop Presets

Loop presets define named step sequences that appear as one-click pattern buttons in the tracker's loop generator UI. **All instrument-specific creative content belongs here** — never in the host application's source code.

```json
"loopPresets": [
  {
    "name": "CLASSIC",
    "steps": [
      { "padIndex": 1 },
      { "padIndex": 3, "volume": 80 },
      { "padIndex": 0 },
      { "padIndex": 5, "pitch": -12, "reverse": false }
    ]
  },
  {
    "name": "STUTTER",
    "steps": [
      { "padIndex": 1 },
      { "padIndex": 1, "volume": 50 },
      { "padIndex": 1, "volume": 25 },
      { "padIndex": 0 }
    ]
  }
]
```

| Step field | Default | Notes |
|---|---|---|
| `padIndex` | — | **Required.** 1-based zone index. `0` = silent step. |
| `pitch` | `0` | Semitone offset. |
| `volume` | `100` | Output level 0–100. |
| `reverse` | `false` | Play the sample slice in reverse. |
| `active` | `true` | `false` mutes the step without removing it. |

> **`padIndex` is 1-based.** `1` refers to `samples[0]`, `2` to `samples[1]`, and so on. `0` is always a silent step.

Pattern length is determined by the number of steps in the array. Common lengths are 8, 16, and 32. Shorter presets loop within the current pattern length.

---

### FX DSP

FX plugins describe a **declarative Web Audio graph** — a list of nodes and directed connections between them.

```json
"dsp": {
  "processorName": null,
  "nodes": [
    { "id": "predelay", "type": "delay",    "maxDelay": 0.5,  "delayTime": 0.02 },
    { "id": "verb",     "type": "convolver","impulse": "samples/hall.wav", "normalize": true },
    { "id": "wet",      "type": "gain",     "gain": 0.3 },
    { "id": "dry",      "type": "gain",     "gain": 1.0 }
  ],
  "connections": [
    { "from": "input",    "to": "predelay" },
    { "from": "input",    "to": "dry"      },
    { "from": "predelay", "to": "verb"     },
    { "from": "verb",     "to": "wet"      },
    { "from": "wet",      "to": "output"   },
    { "from": "dry",      "to": "output"   }
  ]
}
```

`"input"` and `"output"` are **reserved** — they represent the chain's entry and exit points. Do not define nodes with those IDs.

#### Node Types

| Type | Web Audio Node | Settable fields |
|---|---|---|
| `gain` | `GainNode` | `gain` |
| `delay` | `DelayNode` | `delayTime`, `maxDelay` |
| `biquad` | `BiquadFilterNode` | `frequency`, `Q`, `filterType` |
| `compressor` | `DynamicsCompressorNode` | `threshold`, `ratio`, `attack`, `release`, `knee` |
| `convolver` | `ConvolverNode` | `impulse` (file path), `normalize` |
| `panner` | `StereoPannerNode` | `pan` (`-1.0` to `1.0`) |
| `waveshaper` | `WaveShaperNode` | `curve` (`"sigmoid"`, `"clip"`, `"fold"`), `drive` |
| `worklet` | `AudioWorkletNode` | Processor-defined, via `script.js` |
| `mixer` | **v2.** `GainNode` (unity) | `gain`. Summing bus — Web Audio sums all connected inputs. |
| `splitter` | **v2.** `ChannelSplitterNode` | `channelCount` (default 2). Stereo → individual mono channels. |
| `merger` | **v2.** `ChannelMergerNode` | `channelCount` (default 2). Mono channels → stereo. |
| `oscillator` | **v2.** `OscillatorNode` | `oscType`, `oscFrequency`. Audio-rate oscillator (FM synthesis in FX). |
| `constant` | **v2.** `ConstantSourceNode` | `gain` (offset value). DC offset / modulation bias. |
| `analyser` | **v2.** `AnalyserNode` | `fftSize` (default 256). Pass-through with FFT data for UI visualisation. |
| `lfo` | **v2.** `OscillatorNode` + `GainNode` | `lfoShape`, `lfoRate`, `lfoDepth`. Modulation source. |
| `envelope` | **v2.** `ConstantSourceNode` | `envStages[]`. Scheduled ADSR ramps, triggered by note events. |

**v2 LFO shapes:** `"sine"`, `"triangle"`, `"square"`, `"sawtooth"`, `"sample-and-hold"`

**v2 Envelope stages:** `[{ "target": 1.0, "time": 0.01, "curve": "linear" }, { "target": 0.5, "time": 0.2 }, ...]`

#### v2 Connection Fields

Connections support additional fields for modulation and channel routing:

```json
{
  "from": "lfo1",
  "to": "filter1",
  "toParam": "frequency",
  "outputIndex": 0,
  "inputIndex": 0
}
```

| Field | Notes |
|---|---|
| `toParam` | **v2.** Connect to an `AudioParam` on the destination node instead of its audio input. E.g. `"frequency"`, `"gain"`, `"delayTime"`. |
| `outputIndex` | **v2.** For `splitter` nodes: which output channel (0-based). |
| `inputIndex` | **v2.** For `merger` nodes: which input channel (0-based). |

This enables **AudioParam modulation**: an LFO node's output connected via `toParam: "frequency"` will modulate the filter's cutoff in real-time, using Web Audio's native additive AudioParam modulation.

#### v2 Modulation Routes

An alternative to explicit `toParam` connections. Modulation routes insert a depth-scaling GainNode automatically:

```json
"modRoutes": [
  {
    "source": "lfo1",
    "target": "filter1.frequency",
    "depth": 500,
    "bipolar": true
  }
]
```

| Field | Notes |
|---|---|
| `source` | Node ID of the modulation source (`"lfo1"`, `"env2"`). |
| `target` | `"nodeId.paramName"` dot-path to the target AudioParam. |
| `depth` | Scaling factor (gain value of the intermediary GainNode). |
| `bipolar` | `true` for LFO (oscillates ±depth), `false` for envelope (0 to +depth). Default varies. |

#### FX Parameter Keys

Parameter keys for FX plugins use `"nodeId.audioParam"` dot-notation:

```
"wet.gain"           → GainNode named "wet" → .gain
"predelay.delayTime" → DelayNode named "predelay" → .delayTime
"filter.frequency"   → BiquadFilterNode named "filter" → .frequency
"comp.threshold"     → DynamicsCompressorNode named "comp" → .threshold
```

---

## AudioWorklet (script.js)

Only add `script.js` when you need custom DSP that cannot be expressed as a declarative node graph. Most plugins don't need it.

### FX Processor

```javascript
class MyDistortion extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: "drive", defaultValue: 0.5, minValue: 0, maxValue: 1, automationRate: "k-rate" }
    ];
  }

  process(inputs, outputs, parameters) {
    const input  = inputs[0];
    const output = outputs[0];
    const drive  = parameters.drive[0];
    for (let ch = 0; ch < output.length; ch++) {
      const inp = input[ch] ?? new Float32Array(128);
      const out = output[ch];
      for (let i = 0; i < out.length; i++) {
        out[i] = Math.tanh(inp[i] * (1 + drive * 10));
      }
    }
    return true;
  }
}
registerProcessor("my-distortion", MyDistortion);
```

The string passed to `registerProcessor()` must **exactly match** `dsp.processorName` in `plugin.json`.

### Instrument Processor

Instrument processors receive note events via `MessagePort`. The host sends structured objects — not raw MIDI.

```javascript
class MySynth extends AudioWorkletProcessor {
  constructor() {
    super();
    this._voices = [];
    this.port.onmessage = ({ data }) => {
      if (data.type === "noteOn") {
        // { type, note, velocity, frequency }
        this._voices.push({ freq: data.frequency, vel: data.velocity / 127, phase: 0 });
      } else if (data.type === "noteOff") {
        // { type, note } — begin release
      } else if (data.type === "allNotesOff") {
        this._voices = [];
      } else if (data.type === "param") {
        // { type, key, value }
      }
    };
  }

  process(inputs, outputs) {
    const out = outputs[0][0];
    if (!out) return true;
    for (let i = 0; i < out.length; i++) {
      let s = 0;
      for (const v of this._voices) {
        s += Math.sin(2 * Math.PI * v.freq * v.phase / sampleRate) * v.vel;
        v.phase++;
      }
      out[i] = s / Math.max(1, this._voices.length);
    }
    return true;
  }
}
registerProcessor("my-synth", MySynth);
```

#### Message Protocol (Host → Processor)

| Type | Payload | Description |
|---|---|---|
| `noteOn` | `{ note, velocity, frequency }` | Trigger a new voice. `frequency` is pre-calculated in Hz. |
| `noteOff` | `{ note }` | Begin release for the matching voice. |
| `allNotesOff` | `{}` | Immediate silence (sent on tracker stop/reset). |
| `param` | `{ key, value }` | Live parameter update. |
| `setPitch` | **v2.** `{ frequency, time }` | Glide to new frequency. Sent by portamento/vibrato/arpeggio. |
| `setGain` | **v2.** `{ gain, time }` | Set output level (0-1). Sent by volume commands/tremolo. |

---

## Factory Presets (v2)

Presets define named snapshots of parameter values. A dropdown appears at the top of the plugin UI when presets are present.

```json
"presets": [
  {
    "name": "CLASSIC",
    "values": {
      "cutoff": 800,
      "resonance": 12,
      "envMod": 5000,
      "decay": 0.2
    }
  },
  {
    "name": "DEEP BASS",
    "values": {
      "cutoff": 300,
      "resonance": 5,
      "envMod": 1000,
      "decay": 0.5
    }
  }
]
```

| Field | Notes |
|---|---|
| `name` | Display name in the preset dropdown. |
| `values` | `Record<string, number>` — maps parameter keys to their values. Only keys present are changed; others retain their current values. |

Presets are applied client-side by iterating `values` and calling the host's `onChange` for each parameter. They are not serialised in `.ftrk` files — the individual parameter values are saved instead.

---

## Build Tool

```
python3 build_plugin.py PLUGIN_DIR [--out OUTPUT_DIR] [--name FILENAME_STEM]
```

### What it validates

| Check | Fatal? |
|---|---|
| `schemaVersion` is supported (`1` or `2`) | Yes |
| `manifest` has `name`, `version`, `type` | Yes |
| `manifest.type` is `"instrument"` or `"fx"` | Yes |
| All parameters have `min < max` | Yes |
| Sample `keyRange`/`velocityRange` have `lo ≤ hi` | Yes |
| `startOffset` and `duration` are non-negative | Yes |
| `dsp.envelope.sustain` is in `0.0–1.0` | Yes |
| `dsp.voices` is in `1–32` | Yes |
| FX connections reference defined node IDs | Warning |
| Sample file paths exist in the source directory | Warning |
| Parameter `default` is within `[min, max]` | Warning |
| `processorName` set but no `script.js` found | Warning |
| `script.js` present but `processorName` is `null` | Warning |

Warnings are non-fatal — the archive is still produced. Errors abort the build with a clear message.

### Output naming

The output filename defaults to `Name_version.ntins` (or `.ntsfx`), derived from the manifest. Special characters in the name are replaced with underscores. Use `--name` to override:

```bash
python3 build_plugin.py ./my-reverb --name "SpaceVerb_1.2.0"
# → SpaceVerb_1.2.0.ntsfx
```

---

## Examples

### Minimal instrument (oscillator only, no samples)

```json
{
  "schemaVersion": 1,
  "manifest": { "name": "Sine Bass", "version": "1.0.0", "type": "instrument" },
  "dsp": {
    "processorName": null,
    "voices": 8,
    "voiceStealing": "oldest",
    "oscillators": [{ "type": "sine", "detune": 0, "mix": 1.0 }],
    "samples": [],
    "envelope": { "attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.4 },
    "filter": { "type": "lowpass", "frequency": 800, "Q": 2.0 }
  },
  "parameters": [
    { "key": "filter.frequency", "label": "CUTOFF", "min": 20, "max": 20000, "default": 800, "step": 10, "unit": "Hz", "displayDecimals": 0 }
  ],
  "ui": {
    "layout": "flex",
    "controls": [{ "type": "knob", "parameter": "filter.frequency", "label": "CUTOFF" }]
  }
}
```

---

### Drum slicer (32 zones from one file)

```json
{
  "schemaVersion": 1,
  "manifest": { "name": "Break Slicer", "version": "1.0.0", "type": "instrument" },
  "dsp": {
    "processorName": null,
    "voices": 16,
    "voiceStealing": "oldest",
    "oscillators": [],
    "samples": [
      { "file": "samples/loop.wav", "rootKey": 36, "keyRange": { "lo": 36, "hi": 36 }, "velocityRange": { "lo": 0, "hi": 127 }, "loop": false, "loopStart": 0, "loopEnd": 0, "startOffset": 0.00000, "duration": 0.17647 },
      { "file": "samples/loop.wav", "rootKey": 37, "keyRange": { "lo": 37, "hi": 37 }, "velocityRange": { "lo": 0, "hi": 127 }, "loop": false, "loopStart": 0, "loopEnd": 0, "startOffset": 0.17647, "duration": 0.17647 },
      { "file": "samples/loop.wav", "rootKey": 38, "keyRange": { "lo": 38, "hi": 38 }, "velocityRange": { "lo": 0, "hi": 127 }, "loop": false, "loopStart": 0, "loopEnd": 0, "startOffset": 0.35294, "duration": 0.17647 }
    ],
    "envelope": { "attack": 0.001, "decay": 0.0, "sustain": 1.0, "release": 0.05 },
    "filter": null
  },
  "loopPresets": [
    {
      "name": "STRAIGHT",
      "steps": [{ "padIndex": 1 }, { "padIndex": 2 }, { "padIndex": 3 }, { "padIndex": 2 }]
    },
    {
      "name": "STUTTER",
      "steps": [
        { "padIndex": 1 }, { "padIndex": 1, "volume": 60 },
        { "padIndex": 2 }, { "padIndex": 2, "volume": 60 }
      ]
    }
  ]
}
```

---

### Reverb FX plugin (declarative, no script.js)

```json
{
  "schemaVersion": 1,
  "manifest": { "name": "Room Reverb", "version": "1.0.0", "type": "fx" },
  "dsp": {
    "processorName": null,
    "nodes": [
      { "id": "wet",  "type": "gain",     "gain": 0.4 },
      { "id": "dry",  "type": "gain",     "gain": 1.0 },
      { "id": "verb", "type": "convolver","impulse": "samples/room_ir.wav", "normalize": true }
    ],
    "connections": [
      { "from": "input", "to": "verb" },
      { "from": "input", "to": "dry"  },
      { "from": "verb",  "to": "wet"  },
      { "from": "wet",   "to": "output" },
      { "from": "dry",   "to": "output" }
    ]
  },
  "parameters": [
    { "key": "wet.gain", "label": "WET", "min": 0, "max": 100, "default": 40, "step": 1, "unit": "%" },
    { "key": "dry.gain", "label": "DRY", "min": 0, "max": 100, "default": 100, "step": 1, "unit": "%" }
  ],
  "ui": {
    "layout": "flex",
    "controls": [
      { "type": "knob", "parameter": "wet.gain", "label": "WET" },
      { "type": "knob", "parameter": "dry.gain",  "label": "DRY" }
    ]
  }
}
```

---

## Common Mistakes

### Plugin-specific logic in host files
The host application is generic. If you find yourself wanting the host to know your plugin's name or have special handling for it, that content belongs in `plugin.json` — specifically in `loopPresets[]` or the `dsp` block.

### `processorName` mismatch
The string in `dsp.processorName` must **exactly match** the string passed to `registerProcessor()` in `script.js`. A mismatch silently fails worklet registration.

### Undefined node IDs in connections
Every `from` and `to` value in `connections[]` must either be a node `id` from `nodes[]` or the reserved names `input`/`output`. Typos here will produce a broken audio graph.

### Wrong path for sample files
File paths in `samples[].file` and `nodes[].impulse` are relative to the **archive root**, not the source directory. If your WAV is at `my-plugin/samples/kick.wav`, the path in JSON should be `"samples/kick.wav"`.

### `sustain` out of range
`envelope.sustain` is a linear amplitude ratio in the range `0.0–1.0`, not a percentage. `0.8` is correct; `80` is not.

### `padIndex` is 1-based
In `loopPresets[].steps`, `padIndex: 1` refers to `samples[0]` (the first zone). `padIndex: 0` is always a silent step.

### No path from `input` to `output`
Every FX plugin must have at least one audio path connecting `"input"` through nodes to `"output"`. A graph with no such path produces silence.

---

## Reference Tables

### MIDI Note Numbers

| Oct | C | C# | D | D# | E | F | F# | G | G# | A | A# | B |
|-----|---|----|----|----|----|----|----|----|----|----|----|---|
| 2 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 | 35 |
| 3 | 36 | 37 | 38 | 39 | 40 | 41 | 42 | 43 | 44 | 45 | 46 | 47 |
| 4 | 48 | 49 | 50 | 51 | 52 | 53 | 54 | 55 | 56 | 57 | 58 | 59 |
| 5 | 60 | 61 | 62 | 63 | 64 | 65 | 66 | 67 | 68 | **69** | 70 | 71 |

A4 = MIDI 69 = 440 Hz. C3 = MIDI 36 (common root for drum plugins).

### Slice Durations by BPM

| BPM | Quarter | Eighth | Sixteenth |
|-----|---------|--------|-----------|
| 80  | 0.7500 s | 0.3750 s | 0.1875 s |
| 100 | 0.6000 s | 0.3000 s | 0.1500 s |
| 120 | 0.5000 s | 0.2500 s | 0.1250 s |
| 140 | 0.4286 s | 0.2143 s | 0.1071 s |
| 160 | 0.3750 s | 0.1875 s | 0.0938 s |
| 170 | 0.3529 s | 0.1765 s | 0.0882 s |
| 174 | 0.3448 s | 0.1724 s | 0.0862 s |
| 180 | 0.3333 s | 0.1667 s | 0.0833 s |
| 200 | 0.3000 s | 0.1500 s | 0.0750 s |

Formula: `duration = 60 / BPM / subdivisions_per_beat`

### Standard General MIDI Drum Notes

| MIDI | Note | Sound |
|------|------|-------|
| 35 | B1 | Bass Drum 2 |
| 36 | C2 | Bass Drum 1 |
| 38 | D2 | Snare |
| 39 | D#2 | Hand Clap |
| 42 | F#2 | Closed Hi-Hat |
| 46 | A#2 | Open Hi-Hat |
| 49 | C#3 | Crash Cymbal |
| 51 | D#3 | Ride Cymbal |
