// ── State ──────────────────────────────────────────────────────────────
let currentPage   = 'dashboard';
let chatMode      = 'single';
let chatSending   = false;
let allEmployees  = [];
let allEscalations = [];
let activeDeptFilter = 'all';
let activeEscFilter  = 'all';

// ── Thread ID (localStorage persistence) ─────────────────────────────
let currentThreadId = localStorage.getItem('ob_thread_id') || generateId();
localStorage.setItem('ob_thread_id', currentThreadId);

function generateId() {
  return 'thread-' + Math.random().toString(36).slice(2, 10);
}

function newChatSession() {
  currentThreadId = generateId();
  localStorage.setItem('ob_thread_id', currentThreadId);
  updateThreadLabel();
  // Clear chat messages, restore welcome screen
  const msgs = document.getElementById('chat-messages');
  msgs.innerHTML = `
    <div class="chat-welcome">
      <i class="fas fa-robot"></i>
      <h3>Onboarding Agent</h3>
      <p>Ask me about employee onboarding status, compliance, policies, or request actions like sending reminders and escalations.</p>
      <div class="quick-prompts">
        <button class="quick-prompt" onclick="sendQuickPrompt(this)">What is the status of EMP-003?</button>
        <button class="quick-prompt" onclick="sendQuickPrompt(this)">Check compliance for EMP-004</button>
        <button class="quick-prompt" onclick="sendQuickPrompt(this)">Generate onboarding report for EMP-007</button>
        <button class="quick-prompt" onclick="sendQuickPrompt(this)">What are the SOX compliance requirements for Finance?</button>
        <button class="quick-prompt" onclick="sendQuickPrompt(this)">Send a reminder to EMP-003 about overdue tasks</button>
        <button class="quick-prompt" onclick="sendQuickPrompt(this)">What is the health insurance enrollment deadline?</button>
      </div>
    </div>`;
  toast('New session started', 'info');
}

function updateThreadLabel() {
  const el = document.getElementById('thread-id-label');
  if (el) el.textContent = 'Session: ' + currentThreadId.slice(-8);
}

