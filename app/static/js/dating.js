// Dating Module Controller for Ephemeral Chat

function updateInterestCounter() {
  const countSpan = document.getElementById('selected-interests-count');
  const summaryCount = document.getElementById('summary-hobbies-count');
  const checkedBoxes = document.querySelectorAll('.interest-checkbox:checked');
  if (countSpan) {
    countSpan.textContent = `${checkedBoxes.length} Selected`;
  }
  if (summaryCount) {
    summaryCount.textContent = `${checkedBoxes.length} selected`;
  }
}

function onInterestToggle(checkbox, chipId) {
  const chip = document.getElementById(chipId) || checkbox.closest('.interest-chip');
  if (chip) {
    chip.classList.toggle('selected', checkbox.checked);
  }
  updateInterestCounter();
}

function toggleInterestChip(chipElement, checkboxId) {
  const checkbox = document.getElementById(checkboxId);
  if (checkbox) {
    checkbox.checked = !checkbox.checked;
    chipElement.classList.toggle('selected', checkbox.checked);
    updateInterestCounter();
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
