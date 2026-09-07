/**
 * KCMS Collaborative Labeler - Client Application Logic
 */

let storedSessionId = localStorage.getItem("kcms_session_id");
if (!storedSessionId) {
  storedSessionId = "sess_" + Math.random().toString(36).substring(2, 10) + "_" + Date.now();
  localStorage.setItem("kcms_session_id", storedSessionId);
}

// Application State
const state = {
  sessionId: storedSessionId,
  annotator: localStorage.getItem("kcms_annotator") || "",
  currentComment: null,
  selectedSeverity: null,
  selectedTarget: null,
  hasPII: false,
  leaseSecondsLeft: 60,
  leaseTimer: null,
  heartbeatTimer: null,
  statsTimer: null,
  bgmVolume: parseFloat(localStorage.getItem("kcms_bgm_volume") || "0.35"),
  bgmMuted: localStorage.getItem("kcms_bgm_muted") !== "false", // Muted by default
  bgmPlaying: false,
};

// DOM Elements
const el = {
  // Header & Audio
  bgMusic: document.getElementById("bgMusic"),
  btnMusicToggle: document.getElementById("btnMusicToggle"),
  musicIcon: document.getElementById("musicIcon"),
  volumeSlider: document.getElementById("volumeSlider"),
  volumeLabel: document.getElementById("volumeLabel"),
  musicPill: document.getElementById("musicPill"),
  syncStatus: document.getElementById("syncStatus"),
  progressNumbers: document.getElementById("progressNumbers"),
  progressFill: document.getElementById("progressFill"),
  displayAnnotator: document.getElementById("displayAnnotator"),
  userPill: document.getElementById("userPill"),
  btnHistory: document.getElementById("btnHistory"),
  btnLeaderboard: document.getElementById("btnLeaderboard"),

  // Workspaces / States
  loadingCard: document.getElementById("loadingCard"),
  completedCard: document.getElementById("completedCard"),
  labelingWorkspace: document.getElementById("labelingWorkspace"),

  // Comment Presentation
  badgeCommentId: document.getElementById("badgeCommentId"),
  badgeSplit: document.getElementById("badgeSplit"),
  badgeLink: document.getElementById("badgeLink"),
  leaseTimerText: document.getElementById("leaseTimerText"),
  commentText: document.getElementById("commentText"),

  // Form Controls
  severityBtns: document.querySelectorAll(".severity-btn"),
  targetBtns: document.querySelectorAll(".target-btn"),
  checkPII: document.getElementById("checkPII"),
  inputNotes: document.getElementById("inputNotes"),
  btnSubmit: document.getElementById("btnSubmit"),
  btnSkip: document.getElementById("btnSkip"),
  btnRefreshStats: document.getElementById("btnRefreshStats"),

  // Modals
  annotatorModal: document.getElementById("annotatorModal"),
  inputAnnotatorName: document.getElementById("inputAnnotatorName"),
  btnSaveAnnotator: document.getElementById("btnSaveAnnotator"),

  leaderboardModal: document.getElementById("leaderboardModal"),
  btnCloseLeaderboard: document.getElementById("btnCloseLeaderboard"),
  leaderboardTableBody: document.getElementById("leaderboardTableBody"),
  statTotalComments: document.getElementById("statTotalComments"),
  statLabeledCount: document.getElementById("statLabeledCount"),
  statRemainingCount: document.getElementById("statRemainingCount"),
  statActiveLeases: document.getElementById("statActiveLeases"),
  severityStatsRow: document.getElementById("severityStatsRow"),

  historyModal: document.getElementById("historyModal"),
  btnCloseHistory: document.getElementById("btnCloseHistory"),
  historyList: document.getElementById("historyList"),
  btnQuickHistory: document.getElementById("btnQuickHistory"),

  // Edit History Modal
  editModal: document.getElementById("editModal"),
  btnCloseEditModal: document.getElementById("btnCloseEditModal"),
  btnBackToHistory: document.getElementById("btnBackToHistory"),
  btnCancelEdit: document.getElementById("btnCancelEdit"),
  btnSaveEdit: document.getElementById("btnSaveEdit"),
  badgeEditId: document.getElementById("badgeEditId"),
  editCommentText: document.getElementById("editCommentText"),
  editCheckPII: document.getElementById("editCheckPII"),
  editInputNotes: document.getElementById("editInputNotes"),
  editSeverityBtns: document.querySelectorAll("[data-edit-sev]"),
  editTargetBtns: document.querySelectorAll("[data-edit-tgt]"),

  toast: document.getElementById("toast"),
};

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  setupKeyboardShortcuts();
  initAudio();

  if (!state.annotator) {
    showAnnotatorModal();
  } else {
    setAnnotator(state.annotator);
    startSession();
  }
});

