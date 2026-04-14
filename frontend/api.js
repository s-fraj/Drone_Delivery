/* api.js — shared fetch wrapper */
const API = 'http://localhost:8000';

function getToken() {
  return localStorage.getItem('drovery_token');
}
function setToken(t) {
  localStorage.setItem('drovery_token', t);
}
function clearToken() {
  localStorage.removeItem('drovery_token');
  localStorage.removeItem('drovery_user');
}
function isLoggedIn() {
  return !!getToken();
}

async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = 'login.html';
    return;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Request failed');
  }
  if (res.status === 204) return null;
  return res.json();
}

async function getCurrentUser() {
  try { return await apiFetch('/users/me'); }
  catch { return null; }
}

// Update navbar: show user name or login/signup
async function initNavbar() {
  const links = document.querySelectorAll('.navbar ul a');
  links.forEach(a => {
    if (a.getAttribute('href') === window.location.pathname.split('/').pop()) {
      a.classList.add('active');
    }
  });

  if (isLoggedIn()) {
    const user = await getCurrentUser();
    if (user) {
      const li = document.querySelector('#nav-auth');
      if (li) li.innerHTML = `
        <a href="profile.html" class="nav-cta">👤 ${user.first_name}</a>`;
    }
  }
}

document.addEventListener('DOMContentLoaded', initNavbar);
