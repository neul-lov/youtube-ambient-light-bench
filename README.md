# YouTube Ambient Light Benchmark

The benchmark used to measure and tune [YouTube Ambient Light For Safari](https://github.com/neul-lov/youtube-ambient-light-for-safari). It plays a 4K 60 fps video in real Safari and runs one variant of the glow renderer at a time. For each variant (a "phase") it measures the CPU used by each of Safari's processes, plus the system GPU utilization.

This is how the userscript went from updating the glow 30 times a second to updating it 15 times a second with blended frames. On the benchmark's mock page, version 2.9.0 adds about a third less CPU on top of video playback than 2.8.0 did, with no visible difference.

## What's in it

| | |
|---|---|
| `pipeline/` | A stand-in for the glow renderer (video → downscale → projection → 2 blur passes → canvas scaled up behind the player). Each phase swaps one stage. Three suites: `upload`, `schedule`, `crossfade`. |
| `userscript-ab/` | Runs two versions of the real userscript on a mock YouTube watch page, alternating A and B, with a video-only phase before and after. |
| `measure-app.sh` | Measures an app that is already running, such as YouTube added to the Dock. Use it to compare the same video with and without the userscript. |
| `tools/` | The local server that collects phase events, the per-second sampler, and the analyzer that prints the table. |

## Requirements

- macOS with Safari. The results below come from Safari 27.
- Python 3 (the one that comes with the Xcode command line tools is fine). No packages needed.
- [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg`), only to create the test clip. `run.sh` creates it on first use: a 20 s synthetic 4K60 H.264 clip of about 180 MB in `media/`.

## Running

```bash
./run.sh pipeline upload
```

```bash
./run.sh pipeline schedule
```

```bash
./run.sh pipeline crossfade
```

```bash
./run.sh userscript path/to/old.user.js path/to/new.user.js
```

`run.sh` starts the local server (127.0.0.1:8767) and the sampler, then opens the page in a new Safari tab in the background (`open -g`, so it doesn't take focus). It waits for the page to finish and prints the table. Raw data and the table end up in `results/<time>-<suite>/`. A suite takes 3–5 minutes. For a quick check, shorten the phases with `EXTRA="sec=5&warm=1" ./run.sh pipeline schedule`.

**Keep the Safari window visible on screen while it runs.** WebKit throttles pages that are hidden or completely covered by other windows. The page reports `vis` in its first line so you can check.

To measure an app that is already open, play the same video once with the userscript and once without, then run:

```bash
./measure-app.sh "with script" 30 YouTube.app
```

The third argument is matched against the command line of the app responsible for the processes. For example, `YouTube.app` picks a Dock web app, and `Safari.app` picks Safari.

## How it measures

- **Phases:** each one runs for 20 s after a 3 s warm-up. The page POSTs the phase start and end to the local server, which timestamps them.
- **Its own stats:** the page also reports glow updates per second, video-frame callbacks per second, main-thread milliseconds per update and dropped video frames.
- **CPU:** the sampler reads every process's CPU time once a second (`ps`). It groups processes by the app responsible for them, which is how Activity Monitor puts WebContent, GPU and Networking processes under Safari (`responsibility_get_pid_responsible_for_pid`). It also reads the system-wide "Device Utilization %" of the GPU (`ioreg`).
- **Averaging:** the analyzer averages each phase, skipping its first and last second. `vs base` is the difference to the average of the "video only" phases.

All CPU numbers are **% of one core**. The M5 used below has 10 cores, so 10 points is 1% of the whole CPU.

## Results

Measured on Oct 18 2026 on a MacBook with an Apple M5, macOS 27 and Safari 27.0.1, using the clip from `make-video.sh`. The YouTube web app was playing a video in the background the whole time. That makes the system GPU column noisy, but it doesn't affect Safari's own CPU numbers.

Columns:
- **CPU:** extra CPU of all Safari processes compared with playing the video alone, in % of one core.
- **Updates/s:** glow frames drawn per second.
- **Wake-ups/s:** video-frame callbacks per second.
- **Main thread:** milliseconds of JavaScript per update.

The full tables, with the split by process, are in [`results-2026-10-18/`](results-2026-10-18).

### `pipeline upload`: how the video frame gets to the GPU

Every phase except the first sleeps until shortly before the next update is due.

| Phase | CPU | Updates/s | Main thread |
|---|---:|---:|---:|
| Wake-ups only, no drawing (41/s) | +5.4 | – | – |
| WebGL `texImage2D(video)`, 30 fps | +17.8 | 29.1 | 0.8 ms |
| WebGL `texImage2D(video)`, 15 fps | +10.3 | 14.4 | 0.8 ms |
| WebGL `texImage2D(video)`, 10 fps | +6.6 | 9.9 | 0.9 ms |
| WebGL `createImageBitmap` resized to 512×288, 30 fps | +42.7 | 19.7 | 35 ms |
| WebGL 2D-canvas downscale to 512×288, 30 fps | +45.3 | 28.6 | 21 ms |
| WebGL `texSubImage2D(video)`, 30 fps | +57.4 | 22.6 | 27 ms |
| WebGPU `importExternalTexture`, 30 fps | +11.3 | 27.2 | 0.3 ms |

### `pipeline schedule`: when to wake up, and where the time goes

| Phase | CPU | Updates/s | Wake-ups/s |
|---|---:|---:|---:|
| 30 fps, waking on every video frame | +16.4 | 28.4 | 52 |
| 30 fps, sleep, then wait for one video frame | +15.7 | 29.4 | 31 |
| 15 fps, sleep, then wait for one video frame | +9.1 | 14.6 | 15 |
| 10 fps, sleep, then wait for one video frame | +5.0 | 9.8 | 11 |
| 30 fps, upload once and reuse the texture | +17.4 | 28.0 | 29 |
| 30 fps, output canvas hidden | +10.6 | 28.1 | 30 |

### `pipeline crossfade`: making 15 fps look smooth

In the crossfade phases, each new frame fades in over the previous one on the compositor.

| Phase | CPU |
|---|---:|
| 15 fps, one canvas (WebGL) | +12.5 |
| 15 fps crossfade, `OffscreenCanvas` → `ImageBitmap` → 2 canvases | +16.3 |
| 15 fps crossfade, WebGL + 2D copy of the previous frame | +16.2 |
| 15 fps crossfade, WebGPU rendering into 2 canvases | +10.7 |
| 15 fps, one canvas (WebGPU) | +6.6 |
| 30 fps, waking on every video frame (WebGL) | +17.7 |

### `userscript`: 2.8.0 against 2.9.0 on the mock watch page (2 rounds)

| Version | CPU | Updates/s | Wake-ups/s |
|---|---:|---:|---:|
| 2.8.0 (30 fps, waking on every video frame) | +17.5, +21.4 | 28.8–29.1 | 43–56 |
| 2.9.0 (15 fps, sleep, then wait for one frame, blended) | +10.5, +15.6 | 14.7–14.9 | 20–23 |

In the YouTube web app itself, `measure-app.sh` showed 57.0 and 56.8 for 2.8.0, against 49.4 and 51.2 for 2.9.0. That's the CPU of all the app's processes while playing the same video.

### What we learned

- **The cost follows how often the glow is redrawn.** Uploading the 4K frame is cheap: reusing one texture saves almost nothing (+17.4 vs +15.7). Presenting the canvas and compositing it costs about 5 points at 30 fps (hidden output: +10.6). Halving the update rate is the biggest single saving.
- **In Safari, `texImage2D(video)` is the fast path.** Resizing with `createImageBitmap`, downscaling through a 2D canvas and `texSubImage2D` each cost 20–35 ms of main thread per frame.
- **Waking up for every video frame costs about 5 points on its own** (41–57 wake-ups a second with a 60 fps video).
- **A real crossfade needs a copy per frame in WebGL.** That copy costs more than the drop from 30 to 15 fps saves. Only WebGPU can render straight into two canvases. The userscript blends frames on the GPU instead, which costs nothing extra.
- **WebGPU looked cheaper than WebGL in this run** (+11.3 vs +17.8 at 30 fps, +6.6 vs +12.5 at 15 fps). An earlier run had them about equal, so confirm this before porting a renderer.

## Caveats

- Expect about ±3 points of noise per phase. Look at the repeated phases, and run a suite twice before trusting small differences.
- The GPU column is system-wide, so anything else drawing at the same time shows up there.
- The mock watch page has none of YouTube's DOM, CSS or layout work. Inside the real YouTube app the userscript cost more: about 35 points over plain playback for 2.8.0, compared with about 20 here. Use `measure-app.sh` for the in-app number.
- Safari sometimes stalls at the loop point of the test clip, so the pages loop it manually 3 s before the end.
- The pipeline is a stand-in. It has the same stages and sizes as the userscript's renderer, but simpler shaders.

## License

[MIT](LICENSE)
