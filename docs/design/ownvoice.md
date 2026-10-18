# OwnVoice v0.1

2026-10-18. User-approved direction: reusable personal voice, text-to-WAV and
SRT-to-WAV with original timing, automatic CUDA/Mac device selection.

## Scope
Local single-user web application built on the bundled python-foundation. Reference-based
voice cloning using Qwen3-TTS Base; no per-speaker fine tuning in this release.
Web/API and polling worker run separately. SQLite persists profiles, jobs and
per-segment progress. Audio lives in an application-owned data directory.
Router -> Service -> Repository; foundation UnitOfWork owns commits.

## Contracts
POST /api/profiles multipart(name, transcript, audio); GET /api/profiles.
POST /api/jobs JSON(profile_id, mode=text|srt, content, language).
GET /api/jobs and /api/jobs/{id}; POST /api/jobs/{id}/retry.
PATCH /api/jobs/{id}/segments/{index} JSON(text) invalidates that segment only.
GET /api/jobs/{id}/audio returns final WAV only for completed jobs;
GET /api/jobs/{id}/segments/{index}/audio returns raw synthesized audio.
GET /api/runtime reports detected device, dependencies and worker heartbeat.
Mutations require X-OwnVoice: 1. Host and Origin are restricted to localhost
and 127.0.0.1. No remote/multi-user deployment until authentication is added.

## Timing
SRT times are parsed as integer milliseconds, then converted to sample positions.
Reject malformed, empty, unordered, overlapping and excessive inputs explicitly.
Short audio retains natural duration and is followed by silence. Long audio is
pitch-preserving accelerated at most 1.15x (initial engineering limit, requires
listening validation). Above that limit, mark needs_review and do not export a
misaligned final file. Never truncate speech or rewrite text automatically.
Users can edit pronunciation text or retry an individual segment. Original SRT
and original segment text are preserved. Output ends at final subtitle end.
Whole-video trailing silence and automatic multi-attempt synthesis are deferred.

## Worker and storage
One worker per data directory enforced by OS file lock. Jobs are claimed in a
transaction. On restart, running jobs return to queued; completed raw segments
are reused. WAV writes are atomic; a crash between write and DB update may
repeat a segment but cannot expose a partial final WAV. Never persist pickle.
Model is loaded lazily once per worker. Detect CUDA, MPS, CPU in that order;
manual OWNVOICE_DEVICE override is available. Detection is distinct from actual
successful inference. Model load/inference failures are visible; no silent CPU
fallback after an accelerator failure. MPS uses float32/eager initially.

## Validation and limits
Unit/integration tests cover parsing, sample placement, duration overflow,
worker recovery, API input boundaries and cross-origin mutation protection.
A fake engine exists only in tests, never as a production fallback.
Real voice quality requires user reference audio; CUDA cannot be verified on Mac.
SQLite create_all bootstraps schema v0.1; schema migrations needed before upgrades.
Profile deletion, cancellation, multi-user auth and model fine tuning are deferred.

## Progress reporting
Job list/detail expose progress: stage, current segment, completed/total segments,
completion percentage, request age, execution elapsed.
Each execution has started_at/finished_at epoch timestamps; retries reset execution
timing. Legacy jobs without timestamps show request age with unavailable execution
measurements. No guessed start/completion timestamps are backfilled.
Model preparation includes cache checks/download/loading (no fabricated byte %).
User correction: no estimated remaining time or extrapolated per-minute times.
Only measured elapsed and recorded durations are displayed. Completion percentage measures completed segments, not
tokens or elapsed time; review-required segments are reported separately.
Browser elapsed clocks update every second, data polls every four seconds. Progress
updates must not recreate active text editors or reset audio playback.

Preview playback must survive other segments completing. While audio is playing
in the currently selected job, defer structural detail rerenders; progress panels
continue updating independently. A later poll applies deferred updates after
playback ends. Switching to a different job can replace the player deliberately.
Segment audio cache keys depend on that segment's text/duration, not the whole job.