function setupEventListeners() {
  // Annotator Modal
  el.userPill.addEventListener("click", showAnnotatorModal);
  el.btnSaveAnnotator.addEventListener("click", handleSaveAnnotator);
  el.inputAnnotatorName.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSaveAnnotator();
  });

  // Severity Selection
  el.severityBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectSeverity(parseInt(btn.dataset.severity, 10));
    });
  });

  // Target Selection
  el.targetBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectTarget(parseInt(btn.dataset.target, 10));
    });
  });

  // PII Toggle
  el.checkPII.addEventListener("change", (e) => {
    state.hasPII = e.target.checked;
  });

  // Actions
  el.btnSubmit.addEventListener("click", submitCurrentLabel);
  el.btnSkip.addEventListener("click", skipCurrentComment);
  if (el.btnRefreshStats) {
    el.btnRefreshStats.addEventListener("click", () => {
      fetchNextComment();
      updateStats();
    });
  }

  // Modals
  el.btnLeaderboard.addEventListener("click", openLeaderboard);
  el.btnCloseLeaderboard.addEventListener("click", () => el.leaderboardModal.classList.add("hidden"));

  el.btnHistory.addEventListener("click", openHistory);
  if (el.btnQuickHistory) {
    el.btnQuickHistory.addEventListener("click", openHistory);
  }
  el.btnCloseHistory.addEventListener("click", () => el.historyModal.classList.add("hidden"));

  // Edit Modal Wiring
  if (el.btnCloseEditModal) {
    el.btnCloseEditModal.addEventListener("click", () => el.editModal.classList.add("hidden"));
  }
  if (el.btnCancelEdit) {
    el.btnCancelEdit.addEventListener("click", () => {
      el.editModal.classList.add("hidden");
      el.historyModal.classList.remove("hidden");
    });
  }
  if (el.btnBackToHistory) {
    el.btnBackToHistory.addEventListener("click", () => {
      el.editModal.classList.add("hidden");
      el.historyModal.classList.remove("hidden");
    });
  }
  if (el.btnSaveEdit) {
    el.btnSaveEdit.addEventListener("click", saveEditLabel);
  }

  // Edit Option Buttons
  el.editSeverityBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectEditSeverity(parseInt(btn.dataset.editSev, 10));
    });
  });
  el.editTargetBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectEditTarget(parseInt(btn.dataset.editTgt, 10));
    });
  });

  // Close modals on backdrop click
  [el.leaderboardModal, el.historyModal, el.editModal].forEach((m) => {
    if (m) {
      m.addEventListener("click", (e) => {
        if (e.target === m) m.classList.add("hidden");
      });
    }
  });

  // Instant release of unlabelled comment when tab closes or navigates away
  const releaseCurrentLease = () => {
    if (!state.currentComment) return;
    const payload = JSON.stringify({
      comment_id: state.currentComment.comment_id,
      annotator: state.annotator,
      session_id: state.sessionId,
    });
    const blob = new Blob([payload], { type: "application/json" });
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/release", blob);
    } else {
      fetch("/api/release", {
        method: "POST",
        body: payload,
        headers: { "Content-Type": "application/json" },
        keepalive: true,
      });
    }
  };

  window.addEventListener("beforeunload", releaseCurrentLease);
  window.addEventListener("pagehide", releaseCurrentLease);
}

// ---------------------------------------------------------------------------
// Annotator Management
// ---------------------------------------------------------------------------
function showAnnotatorModal() {
  el.inputAnnotatorName.value = state.annotator;
  el.annotatorModal.classList.remove("hidden");
  setTimeout(() => el.inputAnnotatorName.focus(), 100);
}

function handleSaveAnnotator() {
  const name = el.inputAnnotatorName.value.trim();
  if (!name) {
    showToast("Please enter your name to proceed.");
    return;
  }
  setAnnotator(name);
  el.annotatorModal.classList.add("hidden");
  startSession();
}

function setAnnotator(name) {
  state.annotator = name;
  localStorage.setItem("kcms_annotator", name);
  el.displayAnnotator.textContent = name;
}

