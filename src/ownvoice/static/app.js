"use strict";
(async () => {
  await OwnVoiceI18n.ready;
  const { t, tr } = OwnVoiceI18n;
  const segmentDrafts = new Map();
  const $ = (id) => document.getElementById(id);
  let mode = "text",
    selectedJob = null,
    detailVersion = null,
    detailLocale = null,
    recording = null,
    recordedFile = null,
    recordTimer = null,
    previewURL = null;
  const statusNames = () => ({
    queued: t("대기 중"),
    running: t("생성 중"),
    completed: t("완료"),
    failed: t("실패"),
    needs_review: t("조정 필요"),
    pending: t("미생성"),
  });
  function notify(message, error = false) {
    $("notice").textContent = message;
    $("notice").classList.toggle("error", error);
    $("notice").hidden = false;
  }
  async function api(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        "X-OwnVoice": "1",
        "Accept-Language": OwnVoiceI18n.locale,
        ...options.headers,
      },
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : t("입력 내용을 확인해 주세요."),
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
    document
      .querySelectorAll(".tab")
      .forEach((n) => (n.hidden = n.id !== name));
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
        $("content-label").textContent =
          mode === "srt" ? t("SRT 자막") : t("텍스트");
        $("mode-help").textContent =
          mode === "srt"
            ? t("자막 시간 유지 · 초과 구간 검토 후 출력")
            : t("문장 사이 0.2초 간격 · 단일 WAV 출력");
      }),
  );
  $("srt-file").onchange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 400000) return notify(t("SRT 파일이 너무 큽니다."), true);
      $("content").value = await file.text();
    }
  };
  async function profiles() {
    const comparisons = await api("/api/comparisons");
    const compareLink = $("voice-comparison");
    compareLink.hidden = !comparisons.length;
    compareLink.textContent = t("음성 비교 듣기");
    if (comparisons.length)
      compareLink.href = `/comparisons/${encodeURIComponent(comparisons[0])}/index.html`;
    const rows = await api("/api/profiles");
    const current = $("profile").value;
    $("profile").replaceChildren(
      el("option", rows.length ? t("목소리 선택") : t("등록된 목소리 없음")),
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
        el("span", p.transcript ? t("대본 포함") : t("음성 참조"), "badge"),
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
        $("record").textContent = t("● 다시 녹음");
        $("record-status").textContent = t("녹음 완료");
      };
      recording.start();
      $("record").textContent = t("■ 녹음 끝내기");
      $("record-status").textContent = t("녹음 중… 최대 60초");
      recordTimer = setTimeout(() => {
        if (recording.state === "recording") recording.stop();
      }, 59000);
    } catch (e) {
      notify(
        t(
          "마이크를 사용할 수 없습니다. 권한을 확인하거나 파일을 업로드해 주세요.",
        ),
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
        throw new Error(t("먼저 녹음을 끝내 주세요."));
      const file = recordedFile || $("voice-file").files[0];
      if (!file) throw new Error(t("참조 음성을 녹음하거나 올려주세요."));
      const body = new FormData();
      body.append("name", $("voice-name").value);
      body.append("transcript", $("transcript").value);
      body.append("audio", file);
      const p = await api("/api/profiles", { method: "POST", body });
      await profiles();
      $("profile").value = p.id;
      notify(t("목소리 등록 완료"));
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
          engine: $("engine").value,
          mode,
          content: $("content").value,
          language: $("language").value,
        }),
      });
      selectedJob = job.id;
      detailVersion = null;
      tab("jobs");
      notify(t("작업 등록 완료"));
      await refreshJobs();
    } catch (e) {
      notify(e.message, true);
    } finally {
      button.disabled = false;
    }
  };
  const stageNames = () => ({
    queued: t("대기 중"),
    preparing: t("작업 준비 중"),
    initializing: t("음성 엔진 시작 중"),
    model_loading: t("모델 준비 · 최초 다운로드 포함"),
    voice_preparing: t("내 목소리 분석 중"),
    synthesizing: t("음성 합성 중"),
    fitting: t("길이 조정·구간 배치 중"),
    saving: t("WAV 저장 중"),
    completed: t("완료"),
    failed: t("실패"),
    needs_review: t("시간 초과 구간 검토 필요"),
    legacy_running: t("처리 중 · 세부 기록 없음"),
  });
  const progressJobs = new Map();
  let workerOnline = null;
  function duration(seconds) {
    if (seconds === null || seconds === undefined) return t("측정 기록 없음");
    const s = Math.max(0, Math.floor(seconds));
    const h = Math.floor(s / 3600),
      m = Math.floor((s % 3600) / 60);
    return tr`${h ? h + t("시간 ") : ""}${m ? m + t("분 ") : ""}${s % 60}초`;
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
        stageNames()[
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
      [
        "initializing",
        "model_loading",
        "voice_preparing",
        "preparing",
      ].includes(p.stage);
    const bar = el(
      "progress",
      undefined,
      preparing ? "loading-bar" : "completion-bar",
    );
    bar.max = 100;
    if (!preparing) bar.value = p.percent;
    bar.setAttribute(
      "aria-label",
      preparing ? t("모델·목소리 준비 중") : t("구간 완료율"),
    );
    panel.append(bar);
    if (active) {
      const remaining = el("div", undefined, "remaining-time");
      const seconds = p.eta_seconds == null ? null : p.eta_seconds - advance;
      const estimate = seconds !== null && seconds >= 1;
      remaining.append(
        el("span", t("예상 남은 시간"), "runtime-label"),
        el("strong", estimate ? tr`약 ${duration(seconds)}` : t("측정 중")),
        el(
          "small",
          estimate
            ? t("합성 · 이번 실행 실측 기반")
            : t("실측 기록이 확보되면 표시"),
        ),
      );
      panel.append(remaining);
    }
    if (active && p.stage_started_at) {
      panel.append(
        el(
          "small",
          tr`현재 단계 ${duration(Date.now() / 1000 - p.stage_started_at)}`,
          "stage-time",
        ),
      );
    }
    const position =
      active && p.current_segment
        ? tr` · 현재 ${p.current_segment}번째 구간`
        : "";
    panel.append(
      el(
        "small",
        tr`완료 ${p.done}/${p.total}구간${position}${p.needs_review ? t(" · 검토 필요 ") + p.needs_review + t("구간") : ""}`,
      ),
    );
    const metrics = el("div", undefined, "progress-metrics");
    metrics.append(
      el(
        "span",
        `${active ? t("이번 실행 경과") : t("이번 실행 소요")} ${duration(elapsed)}`,
      ),
    );
    if (
      ["queued", "running"].includes(job.status) &&
      (job.status === "queued" || elapsed === null)
    )
      metrics.append(
        el(
          "span",
          tr`요청 후 ${duration(p.request_age_seconds === null ? null : p.request_age_seconds + (["running", "queued"].includes(job.status) ? advance : 0))}`,
        ),
      );
    if (active && job.mode === "srt" && p.current_attempt > 1) {
      metrics.append(
        el(
          "span",
          tr`시간 맞춤 재시도 ${p.current_attempt}/${p.attempt_limit}회`,
        ),
      );
    }
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
        t("첫 구간 합성"),
        duration(perf.first_segment_seconds),
        t("로딩 제외 · 이번 실행"),
      );
      metric(
        t("첫 음성 준비"),
        duration(perf.first_audio_ready_seconds),
        t("초기화·로딩 포함"),
      );
      metric(
        t("생성 음성"),
        duration(perf.audio_seconds),
        tr`${perf.samples}구간 실측`,
      );
      metric(
        t("합성 누적"),
        duration(perf.synthesis_seconds),
        perf.rtf
          ? tr`실측 RTF ${perf.rtf.toFixed(2)} · 로딩 제외`
          : t("로딩·무음 배치 제외"),
      );
      panel.append(performance);
      const phases = perf.phase_seconds || {};
      if (Object.keys(phases).length) {
        const phaseList = el("div", undefined, "phase-timings");
        for (const [key, label] of [
          ["initializing", t("엔진 초기화")],
          ["model_loading", t("모델 로딩")],
          ["voice_preparing", t("목소리 분석")],
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
          el(
            "small",
            tr`측정 장치 ${perf.device.name} · ${perf.device.backend}`,
          ),
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
      panel.append(el("small", t("준비 단계는 완료율에 포함되지 않습니다.")));
    if (["running", "queued"].includes(job.status) && workerOnline === false)
      panel.append(
        el("p", t("처리기 연결 끊김 · 진행 상태 확인 불가"), "worker-warning"),
      );
  }
  setInterval(() => {
    document.querySelectorAll(".job-progress").forEach((panel) => {
      const job = progressJobs.get(panel.dataset.jobId);
      if (job) paintProgress(panel, job);
    });
  }, 1000);

  function markSelectedJob() {
    for (const row of $("job-list").querySelectorAll(".job-row")) {
      const selected = row.dataset.jobId === selectedJob;
      row.classList.toggle("is-selected", selected);
      const button = row.querySelector(".job-header > button");
      button.textContent = selected ? t("상세 닫기") : t("상세 보기");
      button.setAttribute("aria-expanded", String(selected));
      button.setAttribute("aria-controls", "detail");
    }
  }

  async function refreshJobs() {
    const jobs = await api("/api/jobs");
    const list = $("job-list");
    const rows = new Map(Array.from(list.querySelectorAll(":scope > .job-row"), row => [row.dataset.jobId, row]));
    list.querySelector(":scope > .empty")?.remove();
    const ids = new Set(jobs.map(job => job.id));
    for (const [id, row] of rows) {
      if (!ids.has(id)) {
        if (row.contains($("detail"))) {
          $("jobs").append($("detail"));
          $("detail").hidden = true;
          selectedJob = null;
        }
        row.remove();
      }
    }
    if (!jobs.length) list.append(el("div", t("작업 없음"), "empty"));
    let cursor = list.firstElementChild;
    for (const job of jobs) {
      const row = rows.get(job.id) || el("article", undefined, "job-row");
      row.dataset.jobId = job.id;
      row.dataset.status = job.status;
      const header = el("div", undefined, "job-header");
      const info = el("div", undefined, "job-info");
      info.append(
        el(
          "strong",
          job.profile_name +
            " · " + (job.engine_name || "Qwen3-TTS · 1.7B") +
            " · " +
            (job.mode === "srt" ? t("영상 자막") : t("텍스트 TTS")),
        ),
        el(
          "small",
          new Date(job.created_at).toLocaleString(
            OwnVoiceI18n.locale === "ko" ? "ko-KR" : "en-US",
          ) +
            " · " +
            job.done +
            "/" +
            job.total +
            t(" 구간"),
        ),
      );
      const badge = el(
        "span",
        statusNames()[job.status] || job.status,
        "badge",
      );
      const button = el("button", t("상세 보기"));
      button.onclick = () => {
        const closing = selectedJob === job.id;
        $("detail").querySelectorAll("audio").forEach(player => player.pause());
        selectedJob = closing ? null : job.id;
        detailVersion = null;
        $("detail").hidden = true;
        markSelectedJob();
        if (!closing) showDetail().catch((error) => notify(error.message, true));
      };
      header.append(info, badge, button);
      const previousHeader = row.querySelector(":scope > .job-header");
      if (previousHeader) {
        previousHeader.querySelector(".job-info").replaceChildren(...info.childNodes);
        previousHeader.querySelector(".badge").textContent = badge.textContent;
        row.querySelector(":scope > .job-progress").replaceWith(progressPanel(job));
      } else row.append(header, progressPanel(job));
      if (row !== cursor) list.insertBefore(row, cursor);
      cursor = row.nextElementSibling;
    }
    markSelectedJob();
    if (selectedJob) await showDetail();
  }

  function segmentView(job, segment) {
    const section = el("section", undefined, "segment " + segment.status);
    const header = el("div", undefined, "segment-header");
    header.append(
      el(
        "strong",
        `${segment.index + 1}. ${statusNames()[segment.status] || segment.status}`,
      ),
    );
    if (segment.start_ms !== null) {
      header.append(
        el(
          "small",
          tr`${(segment.start_ms / 1000).toFixed(3)}–${(segment.end_ms / 1000).toFixed(3)}초`,
          "segment-time",
        ),
      );
    }
    section.append(header);
    if (segment.duration_ms !== null) {
      section.append(
        el(
          "p",
          tr`원본 합성 ${(segment.duration_ms / 1000).toFixed(2)}초 · 속도 ${segment.speed.toFixed(2)}×`,
          "segment-meta",
        ),
      );
    }
    if (segment.synthesis_attempts > 1) {
      section.append(
        el("p", tr`합성 ${segment.synthesis_attempts}회`, "segment-meta"),
      );
    }
    if (segment.timing_error) {
      section.append(el("p", segment.timing_error, "worker-warning"));
    }
    const input = el("textarea", undefined, "segment-text");
    input.setAttribute("aria-label", tr`${segment.index + 1}번 구간 텍스트`);
    const draftKey = `${job.id}:${segment.index}`;
    input.value = segmentDrafts.get(draftKey) ?? segment.text;
    input.oninput = () => segmentDrafts.set(draftKey, input.value);
    input.maxLength = 1000;
    input.disabled = ["queued", "running"].includes(job.status);
    section.append(input);
    const actions = el("div", undefined, "segment-actions");
    const save = el("button", t("수정·재생성"));
    save.disabled = input.disabled;
    save.onclick = async () => {
      try {
        await api(`/api/jobs/${job.id}/segments/${segment.index}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: input.value }),
        });
        segmentDrafts.delete(draftKey);
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
    const requestedJob = selectedJob;
    const j = await api("/api/jobs/" + requestedJob);
    if (selectedJob !== requestedJob) return;
    const row = Array.from($("job-list").children).find(row => row.dataset.jobId === j.id);
    if (!row) return;
    if ($("detail").parentElement !== row) row.append($("detail"));
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
      $("detail").dataset.jobId === j.id &&
      detailLocale === OwnVoiceI18n.locale &&
      $("detail").contains(document.activeElement) &&
      document.activeElement.tagName === "TEXTAREA"
    )
      return;
    detailVersion = version;
    detailLocale = OwnVoiceI18n.locale;
    const box = $("detail");
    box.dataset.jobId = j.id;
    box.hidden = false;
    box.replaceChildren(
      el("h2", j.profile_name + " · " + statusNames()[j.status]),
      progressPanel(j),
    );
    if (j.error) box.append(el("p", j.error));
    if (j.status === "completed") {
      const link = el("a", t("WAV 다운로드"), "download");
      link.href = "/api/jobs/" + j.id + "/audio";
      const actions = el("div", undefined, "output-actions");
      const player = el("audio", undefined, "audio-player");
      player.controls = true;
      player.src = link.href;
      actions.append(link, player);
      box.append(actions);
    }
    if (["failed", "needs_review"].includes(j.status)) {
      const retry = el("button", t("미완료 구간 재시도"));
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
  let engineCatalog = [];
  function updateEngine() {
    const selected = engineCatalog.find(e => e.id === $("engine").value);
    $("engine-name").textContent = selected?.name || "Qwen3-TTS";
    $("model-name").textContent = selected?.model || "—";
    $("engine-version").textContent = t("선택한 생성 모델");
    $("engine-note").textContent = $("engine").value === "qwen-small"
      ? t("경량 모델 · 속도와 품질은 생성 결과로 비교하세요.")
      : $("engine").value === "chatterbox"
        ? t("참조 음성으로 복제 · 대본은 사용하지 않습니다.")
        : t("참조 음성과 대본으로 복제합니다.");
    const auto = $("language").querySelector('option[value="Auto"]');
    auto.disabled = $("engine").value === "chatterbox";
    if (auto.disabled && $("language").value === "Auto") $("language").value = "Korean";
  }
  $("engine").onchange = updateEngine;
  async function refreshRuntime() {
    const r = await api("/api/runtime");
    workerOnline = r.worker_online;
    const hardware = r.hardware || {};
    engineCatalog = r.engines || [];
    for (const entry of engineCatalog) {
      const option = $("engine").querySelector(`option[value="${entry.id}"]`);
      if (option) {
        option.disabled = !entry.available;
        option.textContent = entry.name + (entry.available ? "" : " · " + t("패키지 미설치"));
      }
    }
    updateEngine();
    $("device-name").textContent =
      hardware.name || r.device || t("장치 미확인");
    $("device-memory").textContent = hardware.memory_gb
      ? `${hardware.memory_kind} ${hardware.memory_gb} GB`
      : t("메모리 정보 없음");
    $("device-backend").textContent = r.device?.startsWith("cuda")
      ? "NVIDIA · CUDA"
      : r.device === "mps"
        ? "Apple Silicon · Metal"
        : r.device === "cpu"
          ? "CPU"
          : t("미확인");
    $("device-state").textContent =
      tr`처리기 ${r.worker_online ? t("연결됨") : t("꺼짐")} · ${r.inference_verified ? t("합성 확인됨") : t("합성 확인 전")}`;
    $("runtime").textContent =
      tr`${r.device || t("장치 미확인")} · 처리기 ${r.worker_online ? t("연결됨") : t("꺼짐")}${r.tts_installed ? "" : t(" · TTS 설치 필요")}`;
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
      notify(t("서버 연결을 확인해 주세요."), true);
    } finally {
      polling = false;
    }
  }, 4000);

  $("ui-locale").onchange = async (event) => {
    OwnVoiceI18n.setLocale(event.target.value);
    $("notice").hidden = true;
    $("content-label").textContent =
      mode === "srt" ? t("SRT 자막") : t("텍스트");
    $("mode-help").textContent =
      mode === "srt"
        ? t("자막 시간 유지 · 초과 구간 검토 후 출력")
        : t("문장 사이 0.2초 간격 · 단일 WAV 출력");
    const isRecording = recording?.state === "recording";
    $("record").textContent = isRecording
      ? t("■ 녹음 끝내기")
      : recordedFile
        ? t("● 다시 녹음")
        : t("● 녹음 시작");
    $("record-status").textContent = isRecording
      ? t("녹음 중… 최대 60초")
      : recordedFile
        ? t("녹음 완료")
        : t("최대 60초");
    detailVersion = null;
    try {
      await Promise.all([profiles(), refreshJobs(), refreshRuntime()]);
    } catch (error) {
      notify(error.message, true);
    }
  };
})().catch((error) => {
  document.getElementById("notice").hidden = false;
  document.getElementById("notice").textContent = error.message;
});
