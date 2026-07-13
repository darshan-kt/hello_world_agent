/**
 * login.js — Demo staff sign-in
 *
 * This is a cosmetic gate, not real authentication: any non-empty
 * username/password is accepted, nothing is sent to a server or checked
 * against a user database. It exists so the app has the look and flow of
 * professional hospital software, matching this project's synthetic-data,
 * no-real-auth POC scope (see HOSPITAL_RAG_ARCHITECTURE.md).
 */

const SESSION_KEY = 'darshan_session';

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('login-form').addEventListener('submit', handleLoginSubmit);
  document.getElementById('login-eye-btn').addEventListener('click', togglePasswordVisibility);
});

function handleLoginSubmit(e) {
  e.preventDefault();

  const usernameInput = document.getElementById('login-username');
  const passwordInput = document.getElementById('login-password');
  const errorEl = document.getElementById('login-error');
  const submitBtn = document.getElementById('login-submit-btn');

  const username = usernameInput.value.trim();
  const password = passwordInput.value.trim();

  if (!username || !password) {
    errorEl.textContent = '⚠️ Please enter both a username and a password.';
    errorEl.hidden = false;
    (username ? passwordInput : usernameInput).focus();
    return;
  }

  errorEl.hidden = true;
  submitBtn.disabled = true;
  submitBtn.textContent = 'Signing in…';

  // Small deliberate delay so sign-in feels real rather than suspiciously instant.
  setTimeout(() => {
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      username,
      loginAt: new Date().toISOString(),
    }));
    window.location.href = '/';
  }, 450);
}

function togglePasswordVisibility() {
  const passwordInput = document.getElementById('login-password');
  const eyeBtn = document.getElementById('login-eye-btn');
  const showing = passwordInput.type === 'text';
  passwordInput.type = showing ? 'password' : 'text';
  eyeBtn.textContent = showing ? '👁️' : '🙈';
  eyeBtn.title = showing ? 'Show password' : 'Hide password';
}
