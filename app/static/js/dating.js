// Dating Module Controller for Ephemeral Chat

function toggleInterestChip(chipElement, checkboxId) {
  const checkbox = document.getElementById(checkboxId);
  if (checkbox) {
    checkbox.checked = !checkbox.checked;
    chipElement.classList.toggle('active', checkbox.checked);
  }
}

async function sendDatingConnectionRequest(userId, username, btnElement) {
  if (btnElement) {
    btnElement.disabled = true;
    btnElement.textContent = 'Connecting...';
  }

  try {
    const resp = await fetchWithCsrf('/api/friends/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, username: username })
    });

    const data = await resp.json();
    if (resp.ok) {
      if (btnElement) {
        btnElement.className = 'btn btn-sm btn-secondary';
        btnElement.textContent = 'Request Sent ✓';
      }
      alert(`Connection request sent to @${username}!`);
    } else {
      alert(data.error || "Failed to send request.");
      if (btnElement) {
        btnElement.disabled = false;
        btnElement.textContent = 'Connect';
      }
    }
  } catch (err) {
    console.error("Error connecting:", err);
    alert("Connection request failed.");
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.textContent = 'Connect';
    }
  }
}

function passDatingMatch(cardId) {
  const card = document.getElementById(cardId);
  if (card) {
    card.style.transition = 'transform 0.3s ease, opacity 0.3s ease';
    card.style.transform = 'scale(0.85) translateY(20px)';
    card.style.opacity = '0';
    setTimeout(() => card.remove(), 300);
  }
}
