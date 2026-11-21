// Muse Video Studio - Client-Side Controller
let currentProjectId = null;
let currentProjectData = null;
let accountsList = [];
let projectsList = [];
let ws = null;
let uploadedRefsForNewShot = [];
let accountsPollTimer = null;
let accountsPollStartedAt = 0;
let wasCheckingAccounts = false;
let accountsBannerTimer = null;

// Khởi chạy khi load trang
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  loadAccounts();
  loadProjects();
  initRefFilesListener();
});

// ----------------- WEBSOCKET REALTIME -----------------
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    appendLog("WebSocket đã kết nối thành công.", "success");
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleWsEvent(msg.type, msg.data);
    } catch (e) {
      console.error("Lỗi parse WS:", e);
    }
  };

  ws.onclose = () => {
    appendLog("Mất kết nối WebSocket. Đang thử kết nối lại sau 3s...", "error");
    setTimeout(initWebSocket, 3000);
  };
}

function handleWsEvent(type, data) {
  switch (type) {
    case "init_state":
      if (data.accounts) renderAccounts(data.accounts);
      updateRenderControls(data.is_rendering);
      break;

    case "accounts_updated":
      renderAccounts(data);
      break;

    case "account_verified":
      const res = data.result || {};
      const statusIcon = res.status === "READY" ? "✅" : (res.status === "COOLDOWN" ? "⏳" : "❌");
      const qSummary = res.usage_info && res.usage_info.summary ? ` [${res.usage_info.summary}]` : "";
      appendLog(`[Xác thực ${data.account_id}] ${statusIcon} ${res.message || res.status}${qSummary}`, res.status === "READY" ? "success" : "warning");
      break;

    case "projects_updated":
      projectsList = data;
      renderProjectSelector(data);
      break;

    case "project_detail_updated":
      if (currentProjectId && data.id === currentProjectId) {
        currentProjectData = data;
        renderProjectBanner(data);
        renderShotsTable(data.shots || []);
        renderGallery(data.shots || []);
      }
      break;

    case "shot_progress":
      updateShotProgress(data.shot_id, data.progress, data.message, data.account_id);
      break;

    case "shot_completed":
      appendLog(`[Hoàn tất] Cảnh ${data.shot_id} đã render xong.`, "success");
      if (currentProjectId) loadProjectDetail(currentProjectId);
      break;

    case "project_started":
      appendLog(`[Hàng đợi] Đã bắt đầu render dự án ${data.project_id}.`, "info");
      updateRenderControls(true);
      break;

    case "project_paused":
      appendLog(`[Hàng đợi] Đã tạm dừng render.`, "warning");
      updateRenderControls(false);
      clearActiveWorkers();
      break;

    case "project_completed":
      appendLog(`[Hàng đợi] 🎉 Tất cả các cảnh đã hoàn thành xuất sắc!`, "success");
      updateRenderControls(false);
      clearActiveWorkers();
      if (currentProjectId) loadProjectDetail(currentProjectId);
      break;
  }
}

// ----------------- TABS NAVIGATION -----------------
function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(el => {
    el.classList.remove("border-indigo-500", "text-indigo-400");
    el.classList.add("border-transparent", "text-slate-400");
  });

  const activePane = document.getElementById(tabId);
  const activeBtn = document.getElementById(`nav-${tabId}`);
  if (activePane) activePane.classList.add("active");
  if (activeBtn) {
    activeBtn.classList.remove("border-transparent", "text-slate-400");
    activeBtn.classList.add("border-indigo-500", "text-indigo-400");
  }

  lucide.createIcons();
}

// ----------------- ACCOUNTS LOGIC -----------------
async function loadAccounts() {
  try {
    const res = await fetch("/api/accounts");
    const data = await res.json();
    accountsList = data;
    renderAccounts(data);
  } catch (e) {
    console.error("Lỗi tải accounts:", e);
  }
}

function setAccountsBanner(message, tone = "info", autoHideMs = 0) {
  const banner = document.getElementById("accounts-status-banner");
  if (!banner) return;
  if (accountsBannerTimer) {
    clearTimeout(accountsBannerTimer);
    accountsBannerTimer = null;
  }
  if (!message) {
    banner.classList.add("hidden");
    banner.innerHTML = "";
    return;
  }
  let toneCls = "bg-cyan-500/10 border-cyan-500/30 text-cyan-200";
  let iconHtml = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin shrink-0"></i>`;
  if (tone === "success") {
    toneCls = "bg-emerald-500/10 border-emerald-500/30 text-emerald-300";
    iconHtml = `<i data-lucide="check-circle-2" class="w-4 h-4 shrink-0"></i>`;
  } else if (tone === "warning") {
    toneCls = "bg-amber-500/10 border-amber-500/30 text-amber-300";
    iconHtml = `<i data-lucide="alert-triangle" class="w-4 h-4 shrink-0"></i>`;
  }
  banner.className = `rounded-xl px-4 py-3 text-xs font-medium flex items-center justify-between border ${toneCls}`;
  banner.innerHTML = `<div class="flex items-center gap-2">${iconHtml}<span>${escapeHtml(message)}</span></div><button onclick="setAccountsBanner('')" class="text-slate-400 hover:text-white ml-4">✕</button>`;
  banner.classList.remove("hidden");
  lucide.createIcons();
  if (autoHideMs > 0) {
    accountsBannerTimer = setTimeout(() => setAccountsBanner(""), autoHideMs);
  }
}

