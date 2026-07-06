/**
 * app.js — Hello Agent Web UI
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

const TOOL_ICONS = {
  calculator:    { icon: '🔢', cls: 'calc' },
  get_weather:   { icon: '🌤️', cls: 'weather' },
  web_search:    { icon: '🔍', cls: 'search' },
  remember:      { icon: '🧠', cls: 'memory' },
  recall:        { icon: '🧠', cls: 'memory' },
  list_memories: { icon: '📋', cls: 'memory' },
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
  removeTypingIndicator();

  switch (step.type) {
    case 'thought':
      ensureAgentBubble();
      appendStep('thought', '💭 Thought', step.content);
      break;

    case 'action':
      ensureAgentBubble();
      const toolDisplay = `${step.tool_name}(${step.content})`;
      appendStep('action', `⚡ Calling: ${step.tool_name}`, toolDisplay);
      break;

    case 'observation':
      ensureAgentBubble();
      appendStep('observation', `👁️ Result from ${step.tool_name}`, step.content);
      break;

    case 'answer':
      ensureAgentBubble();
      appendFinalAnswer(step.content);
      finishThinking();
      break;

    case 'error':
      ensureAgentBubble();
      appendStep('error', '❌ Error', step.content);
      finishThinking();
      break;

    case 'done':
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
    answerEl.innerHTML = markdownToHtml(text);
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
  const dotsDiv = createElement('div', 'typing-dots');
  for (let i = 0; i < 3; i++) {
    const dot = createElement('div', 'typing-dot');
    dotsDiv.append(dot);
  }
  const label = createElement('span', 'typing-label');
  label.textContent = 'Thinking…';
  indicator.append(dotsDiv, label);
  group.append(indicator);
  group.id = 'typing-group';
  document.getElementById('chat-container').append(group);
  typingIndicator = group;
  scrollToBottom();
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
  document.getElementById('user-input').value = el.textContent;
  sendMessage();
}

function startThinking() {
  isThinking = true;
  document.getElementById('send-btn').disabled = true;
  document.getElementById('agent-avatar').style.boxShadow = '0 0 30px rgba(124,106,247,0.8)';
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
// Keyboard Handling
// ──────────────────────────────────────────────
function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

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
