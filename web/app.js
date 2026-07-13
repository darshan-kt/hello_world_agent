/**
 * app.js — Darshan-AI Hospital Assistant Web UI
 * Connects to the FastAPI WebSocket and renders the ReAct loop in real time.
 */

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────
let ws = null;
let isThinking = false;
let currentStepsContainer = null;
let currentAgentBubble = null;
let typingIndicator = null;
let patientsLoaded = false;
let patientSearchDebounce = null;
let currentDrawerPatientId = null;

const TOOL_ICONS = {
  calculator:    { icon: '🔢', cls: 'calc' },
  get_weather:   { icon: '🌤️', cls: 'weather' },
  web_search:    { icon: '🔍', cls: 'search' },
  remember:      { icon: '🧠', cls: 'memory' },
  recall:        { icon: '🧠', cls: 'memory' },
  list_memories: { icon: '📋', cls: 'memory' },
  list_patients:          { icon: '🏥', cls: 'hospital' },
  search_patient:         { icon: '🏥', cls: 'hospital' },
  get_patient_record:     { icon: '🏥', cls: 'hospital' },
  list_patient_documents: { icon: '📄', cls: 'hospital' },
  search_patient_documents:{ icon: '📄', cls: 'hospital' },
};

// ──────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Set welcome time
  document.getElementById('welcome-time').textContent = formatTime(new Date());

  // Connect WebSocket
  connectWebSocket();

  // Load tools
  loadTools();

  // Focus input
  document.getElementById('user-input').focus();
});

// ──────────────────────────────────────────────
// WebSocket
// ──────────────────────────────────────────────
function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${protocol}//${location.host}/ws`;

  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('[WS] Connected');
    updateStatus(true);
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected — reconnecting in 2s…');
    updateStatus(false);
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = (e) => console.error('[WS] Error:', e);

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleAgentStep(msg);
  };
}

function updateStatus(online) {
  const dot = document.querySelector('.status-dot');
  const statusText = document.getElementById('agent-status');
  dot.className = `status-dot ${online ? 'online' : ''}`;
  statusText.innerHTML = `<span class="status-dot ${online ? 'online' : ''}"></span>${online ? 'Online' : 'Reconnecting…'}`;
}

// ──────────────────────────────────────────────
// Agent Step Rendering
// ──────────────────────────────────────────────
function handleAgentStep(step) {
  switch (step.type) {
    // Intermediate steps stay hidden — just update the spinner label
    case 'thought':
      updateTypingLabel('Thinking…');
      break;

    case 'action': {
      const meta = TOOL_ICONS[step.tool_name];
      updateTypingLabel(`${meta ? meta.icon + ' ' : ''}Using ${step.tool_name}…`);
      break;
    }

    case 'observation':
      updateTypingLabel('Processing results…');
      break;

    case 'answer':
      removeTypingIndicator();
      ensureAgentBubble();
      appendFinalAnswer(step.content);
      finishThinking();
      break;

    case 'error':
      removeTypingIndicator();
      ensureAgentBubble();
      appendStep('error', '❌ Error', step.content);
      finishThinking();
      break;

    case 'done':
      removeTypingIndicator();
      finishThinking();
      break;

    case 'reset':
      showToast('Chat cleared ✓');
      break;
  }
}

function ensureAgentBubble() {
  if (currentAgentBubble) return;

  const group = createElement('div', 'message-group agent-group');
  const bubble = createElement('div', 'message-bubble agent-bubble');
  const header = createElement('div', 'bubble-header');

  const role = createElement('span', 'bubble-role');
  role.textContent = document.getElementById('agent-name').textContent;

  const time = createElement('span', 'bubble-time');
  time.textContent = formatTime(new Date());

  header.append(role, time);

  const stepsDiv = createElement('div', 'steps-container');
  bubble.append(header, stepsDiv);
  group.append(bubble);

  document.getElementById('chat-container').append(group);

  currentAgentBubble = bubble;
  currentStepsContainer = stepsDiv;
  scrollToBottom();
}

function appendStep(type, label, content) {
  const card = createElement('div', `step-card step-${type}`);
  const labelEl = createElement('div', 'step-label');
  labelEl.textContent = label;
  const contentEl = createElement('div', 'step-content');
  contentEl.textContent = content;
  card.append(labelEl, contentEl);
  currentStepsContainer.append(card);
  scrollToBottom();
}

function appendFinalAnswer(text) {
  // Remove all step cards — replace with clean answer
  if (currentStepsContainer) {
    // Keep steps but add the final answer below
    const answerEl = createElement('div', 'bubble-content');
    answerEl.style.marginTop = currentStepsContainer.children.length ? '12px' : '0';
    answerEl.innerHTML = markdownToHtml(escapeHtml(text));
    currentAgentBubble.append(answerEl);
    scrollToBottom();
  }
}