function startAccountsPolling() {
  if (!accountsPollStartedAt) accountsPollStartedAt = Date.now();
  if (accountsPollTimer) return;
  accountsPollTimer = setInterval(async () => {
    await loadAccounts();
    const stillChecking = accountsList.some(a => a.status === "CHECKING");
    const elapsed = Date.now() - accountsPollStartedAt;
    if (!stillChecking && elapsed >= 4500) {
      clearInterval(accountsPollTimer);
      accountsPollTimer = null;
      accountsPollStartedAt = 0;
      if (wasCheckingAccounts) {
        wasCheckingAccounts = false;
        const readyAccs = accountsList.filter(a => a.status === "READY");
        const totalRem = readyAccs.reduce((s, a) => s + Number(a.usage_info?.weekly_remaining_pct ?? 0), 0);
        setAccountsBanner(
          `Hoàn tất kiểm tra: ${readyAccs.length}/${accountsList.length} tài khoản READY (Tổng hạn mức còn: ${Math.round(totalRem)}%).`,
          readyAccs.length > 0 ? "success" : "warning"
        );
      }
    }
  }, 2000);
}

function renderAccounts(accounts) {
  accountsList = accounts;
  const container = document.getElementById("accounts-grid");
  if (!container) return;

  // Cập nhật thống kê header
  const readyAccounts = accounts.filter(a => a.status === "READY");
  const readyCount = readyAccounts.length;
  const checkingCount = accounts.filter(a => a.status === "CHECKING").length;
  document.getElementById("stat-ready-accounts").innerText = readyCount;

  const statQuotaEl = document.getElementById("stat-total-quota");
  if (statQuotaEl) {
    const hasBonusOn = (u) => Boolean(u && ((u.bonus_tokens_left !== null && u.bonus_tokens_left !== undefined && Number(u.bonus_tokens_left) > 0) || (u.bonus_remaining_pct !== null && u.bonus_remaining_pct !== undefined && Number(u.bonus_remaining_pct) > 0)));
    const readyWithQuota = readyAccounts.filter(a => a.usage_info && (a.usage_info.weekly_remaining_pct !== null || hasBonusOn(a.usage_info)));
    if (readyWithQuota.length > 0) {
      let anyBonus = false;
      const totalEffRem = readyWithQuota.reduce((s, a) => {
        const u = a.usage_info || {};
        const w = Number(u.weekly_remaining_pct ?? 0);
        const b = hasBonusOn(u) ? Number(u.bonus_remaining_pct ?? 100) : 0;
        if (b > 0) anyBonus = true;
        return s + w + b;
      }, 0);
      statQuotaEl.innerText = anyBonus
        ? `${Math.round(totalEffRem)}% (${readyAccounts.length} acc • Bonus)`
        : `${Math.round(totalEffRem)}% (${readyAccounts.length} acc)`;
    } else if (readyCount > 0) {
      statQuotaEl.innerText = `${readyCount} acc (chưa đo %)`;
    } else {
      statQuotaEl.innerText = `0% (0 READY)`;
    }
  }

  const bulkBtn = document.getElementById("btn-bulk-check");
  if (bulkBtn) {
    if (checkingCount > 0) {
      bulkBtn.disabled = true;
      bulkBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Đang kiểm tra (${checkingCount}/${accounts.length})...</span>`;
    } else {
      bulkBtn.disabled = false;
      bulkBtn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i><span>Kiểm tra tất cả</span>`;
    }
  }

  if (checkingCount > 0) {
    wasCheckingAccounts = true;
    setAccountsBanner(`Đang đăng nhập headless & đo hạn mức ${checkingCount}/${accounts.length} tài khoản trên Muse (khoảng 15–40 giây)...`, "info");
    startAccountsPolling();
  } else if (wasCheckingAccounts && !accountsPollTimer) {
    wasCheckingAccounts = false;
    const totalRem = readyAccounts.reduce((s, a) => s + Number(a.usage_info?.weekly_remaining_pct ?? 0), 0);
    setAccountsBanner(
      `Hoàn tất kiểm tra: ${readyAccounts.length}/${accounts.length} tài khoản READY (Tổng hạn mức còn: ${Math.round(totalRem)}%).`,
      readyAccounts.length > 0 ? "success" : "warning"
    );
  }

  if (accounts.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500 bg-slate-900 border border-slate-800 rounded-xl">
        Chưa có tài khoản nào trong pool. Hãy nhấn <strong>+ Thêm thủ công</strong> hoặc <strong>Nhập hàng loạt</strong> để bắt đầu.
      </div>
    `;
    lucide.createIcons();
    return;
  }

  container.innerHTML = accounts.map(acc => {
    let badgeClass = "badge-unchecked";
    let badgeLabel = acc.status;
    const isChecking = acc.status === "CHECKING";
    if (acc.status === "READY") badgeClass = "badge-ready";
    else if (acc.status === "BUSY") badgeClass = "badge-busy";
    else if (acc.status === "COOLDOWN") badgeClass = "badge-cooldown";
    else if (isChecking) {
      badgeClass = "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 animate-pulse";
      badgeLabel = "CHECKING...";
    }
    else if (acc.status === "ERROR" || acc.status === "LOGGED_OUT") badgeClass = "bg-rose-500/20 text-rose-300 border border-rose-500/30";

    const ui = acc.usage_info || null;
    let quotaHtml = "";
    if (ui) {
      const rem = (ui.weekly_remaining_pct !== null && ui.weekly_remaining_pct !== undefined) ? Number(ui.weekly_remaining_pct) : null;
      const used = (ui.weekly_used_pct !== null && ui.weekly_used_pct !== undefined) ? Number(ui.weekly_used_pct) : (rem !== null ? Math.max(0, 100 - rem) : 0);
      const hasBonus = Boolean((ui.bonus_tokens_left !== null && ui.bonus_tokens_left !== undefined && Number(ui.bonus_tokens_left) > 0) || (ui.bonus_remaining_pct !== null && ui.bonus_remaining_pct !== undefined && Number(ui.bonus_remaining_pct) > 0));
      const bonusRem = hasBonus ? Number(ui.bonus_remaining_pct ?? 100) : 0;
      const bonusUsed = hasBonus ? Number(ui.bonus_used_pct ?? Math.max(0, 100 - bonusRem)) : used;
      const showBonusMode = (rem === null || rem === 0) && hasBonus;
      const remTone = showBonusMode
        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
        : (rem === null ? "bg-slate-700 text-slate-300" : (rem > 25 ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : (rem > 0 ? "bg-amber-500/20 text-amber-300 border border-amber-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30")));
      const barTone = showBonusMode ? "bg-cyan-500" : (rem === null ? "bg-slate-500" : (rem > 25 ? "bg-emerald-500" : (rem > 0 ? "bg-amber-500" : "bg-rose-500")));
      const barWidth = showBonusMode ? Math.max(2, bonusUsed) : used;
      const bonusDisplay = ui.bonus_tokens_detail || (ui.bonus_tokens_left !== null && ui.bonus_tokens_left !== undefined ? `${Number(ui.bonus_tokens_left).toLocaleString()} tokens left` : "");
      const badgeStr = showBonusMode ? `Bonus còn ${bonusRem}%` : (rem !== null ? `Còn ${rem}%` : "Không rõ %");
      quotaHtml = `
        <div class="mt-3 p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1.5">
          <div class="flex items-center justify-between text-xs">
            <span class="font-semibold text-slate-200">${escapeHtml(ui.plan || "Muse Account")}</span>
            <span class="px-2 py-0.5 rounded-full text-[11px] font-bold ${remTone}">
              ${badgeStr}
            </span>
          </div>
          <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
            <div class="${barTone} h-2 rounded-full transition-all" style="width: ${Math.min(100, Math.max(0, barWidth))}%"></div>
          </div>
          <div class="flex justify-between items-center gap-2 text-[11px] text-slate-400">
            <span>${showBonusMode ? `Tuần dùng ${used}%` : `Đã dùng ${used}%`}</span>
            ${bonusDisplay ? `<span class="text-cyan-300 font-semibold truncate">Bonus: ${escapeHtml(bonusDisplay)}</span>` : ""}
          </div>
          ${ui.reset_text ? `<div class="text-[11px] text-slate-400">Reset: <span class="text-slate-200">${escapeHtml(ui.reset_text)}</span></div>` : ""}
        </div>
      `;
    } else {
      quotaHtml = `
        <div class="mt-3 p-2.5 rounded-lg bg-slate-950/50 border border-slate-800/80 text-[11px] text-slate-400 flex items-center gap-1.5">
          <i data-lucide="gauge" class="w-3.5 h-3.5 text-slate-500 shrink-0"></i>
          <span>Chưa kiểm tra hạn mức — Nhấn "Kiểm tra & Hạn mức" để cập nhật</span>
        </div>
      `;
    }

    return `
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 card-hover flex flex-col justify-between">
        <div>
          <div class="flex items-start justify-between gap-2 mb-2">
            <div class="min-w-0">
              <h4 class="font-bold text-white text-base truncate" title="${escapeHtml(acc.name)}">${escapeHtml(acc.name)}</h4>
              <p class="text-xs text-slate-400 font-mono mt-0.5 truncate">${acc.id}${acc.email ? ` • ${escapeHtml(acc.email)}` : ""}</p>
            </div>
            <span class="text-[11px] font-semibold px-2.5 py-0.5 rounded-full shrink-0 ${badgeClass}">
              ${badgeLabel}
            </span>
          </div>

          ${quotaHtml}

          <div class="space-y-1 text-xs text-slate-300 mt-3 pt-3 border-t border-slate-800/80">
            <div class="flex justify-between">
              <span class="text-slate-400">Proxy:</span>
              <span class="font-mono text-slate-300 max-w-[180px] truncate" title="${acc.proxy || 'Trực tiếp'}">
                ${acc.proxy || 'Trực tiếp (Máy tính)'}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">Đã render:</span>
              <span class="font-semibold text-indigo-400">${acc.total_rendered || 0} clip</span>
            </div>
            ${acc.error_message ? `
              <div class="mt-2 p-2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px]">
                ${escapeHtml(acc.error_message)}
              </div>
            ` : ''}
          </div>
        </div>

        <div class="flex items-center gap-2 mt-5 pt-3 border-t border-slate-800/80">
          <button onclick="openLoginBrowser('${acc.id}')" class="px-2.5 flex items-center justify-center gap-1 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-lg text-xs font-medium transition" title="Mở Chrome đăng nhập">
            <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
            <span>Đăng nhập</span>
          </button>
          <button id="btn-check-${acc.id}" onclick="checkAccountSession('${acc.id}')" ${isChecking ? "disabled" : ""} class="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-60 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition" title="Kiểm tra trạng thái & hạn mức">
            <i data-lucide="${isChecking ? "loader-2" : "refresh-cw"}" class="w-3.5 h-3.5 ${isChecking ? "animate-spin" : ""}"></i>
            <span>${isChecking ? "Đang đo hạn mức..." : "Kiểm tra & Hạn mức"}</span>
          </button>
          <button onclick="deleteAccount('${acc.id}')" class="p-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg text-xs" title="Xóa tài khoản">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `;
  }).join("");

  lucide.createIcons();
}

async function addAccount() {
  const name = document.getElementById("new-acc-name").value.trim();
  const email = (document.getElementById("new-acc-email")?.value || "").trim();
  const inviteCode = (document.getElementById("new-acc-invite")?.value || "").trim().toUpperCase();
  const rawCookie = (document.getElementById("new-acc-cookie")?.value || "").trim();
  const proxy = document.getElementById("new-acc-proxy").value.trim();
  const autoVerify = document.getElementById("new-acc-autoverify")?.checked ?? true;

  if (!name) {
    alert("Vui lòng nhập tên tài khoản!");
    return;
  }

  try {
    const res = await fetch("/api/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        email: email || null,
        invite_code: inviteCode || null,
        raw_cookie: rawCookie || null,
        proxy: proxy || null,
        auto_verify: autoVerify
      })
    });
    if (res.ok) {
      closeModal("modal-add-account");
      document.getElementById("new-acc-name").value = "";
      if (document.getElementById("new-acc-email")) document.getElementById("new-acc-email").value = "";
      if (document.getElementById("new-acc-invite")) document.getElementById("new-acc-invite").value = "";
      if (document.getElementById("new-acc-cookie")) document.getElementById("new-acc-cookie").value = "";
      document.getElementById("new-acc-proxy").value = "";
      appendLog(`Đã thêm tài khoản [${name}] vào pool.${autoVerify ? " Đang kiểm tra hạn mức..." : ""}`, "info");
      if (autoVerify || inviteCode || email || rawCookie) {
        wasCheckingAccounts = true;
        setAccountsBanner(`Đã thêm [${name}]. Đang kiểm tra trạng thái, nạp mã mời & đo hạn mức...`, "info");
        startAccountsPolling();
      }
      await loadAccounts();
    } else {
      const err = await res.json();
      alert(`Lỗi: ${err.detail || "Không thể thêm tài khoản"}`);
    }
  } catch (e) {
    alert(`Lỗi kết nối: ${e}`);
  }
}

async function submitBulkImport() {
  const text = document.getElementById("bulk-import-text").value.trim();
  const autoVerify = document.getElementById("bulk-auto-verify").checked;

  if (!text) {
    alert("Vui lòng dán danh sách tài khoản theo định dạng: email|invite_code|password|cookie");
    return;
  }

  appendLog("Đang nạp danh sách tài khoản vào Pool...", "info");
  try {
    const res = await fetch("/api/accounts/bulk_import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: text, auto_verify: autoVerify })
    });
    const data = await res.json();
    if (res.ok) {
      closeModal("modal-bulk-import");
      document.getElementById("bulk-import-text").value = "";
      appendLog(`Đã nạp ${data.total_processed} tài khoản (Mới: ${data.imported_count}, Cập nhật: ${data.updated_count}).`, "success");
      if (autoVerify) {
        appendLog("Đang tiến hành tự động xác thực hàng loạt các tài khoản vừa nạp...", "info");
        wasCheckingAccounts = true;
        setAccountsBanner(`Đã nạp ${data.total_processed} tài khoản. Đang đăng nhập headless & đo hạn mức...`, "info");
        startAccountsPolling();
      }
      await loadAccounts();
    } else {
      alert(`Lỗi: ${data.detail || "Không thể nạp danh sách"}`);
    }
  } catch (e) {
    alert(`Lỗi kết nối: ${e}`);
  }
}

async function bulkCheckAccounts() {
  const bulkBtn = document.getElementById("btn-bulk-check");
  if (bulkBtn) {
    bulkBtn.disabled = true;
    bulkBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Đang khởi chạy...</span>`;
    lucide.createIcons();
  }
  wasCheckingAccounts = true;
  setAccountsBanner("Đang khởi chạy kiểm tra xác thực & đo hạn mức toàn bộ Pool tài khoản...", "info");
  appendLog("Đang kích hoạt kiểm tra xác thực & hạn mức toàn bộ Pool tài khoản...", "info");
  try {
    const res = await fetch("/api/accounts/bulk_check", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      appendLog(data.message, "info");
      await loadAccounts();
      startAccountsPolling();
    } else {
      setAccountsBanner(`Lỗi kiểm tra: ${data.detail}`, "warning");
      alert(`Lỗi: ${data.detail}`);
    }
  } catch (e) {
    setAccountsBanner(`Lỗi kết nối: ${e}`, "warning");
    alert(`Lỗi: ${e}`);
  }
}

