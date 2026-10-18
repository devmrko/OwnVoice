# Validation — 2026-10-18

- `ruff check`, `ruff format --check`, strict mypy: passed.
- pytest: 12 passed. Audio engine is a test double; real FFmpeg conversion,
  atempo fitting, WAV sample placement and download are exercised.
- Cases: malformed/overlapping SRT, exact start/total sample count, limited
  speedup, overflow blocks export, edited-segment cache invalidation,
  interrupted-job recovery, failed-job retry, upload conversion, origin/header
  protection, automatic device priority.
- Wheel build and isolated extracted-wheel imports/static assets: passed.
- Chrome via Playwright: desktop 1440px, mobile 390px; navigation and SRT mode
  passed, no horizontal mobile overflow and no JavaScript errors.
- qwen-tts 0.1.1 imports successfully. Its import emits optional FlashAttention
  and missing SoX warnings. Selected 12Hz path does not use the 25Hz SoX transformer.
- This Apple Silicon Mac: torch MPS built and available outside the agent
  sandbox. Inside the sandbox, MPS availability reports false. Regular terminal
  execution is required for correct device detection here.
- Initial check did not load model weights. Subsequent MPS inference is recorded
  below; CUDA inference and subjective resemblance remain unverified.
- First model use downloads the model. UI device detection is not a claim of
  successful model inference. Runtime exposes `inference_verified` separately.

## Progress update
- 17 tests pass, including elapsed time freezing after completion, missing legacy
  timestamps, preparation excluded from ETA, retry clock reset and review counts.
- Browser checks: completed-job progress 100%, detail progress, textarea survives
  a poll, no mobile overflow or JavaScript errors.
- Existing first user job completed on MPS; no historical start/end timing existed,
  so its total processing time is deliberately not reconstructed. Listening quality
  has not been evaluated. New worker records timing on subsequent attempts.

## Segment preview interruption fix
- Reported second SRT cue: raw WAV 5.44s, 24kHz; preview HTTP body matches original
  file byte-for-byte. Local whisper.cpp large-v3-turbo transcription includes the
  complete requested sentence through its final phrase (ASR evidence, not a human
  listening-quality assessment). No audio regeneration or job changes performed.
- Reproduced browser defect: simulated another segment update while second cue
  plays; previous implementation detached audio, paused it and reset currentTime=0.
- Fixed same-job structural rerenders during playback. Independent progress clocks
  keep updating. Browser regression passed: identical connected player remains
  playing and emits ended at 5.44/5.44 seconds despite polling. No JavaScript errors.
- Node syntax and rebuilt wheel/static-asset verification passed.

## Redwood-inspired UI refresh
- Static UI only; existing web and TTS worker processes were not restarted.
- Desktop 1440px and mobile 390px: navigation, action cards, SRT input and job
  detail passed; no horizontal overflow or JavaScript errors.
- Preview regression passed: second cue remains on same player through a job
  update and reaches ended at 5.44 seconds.
- JavaScript syntax, wheel build and packaged static assets passed.
- Promotional headlines removed; functional Korean labels and short instructions.

## Shared CSS layout refactor
- Removed negative page margins, per-form max widths, float positioning and
  full-width space characters used for positioning. Reusable form/record/segment
  classes now control layout; source HTML/CSS/JS formatted for maintenance.
- Browser geometry checks at 1440, 1000, 768, 720 and 390px passed: heading/panel/card
  edges, select heights and top alignment, job action columns, review/normal segment
  input edges, desktop button/audio center alignment, no horizontal overflow.
- Audio regression passed through 5.44-second completion. JS syntax and wheel
  assets passed. Backend and active worker were not restarted.

## Header/sidebar alignment correction
- Header now uses the same sidebar-width grid column as the body. Removed the
  independent decorative divider and used the brand cell border as the boundary.
- At 2013px and 1440px: brand/sidebar right edge both 220px, header section label
  and page boundary both 252px, brand mark/nav icon boxes both start at 24px.
- At 1000px and 768px: matching column edge 180px and content start 204px.
- Mobile 390px has no horizontal overflow. Active worker was not restarted.

## Public checkout and lifecycle validation

- Bundled the complete tracked python-foundation snapshot at
  e8798f9397d6391d39d9159a801dfa5ec7908663. Root uv.lock resolves a local directory;
  no Git dependency or submodule is required.
- Installed all TTS dependencies into a new temporary virtual environment using
  `uv sync --locked --extra tts`; Qwen and bundled foundation imports passed.
- 25 tests passed in that environment, including exclusive worker lock rejection,
  SIGTERM during the second segment, heartbeat cleanup, restart recovery and
  reuse of the first completed segment. Test synthesis uses a deterministic fake.
- Actual `start` -> HTTP/worker readiness -> SIGTERM -> port/heartbeat cleanup
  -> immediate restart -> stop passed twice on separate temporary data and port.
  Fixed preflight socket reuse to allow immediate restart after TCP TIME_WAIT.
- Model snapshot download and offline cache validation passed. Existing weights
  were reused; a multi-GB download into an empty cache was not repeated.
- Source/wheel builds and packaged UI/import checks passed. The supported install
  route is the repository checkout with uv, which includes the local dependency.
- Public staging excludes .data, recordings, generated audio, virtualenv, model
  weights and environment files. Source files were checked for credential patterns
  and machine-specific home paths.
- Existing user's web and synthesis worker were not stopped, and their environment
  was not synchronized or replaced. New CLI behavior applies to new processes.
- NVIDIA hardware and Windows have not been exercised locally. CI covers the
  model-free tests on Linux/macOS; it does not validate GPU inference or voice quality.
