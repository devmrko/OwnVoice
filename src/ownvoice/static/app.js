"use strict";
const $ = (id) => document.getElementById(id);
let mode = "text",
  selectedJob = null,
  detailVersion = null,
  recording = null,
  recordedFile = null,
  recordTimer = null,
  previewURL = null;
const statusNames = {
  queued: "대기 중",
  running: "생성 중",
  completed: "완료",
  failed: "실패",
  needs_review: "조정 필요",
  pending: "미생성",
};
function notify(message, error = false) {
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
  $("notice").hidden = false;
}
async function api(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "X-OwnVoice": "1", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "입력 내용을 확인해 주세요.",
    );
  return data;
}
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function tab(name) {
  document.querySelectorAll(".tab").forEach((n) => (n.hidden = n.id !== name));
  document
    .querySelectorAll("nav button")
    .forEach((n) => n.classList.toggle("active", n.dataset.tab === name));
  window.scrollTo({ top: 0, behavior: "instant" });
}
document
  .querySelectorAll("[data-tab]")
  .forEach((n) => (n.onclick = () => tab(n.dataset.tab)));
document.querySelectorAll("[data-mode]").forEach(
  (n) =>
    (n.onclick = () => {
      mode = n.dataset.mode;
      document
        .querySelectorAll("[data-mode]")
        .forEach((b) => b.classList.toggle("active", b === n));
      $("srt-upload").hidden = mode !== "srt";
      $("content-label").textContent = mode === "srt" ? "SRT 자막" : "텍스트";
      $("mode-help").textContent =
        mode === "srt"
          ? "자막 시간 유지 · 초과 구간 검토 후 출력"
          : "문장 사이 0.2초 간격 · 단일 WAV 출력";
    }),
);
$("srt-file").onchange = async (e) => {
  const file = e.target.files[0];
  if (file) {
    if (file.size > 400000) return notify("SRT 파일이 너무 큽니다.", true);
    $("content").value = await file.text();
  }
};
async function profiles() {
  const rows = await api("/api/profiles");
  const current = $("profile").value;
  $("profile").replaceChildren(
    el("option", rows.length ? "목소리 선택" : "등록된 목소리 없음"),
  );
  $("profile").firstChild.value = "";
  $("voice-list").replaceChildren();
  for (const p of rows) {
    const option = el("option", p.name);
    option.value = p.id;
    $("profile").append(option);
    const row = el("div", undefined, "voice-row layout-between");
    row.append(
      el("strong", p.name),
      el("span", p.transcript ? "대본 포함" : "음성 참조", "badge"),
    );
    $("voice-list").append(row);
  }
  if (rows.some((p) => p.id === current)) $("profile").value = current;
  else if (rows.length) $("profile").value = rows[0].id;
}
$("voice-file").onchange = () => {
  recordedFile = null;
};
$("record").onclick = async () => {
  if (recording && recording.state === "recording") {
    recording.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];
    try {
      recording = new MediaRecorder(stream);
    } catch (e) {
      stream.getTracks().forEach((t) => t.stop());
      throw e;
    }
    recording.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data);
    };
    recording.onstop = () => {
      clearTimeout(recordTimer);
      stream.getTracks().forEach((t) => t.stop());
      recordedFile = new File(chunks, "recording.webm", {
        type: recording.mimeType,
      });
      $("voice-file").value = "";
      if (previewURL) URL.revokeObjectURL(previewURL);
      previewURL = URL.createObjectURL(recordedFile);
      $("record-preview").src = previewURL;
      $("record-preview").hidden = false;
      $("record").textContent = "● 다시 녹음";
      $("record-status").textContent = "녹음 완료";
    };
    recording.start();
    $("record").textContent = "■ 녹음 끝내기";
    $("record-status").textContent = "녹음 중… 최대 60초";
    recordTimer = setTimeout(() => {
      if (recording.state === "recording") recording.stop();
    }, 59000);
  } catch (e) {
    notify(
      "마이크를 사용할 수 없습니다. 권한을 확인하거나 파일을 업로드해 주세요.",
      true,
    );
  }
};
$("voice-form").onsubmit = async (e) => {
  e.preventDefault();
  const button = e.submitter;
  button.disabled = true;
  try {
    if (recording?.state === "recording")
      throw new Error("먼저 녹음을 끝내 주세요.");
    const file = recordedFile || $("voice-file").files[0];
    if (!file) throw new Error("참조 음성을 녹음하거나 올려주세요.");
    const body = new FormData();
    body.append("name", $("voice-name").value);
    body.append("transcript", $("transcript").value);
    body.append("audio", file);
    const p = await api("/api/profiles", { method: "POST", body });
    await profiles();
    $("profile").value = p.id;
    notify("목소리 등록 완료");
    tab("create");
  } catch (e) {
    notify(e.message, true);
  } finally {
    button.disabled = false;
  }
};
$("create-form").onsubmit = async (e) => {
  e.preventDefault();
  const button = e.submitter;
  button.disabled = true;
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: $("profile").value,
        mode,
        content: $("content").value,
        language: $("language").value,
      }),
    });
    selectedJob = job.id;
    detailVersion = null;
    tab("jobs");
    notify("작업 등록 완료");
    await refreshJobs();
  } catch (e) {
    notify(e.message, true);
  } finally {
    button.disabled = false;
  }
};
const stageNames = {
  queued: "대기 중",
  preparing: "작업 준비 중",
  initializing: "음성 엔진 시작 중",
  model_loading: "모델 준비 · 최초 다운로드 포함",
  voice_preparing: "내 목소리 분석 중",
  synthesizing: "음성 합성 중",
  fitting: "길이 조정·구간 배치 중",
  saving: "WAV 저장 중",
  completed: "완료",
  failed: "실패",
  needs_review: "시간 초과 구간 검토 필요",
  legacy_running: "처리 중 · 세부 기록 없음",
};
const progressJobs = new Map();
let workerOnline = null;
function duration(seconds) {
  if (seconds === null || seconds === undefined) return "측정 기록 없음";
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600),
    m = Math.floor((s % 3600) / 60);
  return `${h ? h + "시간 " : ""}${m ? m + "분 " : ""}${s % 60}초`;
}
function progressPanel(job) {
  progressJobs.set(job.id, job);
  const panel = el("div", undefined, "job-progress");
  panel.dataset.jobId = job.id;
  paintProgress(panel, job);
  return panel;
}
function paintProgress(panel, job) {
  const p = job.progress;
  if (!p) return;
  const active = job.status === "running",
    advance = Math.max(0, Date.now() / 1000 - p.measured_at);
  const elapsed =
    p.elapsed_seconds === null
      ? null
      : p.elapsed_seconds + (active ? advance : 0);
  panel.replaceChildren();
  const title = el("div", undefined, "progress-heading layout-between");
  title.append(
    el(
      "strong",
      stageNames[
        ["completed", "failed", "needs_review"].includes(job.status)
          ? job.status
          : p.stage
      ] || p.stage,
    ),
    el("span", `${p.percent}%`),
  );
  panel.append(title);
  const preparing =
    active &&
    ["initializing", "model_loading", "voice_preparing", "preparing"].includes(
      p.stage,
    );
  const bar = el(
    "progress",
    undefined,
    preparing ? "loading-bar" : "completion-bar",
  );
  bar.max = 100;
  if (!preparing) bar.value = p.percent;
  bar.setAttribute(
    "aria-label",
    preparing ? "모델·목소리 준비 중" : "구간 완료율",
  );
  panel.append(bar);
  if (active) {
    const remaining = el("div", undefined, "remaining-time");
    const seconds = p.eta_seconds == null ? null : p.eta_seconds - advance;
    const estimate = seconds !== null && seconds >= 1;
    remaining.append(
      el("span", "예상 남은 시간", "runtime-label"),
      el("strong", estimate ? `약 ${duration(seconds)}` : "측정 중"),
      el("small", estimate ? "합성 · 이번 실행 실측 기반" : "실측 기록이 확보되면 표시"),
    );
    panel.append(remaining);
  }
  if (active && p.stage_started_at) {
    panel.append(
      el(
        "small",
        `현재 단계 ${duration(Date.now() / 1000 - p.stage_started_at)}`,
        "stage-time",
      ),
    );
  }
  const position =
    active && p.current_segment ? ` · 현재 ${p.current_segment}번째 구간` : "";
  panel.append(
    el(
      "small",
      `완료 ${p.done}/${p.total}구간${position}${p.needs_review ? " · 검토 필요 " + p.needs_review + "구간" : ""}`,
    ),
  );
  const metrics = el("div", undefined, "progress-metrics");
  metrics.append(
    el(
      "span",
      `${active ? "이번 실행 경과" : "이번 실행 소요"} ${duration(elapsed)}`,
    ),
  );
  if (
    ["queued", "running"].includes(job.status) &&
    (job.status === "queued" || elapsed === null)
  )
    metrics.append(
      el(
        "span",
        `요청 후 ${duration(p.request_age_seconds === null ? null : p.request_age_seconds + (["running", "queued"].includes(job.status) ? advance : 0))}`,
      ),
    );
  panel.append(metrics);
  const perf = p.performance;
  if (perf) {
    const performance = el("div", undefined, "performance-grid");
    const metric = (label, value, note) => {
      const item = el("div", undefined, "performance-metric");
      item.append(el("span", label, "runtime-label"), el("strong", value));
      if (note) item.append(el("small", note));
      performance.append(item);
    };
    metric(
      "첫 구간 합성",
      duration(perf.first_segment_seconds),
      "로딩 제외 · 이번 실행",
    );
    metric(
      "첫 음성 준비",
      duration(perf.first_audio_ready_seconds),
      "초기화·로딩 포함",
    );
    metric(
      "생성 음성",
      duration(perf.audio_seconds),
      `${perf.samples}구간 실측`,
    );
    metric(
      "합성 누적",
      duration(perf.synthesis_seconds),
      perf.rtf ? `실측 RTF ${perf.rtf.toFixed(2)} · 로딩 제외` : "로딩·무음 배치 제외",
    );
    panel.append(performance);
    const phases = perf.phase_seconds || {};
    if (Object.keys(phases).length) {
      const phaseList = el("div", undefined, "phase-timings");
      for (const [key, label] of [
        ["initializing", "엔진 초기화"],
        ["model_loading", "모델 로딩"],
        ["voice_preparing", "목소리 분석"],
      ]) {
        let seconds = phases[key] || 0;
        if (active && p.stage === key && p.stage_started_at)
          seconds += Math.max(0, Date.now() / 1000 - p.stage_started_at);
        if (seconds > 0)
          phaseList.append(el("span", `${label} ${duration(seconds)}`));
      }
      panel.append(phaseList);
    }
    if (perf.device)
      panel.append(
        el("small", `측정 장치 ${perf.device.name} · ${perf.device.backend}`),
      );
  }
  if (
    active &&
    [
      "initializing",
      "model_loading",
      "voice_preparing",
      "legacy_running",
    ].includes(p.stage)
  )
    panel.append(el("small", "준비 단계는 완료율에 포함되지 않습니다."));
  if (["running", "queued"].includes(job.status) && workerOnline === false)
    panel.append(
      el("p", "처리기 연결 끊김 · 진행 상태 확인 불가", "worker-warning"),
    );
}
setInterval(() => {
  document.querySelectorAll(".job-progress").forEach((panel) => {
    const job = progressJobs.get(panel.dataset.jobId);
    if (job) paintProgress(panel, job);
  });
}, 1000);

