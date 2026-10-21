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
    let message = 'Request failed';
    if (typeof err.detail === 'string') {
      message = err.detail;
    } else if (Array.isArray(err.detail)) {
      // FastAPI/pydantic validation errors (422) come back as a list of
      // {loc, msg, type} objects rather than a plain string.
      message = err.detail.map(d => d.msg || JSON.stringify(d)).join('; ');
    }
    throw new Error(message);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function getCurrentUser() {
  try { return await apiFetch('/users/me'); }
  catch { return null; }
}

// Update navbar: show user name (+ Admin link for admins) or login/signup
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
      if (li) {
        if (user.is_admin) {
          // Admins see only the Admin link — no separate profile link.
          li.innerHTML = `<a href="admin.html" class="nav-cta">🛠️ Admin</a>`;
        } else {
          li.innerHTML = `<a href="profile.html" class="nav-cta">👤 ${user.first_name}</a>`;
        }
      }
    }
  }
}

// Guard for pages that require an authenticated admin (e.g. admin.html).
// Redirects non-admins back to the profile page instead of showing them
// data or controls they shouldn't have access to.
async function requireAdmin() {
  if (!isLoggedIn()) { window.location.href = 'login.html'; return null; }
  const user = await getCurrentUser();
  if (!user || !user.is_admin) { window.location.href = 'profile.html'; return null; }
  return user;
}

function logout() {
  clearToken();
  window.location.href = 'login.html';
}

document.addEventListener('DOMContentLoaded', initNavbar);