// ──────────────────────────────────────────────
// Typing Indicator
// ──────────────────────────────────────────────
function showTypingIndicator() {
  if (typingIndicator) return;
  const group = createElement('div', 'message-group agent-group');
  const indicator = createElement('div', 'typing-indicator');

  const loader = createElement('div', 'vitals-loader');
  loader.innerHTML = `
    <div class="ring"></div>
    <div class="ring delay"></div>
    <div class="core"></div>
  `;

  const label = createElement('span', 'typing-label');
  label.textContent = 'Thinking…';
  indicator.append(loader, label);
  group.append(indicator);
  group.id = 'typing-group';
  document.getElementById('chat-container').append(group);
  typingIndicator = group;
  scrollToBottom();
}

function updateTypingLabel(text) {
  if (!typingIndicator) showTypingIndicator();
  const label = typingIndicator.querySelector('.typing-label');
  if (label) label.textContent = text;
}

function removeTypingIndicator() {
  if (typingIndicator) {
    typingIndicator.remove();
    typingIndicator = null;
  }
}

// ──────────────────────────────────────────────
// Sending Messages
// ──────────────────────────────────────────────
function sendMessage() {
  const input = document.getElementById('user-input');
  const message = input.value.trim();
  if (!message || isThinking) return;

  // Add user bubble
  addUserBubble(message);

  // Reset input
  input.value = '';
  input.style.height = 'auto';

  // Show typing
  startThinking();
  showTypingIndicator();

  // Reset agent bubble for new response
  currentAgentBubble = null;
  currentStepsContainer = null;

  // Send via WebSocket
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ message }));
  } else {
    // Fallback to REST API
    fetchChat(message);
  }
}

async function fetchChat(message) {
  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await resp.json();
    removeTypingIndicator();

    // Replay steps
    for (const step of data.steps) {
      handleAgentStep(step);
      await sleep(80);
    }
  } catch (e) {
    removeTypingIndicator();
    ensureAgentBubble();
    appendStep('error', '❌ Error', `Failed to connect: ${e.message}`);
    finishThinking();
  }
}

function addUserBubble(text) {
  const group = createElement('div', 'message-group user-group');
  const bubble = createElement('div', 'message-bubble user-bubble');
  const header = createElement('div', 'bubble-header');

  const role = createElement('span', 'bubble-role');
  role.textContent = 'You';
  const time = createElement('span', 'bubble-time');
  time.textContent = formatTime(new Date());
  header.append(role, time);

  const content = createElement('div', 'bubble-content');
  content.textContent = text;

  bubble.append(header, content);
  group.append(bubble);
  document.getElementById('chat-container').append(group);
  scrollToBottom();
}

function sendSuggestion(el) {
  const text = el.textContent.replace(/^[^\s]+\s/, '').trim(); // remove emoji
  document.getElementById('user-input').value = text;
  sendMessage();
}

function startThinking() {
  isThinking = true;
  document.getElementById('send-btn').disabled = true;
  document.getElementById('agent-avatar').style.boxShadow = '0 0 30px rgba(20,184,166,0.8)';
}

function finishThinking() {
  isThinking = false;
  document.getElementById('send-btn').disabled = false;
  document.getElementById('agent-avatar').style.boxShadow = '';
}

// ──────────────────────────────────────────────
// Reset
// ──────────────────────────────────────────────
async function resetConversation() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: 'reset' }));
  } else {
    await fetch('/reset', { method: 'POST' });
  }

  const container = document.getElementById('chat-container');
  // Remove all messages except welcome
  const children = [...container.children];
  children.slice(1).forEach(c => c.remove());

  currentAgentBubble = null;
  currentStepsContainer = null;
  removeTypingIndicator();
  finishThinking();
  showToast('Chat cleared ✓');
}

// ──────────────────────────────────────────────
// Panel Navigation
// ──────────────────────────────────────────────
function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`panel-${name}`).classList.add('active');
  document.getElementById(`btn-${name}`).classList.add('active');

  if (name === 'patients' && !patientsLoaded) {
    patientsLoaded = true;
    loadPatients();
  }
}

// ──────────────────────────────────────────────
// Load Tools
// ──────────────────────────────────────────────
async function loadTools() {
  try {
    const resp = await fetch('/tools');
    const tools = await resp.json();
    renderTools(tools);

    // Update model badge
    const health = await fetch('/health');
    const data = await health.json();
    document.getElementById('agent-name').textContent = data.agent;
    document.getElementById('model-name').textContent = data.model;
  } catch (e) {
    console.warn('Could not load tools:', e);
  }
}