async function bulkRedeemInviteCode() {
  const raw = prompt("Nhập mã mời Muse (6 ký tự, chỉ áp dụng cho tài khoản tạo chưa quá 48h):", "X4XG1F");
  if (!raw) return;
  const code = raw.trim().toUpperCase();
  if (!code) return;

  const btn = document.getElementById("btn-bulk-redeem");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Đang nạp ${escapeHtml(code)}...</span>`;
    lucide.createIcons();
  }
  wasCheckingAccounts = true;
  setAccountsBanner(`Đang gửi mã mời ${code} lên Muse để kích hoạt Bonus Token...`, "info");
  appendLog(`Đang nạp mã mời [${code}] cho Pool tài khoản...`, "info");
  try {
    const res = await fetch("/api/accounts/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code })
    });
    const data = await res.json();
    if (res.ok) {
      appendLog(data.message, "info");
      await loadAccounts();
      startAccountsPolling();
    } else {
      setAccountsBanner(`Lỗi nhập mã mời: ${data.detail}`, "warning");
      alert(`Lỗi: ${data.detail}`);
    }
  } catch (e) {
    setAccountsBanner(`Lỗi kết nối: ${e}`, "warning");
    alert(`Lỗi: ${e}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="gift" class="w-4 h-4"></i><span>Nhập mã mời (1B)</span>`;
      lucide.createIcons();
    }
  }
}

async function openLoginBrowser(accountId) {
  appendLog(`Đang mở trình duyệt để đăng nhập tài khoản ${accountId}...`, "info");
  try {
    const res = await fetch(`/api/accounts/${accountId}/open_login`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      appendLog(`Cửa sổ trình duyệt đã mở. Hãy đăng nhập vào Muse và đóng cửa sổ khi hoàn tất.`, "success");
    } else {
      alert(`Lỗi: ${data.detail}`);
    }
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

async function checkAccountSession(accountId) {
  appendLog(`Đang kiểm tra trạng thái & hạn mức của tài khoản ${accountId}...`, "info");
  const btn = document.getElementById(`btn-check-${accountId}`);
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Đang kiểm tra...</span>`;
    lucide.createIcons();
  }
  try {
    const res = await fetch(`/api/accounts/${accountId}/check`, { method: "POST" });
    const data = await res.json();
    const qInfo = data.usage_info?.summary ? ` | ${data.usage_info.summary}` : "";
    appendLog(`[${accountId}] Kết quả kiểm tra: ${data.message}${qInfo}`, data.status === "READY" ? "success" : "warning");
    await loadAccounts();
  } catch (e) {
    alert(`Lỗi: ${e}`);
    await loadAccounts();
  }
}