// ── Toast Notifications ───────────────────────────────────────────────
function toast(message, type = 'info') {
  const iconMap = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<i class="fas ${iconMap[type]} ${type}"></i><span>${escapeHtml(message)}</span>`;
  document.getElementById('toast-container').appendChild(t);
  setTimeout(() => {
    t.classList.add('hiding');
    setTimeout(() => t.remove(), 280);
  }, 3000);
}

// ── Avatar Color (hash-based, consistent) ─────────────────────────────
const AVATAR_COLORS = ['#6c5ce7','#00b894','#0984e3','#e17055','#fd79a8','#fdcb6e','#a29bfe','#55efc4'];
function avatarColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

// ── Navigation ────────────────────────────────────────────────────────
document.querySelectorAll('.nav-links a').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    navigateTo(link.dataset.page);
  });
});

function navigateTo(page) {
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  const pageEl = document.getElementById('page-' + page);
  if (pageEl) pageEl.classList.add('active');
  const navLink = document.querySelector(`.nav-links a[data-page="${page}"]`);
  if (navLink) navLink.classList.add('active');

  if (page === 'dashboard')  loadDashboard();
  else if (page === 'employees')  loadEmployees();
  else if (page === 'escalations') loadEscalations();
  else if (page === 'emails') loadEmails();
  else if (page === 'chat')   updateThreadLabel();
}

// ── API Helper ────────────────────────────────────────────────────────
async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw Object.assign(new Error(err.error || res.statusText), { status: res.status, detail: err.detail });
  }
  return res.json();
}

// ── Dashboard ─────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [stats, emps, escs] = await Promise.all([
      api('/api/stats'),
      api('/api/employees'),
      api('/api/escalations'),
    ]);

    document.getElementById('stats-grid').innerHTML = [
      statCard('fa-users',           stats.totalEmployees,                        'Employees',   '--accent',  '--purple-dim'),
      statCard('fa-list-check',      stats.completedTasks+'/'+stats.totalTasks,   'Tasks Done',  '--green',   '--green-dim'),
      statCard('fa-clock',           stats.overdueTasks,                          'Overdue',     '--red',     '--red-dim',  stats.overdueTasks > 0),
      statCard('fa-shield-halved',   stats.compliantEmployees+'/'+stats.totalEmployees, 'Compliant', '--blue', '--blue-dim'),
      statCard('fa-percent',         stats.completionRate+'%',                    'Completion',  '--orange',  '--orange-dim'),
      statCard('fa-triangle-exclamation', stats.openEscalations,                 'Escalations', '--red',     '--red-dim',  stats.openEscalations > 0),
      statCard('fa-envelope',        stats.emailsSent,                            'Emails Sent', '--purple',  '--purple-dim'),
    ].join('');

    // Employee progress
    document.getElementById('employee-progress-list').innerHTML = emps.map(emp => {
      const pct   = emp.taskProgress.percentage;
      const color = pct === 100 ? 'var(--green)' : pct > 50 ? 'var(--orange)' : 'var(--red)';
      const color_hex = avatarColor(emp.employeeId);
      return `
        <div class="progress-item" onclick="showEmployee('${emp.employeeId}')">
          <div class="avatar" style="background:${color_hex}">${emp.firstName[0]}${emp.lastName[0]}</div>
          <div class="info">
            <div class="name">${emp.firstName} ${emp.lastName}
              <span style="color:var(--text-dim);font-weight:400;font-size:12px"> ${emp.employeeId}</span>
            </div>
            <div class="dept">${emp.department} &middot; ${emp.role}</div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width:${pct}%;background:${color}"></div>
            </div>
          </div>
          <div class="progress-pct" style="color:${color}">${pct}%</div>
        </div>`;
    }).join('');

    // Recent escalations
    const recent = escs.slice(0, 5);
    document.getElementById('recent-escalations-list').innerHTML = recent.length
      ? recent.map(e => escalationItem(e)).join('')
      : '<div class="empty-state"><i class="fas fa-check-circle" style="color:var(--green)"></i><p>No escalations — all clear!</p></div>';

  } catch (e) {
    toast('Failed to load dashboard: ' + e.message, 'error');
  }
}

function statCard(icon, value, label, colorVar, bgVar, warn = false) {
  return `
    <div class="stat-card ${warn ? 'warn' : ''}">
      <div class="stat-icon" style="background:var(${bgVar});color:var(${colorVar})">
        <i class="fas ${icon}"></i>
      </div>
      <div class="stat-value">${value}</div>
      <div class="stat-label">${label}</div>
    </div>`;
}

function escalationItem(e) {
  const icon = e.urgency === 'critical' ? 'fa-fire' : e.urgency === 'high' ? 'fa-bolt' : 'fa-flag';
  return `
    <div class="esc-item">
      <div class="esc-icon ${e.urgency}"><i class="fas ${icon}"></i></div>
      <div class="esc-info">
        <div class="esc-title">${escapeHtml(e.employeeName)} (${e.employeeCode}) &mdash; ${escapeHtml(e.taskName)}</div>
        <div class="esc-reason">${escapeHtml(truncate(e.reason, 100))}</div>
        <div class="esc-time"><i class="fas fa-clock"></i> ${formatDate(e.createdAt)} &middot; <span class="badge ${e.urgency}">${e.urgency}</span></div>
      </div>
    </div>`;
}

// ── Employees ─────────────────────────────────────────────────────────
async function loadEmployees() {
  document.getElementById('employees-grid').innerHTML = '<div class="loading"><i class="fas fa-spinner"></i> Loading...</div>';
  try {
    allEmployees = await api('/api/employees');
    buildDeptChips();
    renderEmployees(allEmployees);
  } catch (e) {
    toast('Failed to load employees: ' + e.message, 'error');
  }
}

function buildDeptChips() {
  const depts = ['all', ...new Set(allEmployees.map(e => e.department))].sort();
  const container = document.getElementById('dept-filter-chips');
  container.innerHTML = depts.map(d => `
    <button class="filter-chip ${d === activeDeptFilter ? 'active' : ''}"
            data-dept="${d}" onclick="setDeptFilter('${d}')">
      ${d === 'all' ? 'All Departments' : d}
    </button>`).join('');
}

function setDeptFilter(dept) {
  activeDeptFilter = dept;
  document.querySelectorAll('.filter-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.dept === dept);
  });
  applyEmployeeFilters();
}

function applyEmployeeFilters() {
  const q = (document.getElementById('employee-search')?.value || '').toLowerCase();
  let filtered = allEmployees;
  if (activeDeptFilter !== 'all') {
    filtered = filtered.filter(e => e.department === activeDeptFilter);
  }
  if (q) {
    filtered = filtered.filter(e =>
      `${e.firstName} ${e.lastName} ${e.employeeId} ${e.department} ${e.role}`.toLowerCase().includes(q)
    );
  }
  renderEmployees(filtered);
}

document.getElementById('employee-search').addEventListener('input', applyEmployeeFilters);

function renderEmployees(emps) {
  if (!emps.length) {
    document.getElementById('employees-grid').innerHTML =
      '<div class="empty-state"><i class="fas fa-search"></i><p>No employees match your search.</p></div>';
    return;
  }
  document.getElementById('employees-grid').innerHTML = emps.map(emp => {
    const p       = emp.taskProgress;
    const pending = Math.max(0, p.total - p.completed - p.overdue);
    const color   = avatarColor(emp.employeeId);
    const pctColor = p.percentage === 100 ? 'var(--green)' : p.percentage > 50 ? 'var(--orange)' : 'var(--red)';
    return `
      <div class="emp-card ${p.overdue > 0 ? 'has-overdue' : ''}" onclick="showEmployee('${emp.employeeId}')">
        <div class="emp-card-header">
          <div class="avatar" style="background:${color}">${emp.firstName[0]}${emp.lastName[0]}</div>
          <div class="info">
            <h4>${escapeHtml(emp.firstName + ' ' + emp.lastName)}</h4>
            <div class="meta">${emp.employeeId} &middot; ${emp.department} &middot; ${emp.role}</div>
          </div>
        </div>
        <div class="emp-card-stats">
          <div class="emp-stat done"><span class="num">${p.completed}</span>Done</div>
          <div class="emp-stat overdue"><span class="num">${p.overdue}</span>Overdue</div>
          <div class="emp-stat pending"><span class="num">${pending}</span>Pending</div>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width:${p.percentage}%;background:${pctColor}"></div>
        </div>
      </div>`;
  }).join('');
}

// ── Employee Detail ───────────────────────────────────────────────────
async function showEmployee(empId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-employee-detail').classList.add('active');
  document.getElementById('detail-content').innerHTML = '<div class="loading"><i class="fas fa-spinner"></i> Loading...</div>';

  try {
    const emp = await api('/api/employees/' + empId);

    document.getElementById('detail-name').textContent     = `${emp.firstName} ${emp.lastName}`;
    document.getElementById('detail-subtitle').textContent = `${emp.employeeId} — ${emp.role} — ${emp.department}`;

    const compBadge = emp.compliance.status === 'COMPLIANT'
      ? '<span class="badge compliant">Compliant</span>'
      : '<span class="badge non-compliant">Non-Compliant</span>';

    const totalTasks  = emp.tasks.length;
    const doneTasks   = emp.tasks.filter(t => t.status === 'complete').length;
    const overdueTasks = emp.tasks.filter(t => t.status === 'overdue').length;
    const pct         = totalTasks ? Math.round(doneTasks / totalTasks * 100) : 0;
    const ringColor   = pct === 100 ? 'var(--green)' : pct > 50 ? 'var(--orange)' : 'var(--red)';
    const ringBg      = `conic-gradient(${ringColor} ${pct}%, var(--bg-input) ${pct}%)`;

    // Category breakdown
    const catHtml = Object.entries(emp.categoryBreakdown).map(([cat, v]) => {
      const catPct  = v.total ? Math.round(v.completed / v.total * 100) : 0;
      const catColor = catPct === 100 ? 'var(--green)' : catPct > 50 ? 'var(--orange)' : 'var(--red)';
      return `
        <div style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
            <span style="text-transform:capitalize">${cat.replace(/_/g,' ')}</span>
            <span style="color:${catColor}">${v.completed}/${v.total}</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width:${catPct}%;background:${catColor}"></div>
          </div>
        </div>`;
    }).join('');

    // Tasks
    const taskRows = emp.tasks.map(t => `
      <tr>
        <td>${escapeHtml(t.taskName)}</td>
        <td style="text-transform:capitalize">${t.category.replace(/_/g,' ')}</td>
        <td><span class="badge ${t.status}">${t.status.replace('_',' ')}</span></td>
        <td>${t.dueDate || '—'}</td>
        <td>${t.completedDate || '—'}</td>
        <td style="text-align:center">${t.reminderCount}</td>
      </tr>`).join('');

    // Escalations
    const escRows = emp.escalations.length ? emp.escalations.map(e => `
      <tr>
        <td><span class="badge ${e.urgency}">${e.urgency}</span></td>
        <td>${escapeHtml(truncate(e.reason, 80))}</td>
        <td>${formatDate(e.createdAt)}</td>
        <td>${e.resolvedAt ? formatDate(e.resolvedAt) : '<span style="color:var(--orange)">Open</span>'}</td>
      </tr>`).join('')
      : '<tr><td colspan="4" style="color:var(--text-muted);text-align:center;padding:20px">No escalations</td></tr>';

    // Emails
    const emailRows = emp.emails.length ? emp.emails.map(e => `
      <tr>
        <td><span class="badge ${e.emailType}">${e.emailType}</span></td>
        <td>${escapeHtml(e.subject)}</td>
        <td>${formatDate(e.sentAt)}</td>
      </tr>`).join('')
      : '<tr><td colspan="3" style="color:var(--text-muted);text-align:center;padding:20px">No emails sent</td></tr>';

    document.getElementById('detail-content').innerHTML = `
      <div class="detail-grid">
        <div class="card">
          <h3><i class="fas fa-user"></i> Employee Info</h3>
          <div class="info-grid">
            <div class="info-item"><label>Email</label><span>${escapeHtml(emp.email)}</span></div>
            <div class="info-item"><label>Manager</label><span>${escapeHtml(emp.manager || '—')}</span></div>
            <div class="info-item"><label>Start Date</label><span>${emp.startDate || '—'}</span></div>
            <div class="info-item"><label>Location</label><span>${escapeHtml(emp.location || '—')}</span></div>
            <div class="info-item"><label>Status</label><span style="text-transform:capitalize">${emp.status}</span></div>
            <div class="info-item"><label>Compliance</label><span>${compBadge}</span></div>
          </div>
        </div>
        <div class="card">
          <h3><i class="fas fa-chart-bar"></i> Progress Overview</h3>
          <div class="ring-wrap">
            <div class="ring" style="background:${ringBg}">
              <span class="ring-label" style="color:${ringColor}">${pct}%</span>
            </div>
            <div class="ring-sub">${doneTasks}/${totalTasks} tasks &middot; ${overdueTasks} overdue</div>
          </div>
          ${catHtml}
        </div>
      </div>

      <div class="card" style="margin-bottom:20px">
        <h3><i class="fas fa-tasks"></i> Tasks (${totalTasks})</h3>
        <div class="table-container">
          <table>
            <thead><tr><th>Task</th><th>Category</th><th>Status</th><th>Due</th><th>Completed</th><th>Reminders</th></tr></thead>
            <tbody>${taskRows}</tbody>
          </table>
        </div>
      </div>

      <div class="dashboard-row">
        <div class="card">
          <h3><i class="fas fa-triangle-exclamation"></i> Escalations (${emp.escalations.length})</h3>
          <div class="table-container">
            <table>
              <thead><tr><th>Urgency</th><th>Reason</th><th>Created</th><th>Resolved</th></tr></thead>
              <tbody>${escRows}</tbody>
            </table>
          </div>
        </div>
        <div class="card">
          <h3><i class="fas fa-envelope"></i> Emails (${emp.emails.length})</h3>
          <div class="table-container">
            <table>
              <thead><tr><th>Type</th><th>Subject</th><th>Sent</th></tr></thead>
              <tbody>${emailRows}</tbody>
            </table>
          </div>
        </div>
      </div>`;

  } catch (e) {
    toast('Failed to load employee: ' + e.message, 'error');
    document.getElementById('detail-content').innerHTML =
      '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Could not load employee data.</p></div>';
  }
}

// ── Escalations Page ──────────────────────────────────────────────────
async function loadEscalations() {
  document.getElementById('escalations-list').innerHTML = '<div class="loading"><i class="fas fa-spinner"></i> Loading...</div>';
  try {
    allEscalations = await api('/api/escalations');
    // Wire up filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeEscFilter = tab.dataset.filter;
        renderEscalations();
      });
    });
    renderEscalations();
  } catch (e) {
    toast('Failed to load escalations: ' + e.message, 'error');
  }
}

function renderEscalations() {
  let filtered = allEscalations;
  if (activeEscFilter === 'open')     filtered = filtered.filter(e => !e.resolvedAt);
  else if (activeEscFilter === 'resolved') filtered = filtered.filter(e =>  e.resolvedAt);
  else if (['critical','high','medium','low'].includes(activeEscFilter)) {
    filtered = filtered.filter(e => e.urgency === activeEscFilter);
  }

  if (!filtered.length) {
    document.getElementById('escalations-list').innerHTML =
      '<div class="empty-state"><i class="fas fa-check-circle" style="color:var(--green)"></i><p>No escalations match this filter.</p></div>';
    return;
  }

  document.getElementById('escalations-list').innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Employee</th><th>Task</th><th>Urgency</th>
          <th>Reason</th><th>Created</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${filtered.map(e => `
          <tr>
            <td>
              <strong>${escapeHtml(e.employeeName)}</strong><br>
              <span style="color:var(--text-muted);font-size:11px">${e.employeeCode}</span>
            </td>
            <td>${escapeHtml(e.taskName)}</td>
            <td><span class="badge ${e.urgency}">${e.urgency}</span></td>
            <td>${escapeHtml(truncate(e.reason, 60))}</td>
            <td>${formatDate(e.createdAt)}</td>
            <td>${e.resolvedAt
                  ? '<span class="badge complete">Resolved</span>'
                  : '<span class="badge overdue">Open</span>'}
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Emails Page ───────────────────────────────────────────────────────
async function loadEmails() {
  document.getElementById('emails-list').innerHTML = '<div class="loading"><i class="fas fa-spinner"></i> Loading...</div>';
  try {
    const emails = await api('/api/emails');
    if (!emails.length) {
      document.getElementById('emails-list').innerHTML =
        '<div class="empty-state"><i class="fas fa-envelope-open"></i><p>No emails have been sent yet.</p></div>';
      return;
    }
    document.getElementById('emails-list').innerHTML = `
      <table>
        <thead><tr><th>Employee</th><th>Type</th><th>Subject</th><th>Recipient</th><th>Sent</th></tr></thead>
        <tbody>
          ${emails.map(e => `
            <tr>
              <td>
                <strong>${escapeHtml(e.employeeName)}</strong><br>
                <span style="color:var(--text-muted);font-size:11px">${e.employeeCode}</span>
              </td>
              <td><span class="badge ${e.emailType}">${e.emailType}</span></td>
              <td>${escapeHtml(e.subject)}</td>
              <td style="color:var(--text-muted)">${escapeHtml(e.recipient)}</td>
              <td>${formatDate(e.sentAt)}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch (e) {
    toast('Failed to load emails: ' + e.message, 'error');
  }
}

// ── Chat ──────────────────────────────────────────────────────────────
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    chatMode = btn.dataset.mode;
  });
});

