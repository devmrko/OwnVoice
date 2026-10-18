# Validation — 2026-10-18

## 0.2.0a1: inline job details

- Selected jobs expand their details inside the corresponding row. A teal
  border/background and an expanded-state toggle distinguish the selection;
  closing or selecting another row updates the highlight and ARIA state.
- Job polling reconciles rows by ID instead of replacing the whole list. Chrome
  confirmed the same audio element continues playing through polling and a
  simulated new job insertion, with no pause events. Draft text survives polling
  and switching away/back. Korean/English labels and 390px layout passed.
- Package version and root lockfile updated to `0.2.0a1` for Git tag
  `v0.2.0-alpha.1`. Tests: 36 passed; source/wheel builds and packaged assets passed.

## Model selection and real MPS comparison

- Jobs persist an engine selection: Qwen 1.7B, Qwen 0.6B or Chatterbox Multilingual
  V3. Legacy jobs default to Qwen. Switching releases the previous model and its
  subprocess before loading the next; SRT fitting and assembly stay shared.
- Chatterbox runs in its locked Python 3.12 environment. Fixed venv executable
  symlink resolution, which initially selected base Python without dependencies;
  both affected jobs were retried and completed. Regression test covers this.
- 36 tests, Ruff and strict mypy passed. Browser: three model choices, explicit
  Chatterbox language, ko/en labels, 390px layout and ten comparison audio players
  passed. Source/wheel build and packaged asset checks passed.
- Apple M4, same reference and three Korean sentences, one run per model:
  Qwen 1.7B synthesis 38.21s / audio 11.44s / RTF 3.34;
  Qwen 0.6B 32.85s / 12.24s / RTF 2.68;
  Chatterbox V3 24.13s / 12.20s / RTF 1.98.
  These exclude download/loading. Chatterbox was already loaded by a preceding
  job; its comparison has no cold-load measurement. Qwen loading was 15.43s and
  7.98s respectively. No general speed or listening-quality advantage is claimed.
- Local Whisper large-v3-turbo recognized the requested content in all nine
  samples; punctuation/spacing and AI spelling differed. Speaker resemblance
  and naturalness require listening. Windows CUDA has not been exercised here.
- Optional runtime source archives are pinned, with a separate uv lockfile;
  installation does not need Git. Generated voices, reports, models and logs
  stay outside version control. Comparison reports are local-only HTTP assets.

## Reference transcript listening experiment

- Generated three Korean sentences with and without the reference transcript;
  six private WAVs and an HTML listening page are under `.data/diagnostics/`.
  Reusable standalone runner: `scripts/compare_voice.py PROFILE_ID`. Stop the
  application worker first; the runner now holds the worker lock to prevent
  concurrent model instances. It does not change registered voices or jobs.
- First two pairs used matching per-sentence seeds, reset immediately before
  synthesis. Measured synthesis times (without/with transcript): 10.82/11.66
  seconds and 19.80/18.19 seconds. These are individual observations, not a
  statistically validated speed or quality improvement.
- A user job began during the initial experiment. The third no-transcript sample
  took 140.92 seconds; cause is unconfirmed. The experiment was interrupted and
  its final sample was generated through the existing service worker (17.88
  seconds, uncontrolled seed). The third pair is not a controlled benchmark.
- Local whisper.cpp large-v3-turbo recognized the requested content in all six
  samples, with punctuation/spacing and AI spelling normalization. This checks
  intelligibility, not speaker resemblance or subjective naturalness.
- Chrome loaded all seven audio players (reference plus six outputs); mobile
  layout at 390px had no horizontal overflow. Listening preference and a
  selection/registration workflow remain unverified/unimplemented.
- Restored the stopped local web/worker as an independent service process;
  its recovered user job completed both segments and produced a 9.24-second WAV.
  The exit cause was not established. Text TTS no longer shows the SRT-only
  timing-retry badge after interrupted execution; JavaScript syntax check passed.

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

## Automatic SRT timing retries

- 28 tests passed: several cues needing different attempt counts, exact final
  sample timeline after retries, bounded exhaustion, preservation of shortest
  candidate, continuing later cues, manual retry reset and completed-cue reuse.
- Retry tests use controlled audio durations; no user's completed audio is modified.
- Existing lifecycle, audio fitting, API boundaries and progress tests remain passing.

## Documentation, localization and portable launchers

- Added storage/schema/backup, architecture, library/lock inventory, repository audit
  and platform/bootstrap documents; English quickstart included.
- Removed only redundant nested foundation CI, lockfile and Python-dependent uvw.
  Foundation source/examples/tests remain; 33 foundation tests passed locally.
- 32 OwnVoice tests passed, including ko/en catalog/parameter parity, API locale
  negotiation, legacy error localization without changing user data, and CUDA
  detection when no MPS backend exists.
- Browser: ko/en switching, English title/runtime, persistent locale, retained
  generation input and 390px layout passed with no JavaScript errors.
- Downloaded pinned uv and managed Python 3.12.12 into a clean temporary folder
  using the root bootstrap without invoking a preinstalled Python or uv.
- Windows CI added for model-free installation, tests and packaging. Actual NVIDIA
  inference, CUDA wheel selection and interactive Windows console shutdown need
  hardware validation; these are not claimed from CPU CI.

- Windows, Linux and macOS CI all passed for the documentation/i18n/bootstrap
  changes (32 application tests; one POSIX signal test skipped on Windows).
- Full first-start installation passed with a project-managed Python 3.12.12
  under .tools/python; a preinstalled system Python is not required.
- Browser detail language switch preserves unsaved segment drafts; tested with
  mocked HTTP responses without mutating stored user jobs.

## 0.2.0 Alpha 2 — local API

- `ruff check`, `ruff format --check`, strict mypy: passed.
- 42 tests passed: JSON/origin boundaries, unsupported options, model/voice discovery,
  queued→completed SSE, reconnect snapshots, SRT review/failure events, WAV download,
  edit/retry, synchronous speech and wait timeout preserving the queued job.
- Apple M4/MPS, Qwen 0.6B: real `/v1/jobs` request delivered 20 progress snapshots,
  one `segment_ready` and one `completed` in 20.05s; final WAV download succeeded.
  `/v1/audio/speech` returned HTTP 200 and a valid 103,724-byte WAV. These are single
  smoke-test observations, not performance guarantees. Private job IDs/audio remain
  under ignored `.data`.
- Source/wheel build and wheel asset/import verification passed. No new dependencies.
- SSE sends snapshots and completed-segment URLs; incremental model audio streaming,
  historical event replay, submission deduplication and remote authenticated hosting
  are not implemented. Windows/CUDA inference was not exercised on this Mac.
