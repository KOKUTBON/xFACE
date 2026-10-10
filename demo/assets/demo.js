"use strict";
// Local UI only: no fetch, API clients or cookies. The optional camera preview
// starts only on an explicit click, stays in this browser and is never recorded.
// Browser storage is used only by theme.js to remember the colour theme.
const subjects = [
  { name: "Alex Morgan", samples: 4 },
  { name: "Jamie Chen", samples: 3 },
  { name: "Sam Rivera", samples: 5 },
  { name: "Taylor Brooks", samples: 3 },
  { name: "Jordan Lee", samples: 4 },
  { name: "Casey Patel", samples: 2 },
];
const $ = (selector) => document.querySelector(selector);
const icon = (name, cls = "") =>
  `<svg class="i ${cls}" aria-hidden="true" focusable="false"><use href="#i-${name}"/></svg>`;

/* ---------- Shell ---------- */

function toast(message, type = "info") {
  const stack = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.setAttribute("role", "status");
  el.innerHTML = `<span class="t-icon">${icon(type === "success" ? "check" : "info")}</span><div class="t-msg"></div>`;
  el.querySelector(".t-msg").textContent = message;
  stack.append(el);
  while (stack.children.length > 3) stack.firstElementChild.remove();
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 250);
  }, 4000);
}

const navToggle = $("[data-nav-toggle]");
function setNav(open) {
  document.body.classList.toggle("nav-open", open);
  navToggle.setAttribute("aria-expanded", String(open));
}
navToggle.addEventListener("click", () =>
  setNav(!document.body.classList.contains("nav-open")),
);
$("[data-nav-close]").addEventListener("click", () => setNav(false));

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-close]"))
    event.target.closest("dialog").close();
  else if (event.target instanceof HTMLDialogElement) event.target.close();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setNav(false);
  const tag = document.activeElement?.tagName;
  if (event.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(tag)) {
    const search = $("[data-search]");
    if (search && !document.querySelector("dialog[open]")) {
      event.preventDefault();
      search.focus();
    }
  }
});

// The demo clock starts from the fixture time so the scene stays coherent
const clocks = document.querySelectorAll("[data-clock]");
let demoSeconds = 10 * 3600 + 42 * 60 + 18;
setInterval(() => {
  demoSeconds = (demoSeconds + 1) % 86400;
  const pad = (n) => String(n).padStart(2, "0");
  const text = `${pad(Math.floor(demoSeconds / 3600))}:${pad(Math.floor(demoSeconds / 60) % 60)}:${pad(demoSeconds % 60)}`;
  clocks.forEach((el) => (el.textContent = text));
}, 1000);

$("#open-door").addEventListener("click", () => {
  toast("Demo unlock complete. Only a simulated relay state changed.", "success");
  if ($("#door-panel")) setDoor(true, "Manual unlock");
});

/* ---------- Subjects ---------- */

if ($("#subject-search")) {
  $("#subject-search").addEventListener("input", (event) => {
    const query = event.target.value.toLowerCase().trim();
    let visible = 0;
    document.querySelectorAll(".subject-card").forEach((card) => {
      card.hidden = !card.dataset.name.includes(query);
      if (!card.hidden) visible++;
    });
    $("#subject-empty").hidden = visible !== 0;
    $("#subject-count").textContent = query
      ? `${visible} of ${subjects.length}`
      : `${subjects.length} total`;
  });
  const dialog = $("#sample-dialog");
  document.querySelectorAll("[data-samples]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.samples);
      const subject = subjects[index];
      $("#sample-title").textContent =
        `${subject.name} · ${subject.samples} synthetic samples`;
      const gallery = $("#sample-gallery");
      gallery.replaceChildren();
      for (let i = 0; i < subject.samples; i++) {
        const figure = document.createElement("figure");
        const img = document.createElement("img");
        img.src = `assets/avatar-${index}.svg`;
        img.alt = `Illustrated placeholder ${i + 1} for fictional subject ${subject.name}`;
        const caption = document.createElement("figcaption");
        caption.innerHTML = `<span>SAMPLE ${String(i + 1).padStart(2, "0")}</span>${icon("check", "i-sm")}`;
        figure.append(img, caption);
        gallery.append(figure);
      }
      dialog.showModal();
    });
  });
}