async function refreshJobs() {
  const jobs = await api("/api/jobs");
  const list = $("job-list");
  list.replaceChildren();
  if (!jobs.length) list.append(el("div", "작업 없음", "empty"));
  for (const job of jobs) {
    const row = el("article", undefined, "job-row");
    row.dataset.status = job.status;
    const header = el("div", undefined, "job-header");
    const info = el("div", undefined, "job-info");
    info.append(
      el(
        "strong",
        job.profile_name +
          " · " +
          (job.mode === "srt" ? "영상 자막" : "텍스트 TTS"),
      ),
      el(
        "small",
        new Date(job.created_at).toLocaleString("ko-KR") +
          " · " +
          job.done +
          "/" +
          job.total +
          " 구간",
      ),
    );
    const badge = el("span", statusNames[job.status] || job.status, "badge");
    const button = el("button", "상세 보기");
    button.onclick = () => {
      selectedJob = job.id;
      detailVersion = null;
      showDetail().catch((error) => notify(error.message, true));
    };
    header.append(info, badge, button);
    row.append(header, progressPanel(job));
    list.append(row);
  }
  if (selectedJob) await showDetail();
}

function segmentView(job, segment) {
  const section = el("section", undefined, "segment " + segment.status);
  const header = el("div", undefined, "segment-header");
  header.append(
    el(
      "strong",
      `${segment.index + 1}. ${statusNames[segment.status] || segment.status}`,
    ),
  );
  if (segment.start_ms !== null) {
    header.append(
      el(
        "small",
        `${(segment.start_ms / 1000).toFixed(3)}–${(segment.end_ms / 1000).toFixed(3)}초`,
        "segment-time",
      ),
    );
  }
  section.append(header);
  if (segment.duration_ms !== null) {
    section.append(
      el(
        "p",
        `원본 합성 ${(segment.duration_ms / 1000).toFixed(2)}초 · 속도 ${segment.speed.toFixed(2)}×`,
        "segment-meta",
      ),
    );
  }
  const input = el("textarea", undefined, "segment-text");
  input.setAttribute("aria-label", `${segment.index + 1}번 구간 텍스트`);
  input.value = segment.text;
  input.maxLength = 1000;
  input.disabled = ["queued", "running"].includes(job.status);
  section.append(input);
  const actions = el("div", undefined, "segment-actions");
  const save = el("button", "수정·재생성");
  save.disabled = input.disabled;
  save.onclick = async () => {
    try {
      await api(`/api/jobs/${job.id}/segments/${segment.index}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: input.value }),
      });
      detailVersion = null;
      await refreshJobs();
    } catch (error) {
      notify(error.message, true);
    }
  };
  actions.append(save);
  if (segment.duration_ms !== null) {
    const player = el("audio", undefined, "audio-player");
    player.controls = true;
    player.preload = "none";
    player.src = `/api/jobs/${job.id}/segments/${segment.index}/audio?v=${encodeURIComponent(segment.text + "-" + segment.duration_ms)}`;
    actions.append(player);
  }
  section.append(actions);
  return section;
}

async function showDetail() {
  const j = await api("/api/jobs/" + selectedJob);
  progressJobs.set(j.id, j);
  const version = JSON.stringify({
    ...j,
    progress: undefined,
    stage: undefined,
    stage_started_at: undefined,
    current_segment: undefined,
    synthesis_timings: undefined,
    phase_seconds: undefined,
    first_audio_ready_seconds: undefined,
  });
  if (version === detailVersion) return;
  if (
    $("detail").dataset.jobId === j.id &&
    Array.from($("detail").querySelectorAll("audio")).some(
      (player) => !player.paused && !player.ended,
    )
  )
    return;
  if (
    $("detail").contains(document.activeElement) &&
    document.activeElement.tagName === "TEXTAREA"
  )
    return;
  detailVersion = version;
  const box = $("detail");
  box.dataset.jobId = j.id;
  box.hidden = false;
  box.replaceChildren(
    el("h2", j.profile_name + " · " + statusNames[j.status]),
    progressPanel(j),
  );
  if (j.error) box.append(el("p", j.error));
  if (j.status === "completed") {
    const link = el("a", "WAV 다운로드", "download");
    link.href = "/api/jobs/" + j.id + "/audio";
    const actions = el("div", undefined, "output-actions");
    const player = el("audio", undefined, "audio-player");
    player.controls = true;
    player.src = link.href;
    actions.append(link, player);
    box.append(actions);
  }
  if (["failed", "needs_review"].includes(j.status)) {
    const retry = el("button", "미완료 구간 재시도");
    retry.onclick = async () => {
      try {
        await api("/api/jobs/" + j.id + "/retry", { method: "POST" });
        detailVersion = null;
        await refreshJobs();
      } catch (e) {
        notify(e.message, true);
      }
    };
    box.append(retry);
  }
  const segments = el("div", undefined, "segment-list");
  for (const segment of j.segments) segments.append(segmentView(j, segment));
  box.append(segments);
}
async function refreshRuntime() {
  const r = await api("/api/runtime");
  workerOnline = r.worker_online;
  const hardware = r.hardware || {};
  $("engine-name").textContent = r.engine?.name || "Qwen3-TTS";
  $("engine-version").textContent = r.engine?.version
    ? `qwen-tts ${r.engine.version}`
    : "패키지 미설치";
  $("model-name").textContent = r.model?.replace("Qwen/", "") || "미설정";
  $("device-name").textContent = hardware.name || r.device || "장치 미확인";
  $("device-memory").textContent = hardware.memory_gb
    ? `${hardware.memory_kind} ${hardware.memory_gb} GB`
    : "메모리 정보 없음";
  $("device-backend").textContent = r.device?.startsWith("cuda")
    ? "NVIDIA · CUDA"
    : r.device === "mps"
      ? "Apple Silicon · Metal"
      : r.device === "cpu"
        ? "CPU"
        : "미확인";
  $("device-state").textContent =
    `처리기 ${r.worker_online ? "연결됨" : "꺼짐"} · ${r.inference_verified ? "합성 확인됨" : "합성 확인 전"}`;
  $("runtime").textContent =
    `${r.device || "장치 미확인"} · 처리기 ${r.worker_online ? "연결됨" : "꺼짐"}${r.tts_installed ? "" : " · TTS 설치 필요"}`;
}
(async () => {
  try {
    await Promise.all([profiles(), refreshJobs(), refreshRuntime()]);
  } catch (e) {
    notify(e.message, true);
  }
})();
let polling = false;
setInterval(async () => {
  if (polling) return;
  polling = true;
  try {
    await Promise.all([refreshJobs(), refreshRuntime()]);
  } catch (e) {
    notify("서버 연결을 확인해 주세요.", true);
  } finally {
    polling = false;
  }
}, 4000);
