"use strict";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

let toastTimer = null;
function toast(msg, type) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (type ? " " + type : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, type === "err" ? 6000 : 3500);
}

// ---------------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------------
let BOOT = null;
let frameW = 0, frameH = 0;
let baseImage = null;    // current canvas base (the captured frame)
let startPoint = null;   // [x,y] px -- pick
let endPoint = null;     // [x,y] px -- place
let episodeId = null;
let stepIndex = 0;

const canvas = $("canvas");
const ctx = canvas.getContext("2d");

function clickMode() { return document.querySelector('input[name="mode"]:checked').value; }
function setClickMode(v) { document.querySelector(`input[name="mode"][value="${v}"]`).checked = true; }

// ---------------------------------------------------------------------------
// Canvas drawing
// ---------------------------------------------------------------------------
function toFramePoint(evt) {
  const r = canvas.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(frameW, (evt.clientX - r.left) * (canvas.width / r.width))),
    y: Math.max(0, Math.min(frameH, (evt.clientY - r.top) * (canvas.height / r.height))),
  };
}

function drawArrow(from, to, color) {
  const sz = Math.max(8, frameW * 0.022);
  const a = Math.atan2(to[1] - from[1], to[0] - from[0]);
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2, frameW * 0.006);
  ctx.beginPath(); ctx.moveTo(from[0], from[1]); ctx.lineTo(to[0], to[1]); ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(to[0], to[1]);
  ctx.lineTo(to[0] - sz * Math.cos(a - Math.PI / 6), to[1] - sz * Math.sin(a - Math.PI / 6));
  ctx.lineTo(to[0] - sz * Math.cos(a + Math.PI / 6), to[1] - sz * Math.sin(a + Math.PI / 6));
  ctx.closePath(); ctx.fillStyle = color; ctx.fill();
}

function dot(pt, color) {
  const r = Math.max(5, frameW * 0.013);
  ctx.beginPath(); ctx.arc(pt[0], pt[1], r, 0, 2 * Math.PI);
  ctx.fillStyle = color; ctx.fill();
  ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
}

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!baseImage) return;
  ctx.drawImage(baseImage, 0, 0, frameW, frameH);
  if (startPoint && endPoint) drawArrow(startPoint, endPoint, "#eab308");
  if (startPoint) dot(startPoint, "#ef4444");
  if (endPoint) dot(endPoint, "#3b82f6");
}

function loadBase(url, cb) {
  const img = new Image();
  img.onload = () => { baseImage = img; redraw(); if (cb) cb(); };
  img.src = url;
}

function updatePointInfo() {
  const parts = [];
  if (startPoint) parts.push(`start (${startPoint[0]}, ${startPoint[1]})`);
  if (endPoint) parts.push(`end (${endPoint[0]}, ${endPoint[1]})`);
  $("pointInfo").textContent = parts.join("  ·  ");
  $("btnExecute").disabled = !(startPoint && endPoint);
}

// ---------------------------------------------------------------------------
// Header / episode status
// ---------------------------------------------------------------------------
function updateHeaderCounts(summary) {
  $("episodeCount").textContent = summary.num_episodes;
  $("stepCount").textContent = summary.num_steps;
}

function updateEpisodeStatus() {
  if (!episodeId) {
    $("episodeIdLine").textContent = "No active episode.";
    $("epStatus").textContent = "No active episode. Put the cloth in frame and capture.";
  } else {
    $("episodeIdLine").innerHTML = `Episode <b>${episodeId}</b> &mdash; ${stepIndex} step${stepIndex === 1 ? "" : "s"} recorded.`;
    $("epStatus").innerHTML = `Episode <b>${episodeId}</b>, step ${stepIndex}. Pick a start and end point.`;
  }
  $("btnFinish").disabled = !(episodeId && stepIndex >= 1);
}