async function deleteAccount(accountId) {
  if (!confirm("Bạn có chắc chắn muốn xóa tài khoản này khỏi pool?")) return;
  try {
    await fetch(`/api/accounts/${accountId}`, { method: "DELETE" });
    appendLog(`Đã xóa tài khoản ${accountId}.`, "info");
    loadAccounts();
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

// ----------------- PROJECTS & SHOTS LOGIC -----------------
async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    const data = await res.json();
    projectsList = data;
    renderProjectSelector(data);

    // Mặc định chọn dự án đầu tiên nếu chưa chọn
    if (!currentProjectId && data.length > 0) {
      selectProject(data[0].id);
    }
  } catch (e) {
    console.error("Lỗi tải projects:", e);
  }
}

function renderProjectSelector(projects) {
  const sel = document.getElementById("project-selector");
  if (!sel) return;

  const currentVal = sel.value;
  sel.innerHTML = '<option value="">-- Chọn dự án --</option>' + projects.map(p => {
    return `<option value="${p.id}" ${p.id === currentProjectId ? "selected" : ""}>${escapeHtml(p.name)} (${p.completed_shots || 0}/${p.total_shots || 0})</option>`;
  }).join("");

  sel.onchange = (e) => {
    if (e.target.value) selectProject(e.target.value);
  };
}