const chatInput = document.getElementById('chat-input');
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

function sendQuickPrompt(btn) {
  chatInput.value = btn.textContent.trim();
  sendMessage();
}

// ── DOM helpers for chat ──────────────────────────────────────────────
function appendUserMsg(text) {
  const msgsEl = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg user';
  div.innerHTML = `
    <div class="msg-avatar"><i class="fas fa-user"></i></div>
    <div class="msg-bubble">${escapeHtml(text)}</div>`;
  msgsEl.appendChild(div);
  msgsEl.scrollTop = msgsEl.scrollHeight;
}

function appendTypingIndicator() {
  const msgsEl = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg assistant';
  div.id = 'typing-msg';
  div.innerHTML = `
    <div class="msg-avatar"><i class="fas fa-robot"></i></div>
    <div class="msg-bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
  msgsEl.appendChild(div);
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return div;
}

function buildAssistantBubble() {
  const msgsEl = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg assistant';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.innerHTML = '<i class="fas fa-robot"></i>';
  div.appendChild(avatar);
  div.appendChild(bubble);
  msgsEl.appendChild(div);
  return { div, bubble };
}

function addToolCallToMessage(bubble, toolName, args) {
  let tcContainer = bubble.querySelector('.tool-calls');
  if (!tcContainer) {
    tcContainer = document.createElement('div');
    tcContainer.className = 'tool-calls';
    tcContainer.innerHTML = '<small style="color:var(--text-dim)">Tool calls:</small>';
    bubble.appendChild(tcContainer);
  }
  const item = document.createElement('div');
  item.className = 'tool-call-item';
  item.dataset.tool = toolName;
  item.innerHTML = `
    <div class="tool-call-header" onclick="this.parentElement.classList.toggle('open')">
      <i class="fas fa-wrench" style="font-size:10px"></i>
      <span>${escapeHtml(toolName)}</span>
      <i class="fas fa-chevron-down tc-chevron"></i>
    </div>
    <div class="tool-call-body">
      <strong>Args:</strong><br>${escapeHtml(JSON.stringify(args, null, 2))}
    </div>`;
  tcContainer.appendChild(item);
  return item;
}

function updateToolResult(item, result) {
  const body = item.querySelector('.tool-call-body');
  if (body) {
    const resultEl = document.createElement('div');
    resultEl.className = 'tool-result-section';
    resultEl.innerHTML = `<strong>Result:</strong><br>${escapeHtml(truncate(result, 300))}`;
    body.appendChild(resultEl);
  }
}

// ── SSE Streaming Send ────────────────────────────────────────────────
async function sendMessage() {
  const msg = chatInput.value.trim();
  if (!msg || chatSending) return;

  chatSending = true;
  const sendBtn = document.getElementById('chat-send');
  sendBtn.disabled = true;
  chatInput.value = '';
  chatInput.style.height = 'auto';

  // Remove welcome screen on first message
  const welcome = document.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  appendUserMsg(msg);
  appendTypingIndicator();

  const msgsEl = document.getElementById('chat-messages');

  try {
    const response = await fetch('/api/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, mode: chatMode, thread_id: currentThreadId }),
    });

    if (!response.ok) {
      throw new Error(`Server error ${response.status}`);
    }

    // Remove typing indicator and build the real bubble
    document.getElementById('typing-msg')?.remove();
    const { div: msgDiv, bubble } = buildAssistantBubble();

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer    = '';
    let responseText = '';
    const toolItems  = {};  // tool name -> item element

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();  // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let data;
        try { data = JSON.parse(line.slice(6)); } catch { continue; }

        if (data.type === 'tool_call') {
          const item = addToolCallToMessage(bubble, data.tool, data.args);
          toolItems[data.tool] = item;

        } else if (data.type === 'tool_result') {
          const item = toolItems[data.tool];
          if (item) updateToolResult(item, data.content);

        } else if (data.type === 'agent_response') {
          responseText = data.content;
          // Find or create text node before tool-calls div
          let textNode = bubble.querySelector('.msg-text');
          if (!textNode) {
            textNode = document.createElement('div');
            textNode.className = 'msg-text';
            bubble.insertBefore(textNode, bubble.querySelector('.tool-calls'));
          }
          textNode.innerHTML = formatMarkdown(responseText);

        } else if (data.type === 'done') {
          break;

        } else if (data.type === 'error') {
          bubble.innerHTML = `<i class="fas fa-exclamation-circle" style="color:var(--red)"></i> ${escapeHtml(data.content)}`;
        }
      }

      msgsEl.scrollTop = msgsEl.scrollHeight;
    }

    // If no agent_response came through, show a fallback
    if (!responseText && !bubble.querySelector('.msg-text')) {
      bubble.innerHTML = '<em style="color:var(--text-muted)">No response returned.</em>';
    }

  } catch (err) {
    document.getElementById('typing-msg')?.remove();

    let errMsg = 'Connection error. Is the server running?';
    if (err.message.includes('429')) errMsg = 'Rate limit exceeded. Please wait a minute.';
    else if (err.message) errMsg = err.message;

    const { bubble } = buildAssistantBubble();
    bubble.style.borderColor = 'var(--red)';
    bubble.innerHTML = `<i class="fas fa-exclamation-circle" style="color:var(--red)"></i> ${escapeHtml(errMsg)}`;
    toast(errMsg, 'error');
  }

  msgsEl.scrollTop = msgsEl.scrollHeight;
  chatSending = false;
  sendBtn.disabled = false;
  chatInput.focus();
}

// ── Helpers ────────────────────────────────────────────────────────────
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function formatMarkdown(text) {
  if (!text) return '<em style="color:var(--text-muted)">No response</em>';
  let html = escapeHtml(text);
  // Code blocks first (before other replacements mangle them)
  html = html.replace(/```([\s\S]*?)```/g, '<pre>$1</pre>');
  html = html.replace(/`([^`]+)`/g, '<code style="background:var(--bg-dark);padding:2px 6px;border-radius:4px;font-size:12px">$1</code>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g,     '<em>$1</em>');
  html = html.replace(/^### (.+)$/gm,   '<h4 style="margin:10px 0 4px;font-size:14px">$1</h4>');
  html = html.replace(/^## (.+)$/gm,    '<h3 style="margin:10px 0 4px">$1</h3>');
  html = html.replace(/^# (.+)$/gm,     '<h2 style="margin:10px 0 4px">$1</h2>');
  html = html.replace(/^- (.+)$/gm,     '<div style="padding-left:14px">&bull; $1</div>');
  html = html.replace(/^\* (.+)$/gm,    '<div style="padding-left:14px">&bull; $1</div>');
  html = html.replace(/^\d+\. (.+)$/gm, '<div style="padding-left:14px">$&</div>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return isNaN(d) ? isoStr : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function truncate(str, max) {
  if (!str) return '';
  return str.length > max ? str.slice(0, max) + '...' : str;
}

// ── Init ──────────────────────────────────────────────────────────────
updateThreadLabel();
loadDashboard();