function addLogEntry(row, pickXy, placeXy) {
  const li = document.createElement("li");
  li.innerHTML = `<b>Step ${row.step_index}</b> &mdash; ` +
    `pick (${row.pick_x_px}, ${row.pick_y_px})px &rarr; place (${row.place_x_px}, ${row.place_y_px})px ` +
    `&nbsp;|&nbsp; robot (${pickXy[0].toFixed(3)}, ${pickXy[1].toFixed(3)}) &rarr; (${placeXy[0].toFixed(3)}, ${placeXy[1].toFixed(3)})`;
  $("stepLog").appendChild(li);
  $("stepLog").scrollTop = $("stepLog").scrollHeight;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function doCapture() {
  $("btnCapture").disabled = true;
  $("canvasHint").textContent = "Capturing…";
  $("canvasHint").hidden = false;
  try {
    const r = await api("/api/capture", {});
    frameW = r.width; frameH = r.height;
    canvas.width = frameW; canvas.height = frameH;
    episodeId = r.episode_id; stepIndex = r.step_index;
    startPoint = null; endPoint = null;
    setClickMode("start");
    updatePointInfo();
    updateEpisodeStatus();
    loadBase(r.image, () => { $("canvasHint").hidden = true; });
    toast("Frame captured. Click the start point.", "ok");
  } catch (e) {
    $("canvasHint").textContent = "Capture failed.";
    toast(e.message, "err");
  } finally {
    $("btnCapture").disabled = false;
  }
}

async function doExecute() {
  if (!startPoint || !endPoint) { toast("Click both a start and an end point first.", "err"); return; }
  $("btnExecute").disabled = true;
  $("btnCapture").disabled = true;
  const busyMsg = BOOT.robot_enabled ? "Robot moving…" : "Simulating action…";
  $("epStatus").textContent = busyMsg;
  try {
    const r = await api("/api/execute", { pick: startPoint, place: endPoint });
    episodeId = r.episode_id; stepIndex = r.step_index;
    addLogEntry(r.row, r.pick_xy, r.place_xy);
    toast(`Step ${r.row.step_index} executed.`, "ok");

    // The backend requires a fresh capture before the next execute (the
    // cloth has moved). Clear the canvas and points accordingly.
    baseImage = null; startPoint = null; endPoint = null;
    canvas.width = 10; canvas.height = 10;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    $("canvasHint").textContent = "Capture frame to see the cloth's new position.";
    $("canvasHint").hidden = false;
    setClickMode("start");
    updatePointInfo();
    updateEpisodeStatus();
  } catch (e) {
    toast(e.message, "err");
    updateEpisodeStatus();
  } finally {
    $("btnCapture").disabled = false;
  }
}

async function doFinish() {
  $("btnFinish").disabled = true;
  try {
    const r = await api("/api/finish", { notes: $("notes").value });
    toast(`Episode ${r.episode.episode_id} saved: ${r.episode.num_steps} step(s).`, "ok");
    updateHeaderCounts(r.summary);

    episodeId = null; stepIndex = 0;
    baseImage = null; startPoint = null; endPoint = null;
    canvas.width = 10; canvas.height = 10;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    $("canvasHint").textContent = "Click Capture frame to begin.";
    $("canvasHint").hidden = false;
    $("stepLog").innerHTML = "";
    $("notes").value = "";
    setClickMode("start");
    updatePointInfo();
    updateEpisodeStatus();
  } catch (e) {
    toast(e.message, "err");
    $("btnFinish").disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Canvas mouse events
// ---------------------------------------------------------------------------
canvas.addEventListener("mousedown", (e) => {
  if (!baseImage) return;
  const pt = toFramePoint(e);
  const p = [Math.round(pt.x), Math.round(pt.y)];

  if (clickMode() === "start") {
    startPoint = p;
    setClickMode("end");
  } else {
    endPoint = p;
  }
  redraw();
  updatePointInfo();
});

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
$("btnCapture").addEventListener("click", doCapture);
$("btnExecute").addEventListener("click", doExecute);
$("btnFinish").addEventListener("click", doFinish);
$("btnClearPoints").addEventListener("click", () => {
  startPoint = null; endPoint = null;
  setClickMode("start");
  redraw();
  updatePointInfo();
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  try {
    BOOT = await (await fetch("/api/bootstrap")).json();
  } catch (e) {
    toast("Failed to load app data: " + e.message, "err");
    return;
  }
  $("datasetDir").textContent = BOOT.dataset_dir;
  $("captureSource").textContent = BOOT.capture_source;
  $("robotMode").textContent = BOOT.robot_enabled ? "ENABLED (live)" : "SIMULATED";
  $("robotMode").className = BOOT.robot_enabled ? "live" : "sim";
  $("simBanner").hidden = !!BOOT.robot_enabled;
  updateHeaderCounts(BOOT.summary);
  updateEpisodeStatus();
}

init();