async function selectProject(projectId) {
  currentProjectId = projectId;
  document.getElementById("project-selector").value = projectId;
  await loadProjectDetail(projectId);
}

async function loadProjectDetail(projectId) {
  try {
    const res = await fetch(`/api/projects/${projectId}`);
    if (!res.ok) return;
    const data = await res.json();
    currentProjectData = data;
    renderProjectBanner(data);
    renderShotsTable(data.shots || []);
    renderGallery(data.shots || []);
  } catch (e) {
    console.error("Lỗi load chi tiết dự án:", e);
  }
}

function renderProjectBanner(proj) {
  document.getElementById("banner-proj-name").innerText = proj.name;
  document.getElementById("banner-proj-mode").innerText = proj.mode === "chained_continuity" ? "Chained Continuity" : "Batch Parallel";
  document.getElementById("banner-proj-status").innerText = proj.status;

  const total = proj.total_shots || 0;
  const done = proj.completed_shots || 0;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  document.getElementById("stat-project-progress").innerText = `${pct}%`;
  document.getElementById("banner-progress-text").innerText = `${done}/${total} Cảnh (${pct}%)`;
  document.getElementById("banner-progress-bar").style.width = `${pct}%`;
}

function renderShotsTable(shots) {
  const tbody = document.getElementById("shots-table-body");
  if (!tbody) return;

  if (shots.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="px-4 py-10 text-center text-slate-500">
          Chưa có cảnh nào trong kịch bản. Hãy nhấn <strong>Thêm cảnh mới</strong> hoặc <strong>Import CSV</strong>.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = shots.map((s, idx) => {
    let statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-400">PENDING</span>`;
    if (s.status === "RUNNING") {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-amber-500/20 text-amber-300 animate-pulse border border-amber-500/30">RUNNING ${s.progress || 0}%</span>`;
    } else if (s.status === "COMPLETED") {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">COMPLETED</span>`;
    } else if (s.status === "FAILED") {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[11px] bg-rose-500/20 text-rose-300 border border-rose-500/30">FAILED</span>`;
    }

    const refsPreview = (s.reference_images || []).map((r, i) => {
      const fileName = r.split(/[\\/]/).pop();
      return `<span class="inline-block px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 truncate max-w-[100px]" title="${escapeHtml(fileName)}">Ref ${i+1}</span>`;
    }).join(" ");

    return `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="px-4 py-3 text-slate-400 text-xs font-mono">${s.order || idx + 1}</td>
        <td class="px-4 py-3 font-semibold text-white text-xs">${escapeHtml(s.id)}</td>
        <td class="px-4 py-3 max-w-md">
          <div class="text-xs text-slate-200 line-clamp-2">${escapeHtml(s.prompt)}</div>
          ${s.dialogue ? `<div class="text-[11px] text-indigo-400 italic mt-0.5">"${escapeHtml(s.dialogue)}"</div>` : ''}
          ${s.error ? `<div class="text-[10px] text-rose-400 mt-1">${escapeHtml(s.error)}</div>` : ''}
        </td>
        <td class="px-4 py-3">
          <div class="flex flex-wrap gap-1">
            ${refsPreview || '<span class="text-[11px] text-slate-500">Không có</span>'}
          </div>
        </td>
        <td class="px-4 py-3" id="shot-status-${s.id}">
          ${statusBadge}
        </td>
        <td class="px-4 py-3">
          <div class="flex items-center gap-1.5">
            ${s.output_clip ? `
              <button onclick="previewVideo('${escapeHtml(s.output_clip)}', '${escapeHtml(s.id)}')" class="p-1 rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300" title="Xem video">
                <i data-lucide="play" class="w-3.5 h-3.5"></i>
              </button>
            ` : ''}
            <button onclick="deleteShot('${s.id}')" class="p-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400" title="Xóa cảnh">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  lucide.createIcons();
}

async function createProject() {
  const name = document.getElementById("new-proj-name").value.trim();
  const mode = document.getElementById("new-proj-mode").value;

  if (!name) {
    alert("Vui lòng nhập tên dự án!");
    return;
  }

  try {
    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, mode })
    });
    if (res.ok) {
      const proj = await res.json();
      closeModal("modal-create-project");
      document.getElementById("new-proj-name").value = "";
      appendLog(`Đã tạo dự án mới: [${name}].`, "success");
      await loadProjects();
      selectProject(proj.id);
    }
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

function initRefFilesListener() {
  const fileInput = document.getElementById("shot-ref-files");
  if (!fileInput) return;

  fileInput.addEventListener("change", async (e) => {
    if (!currentProjectId) {
      alert("Vui lòng chọn hoặc tạo dự án trước khi tải ảnh!");
      fileInput.value = "";
      return;
    }

    uploadedRefsForNewShot = [];
    const files = Array.from(e.target.files).slice(0, 9);
    const previewContainer = document.getElementById("selected-refs-preview");
    previewContainer.innerHTML = '<span class="text-xs text-slate-400">Đang upload ảnh tham chiếu...</span>';

    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f);
      try {
        const res = await fetch(`/api/projects/${currentProjectId}/upload_ref`, {
          method: "POST",
          body: fd
        });
        if (res.ok) {
          const data = await res.json();
          uploadedRefsForNewShot.push(data.absolute_path);
        }
      } catch (err) {
        console.error("Lỗi upload ảnh:", err);
      }
    }

    previewContainer.innerHTML = uploadedRefsForNewShot.map((p, i) => {
      const name = p.split(/[\\/]/).pop();
      return `<span class="px-2 py-0.5 bg-slate-800 text-[11px] rounded border border-slate-700 text-slate-300">Slot ${i+1}: ${escapeHtml(name)}</span>`;
    }).join("");
  });
}

async function saveShot() {
  if (!currentProjectId) {
    alert("Vui lòng chọn dự án trước!");
    return;
  }

  const prompt = document.getElementById("new-shot-prompt").value.trim();
  const dialogue = document.getElementById("new-shot-dialogue").value.trim();
  const shotId = document.getElementById("new-shot-id").value.trim() || null;

  if (!prompt) {
    alert("Vui lòng nhập Prompt cho cảnh!");
    return;
  }

  try {
    const res = await fetch(`/api/projects/${currentProjectId}/shots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        dialogue: dialogue || null,
        reference_images: uploadedRefsForNewShot,
        shot_id: shotId
      })
    });

    if (res.ok) {
      closeModal("modal-add-shot");
      document.getElementById("new-shot-prompt").value = "";
      document.getElementById("new-shot-dialogue").value = "";
      document.getElementById("new-shot-id").value = "";
      document.getElementById("shot-ref-files").value = "";
      document.getElementById("selected-refs-preview").innerHTML = "";
      uploadedRefsForNewShot = [];
      appendLog("Đã thêm cảnh mới vào kịch bản.", "success");
      loadProjectDetail(currentProjectId);
    }
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