// ---------------------------------------------------------------------------
// Main Flow: Claim, Heartbeat & Timers
// ---------------------------------------------------------------------------
function startSession() {
  fetchNextComment();
  updateStats();

  // Background Intervals: 15s heartbeat to refresh 60s lease
  clearInterval(state.heartbeatTimer);
  state.heartbeatTimer = setInterval(sendHeartbeat, 15000); // 15s heartbeat

  clearInterval(state.statsTimer);
  state.statsTimer = setInterval(updateStats, 5000); // 5s stats refresh
}

async function fetchNextComment() {
  showLoading();
  resetForm();

  try {
    const res = await fetch("/api/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        annotator: state.annotator,
        session_id: state.sessionId,
      }),
    });

    if (!res.ok) throw new Error("Failed to claim comment");

    const data = await res.json();
    if (!data.has_comment || !data.comment) {
      showCompleted();
      return;
    }

    renderComment(data.comment);
  } catch (err) {
    console.error(err);
    showToast("Error connecting to server. Retrying...");
    setTimeout(fetchNextComment, 3000);
  }
}

function renderComment(comment) {
  state.currentComment = comment;

  const itemProgress = comment.row_index ? `Item #${comment.row_index} of ${comment.total_count}` : `ID: ${comment.comment_id}`;
  el.badgeCommentId.textContent = itemProgress;
  el.badgeSplit.textContent = `Split: ${comment.split || "train"}`;
  
  if (comment.link_flagged) {
    el.badgeLink.classList.remove("hidden");
  } else {
    el.badgeLink.classList.add("hidden");
  }

  el.commentText.textContent = comment.text;

  // Reset lease timer (60 seconds)
  startLeaseCountdown(60);

  // Show Workspace
  el.loadingCard.classList.add("hidden");
  el.completedCard.classList.add("hidden");
  el.labelingWorkspace.classList.remove("hidden");
}

function startLeaseCountdown(seconds) {
  state.leaseSecondsLeft = seconds;
  clearInterval(state.leaseTimer);

  updateLeaseDisplay();
  state.leaseTimer = setInterval(() => {
    state.leaseSecondsLeft--;
    updateLeaseDisplay();

    if (state.leaseSecondsLeft <= 0) {
      clearInterval(state.leaseTimer);
      showToast("Lease expired. Re-fetching comment...");
      fetchNextComment();
    }
  }, 1000);
}

function updateLeaseDisplay() {
  const mins = Math.floor(state.leaseSecondsLeft / 60);
  const secs = state.leaseSecondsLeft % 60;
  el.leaseTimerText.textContent = `${mins}:${secs.toString().padStart(2, "0")}`;
}

async function sendHeartbeat() {
  if (!state.currentComment) return;
  try {
    await fetch("/api/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        comment_id: state.currentComment.comment_id,
        annotator: state.annotator,
        session_id: state.sessionId,
      }),
    });
  } catch (e) {
    console.warn("Heartbeat error", e);
  }
}

// ---------------------------------------------------------------------------
// Form State & Selection
// ---------------------------------------------------------------------------
function selectSeverity(val) {
  state.selectedSeverity = val;
  el.severityBtns.forEach((btn) => {
    const btnVal = parseInt(btn.dataset.severity, 10);
    btn.classList.toggle("selected", btnVal === val);
  });
}

function selectTarget(val) {
  state.selectedTarget = val;
  el.targetBtns.forEach((btn) => {
    const btnVal = parseInt(btn.dataset.target, 10);
    btn.classList.toggle("selected", btnVal === val);
  });
}

function resetForm() {
  state.selectedSeverity = null;
  state.selectedTarget = null;
  state.hasPII = false;

  el.severityBtns.forEach((b) => b.classList.remove("selected"));
  el.targetBtns.forEach((b) => b.classList.remove("selected"));
  el.checkPII.checked = false;
  el.inputNotes.value = "";
}

// ---------------------------------------------------------------------------
// Submit & Skip
// ---------------------------------------------------------------------------
async function submitCurrentLabel() {
  if (!state.currentComment) return;

  if (state.selectedSeverity === null) {
    showToast("⚠️ Please select Severity (Keys [1], [2], or [3])");
    return;
  }
  if (state.selectedTarget === null) {
    showToast("⚠️ Please select Target (Keys [Q], [W], or [E])");
    return;
  }

  const payload = {
    comment_id: state.currentComment.comment_id,
    annotator: state.annotator,
    session_id: state.sessionId,
    severity_id: state.selectedSeverity,
    target_id: state.selectedTarget,
    has_pii: el.checkPII.checked,
    notes: el.inputNotes.value.trim(),
  };

  try {
    const res = await fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("Failed to submit label");

    const data = await res.json();
    showToast("✓ Label saved successfully");
    updateStats();

    // If server immediately provided next comment, render directly
    if (data.has_next && data.next_comment) {
      resetForm();
      renderComment(data.next_comment);
    } else {
      fetchNextComment();
    }
  } catch (err) {
    console.error(err);
    showToast("Error saving label. Please try again.");
  }
}