/* ---------- Access logs ---------- */

if ($("#log-search")) {
  const rows = Array.from(document.querySelectorAll("tbody tr"));
  function filter() {
    const name = $("#log-search").value.toLowerCase().trim();
    const status = $("#log-status").value;
    let visible = 0;
    rows.forEach((row) => {
      row.hidden =
        !row.dataset.subject.includes(name) ||
        (status && row.dataset.status !== status);
      if (!row.hidden) visible++;
    });
    $("#log-count").textContent =
      `${visible} sample event${visible === 1 ? "" : "s"}`;
    $("#log-empty").hidden = visible !== 0;
  }
  $("#log-search").addEventListener("input", filter);
  $("#log-status").addEventListener("change", filter);
  $("#reset-filters").addEventListener("click", () => {
    $("#log-search").value = "";
    $("#log-status").value = "";
    filter();
  });
  $("#export-csv").addEventListener("click", () => {
    const quote = (value) => `"${value.replaceAll('"', '""')}"`;
    const csv = [
      "timestamp_utc,subject,status,similarity_percent,device,relay,synthetic",
    ];
    rows
      .filter((row) => !row.hidden)
      .forEach((row) => {
        csv.push(
          [
            `2026-10-05T${row.dataset.time}Z`,
            row.dataset.name,
            row.dataset.status,
            row.dataset.similarity,
            "Entrance 01",
            "SIMULATED",
            "true",
          ]
            .map(quote)
            .join(","),
        );
      });
    const url = URL.createObjectURL(
      new Blob([csv.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "xface-synthetic-events.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(
      `Exported ${csv.length - 1} synthetic event${csv.length === 2 ? "" : "s"}.`,
      "success",
    );
  });
}

/* ---------- Live monitor ---------- */

let doorTimer;
function setDoor(open, label) {
  const panel = $("#door-panel");
  if (!panel) return;
  panel.classList.toggle("open", open);
  $("#door-icon").setAttribute("href", open ? "#i-door-open" : "#i-door-closed");
  $("#door-state").textContent = label || (open ? "Unlocked" : "Locked");
  const doorTag = $("#door-tag");
  doorTag.className = `tag ${open ? "ok" : "neutral"}`;
  doorTag.innerHTML = open ? `${icon("unlock")} Open` : `${icon("lock")} Secured`;
  clearTimeout(doorTimer);
  if (open) doorTimer = setTimeout(() => setDoor(false), 5000);
}

if ($("#monitor-avatar")) {
  const scenarios = {
    granted: {
      index: 0,
      state: "authorized",
      label: "Alex Morgan · 98.4%",
      title: "Welcome, Alex Morgan",
      subject: "Access granted",
      score: 98.4,
      icon: "check",
      open: true,
      color: "#3ddc97",
    },
    denied: {
      index: 3,
      state: "denied",
      label: "NO MATCH · 78.6%",
      title: "Access denied",
      subject: "Similarity below the demo threshold",
      score: 78.6,
      icon: "x",
      open: false,
      color: "#ff5d6e",
    },
    unknown: {
      index: 5,
      state: "unknown",
      label: "UNKNOWN · 42.1%",
      title: "Not recognised",
      subject: "No enrolled identity matched",
      score: 42.1,
      icon: "user-unknown",
      open: false,
      color: "#ffb547",
    },
    scanning: {
      state: "idle",
      label: "SCANNING…",
      title: "Scanning…",
      subject: "Hold still and look at the camera",
      score: 0,
      icon: "scan-face",
      open: false,
      color: "#5ce1ff",
    },
  };

  const overlay = $("#face-overlay");
  const video = $("#monitor-video");
  const avatarImg = $("#monitor-avatar");
  let current = scenarios.granted;
  let stream = null;
  let liveBox = null; // last detected face box in video pixels (already mirrored)
  let detector = null;
  let detectTimer = null;
  let scanTimer = null;

  // Coordinate space of whatever the stage is showing
  function frame() {
    return stream && video.videoWidth
      ? { w: video.videoWidth, h: video.videoHeight }
      : { w: 320, h: 240 };
  }

  function drawFace() {
    const scene = current;
    const { w: W, h: H } = frame();
    overlay.setAttribute("viewBox", `0 0 ${W} ${H}`);
    let box;
    if (!stream) box = [104, 44, 112, 140];
    else if (liveBox) box = liveBox;
    else box = [W * 0.5 - H * 0.22, H * 0.2, H * 0.44, H * 0.56]; // centred guide
    const [x, y, w, h] = box;
    const k = stream ? W / 560 : W / 320;
    const c = Math.min(w, h) * 0.22;
    const fs = 10.5 * k;
    const label = stream && scene.state === "authorized" ? `SIMULATED · ${scene.score}%` : scene.label;
    const tagW = label.length * fs * 0.62 + 14 * k;
    // Keep the label clear of the top HUD pills when showing the live camera
    const topLimit = stream ? H * 0.17 : 0;
    const tagY = y - 22 * k < topLimit ? y + h + 5 * k : y - 22 * k;
    overlay.innerHTML = `
      <g class="face-box" style="color:${scene.color}">
        <rect class="box" x="${x}" y="${y}" width="${w}" height="${h}" rx="${6 * k}" stroke="currentColor" stroke-opacity=".45"/>
        <path class="corner" stroke="currentColor" d="M${x} ${y + c}V${y}H${x + c}M${x + w - c} ${y}H${x + w}V${y + c}M${x + w} ${y + h - c}V${y + h}H${x + w - c}M${x + c} ${y + h}H${x}V${y + h - c}"/>
        <rect x="${x}" y="${tagY}" width="${tagW}" height="${17 * k}" rx="${4 * k}" fill="currentColor"/>
        <text x="${x + 7 * k}" y="${tagY + 12.5 * k}" fill="#03131c" font-size="${fs}"></text>
      </g>`;
    overlay.querySelector("text").textContent = label;
  }

  function showScenario(key) {
    const scene = scenarios[key];
    current = scene;
    const decision = $("#decision");
    if (!stream && scene.index !== undefined) {
      avatarImg.src = `assets/avatar-${scene.index}.svg`;
      avatarImg.alt = `Illustrated synthetic visitor for ${key} scenario`;
    }
    decision.dataset.state = scene.state;
    const core = decision.querySelector(".ring-core");
    core.style.animation = "none";
    void core.offsetWidth;
    core.style.animation = "";
    $("#decision-icon use").setAttribute("href", `#i-${scene.icon}`);
    $("#decision-title").textContent =
      stream && scene.state === "authorized" ? "Welcome (simulated)" : scene.title;
    $("#decision-subject").textContent = scene.subject;
    $("#decision-score").textContent = scene.score ? `${scene.score}%` : "—";
    $("#ring-value").style.strokeDasharray = `${scene.score} 100`;
    drawFace();
    setDoor(scene.open);
    document.querySelectorAll("[data-scenario]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.scenario === key),
      );
    });
  }

  /* ----- Optional local camera preview ----- */

  function renderCameraButtons() {
    document.querySelectorAll("[data-camera-toggle]").forEach((button) => {
      const small = button.closest(".hud") !== null;
      button.innerHTML = stream
        ? `${icon("camera-off", small ? "i-sm" : "")} <span>Stop camera</span>`
        : `${icon("camera", small ? "i-sm" : "")} <span>Use my camera</span>`;
      button.setAttribute("aria-pressed", String(Boolean(stream)));
    });
    $("#feed-label").textContent = stream ? "YOUR CAMERA" : "DEMO FEED";
    $("#feed-meta").textContent = stream
      ? `${video.videoWidth || "—"}×${video.videoHeight || "—"} · LOCAL ONLY`
      : "320×240 · SYNTHETIC";
    $("#feed-source").textContent = stream
      ? "Local preview · nothing leaves this browser"
      : "Entrance 01 · illustrated scene";
  }

  async function detectLoop() {
    if (!stream || !detector) return;
    try {
      if (video.readyState >= 2) {
        const faces = await detector.detect(video);
        if (faces.length) {
          const b = faces[0].boundingBox;
          const pad = b.height * 0.18;
          // The preview is mirrored, so mirror the box horizontally too
          liveBox = [video.videoWidth - b.x - b.width, b.y - pad, b.width, b.height + pad];
        } else {
          liveBox = null;
        }
        drawFace();
      }
    } catch {
      detector = null; // unsupported in practice: keep the centred guide
      return;
    }
    detectTimer = setTimeout(detectLoop, 120);
  }

  function stopCamera() {
    clearTimeout(detectTimer);
    clearTimeout(scanTimer);
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    liveBox = null;
    video.srcObject = null;
    video.hidden = true;
    avatarImg.hidden = false;
    overlay.setAttribute("preserveAspectRatio", "xMidYMid meet");
    renderCameraButtons();
    showScenario("granted");
  }

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      toast("Camera access is not available in this browser.");
      return;
    }
    stopPlayer();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (error) {
      stream = null;
      toast(
        error && error.name === "NotAllowedError"
          ? "Camera permission was denied. The demo keeps using illustrated scenes."
          : "No camera could be opened.",
      );
      return;
    }
    video.srcObject = stream;
    await video.play().catch(() => {});
    if (!video.videoWidth) await new Promise((resolve) => video.addEventListener("loadedmetadata", resolve, { once: true }));
    video.hidden = false;
    avatarImg.hidden = true;
    // The video fills the stage (cover), so the overlay must crop the same way
    overlay.setAttribute("preserveAspectRatio", "xMidYMid slice");
    renderCameraButtons();
    toast("Camera on. The preview stays in this browser; nothing is recorded or recognised.", "success");
    if ("FaceDetector" in window) {
      try {
        detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 });
        detectLoop();
      } catch {
        detector = null;
      }
    }
    // You are not enrolled, so the honest outcome is "unknown"
    showScenario("scanning");
    scanTimer = setTimeout(() => showScenario("unknown"), 2200);
  }

  document.querySelectorAll("[data-camera-toggle]").forEach((button) => {
    button.addEventListener("click", () => (stream ? stopCamera() : startCamera()));
  });
  window.addEventListener("pagehide", () => stream && stopCamera());

  let player;
  let step = 0;
  const playButton = $("#play-scenarios");
  function stopPlayer() {
    clearInterval(player);
    player = null;
    playButton.innerHTML = `${icon("play")} <span>Auto-play</span>`;
    playButton.setAttribute("aria-pressed", "false");
  }
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.addEventListener("click", () => {
      stopPlayer();
      clearTimeout(scanTimer);
      showScenario(button.dataset.scenario);
    });
  });
  playButton.addEventListener("click", () => {
    if (player) {
      stopPlayer();
      return;
    }
    clearTimeout(scanTimer);
    playButton.innerHTML = `${icon("pause")} <span>Pause playback</span>`;
    playButton.setAttribute("aria-pressed", "true");
    const advance = () =>
      showScenario(["granted", "denied", "unknown"][step++ % 3]);
    advance();
    player = setInterval(advance, 3500);
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) return;
    stopPlayer();
    if (stream) stopCamera(); // never keep the camera running in a background tab
  });

  const fullscreenButton = $("#fullscreen");
  fullscreenButton.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if ($("#stage").requestFullscreen)
        await $("#stage").requestFullscreen();
      else toast("Fullscreen is unavailable in this browser.");
    } catch {
      toast("Fullscreen is unavailable in this browser.");
    }
  });
  document.addEventListener("fullscreenchange", () => {
    fullscreenButton.innerHTML = document.fullscreenElement
      ? `${icon("compress", "i-sm")} <span>Exit</span>`
      : `${icon("expand", "i-sm")} <span>Fullscreen</span>`;
  });
  showScenario("granted");
}