async function deleteShot(shotId) {
  if (!confirm("Bạn có chắc chắn muốn xóa cảnh này?")) return;
  try {
    await fetch(`/api/projects/${currentProjectId}/shots/${shotId}`, { method: "DELETE" });
    appendLog(`Đã xóa cảnh ${shotId}.`, "info");
    loadProjectDetail(currentProjectId);
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

async function uploadCSV(event) {
  if (!currentProjectId) {
    alert("Vui lòng chọn dự án trước khi import CSV!");
    return;
  }
  const file = event.target.files[0];
  if (!file) return;

  const fd = new FormData();
  fd.append("file", file);

  appendLog(`Đang import danh sách cảnh từ file CSV [${file.name}]...`, "info");
  try {
    const res = await fetch(`/api/projects/${currentProjectId}/import_csv`, {
      method: "POST",
      body: fd
    });
    const data = await res.json();
    if (res.ok) {
      appendLog(`Đã nạp thành công ${data.imported_count} cảnh vào kịch bản!`, "success");
      loadProjectDetail(currentProjectId);
    } else {
      alert("Lỗi khi import CSV!");
    }
  } catch (e) {
    alert(`Lỗi: ${e}`);
  } finally {
    event.target.value = "";
  }
}

// ----------------- RENDER DISPATCHER CONTROLS -----------------
async function startRender() {
  if (!currentProjectId) {
    alert("Vui lòng chọn dự án trước khi render!");
    return;
  }

  const concurrency = parseInt(document.getElementById("concurrency-input").value) || 3;
  const simulate = document.getElementById("simulate-toggle").checked;

  try {
    const res = await fetch("/api/render/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: currentProjectId,
        concurrency,
        simulate
      })
    });
    const data = await res.json();
    if (res.ok) {
      updateRenderControls(true);
      appendLog(data.message, "success");
    } else {
      alert(`Không thể bắt đầu render: ${data.detail}`);
    }
  } catch (e) {
    alert(`Lỗi kết nối: ${e}`);
  }
}

