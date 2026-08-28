// Global Application Scripts for Ephemeral Chat

// Get CSRF Token from meta tag or cookie
function getCsrfToken() {
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if (metaTag) return metaTag.getAttribute('content');
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : '';
}

// Fetch wrapper with CSRF headers
async function fetchWithCsrf(url, options = {}) {
  const headers = options.headers || {};
  const token = getCsrfToken();
  if (token && !headers['X-CSRFToken'] && !headers['X-CSRF-Token']) {
    headers['X-CSRFToken'] = token;
  }
  options.headers = headers;
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
      }
      alert(`Connection request sent to @${username}!`);
    } else {
      alert(data.error || "Failed to send connection request.");
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.textContent = 'Connect';
      }
    }
  } catch (err) {
    console.error("Error sending connection request:", err);
    alert("Connection request failed. Please check network connection.");
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.textContent = 'Connect';
    }
  }
}

async function acceptFriend(id) {
  try {
    const resp = await fetchWithCsrf(`/api/friends/${id}/accept`, { method: 'POST' });
    if (resp.ok) window.location.reload();
    else {
      const data = await resp.json();
      alert(data.error || "Failed to accept request.");
    }
  } catch (err) {
    console.error(err);
  }
}

async function rejectFriend(id) {
  try {
    const resp = await fetchWithCsrf(`/api/friends/${id}/reject`, { method: 'POST' });
    if (resp.ok) window.location.reload();
    else {
      const data = await resp.json();
      alert(data.error || "Failed to decline request.");
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
    if (resp.ok) window.location.reload();
    else alert("Failed to block user.");
  } catch(err) {
    console.error(err);
  }
}

async function unblockUser(userId) {
  try {
    const resp = await fetchWithCsrf(`/api/users/${userId}/unblock`, { method: 'POST' });
    if (resp.ok) window.location.reload();
    else alert("Failed to unblock user.");
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
