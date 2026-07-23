# Sound of Ultrasound (s_of_us)

Real-time physical-modeling sonification of ultrasound-derived mass-spring topologies, built on [Processing 4](https://processing.org/) and the [miPhysics](https://github.com/mi-creative/miPhysics_JAVA) engine. A 2D/3D mesh of masses and springs is loaded from a JSON topology file, simulated in real time, rendered in an interactive 3D view, and sonified through direct audio synthesis (tapping mass velocities/forces, not sample playback).

Maintainer: veronica.ruozzi@tum.de
Tested on: **Ubuntu 24.04**

---

## Features

- **Physical modeling engine** — masses and damped springs simulated in real time via `PhysicsContext` (miPhysics), with configurable global friction and gravity.
- **JSON-driven topology** — the mesh (masses, springs, and driver/listener assignments) is entirely defined by an external JSON config file; no recompilation needed to load a new dataset.
- **Real-time audio synthesis** — the physical model's motion is sonified directly by `miTappedPhyAudioClient` (miPhysics' own audio client), tapped to a WAV recorder; no offline rendering step.
- **Interactive 3D visualization** — `PeasyCam`-driven orbit/pan/zoom camera, with the mesh automatically centered on its own centroid regardless of rotation.
- **Two independent control tracks** — trigger drivers directly from the keyboard for quick local testing, or drive everything remotely over OSC from a Python (or any OSC-capable) process. See [Usage](#usage) below.
- **WAV recording** — start/stop full-session recording, or a quick fixed-length capture, from the keyboard or remotely over OSC.
- **Topology generator** (`generate_topology.py`) — a standalone Python utility that builds a masses/springs JSON topology from BioSonix-style ultrasound config files.

---

## Requirements

- Processing 4.x (developed/tested against the Processing 4 IDE on Linux)
- Processing libraries: `oscP5`, `netP5`, `PeasyCam`
- The `miPhysics` Processing/Java library (Engine, Sound, Renderer, Utility packages) on the sketch's classpath
- Linux audio: the sketch opens a direct audio line via `javax.sound.sampled`. On modern Ubuntu (PipeWire-based audio), this line's sample rate must match PipeWire's session clock rate — see [Audio notes](#audio-notes) below if you hit `LineUnavailableException`.

---

## Project structure

| File | Purpose |
|---|---|
| `s_of_us_main.pde` | Sketch entry point: setup/draw loop, topology loading, mesh construction, camera, keyboard controls. |
| `AudioHandler.pde` | Creates and (re)configures the real-time audio client and WAV tap recorder. |
| `osc.pde` | OSC message handling — the remote-control interface described in the [OSC track](#track-2--osc-controlled-run-python-integration). |
| `ConfigManager.pde` | Small JSON config wrapper (drivers/listeners/config accessors) available for use elsewhere in the sketch. |
| `MiPhysicsWavRecorder.java` | Taps the audio client's output blocks and writes them to a 16-bit PCM WAV file. |
| `miTappedPhyAudioClient.java` | Extends miPhysics' audio client with a tap API, debug tone injection, and listener axis/force mirroring. |
| `generate_topology.py` | Standalone script: builds a `masses`/`springs` topology JSON from a BioSonix-style ultrasound config. |

---

## Topology JSON format

The sketch expects a single JSON file with this shape:

```json
{
  "masses": [
    { "id": "m_0_0_0", "x": 0.0, "y": 0.0, "z": 0.0, "mass": 0.0, "radius": 0.5 }
  ],
  "springs": [
    { "id": "s_0", "a": "m_0_0_0", "b": "m_1_0_0", "rest_length": 10.0, "stiffness": 1.25, "damping": 0.01 }
  ],
  "sonification_set_up": {
    "drivers":   ["m_0_9_0", "m_2_9_0", "..."],
    "listeners": ["m_7_9_0", "m_7_12_0"],
    "driver_positions_image_space":   [ ... ],
    "listener_positions_image_space": [ ... ]
  }
}
```

- A mass with `mass: 0.0` is instantiated as a **fixed** `Ground3D` node instead of a movable `Mass3D` (anchors/boundary nodes).
- `sonification_set_up.drivers` — mass IDs that receive excitation (force impulses), in order. Their index in this array is the index used both by keyboard control and by the `/magnitudeMultipleToggle` OSC message.
- `sonification_set_up.listeners` — mass IDs tapped for audio output.
- Positions are centered on the mesh's own centroid and have X/Y swapped at load time for the on-screen orientation; the original (image-space) coordinates are preserved unmodified in memory for any future picking/mapping use.

**Coordinate convention:** the model plane — which is also the source ultrasound image plane — is the **XY plane** (mass `z` is `0` for every node in a 2D topology). Excitation is applied **out of that plane, along Z**, via the OSC track's `/magnitudeMultipleToggle` message. This is the physically meaningful direction to push the mesh: an in-plane (X/Y) force doesn't produce the kind of transverse motion the springs are set up to resonate with. Note that the keyboard shortcut (`1`–`9`, Track 1) currently applies its impulse along X/Y rather than Z — see the caveat in [Track 1](#track-1--fast-run-standalone-keyboard-driven).

`generate_topology.py` can produce this file from a BioSonix-style ultrasound acquisition config:

```bash
python3 generate_topology.py --config /path/to/config.json --out topology.json
```

---

## Pointing the sketch at your config file

The sketch resolves its topology file at startup, in this order:

1. **`ULTRASONIX_CONF` environment variable**, if set and the file exists.
2. A hardcoded fallback path in `getConfig()` (`s_of_us_main.pde`) — machine-specific, only useful as a personal default. **Set `ULTRASONIX_CONF` explicitly rather than relying on this.**

```bash
export ULTRASONIX_CONF=/absolute/path/to/your_config.json
```

Set this before launching Processing (or before launching a compiled export — see [Compiling](#compiling-recommended-for-both-tracks) below).

---

## Usage

There are two independent ways to drive the model, described below.

### Track 1 — Fast run (standalone, keyboard-driven)

For quick local testing with no external process required.

1. Set `ULTRASONIX_CONF` to your topology JSON (see above).
2. Open `s_of_us_main.pde` in the Processing 4 IDE and run it (or launch a compiled export — recommended, see below).
3. The mesh loads, centers itself, and starts rendering; the audio client starts automatically.

**Keyboard controls:**

| Key | Action |
|---|---|
| `1`–`9` | Trigger driver **0–8** (index = key value − 1) with a fixed impulse force. The active driver → mass-name mapping is shown live in the bottom-left of the window. |
| `0` | Not mapped to a driver (reserved). |
| `r` | Toggle full-session WAV recording on/off. Files are written as `miphys_recording_<n>.wav`, incrementing `<n>` each session. |
| `c` | Quick fixed-length (2 s) capture; recording stops automatically. |
| `i` | Toggle renderer module-name display, if supported by the current `ModelRenderer` build. |
| `h` | Toggle the on-screen instructions overlay. |
| Left-drag | Orbit the camera (PeasyCam). |
| Mouse wheel | Zoom in/out. |

Only 9 drivers (indices 0–8) are reachable from the keyboard, since `0` doesn't map to an index. If your topology defines more than 9 drivers, use the OSC track to reach the rest.

**Tuning for audibility.** Two parameters in `s_of_us_main.pde` control how audible the result is, and they are not interchangeable:

| Variable | Default | Effect |
|---|---|---|
| `gain` | `0.4` | Linear output-stage multiplier applied after synthesis. Purely an audio loudness control — it does **not** change the physical simulation in any way, so it's safe to tune freely without affecting the model's behavior. |
| `excitationForce` | `10.0` | Magnitude of the impulse applied to a driver mass on keypress. This **does** feed into the physics — it's the actual force pushing the mesh. There's no universally correct value: it needs to be scaled to your model's physical dimensions and the mass values in your topology (a large/heavy mesh needs proportionally more force to produce a comparable audible response than a small/light one). |

In short: if the result is quiet but the model's motion looks physically reasonable, raise `gain`. If the model itself barely moves, raise `excitationForce` instead.

**Known caveat:** the keyboard impulse currently applies `(excitationForce, excitationForce, 0)` — i.e. along X/Y, the model/image plane — rather than along Z like the OSC track's `/magnitudeMultipleToggle` (see [Coordinate convention](#topology-json-format)). Keep this in mind if you're comparing keyboard-triggered and OSC-triggered excitation directly.

### Track 2 — OSC-controlled run (Python integration)

For driving the model remotely — e.g. synchronized to another process, a batch of trials, or a live signal pipeline — the sketch runs an OSC server on **UDP port 12001** for its entire lifetime, independent of the keyboard controls above (both work simultaneously).

**Supported OSC addresses:**

| Address | Arguments | Effect |
|---|---|---|
| `/magnitudeMultipleToggle` | one float per driver, in driver order | Applies a force impulse of `(0, 0, value)` to each corresponding driver mass. Argument count should match the number of configured drivers; excess/missing arguments are logged and clamped rather than crashing the sketch. |
| `/record/start` | one string: absolute output file path | Starts the miPhysics WAV recorder writing to that path. Parent folders are created automatically if missing. Ignored if a recording is already in progress. |
| `/record/end` | none | Stops the current OSC-triggered recording and finalizes the WAV file. |
| `/quit` | none | Cleanly exits the running sketch (`exit()`), useful for scripted/batch teardown. |

`/magnitudeMultipleToggle` is the physically correct way to excite the model, applying force along Z — out of the XY model/image plane (see [Coordinate convention](#topology-json-format)).

**Minimal Python example** (using [`python-osc`](https://pypi.org/project/python-osc/)):

```python
from pythonosc.udp_client import SimpleUDPClient

HOST = "127.0.0.1"   # or the machine's IP if the sketch runs elsewhere
PORT = 12001

client = SimpleUDPClient(HOST, PORT)

# Excite 3 drivers with different magnitudes (pad/trim to your driver count)
client.send_message("/magnitudeMultipleToggle", [0.8, 0.0, 0.3])

# Start/stop a recording at an explicit path
client.send_message("/record/start", "/home/you/recordings/take_01.wav")
client.send_message("/record/end", [])

# Cleanly close the sketch when the session is done
client.send_message("/quit", [])
```

---

## Compiling (recommended for both tracks)

Running from the Processing IDE works, but for either track we recommend **exporting a standalone application**:

`File > Export Application`, check your target OS, and check **"Embed Java"**.

This gives two practical benefits:

- **More stable timing/audio behavior** than running inside the IDE.
- **Directly callable as a subprocess** from a Python OSC-driving framework (Track 2) — launch the exported binary/script, wait for the OSC server to come up, then start sending messages — without needing Processing installed on the target machine at all.

---

## Audio notes

- The internal simulation and audio sample rate is fixed at **48000 Hz** throughout the sketch (physics `setSimRate`, the audio client, and the WAV recorder). This must match your system audio server's session clock rate. On PipeWire-based systems (Ubuntu 22.04+/24.04), check yours with:

  ```bash
  pw-metadata -n settings 0 clock.rate
  ```

  If it differs from 48000, either change PipeWire's configured rate or update the `SAMPLE_RATE` constant in `AudioHandler.pde` (and the matching value in `s_of_us_main.pde`'s `PhysicsContext(...)` call) to match.

- **Use a real (wired/built-in) audio output**, not Bluetooth. Bluetooth sinks are virtual PipeWire/BlueZ routes rather than real ALSA hardware devices, and direct hardware-line access (as used here) is unreliable against them.

- `gain` (in `s_of_us_main.pde`) is a linear output-stage multiplier — `1.0` = unity, not dB. It doesn't affect simulation stability, only loudness, so it's safe to tune freely. Because the model can sum energy from several simultaneously-excited drivers, test your loudest multi-driver scenario before settling on a value, to avoid clipping.

- Recordings are always written by `MiPhysicsWavRecorder` (16-bit PCM WAV), tapping the audio client directly. An older `Minim`-based line-in/out path exists in `AudioHandler.pde` but is currently disabled — it wasn't used for either playback or recording, and left enabled it competes with the audio client for exclusive access to the sound card. Leave it disabled unless you have a specific need (e.g. live level metering) and route it to a different device if you re-enable it.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `javax.sound.sampled.LineUnavailableException` / `Minim Error: Couldn't open the line` | Sample-rate mismatch with your system's audio session clock, and/or default audio output is a Bluetooth device. See [Audio notes](#audio-notes). |
| Model loads (console shows mass/spring/driver counts) but nothing draws | `renderer.renderScene(phys)` isn't being called in `draw()` — confirm it isn't commented out. |
| Mesh renders off-center or oddly oriented | Confirm the centroid-centering and X/Y swap block in `s_of_us_main.pde`'s mass-construction loop is intact. |
| Topology fails to load / wrong dataset loads | Confirm `ULTRASONIX_CONF` points to the intended file — the sketch will otherwise silently fall back to a machine-specific default path. |