## UI direction (2026-10-18)
User requested Oracle Redwood/Data Studio-inspired appearance and concise UI copy.
Use a dark application header, light task navigation, warm neutral page surfaces,
teal actions, compact bordered panels and explicit status colors. Keep OwnVoice
identity; do not imply Oracle affiliation. Original CSS geometry provides the
banner accent. Labels: 음성 생성, 목소리 관리, 작업 내역. No promotional slogans.
Reference: https://docs.oracle.com/en/cloud/saas/readiness/redwood-adoption/index.html
Reference: https://docs.oracle.com/en/cloud/paas/autonomous-database/data-studio-guide/access-and-navigate.html
Only static HTML/CSS/JS changed; active backend and worker remain running.

## Shared layout classes
Page heading, forms, lists and footer use the same page boundary; no negative
margins or per-screen maximum widths. Spacing, control height and panel padding
are CSS custom properties. `layout-between` and `layout-inline` provide reusable
Flex alignment; `form-grid`/`form-field` own form layout. Controls have no margins.
`job-header` fixes status/action columns across records. `segment-header`,
`segment-actions` and `output-actions` provide explicit Grid rows instead of floats
or whitespace characters. `segmentView` is the single renderer for all segments.
Review highlighting must not change field alignment. Static assets are formatted
source files, not handwritten minified code.

## Device and measured performance
Runtime reports exact CUDA device name/VRAM or macOS chip name/system shared
memory. System memory is never presented as free GPU memory. Per-job execution
metadata pins the worker device for newly instrumented runs. Existing records
without device metadata must not be used as cross-hardware benchmark results.
Synthesis RTF = measured synthesis seconds / generated audio seconds (before
SRT speed fitting and silence insertion). Show first segment inference time
excluding initialization, and first audio readiness including initialization when
recorded. These are per-execution measurements, not universal startup estimates.
Worker records phase durations using monotonic time; retries reset measurements.
Model loading has no byte progress hook: show indeterminate bar + elapsed phase
time rather than a fabricated percent. Numeric bar remains completed-segment %.
NVIDIA vs Apple Silicon ranking requires matched model/text/settings measurements;
no theoretical or invented comparative score is displayed.

Remaining synthesis time may be estimated from at least two measured samples in
the current execution, using measured seconds per character and remaining text.
Label estimates separately from actual durations. Without sufficient records, or
when the estimate is exceeded, omit ETA; never insert hardware-based defaults.
Loading, fitting and saving durations are not predicted from synthesis samples.

## Distribution and process lifecycle

The author's foundation source snapshot is vendored, not a Git submodule. The
root uv project uses a relative path dependency so anonymous checkout is enough.
`start` owns web and worker subprocesses; Ctrl+C/SIGTERM stops only those children.
An occupied port is rejected before starting a worker. The worker lock prevents
concurrent recovery/claims on the same data. Interrupted segments are regenerated
on restart; committed completed segments are reused. `doctor` checks dependency
presence, device availability and FFmpeg. `download-model` downloads a complete
Hugging Face snapshot without GPU allocation; `--offline` checks cached files.

## Bounded SRT timing retries

Every SRT cue uses the same timing retry policy, independent of source text or
cue number. On TimingOverflow, synthesize the unchanged text again, up to
OWNVOICE_SRT_MAX_ATTEMPTS (default 3 total attempts, range 1–5). Retain the
shortest complete candidate. Fit at no more than the configured speed limit;
do not truncate speech, edit text, move cues or borrow the next cue's time.
Persist attempt counts before inference; resume uses saved candidates and
remaining budget. A manual retry/edit resets the selected cue's budget.
Completed cues are cached. Exhausted cues include measured duration, allotted
time and attempt count; other cues continue and final export remains blocked.
Timing samples include each inference attempt, including discarded candidates.
This increases the chance of fitting; it does not guarantee fit or validate
that the model pronounced every word. Preview remains necessary for quality.