async function skipCurrentComment() {
  if (!state.currentComment) return;

  try {
    await fetch("/api/skip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        comment_id: state.currentComment.comment_id,
        annotator: state.annotator,
        session_id: state.sessionId,
      }),
    });
    fetchNextComment();
  } catch (err) {
    console.error(err);
  }
}

// ---------------------------------------------------------------------------
// Stats & Leaderboard
// ---------------------------------------------------------------------------
async function updateStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const stats = await res.json();

    el.progressNumbers.textContent = `${stats.labeled} / ${stats.total} (${stats.percent_complete}%)`;
    el.progressFill.style.width = `${stats.percent_complete}%`;

    // Leaderboard Modal values
    el.statTotalComments.textContent = stats.total;
    el.statLabeledCount.textContent = stats.labeled;
    el.statRemainingCount.textContent = stats.remaining;
    el.statActiveLeases.textContent = stats.active_leases_count;

    // Leaderboard table
    if (el.leaderboardTableBody) {
      const entries = Object.entries(stats.leaderboard || {}).sort((a, b) => b[1] - a[1]);
      el.leaderboardTableBody.innerHTML = entries
        .map(([name, count], i) => `
          <tr>
            <td><strong>#${i + 1}</strong></td>
            <td>${escapeHtml(name)} ${name === state.annotator ? '<span class="meta-badge">(You)</span>' : ''}</td>
            <td><strong>${count}</strong></td>
            <td>${((count / (stats.labeled || 1)) * 100).toFixed(1)}%</td>
          </tr>
        `)
        .join("");
    }
  } catch (e) {
    console.warn("Stats fetch failed", e);
  }
}

function openLeaderboard() {
  updateStats();
  el.leaderboardModal.classList.remove("hidden");
}

async function openHistory() {
  try {
    const res = await fetch(`/api/history?annotator=${encodeURIComponent(state.annotator)}&limit=30`);
    const data = await res.json();
    const history = data.history || [];
    state.recentHistory = history;

    if (history.length === 0) {
      el.historyList.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:24px;">You haven't submitted any comments yet.</p>`;
    } else {
      const sevLabels = ["Safe", "Offensive", "Harmful"];
      const tgtLabels = ["Neither", "Person", "Institution"];
      el.historyList.innerHTML = history
        .map((item, idx) => `
          <div class="history-item" data-history-idx="${idx}">
            <div class="history-item-left">
              <div class="history-item-header">
                <span class="meta-badge id-badge">ID: ${escapeHtml(item.comment_id)}</span>
                <span class="meta-badge split-badge">Split: ${escapeHtml(item.split || "train")}</span>
                ${item.has_pii ? '<span class="meta-badge link-badge">PII</span>' : ''}
              </div>
              <div class="history-text">${escapeHtml(item.text)}</div>
            </div>
            <div class="history-actions">
              <div class="history-badges">
                <span class="meta-badge ${item.severity_id === 0 ? 'text-green' : item.severity_id === 1 ? 'text-amber' : 'text-harmful'}">
                  ${sevLabels[item.severity_id]}
                </span>
                <span class="meta-badge ${item.target_id === 1 ? 'text-blue' : ''}">
                  ${tgtLabels[item.target_id]}
                </span>
              </div>
              <button class="btn-edit-history-item" data-history-idx="${idx}" title="Edit this label">
                ✏️ Edit
              </button>
            </div>
          </div>
        `)
        .join("");

      // Attach click listeners to open edit modal
      el.historyList.querySelectorAll(".history-item").forEach((card) => {
        card.addEventListener("click", () => {
          const idx = parseInt(card.dataset.historyIdx, 10);
          if (!isNaN(idx) && state.recentHistory[idx]) {
            openEditModal(state.recentHistory[idx]);
          }
        });
      });
    }
    el.historyModal.classList.remove("hidden");
  } catch (e) {
    showToast("Failed to load history.");
  }
}