async function stopRender() {
  try {
    const res = await fetch("/api/render/stop", { method: "POST" });
    const data = await res.json();
    updateRenderControls(false);
    appendLog(data.message, "warning");
    clearActiveWorkers();
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

function updateRenderControls(isRendering) {
  const startBtn = document.getElementById("btn-start-render");
  const stopBtn = document.getElementById("btn-stop-render");
  if (isRendering) {
    startBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
  } else {
    startBtn.classList.remove("hidden");
    stopBtn.classList.add("hidden");
  }
}

function updateShotProgress(shotId, progress, message, accountId) {
  // Cập nhật badge trong bảng
  const statusEl = document.getElementById(`shot-status-${shotId}`);
  if (statusEl) {
    statusEl.innerHTML = `<span class="px-2 py-0.5 rounded text-[11px] bg-amber-500/20 text-amber-300 animate-pulse border border-amber-500/30">RUNNING ${progress}%</span>`;
  }

  // Cập nhật Worker Grid
  updateActiveWorkerCard(shotId, progress, message, accountId);
}

function updateActiveWorkerCard(shotId, progress, message, accountId) {
  const grid = document.getElementById("active-workers-grid");
  if (!grid) return;

  // Xóa empty state nếu có
  if (grid.querySelector(".col-span-full")) {
    grid.innerHTML = "";
  }

  let card = document.getElementById(`worker-card-${shotId}`);
  if (!card) {
    card = document.createElement("div");
    card.id = `worker-card-${shotId}`;
    card.className = "bg-slate-900 border border-indigo-500/30 rounded-xl p-4 shadow-sm";
    grid.appendChild(card);
  }

  card.innerHTML = `
    <div class="flex justify-between items-start mb-2">
      <div>
        <h4 class="font-bold text-white text-sm flex items-center gap-2">
          <span>${escapeHtml(shotId)}</span>
          <span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
        </h4>
        <p class="text-[11px] text-slate-400 font-mono">Tài khoản: ${escapeHtml(accountId || 'Auto')}</p>
      </div>
      <span class="text-xs font-bold text-indigo-400">${progress}%</span>
    </div>
    <div class="w-full bg-slate-800 rounded-full h-2 mb-2 overflow-hidden">
      <div class="bg-gradient-to-r from-indigo-500 to-emerald-400 h-2 rounded-full transition-all duration-300" style="width: ${progress}%"></div>
    </div>
    <p class="text-[11px] text-slate-400 truncate">${escapeHtml(message || 'Đang xử lý...')}</p>
  `;

  // Cập nhật tổng số worker đang chạy trên badge header
  const activeCount = grid.querySelectorAll("[id^='worker-card-']").length;
  document.getElementById("stat-active-workers").innerText = activeCount;
}

function clearActiveWorkers() {
  const grid = document.getElementById("active-workers-grid");
  if (grid) {
    grid.innerHTML = `
      <div class="col-span-full py-8 text-center text-slate-500 bg-slate-900/40 border border-slate-800/80 rounded-xl">
        Hiện không có luồng nào đang render. Nhấn "Bắt đầu Render" để chạy.
      </div>
    `;
  }
  document.getElementById("stat-active-workers").innerText = 0;
}

// ----------------- GALLERY & EXPORT -----------------
function renderGallery(shots) {
  const grid = document.getElementById("gallery-grid");
  if (!grid) return;

  const completed = shots.filter(s => s.status === "COMPLETED" && s.output_clip);
  if (completed.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-12 text-center text-slate-500 bg-slate-900 border border-slate-800 rounded-xl">
        Chưa có video nào hoàn tất. Khi render xong, video sẽ xuất hiện tại đây để xem trước và ghép nối.
      </div>
    `;
    return;
  }

  grid.innerHTML = completed.map(s => {
    const clipUrl = `/media/${currentProjectId}/clips/${s.id}.mp4`;
    return `
      <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden card-hover">
        <div class="relative aspect-video bg-black flex items-center justify-center cursor-pointer group" onclick="previewVideo('${clipUrl}', '${s.id}')">
          <video src="${clipUrl}" class="w-full h-full object-cover" muted preload="metadata"></video>
          <div class="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
            <div class="w-10 h-10 rounded-full bg-indigo-600/90 text-white flex items-center justify-center shadow-lg">
              <i data-lucide="play" class="w-5 h-5 ml-0.5"></i>
            </div>
          </div>
        </div>
        <div class="p-3">
          <div class="flex justify-between items-center">
            <h5 class="font-bold text-white text-xs">${escapeHtml(s.id)}</h5>
            <a href="${clipUrl}" download class="text-slate-400 hover:text-indigo-400" title="Tải clip">
              <i data-lucide="download" class="w-3.5 h-3.5"></i>
            </a>
          </div>
          <p class="text-[11px] text-slate-400 truncate mt-1">${escapeHtml(s.prompt)}</p>
        </div>
      </div>
    `;
  }).join("");

  lucide.createIcons();
}

function previewVideo(videoUrl, title) {
  const modal = document.getElementById("modal-video-player");
  const player = document.getElementById("video-modal-player");
  const titleEl = document.getElementById("video-modal-title");
  const downloadEl = document.getElementById("video-modal-download");

  titleEl.innerText = `Xem trước: ${title}`;
  player.src = videoUrl;
  downloadEl.href = videoUrl;
  downloadEl.download = `${title}.mp4`;

  modal.classList.remove("hidden");
  player.play().catch(() => {});
}

function closeVideoModal() {
  const modal = document.getElementById("modal-video-player");
  const player = document.getElementById("video-modal-player");
  player.pause();
  player.src = "";
  modal.classList.add("hidden");
}

async function mergeAllVideos() {
  if (!currentProjectId) {
    alert("Vui lòng chọn dự án!");
    return;
  }

  appendLog("Đang kích hoạt FFmpeg để ghép nối toàn bộ video hoàn chỉnh...", "info");
  try {
    const res = await fetch(`/api/projects/${currentProjectId}/merge`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      appendLog(`Ghép nối thành công ${data.clips_count} clip! Tổng thời lượng: ${Math.round(data.total_duration)}s.`, "success");
      previewVideo(data.output_url, "Video Hoàn Chỉnh");
    } else {
      alert(`Lỗi khi ghép video: ${data.detail}`);
    }
  } catch (e) {
    alert(`Lỗi: ${e}`);
  }
}

function downloadProjectZip() {
  if (!currentProjectId) {
    alert("Vui lòng chọn dự án!");
    return;
  }
  window.open(`/api/projects/${currentProjectId}/download_zip`, "_blank");
}

// ----------------- UTILITIES -----------------
function appendLog(message, type = "info") {
  const logBox = document.getElementById("realtime-logs");
  if (!logBox) return;

  const timeStr = new Date().toLocaleTimeString();
  let colorClass = "text-slate-300";
  if (type === "success") colorClass = "text-emerald-400";
  else if (type === "warning") colorClass = "text-amber-400";
  else if (type === "error") colorClass = "text-rose-400";

  const line = document.createElement("div");
  line.className = colorClass;
  line.innerHTML = `<span class="text-slate-500">[${timeStr}]</span> ${escapeHtml(message)}`;
  logBox.appendChild(line);
  logBox.scrollTop = logBox.scrollHeight;
}

function clearLogs() {
  const logBox = document.getElementById("realtime-logs");
  if (logBox) logBox.innerHTML = "";
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove("hidden");
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("hidden");
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