function renderTools(tools) {
  const grid = document.getElementById('tools-grid');
  grid.innerHTML = '';

  for (const [name, tool] of Object.entries(tools)) {
    const meta = TOOL_ICONS[name] || { icon: '🔧', cls: 'default' };
    const card = createElement('div', 'tool-card');
    card.innerHTML = `
      <div class="tool-card-header">
        <div class="tool-icon ${meta.cls}">${meta.icon}</div>
        <div class="tool-name">${name}</div>
      </div>
      <div class="tool-desc">${tool.description}</div>
      <div class="tool-params">${JSON.stringify(tool.parameters, null, 2)}</div>
    `;
    grid.append(card);
  }
}

// ──────────────────────────────────────────────
// Patients Panel — instant DB browsing (no LLM call)
// ──────────────────────────────────────────────
async function loadPatients() {
  await fetchPatients('');
}

function searchPatients(query) {
  clearTimeout(patientSearchDebounce);
  patientSearchDebounce = setTimeout(() => fetchPatients(query), 250);
}

async function fetchPatients(query) {
  const grid = document.getElementById('patients-grid');
  try {
    const resp = await fetch(`/patients?query=${encodeURIComponent(query)}&limit=100`);
    const data = await resp.json();
    renderPatients(data.patients);
  } catch (e) {
    grid.innerHTML = `<div class="patients-empty">⚠️ Could not load patients: ${e.message}</div>`;
  }
}

function renderPatients(patients) {
  const grid = document.getElementById('patients-grid');
  const count = document.getElementById('patients-count');
  count.textContent = `${patients.length} patient${patients.length === 1 ? '' : 's'}`;

  if (!patients.length) {
    grid.innerHTML = '<div class="patients-empty">No patients match that search.</div>';
    return;
  }

  grid.innerHTML = '';
  patients.forEach((p, i) => {
    const card = createElement('div', 'patient-card');
    card.style.animationDelay = `${Math.min(i * 30, 300)}ms`;
    card.onclick = () => openPatientDrawer(p.patient_id);
    card.innerHTML = `
      <div class="patient-avatar" style="background: ${avatarGradient(p.patient_id)}">${initials(p.name)}</div>
      <div class="patient-card-body">
        <div class="patient-card-name">${escapeHtml(p.name)}</div>
        <div class="patient-card-meta">
          <span>ID ${p.patient_id} · ${p.age}y · ${escapeHtml(p.gender)}</span>
          <span class="blood-badge ${bloodBadgeClass(p.blood_group)}">${escapeHtml(p.blood_group)}</span>
        </div>
      </div>
    `;
    grid.append(card);
  });
}

function initials(name) {
  return name.split(' ').filter(Boolean).map(w => w[0]).slice(0, 2).join('').toUpperCase();
}

function bloodBadgeClass(bloodGroup) {
  const letter = (bloodGroup || '').replace(/[+-]/, '');
  if (letter === 'AB') return 'grp-ab';
  if (letter === 'A') return 'grp-a';
  if (letter === 'B') return 'grp-b';
  return 'grp-o';
}