// ---------------------------------------------------------------------------
// Keyboard Shortcuts
// ---------------------------------------------------------------------------
function setupKeyboardShortcuts() {
  window.addEventListener("keydown", (e) => {
    // Ignore hotkeys when typing in inputs or when modals are open
    const activeTag = document.activeElement.tagName.toLowerCase();
    if (activeTag === "input" || activeTag === "textarea") {
      if (e.key === "Enter" && activeTag === "input") {
        if (document.activeElement.id === "inputNotes") {
          submitCurrentLabel();
        } else if (document.activeElement.id === "editInputNotes") {
          saveEditLabel();
        }
      }
      return;
    }

    if (!el.annotatorModal.classList.contains("hidden")) return;
    if (!el.leaderboardModal.classList.contains("hidden")) {
      if (e.key === "Escape") el.leaderboardModal.classList.add("hidden");
      return;
    }
    if (!el.editModal.classList.contains("hidden")) {
      if (e.key === "Escape") {
        el.editModal.classList.add("hidden");
        el.historyModal.classList.remove("hidden");
      } else if (e.key === "Enter") {
        saveEditLabel();
      }
      return;
    }
    if (!el.historyModal.classList.contains("hidden")) {
      if (e.key === "Escape") el.historyModal.classList.add("hidden");
      return;
    }

    const key = e.key.toLowerCase();

    // Severity: 1, 2, 3
    if (key === "1") {
      e.preventDefault();
      selectSeverity(0);
    } else if (key === "2") {
      e.preventDefault();
      selectSeverity(1);
    } else if (key === "3") {
      e.preventDefault();
      selectSeverity(2);
    }

    // Target: Q, W, E
    else if (key === "q") {
      e.preventDefault();
      selectTarget(0);
    } else if (key === "w") {
      e.preventDefault();
      selectTarget(1);
    } else if (key === "e") {
      e.preventDefault();
      selectTarget(2);
    }

    // PII toggle: P
    else if (key === "p") {
      e.preventDefault();
      el.checkPII.checked = !el.checkPII.checked;
      state.hasPII = el.checkPII.checked;
    }

    // Submit: Enter
    else if (key === "enter") {
      e.preventDefault();
      submitCurrentLabel();
    }

    // Skip: S
    else if (key === "s") {
      e.preventDefault();
      skipCurrentComment();
    }

    // History: H
    else if (key === "h") {
      e.preventDefault();
      openHistory();
    }

    // Music Mute / Unmute: M
    else if (key === "m") {
      e.preventDefault();
      toggleMusicMute();
    }
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function showLoading() {
  el.loadingCard.classList.remove("hidden");
  el.labelingWorkspace.classList.add("hidden");
  el.completedCard.classList.add("hidden");
}

function showCompleted() {
  el.loadingCard.classList.add("hidden");
  el.labelingWorkspace.classList.add("hidden");
  el.completedCard.classList.remove("hidden");
}

function showToast(msg) {
  el.toast.textContent = msg;
  el.toast.classList.remove("hidden");
  clearTimeout(el.toast._timer);
  el.toast._timer = setTimeout(() => {
    el.toast.classList.add("hidden");
  }, 2400);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ---------------------------------------------------------------------------
// Background Music & Audio System
// ---------------------------------------------------------------------------
function initAudio() {
  if (!el.bgMusic) return;

  el.bgMusic.volume = state.bgmVolume;
  el.bgMusic.muted = state.bgmMuted;

  if (el.volumeSlider) {
    el.volumeSlider.value = state.bgmVolume;
  }
  if (el.volumeLabel) {
    el.volumeLabel.textContent = `${Math.round(state.bgmVolume * 100)}%`;
  }
  updateMusicIcon();

  // Mute / Unmute Button Click
  if (el.btnMusicToggle) {
    el.btnMusicToggle.addEventListener("click", toggleMusicMute);
  }

  // Volume Slider Input & Change
  if (el.volumeSlider) {
    el.volumeSlider.addEventListener("input", (e) => {
      setMusicVolume(parseFloat(e.target.value));
    });
  }
}

function playBGM() {
  if (!el.bgMusic) return;
  el.bgMusic
    .play()
    .then(() => {
      state.bgmPlaying = true;
      if (el.musicPill) el.musicPill.classList.add("playing");
      updateMusicIcon();
    })
    .catch((err) => {
      console.log("Audio waiting for user gesture:", err.message);
    });
}

function toggleMusicMute() {
  if (!el.bgMusic) return;

  if (el.bgMusic.paused || state.bgmMuted) {
    el.bgMusic.muted = false;
    state.bgmMuted = false;
    playBGM();
    showToast("🔊 Music playing");
  } else {
    el.bgMusic.muted = true;
    state.bgmMuted = true;
    showToast("🔇 Music muted");
  }

  localStorage.setItem("kcms_bgm_muted", state.bgmMuted ? "true" : "false");
  updateMusicIcon();
}

function setMusicVolume(val) {
  if (!el.bgMusic) return;
  const vol = Math.max(0, Math.min(1, val));
  state.bgmVolume = vol;
  el.bgMusic.volume = vol;

  if (vol === 0) {
    el.bgMusic.muted = true;
    state.bgmMuted = true;
  } else if (el.bgMusic.muted && vol > 0) {
    el.bgMusic.muted = false;
    state.bgmMuted = false;
    playBGM();
  }

  if (el.volumeSlider) el.volumeSlider.value = vol;
  if (el.volumeLabel) el.volumeLabel.textContent = `${Math.round(vol * 100)}%`;

  localStorage.setItem("kcms_bgm_volume", vol.toString());
  localStorage.setItem("kcms_bgm_muted", state.bgmMuted ? "true" : "false");
  updateMusicIcon();
}

function updateMusicIcon() {
  if (!el.musicIcon) return;
  if (state.bgmMuted || state.bgmVolume === 0 || (el.bgMusic && el.bgMusic.muted)) {
    el.musicIcon.textContent = "🔇";
    if (el.musicPill) el.musicPill.classList.remove("playing");
  } else if (state.bgmVolume < 0.35) {
    el.musicIcon.textContent = "🔈";
    if (el.musicPill && state.bgmPlaying) el.musicPill.classList.add("playing");
  } else if (state.bgmVolume < 0.7) {
    el.musicIcon.textContent = "🔉";
    if (el.musicPill && state.bgmPlaying) el.musicPill.classList.add("playing");
  } else {
    el.musicIcon.textContent = "🔊";
    if (el.musicPill && state.bgmPlaying) el.musicPill.classList.add("playing");
  }
}

// ---------------------------------------------------------------------------
// Historical Comment Editing System
// ---------------------------------------------------------------------------
function openEditModal(item) {
  state.editingItem = item;
  state.editSeverity = item.severity_id !== undefined ? item.severity_id : 0;
  state.editTarget = item.target_id !== undefined ? item.target_id : 0;

  if (el.badgeEditId) el.badgeEditId.textContent = item.comment_id;
  if (el.editCommentText) el.editCommentText.textContent = item.text;
  if (el.editCheckPII) el.editCheckPII.checked = !!item.has_pii;
  if (el.editInputNotes) el.editInputNotes.value = item.notes || "";

  selectEditSeverity(state.editSeverity);
  selectEditTarget(state.editTarget);

  el.historyModal.classList.add("hidden");
  el.editModal.classList.remove("hidden");
}

function selectEditSeverity(val) {
  state.editSeverity = val;
  el.editSeverityBtns.forEach((btn) => {
    const btnVal = parseInt(btn.dataset.editSev, 10);
    btn.classList.toggle("selected", btnVal === val);
  });
}

function selectEditTarget(val) {
  state.editTarget = val;
  el.editTargetBtns.forEach((btn) => {
    const btnVal = parseInt(btn.dataset.editTgt, 10);
    btn.classList.toggle("selected", btnVal === val);
  });
}

async function saveEditLabel() {
  if (!state.editingItem) return;

  if (state.editSeverity === null) {
    showToast("⚠️ Please select Severity");
    return;
  }
  if (state.editTarget === null) {
    showToast("⚠️ Please select Target");
    return;
  }

  const payload = {
    comment_id: state.editingItem.comment_id,
    annotator: state.annotator,
    severity_id: state.editSeverity,
    target_id: state.editTarget,
    has_pii: el.editCheckPII.checked,
    notes: el.editInputNotes.value.trim(),
  };

  try {
    const res = await fetch("/api/edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("Failed to update label");

    showToast(`✓ Updated ${state.editingItem.comment_id}`);
    updateStats();

    // Close edit modal and return to refreshed history view
    el.editModal.classList.add("hidden");
    openHistory();
  } catch (err) {
    console.error(err);
    showToast("Error updating label. Please try again.");
  }
}
