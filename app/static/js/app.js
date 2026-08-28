// Global Application Scripts for Ephemeral Chat

// Toast Notification System
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.style.cssText = 'position:fixed; top:20px; right:20px; z-index:99999; display:flex; flex-direction:column; gap:10px; max-width:360px; width:calc(100% - 40px); pointer-events:none;';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const bg = type === 'success' ? '#10b981' : type === 'danger' || type === 'error' ? '#ef4444' : '#6366f1';
  toast.style.cssText = `background:${bg}; color:#fff; padding:12px 18px; border-radius:10px; font-size:14px; font-weight:500; box-shadow:0 10px 25px rgba(0,0,0,0.3); pointer-events:auto; transition:all 0.3s ease; opacity:0; transform:translateY(-10px);`;
  toast.textContent = message;

  toastContainer.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Get CSRF Token from meta tag or cookie
function getCsrfToken() {
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if (metaTag) return metaTag.getAttribute('content');
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : '';
}

// Fetch wrapper with CSRF headers & same-origin credentials
async function fetchWithCsrf(url, options = {}) {
  const headers = options.headers || {};
  const token = getCsrfToken();
  if (token && !headers['X-CSRFToken'] && !headers['X-CSRF-Token']) {
    headers['X-CSRFToken'] = token;
  }
  options.headers = headers;
  options.credentials = 'same-origin';
  return fetch(url, options);
}

// Relative time formatting
function formatRelativeTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

// Global Connection / Friend Request Handler
async function sendDatingConnectionRequest(userId, username, btnElement) {
  return sendConnectionRequest(userId, username, btnElement);
}

async function sendConnectionRequest(userId, username, btnElement) {
  if (btnElement) {
    btnElement.disabled = true;
    btnElement.textContent = 'Connecting...';
  }

  try {
    const payload = {};
    if (userId) payload.user_id = userId;
    if (username) payload.username = username;

    const resp = await fetchWithCsrf('/api/friends/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await resp.json();
    if (resp.ok) {
      if (btnElement) {
        btnElement.className = 'btn btn-sm btn-secondary';
        btnElement.textContent = 'Request Sent ✓';
        btnElement.disabled = true;
      }
      showToast(`Connection request sent to @${username}!`, 'success');
    } else {
      showToast(data.error || "Failed to send connection request.", 'error');
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.textContent = 'Connect';
      }
    }
  } catch (err) {
    console.error("Error sending connection request:", err);
    showToast("Connection request failed. Please check network connection.", 'error');
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.textContent = 'Connect';
    }
  }
}

async function acceptFriend(id) {
  try {
    const resp = await fetchWithCsrf(`/api/friends/${id}/accept`, { method: 'POST' });
    if (resp.ok) {
      showToast("Friend request accepted!", "success");
      setTimeout(() => window.location.reload(), 500);
    } else {
      const data = await resp.json();
      showToast(data.error || "Failed to accept request.", "error");
    }
  } catch (err) {
    console.error(err);
  }
}

async function rejectFriend(id) {
  try {
    const resp = await fetchWithCsrf(`/api/friends/${id}/reject`, { method: 'POST' });
    if (resp.ok) {
      showToast("Request declined.", "info");
      setTimeout(() => window.location.reload(), 500);
    } else {
      const data = await resp.json();
      showToast(data.error || "Failed to decline request.", "error");
    }
  } catch (err) {
    console.error(err);
  }
}

async function blockUser(userId, username) {
  if (!confirm(`Are you sure you want to block @${username}? They will no longer be able to message you or see you in dating suggestions.`)) {
    return;
  }
  try {
    const resp = await fetchWithCsrf(`/api/users/${userId}/block`, { method: 'POST' });
    if (resp.ok) {
      showToast(`Blocked @${username}`, "info");
      setTimeout(() => window.location.reload(), 500);
    } else {
      showToast("Failed to block user.", "error");
    }
  } catch(err) {
    console.error(err);
  }
}

async function unblockUser(userId) {
  try {
    const resp = await fetchWithCsrf(`/api/users/${userId}/unblock`, { method: 'POST' });
    if (resp.ok) {
      showToast("User unblocked.", "success");
      setTimeout(() => window.location.reload(), 500);
    } else {
      showToast("Failed to unblock user.", "error");
    }
  } catch(err) {
    console.error(err);
  }
}

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });
});