function avatarGradient(seed) {
  // Deterministic hue per patient ID so avatars aren't all identical.
  const hue = (seed * 47) % 360;
  return `linear-gradient(135deg, hsl(${hue}, 60%, 42%), hsl(${(hue + 40) % 360}, 65%, 52%))`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Patient Detail Drawer ───────────────────────
async function openPatientDrawer(patientId) {
  currentDrawerPatientId = patientId;
  document.getElementById('drawer-backdrop').classList.add('open');
  document.getElementById('patient-drawer').classList.add('open');
  document.getElementById('drawer-body').innerHTML = '<div class="drawer-empty">Loading record…</div>';

  try {
    const resp = await fetch(`/patients/${patientId}`);
    const record = await resp.json();
    if (!resp.ok) throw new Error(record.detail || 'Patient not found');
    if (currentDrawerPatientId === patientId) renderDrawer(record);
  } catch (e) {
    document.getElementById('drawer-body').innerHTML =
      `<div class="drawer-empty">⚠️ Could not load patient: ${e.message}</div>`;
  }
}

function closeDrawer() {
  document.getElementById('drawer-backdrop').classList.remove('open');
  document.getElementById('patient-drawer').classList.remove('open');
  currentDrawerPatientId = null;
}

function renderDrawer(record) {
  const p = record.patient;
  document.getElementById('drawer-avatar').textContent = initials(p.name);
  document.getElementById('drawer-avatar').style.background = avatarGradient(p.patient_id);
  document.getElementById('drawer-name').textContent = p.name;
  document.getElementById('drawer-sub').innerHTML =
    `ID ${p.patient_id} · ${p.age}y · ${escapeHtml(p.gender)} · ` +
    `<span class="blood-badge ${bloodBadgeClass(p.blood_group)}">${escapeHtml(p.blood_group)}</span> · ${escapeHtml(p.phone)}`;

  const body = document.getElementById('drawer-body');
  body.innerHTML = '';

  body.append(
    aiSummarySection(p.patient_id),
    drawerSection('🏨 Admissions', record.admissions.map(a =>
      recordRow(a.diagnosis, `${a.admission_date} → ${a.discharge_date} · ${a.ward}`))),
    drawerSection('💊 Prescriptions', record.prescriptions.map(rx =>
      recordRow(`${rx.medicine} (${rx.dosage})`, `Prescribed ${rx.prescribed_date} by ${rx.prescribed_by}`))),
    drawerSection('🧪 Lab Reports', record.lab_reports.map(lab =>
      recordRow(`${lab.test_name}: ${lab.result}`, `Normal range ${lab.normal_range} · ${lab.test_date}`))),
    drawerSection('🔪 Surgeries', record.surgeries.map(s =>
      recordRow(s.surgery_name, `${s.surgery_date} by ${s.surgeon} · ${s.outcome}`))),
    drawerSection('📄 Documents', record.documents.map(d =>
      recordRow(`${d.document_type}: ${d.title}`, d.created_date))),
  );
}

function drawerSection(title, rowElements) {
  const section = createElement('div');
  const heading = createElement('div', 'drawer-section-title');
  heading.textContent = title;
  section.append(heading);

  if (!rowElements.length) {
    const empty = createElement('div', 'drawer-empty');
    empty.textContent = 'None on record.';
    section.append(empty);
  } else {
    rowElements.forEach(el => section.append(el));
  }
  return section;
}

function recordRow(main, sub) {
  const row = createElement('div', 'record-row');
  const mainEl = createElement('div', 'rr-main');
  mainEl.textContent = main;
  const subEl = createElement('div', 'rr-sub');
  subEl.textContent = sub;
  row.append(mainEl, subEl);
  return row;
}

function aiSummarySection(patientId) {
  const section = createElement('div');
  const heading = createElement('div', 'drawer-section-title');
  heading.textContent = '✨ AI Summary';
  const btn = createElement('button', 'ai-summary-btn');
  btn.textContent = '✨ Generate AI Summary';
  btn.onclick = () => generateAiSummary(patientId, section, btn);
  section.append(heading, btn);
  return section;
}

async function generateAiSummary(patientId, section, btn) {
  btn.disabled = true;
  btn.textContent = '⏳ Analyzing records + documents…';

  try {
    const resp = await fetch(`/patients/${patientId}/summary`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Summary generation failed');
    if (currentDrawerPatientId !== patientId) return; // drawer moved on while we waited

    btn.remove();
    const card = createElement('div', 'ai-summary-card');
    card.innerHTML = markdownToHtml(escapeHtml(data.summary));
    section.append(card);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '✨ Generate AI Summary';
    showToast(`⚠️ ${e.message}`);
  }
}

// ──────────────────────────────────────────────
// Keyboard Handling
// ──────────────────────────────────────────────
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeDrawer();
});

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

// ──────────────────────────────────────────────
// Utilities
// ──────────────────────────────────────────────
function createElement(tag, className = '') {
  const el = document.createElement(tag);
  if (className) el.className = className;
  return el;
}

function scrollToBottom() {
  const container = document.getElementById('chat-container');
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function markdownToHtml(text) {
  // Very simple markdown-like rendering
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code style="font-family:var(--font-mono);font-size:12px;background:rgba(255,255,255,0.08);padding:2px 6px;border-radius:4px">$1</code>')
    .replace(/\n/g, '<br>');
}

function showToast(msg) {
  const toast = createElement('div');
  toast.textContent = msg;
  Object.assign(toast.style, {
    position: 'fixed', bottom: '24px', right: '24px',
    background: 'var(--bg-card)', border: '1px solid var(--border-accent)',
    color: 'var(--text-primary)', padding: '12px 20px',
    borderRadius: 'var(--radius-md)', fontSize: '13px',
    boxShadow: 'var(--shadow-md)', zIndex: '9999',
    animation: 'fadeUp 0.3s ease',
    transition: 'opacity 0.3s ease',
  });
  document.body.append(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 2000);
}
