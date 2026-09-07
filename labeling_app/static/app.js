/**
 * KCMS Collaborative Labeler - Client Application Logic
 */

// Application State
const state = {
  annotator: localStorage.getItem("kcms_annotator") || "",
  currentComment: null,
  selectedSeverity: null,
  selectedTarget: null,
  hasPII: false,
  leaseSecondsLeft: 300,
  leaseTimer: null,
  heartbeatTimer: null,
  statsTimer: null,
};

// DOM Elements
const el = {
  // Header
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

  toast: document.getElementById("toast"),
};

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  setupKeyboardShortcuts();

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
  el.btnCloseHistory.addEventListener("click", () => el.historyModal.classList.add("hidden"));

  // Close modals on backdrop click
  [el.leaderboardModal, el.historyModal].forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) m.classList.add("hidden");
    });
  });
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

  // Background Intervals
  clearInterval(state.heartbeatTimer);
  state.heartbeatTimer = setInterval(sendHeartbeat, 30000); // 30s heartbeat

  clearInterval(state.statsTimer);
  state.statsTimer = setInterval(updateStats, 6000); // 6s stats refresh
}

async function fetchNextComment() {
  showLoading();
  resetForm();

  try {
    const res = await fetch("/api/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ annotator: state.annotator }),
    });

    if (!res.ok) throw new Error("Failed to claim comment");

    const data = await res.json();
    if (!data.has_comment) {
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

  el.badgeCommentId.textContent = `ID: ${comment.comment_id}`;
  el.badgeSplit.textContent = `Split: ${comment.split || "train"}`;
  
  if (comment.link_flagged) {
    el.badgeLink.classList.remove("hidden");
  } else {
    el.badgeLink.classList.add("hidden");
  }

  el.commentText.textContent = comment.text;

  // Reset lease timer (300 seconds)
  startLeaseCountdown(300);

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
    const res = await fetch(`/api/history?annotator=${encodeURIComponent(state.annotator)}&limit=15`);
    const data = await res.json();
    const history = data.history || [];

    if (history.length === 0) {
      el.historyList.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:20px;">You haven't submitted any comments yet.</p>`;
    } else {
      el.historyList.innerHTML = history
        .map((item) => {
          const sevLabels = ["Safe", "Offensive", "Harmful"];
          const tgtLabels = ["Neither", "Person", "Institution"];
          return `
            <div class="history-item">
              <div class="history-text">${escapeHtml(item.text)}</div>
              <div class="history-badges">
                <span class="meta-badge">${sevLabels[item.severity_id]}</span>
                <span class="meta-badge">${tgtLabels[item.target_id]}</span>
                ${item.has_pii ? '<span class="meta-badge link-badge">PII</span>' : ''}
              </div>
            </div>
          `;
        })
        .join("");
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
      if (e.key === "Enter" && activeTag === "input" && document.activeElement.id === "inputNotes") {
        submitCurrentLabel();
      }
      return;
    }

    if (!el.annotatorModal.classList.contains("hidden")) return;
    if (!el.leaderboardModal.classList.contains("hidden")) {
      if (e.key === "Escape") el.leaderboardModal.classList.add("hidden");
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
