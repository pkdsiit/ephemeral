// Ephemeral Private Chat Controller

class ChatApp {
  constructor(config = {}) {
    this.conversationId = config.conversationId;
    this.currentUserId = config.currentUserId;
    this.recipientUsername = config.recipientUsername;

    this.messagesContainer = document.getElementById('chat-messages');
    this.messageInput = document.getElementById('chat-input');
    this.sendBtn = document.getElementById('chat-send-btn');
    this.fileInput = document.getElementById('chat-file-input');
    this.cameraInput = document.getElementById('chat-camera-input');
    this.webcamBtn = document.getElementById('chat-webcam-btn');
    this.typingIndicator = document.getElementById('typing-indicator');

    // Ephemeral Viewer Modal
    this.ephemeralModal = document.getElementById('ephemeral-viewer-modal');
    this.ephemeralImg = document.getElementById('ephemeral-viewer-img');
    this.ephemeralTimer = document.getElementById('ephemeral-countdown');
    this.ephemeralCloseBtn = document.getElementById('ephemeral-close-btn');

    this.socket = null;
    this.countdownInterval = null;
    this.typingTimeout = null;

    this.initSocket();
    this.initEvents();
    this.initWebcam();
    this.loadMessages();
  }

  initSocket() {
    if (typeof io !== 'undefined') {
      try {
        this.socket = io();

        this.socket.on('connect', () => {
          console.log("Connected to real-time server");
          if (this.conversationId) {
            this.socket.emit('join_conversation', { conversation_id: this.conversationId });
          }
        });

      this.socket.on('new_message', (msg) => {
        if (msg.conversation_id === this.conversationId) {
          this.appendMessage(msg);
          this.scrollToBottom();
        }
      });

      this.socket.on('image_seen', (data) => {
        if (data.conversation_id === this.conversationId) {
          this.updateImageState(data.image_id, 'SEEN');
        }
      });

      this.socket.on('image_deleted', (data) => {
        if (data.conversation_id === this.conversationId) {
          this.updateImageState(data.image_id, 'DELETED');
        }
      });

      this.socket.on('message_deleted', (data) => {
        if (data.conversation_id === this.conversationId) {
          const msgEl = document.getElementById(`msg-${data.message_id}`);
          if (msgEl) {
            msgEl.querySelector('.message-body').textContent = '[ Message deleted ]';
            const actionBtn = msgEl.querySelector('.message-actions');
            if (actionBtn) actionBtn.remove();
          }
        }
      });

      this.socket.on('user_typing', (data) => {
        if (data.conversation_id === this.conversationId && data.user_id !== this.currentUserId) {
          if (this.typingIndicator) this.typingIndicator.style.display = 'block';
        }
      });

        this.socket.on('user_stopped_typing', (data) => {
          if (data.conversation_id === this.conversationId) {
            if (this.typingIndicator) this.typingIndicator.style.display = 'none';
          }
        });
      } catch (err) {
        console.warn("Socket initialization skipped/failed:", err);
      }
    }
  }

  initEvents() {
    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => this.sendTextMessage());
    }

    if (this.messageInput) {
      this.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendTextMessage();
        } else {
          this.handleTyping();
        }
      });
    }

    if (this.fileInput) {
      this.fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          this.uploadImageFile(e.target.files[0]);
          e.target.value = '';
        }
      });
    }

    if (this.cameraInput) {
      this.cameraInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          this.uploadImageFile(e.target.files[0]);
          e.target.value = '';
        }
      });
    }

    if (this.ephemeralCloseBtn) {
      this.ephemeralCloseBtn.addEventListener('click', () => this.closeEphemeralModal());
    }
  }

  initWebcam() {
    if (this.webcamBtn) {
      this.webcamManager = new WebcamManager({
        onSend: async (blob, filename) => {
          await this.uploadImageFile(blob, filename);
        }
      });

      this.webcamBtn.addEventListener('click', () => {
        this.webcamManager.open();
      });
    }
  }

  handleTyping() {
    if (this.socket && this.socket.connected) {
      this.socket.emit('typing_start', { conversation_id: this.conversationId });
      clearTimeout(this.typingTimeout);
      this.typingTimeout = setTimeout(() => {
        this.socket.emit('typing_stop', { conversation_id: this.conversationId });
      }, 2000);
    }
  }

  async loadMessages() {
    if (!this.conversationId) return;
    try {
      const resp = await fetchWithCsrf(`/api/chats/${this.conversationId}/messages`);
      if (resp.ok) {
        const data = await resp.json();
        this.renderAllMessages(data.messages || []);
        this.scrollToBottom();
      }
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  }

  renderAllMessages(messages) {
    if (!this.messagesContainer) return;
    this.messagesContainer.innerHTML = '';
    messages.forEach(msg => this.appendMessage(msg));
  }

  appendMessage(msg) {
    if (!this.messagesContainer) return;
    
    // Check if already rendered
    if (document.getElementById(`msg-${msg.id}`)) return;

    const isSender = msg.sender_id === this.currentUserId || msg.is_sender;
    const bubble = document.createElement('div');
    bubble.id = `msg-${msg.id}`;
    bubble.className = `message-bubble ${isSender ? 'message-sent' : 'message-received'}`;

    let bodyHtml = '';
    if (msg.message_type === 'IMAGE') {
      const imgData = msg.image || {};
      const isAccessible = imgData.is_accessible;
      const isDeleted = imgData.state === 'DELETED' || imgData.state === 'EXPIRED';

      if (isDeleted) {
        bodyHtml = `
          <div class="ephemeral-card ephemeral-expired" id="img-card-${imgData.id || msg.id}">
            <div class="ephemeral-icon">✕</div>
            <div class="ephemeral-text">Ephemeral Photo Expired & Deleted</div>
          </div>
        `;
      } else if (isAccessible) {
        bodyHtml = `
          <div class="ephemeral-card" id="img-card-${imgData.id || msg.id}" onclick="chatApp.openEphemeralImage('${imgData.id}')">
            <div class="ephemeral-icon">🔒</div>
            <div class="ephemeral-text">Ephemeral Photo</div>
            <div class="ephemeral-subtext">${imgData.state === 'CONSUMED' ? 'Viewed • Will delete on next reply' : 'Tap to reveal • Disappears forever'}</div>
          </div>
        `;
      } else {
        bodyHtml = `<div class="ephemeral-card ephemeral-expired"><div class="ephemeral-text">Photo Expired</div></div>`;
      }
    } else {
      bodyHtml = `<div class="message-body">${this.escapeHtml(msg.content)}</div>`;
    }

    const timeStr = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let deleteBtnHtml = '';
    if (isSender && !msg.is_deleted) {
      deleteBtnHtml = `
        <div class="message-actions">
          <button class="btn btn-sm btn-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="chatApp.deleteMessage('${msg.id}')">Delete</button>
        </div>
      `;
    }

    bubble.innerHTML = `
      ${deleteBtnHtml}
      ${bodyHtml}
      <div class="message-meta">
        <span>${timeStr}</span>
        ${isSender ? `<span class="seen-check">${msg.is_seen ? '✓✓' : '✓'}</span>` : ''}
      </div>
    `;

    this.messagesContainer.appendChild(bubble);
  }

  async sendTextMessage() {
    if (!this.conversationId) {
      if (typeof showToast === 'function') showToast("Conversation is not ready.", "error");
      return;
    }
    if (!this.messageInput) return;
    const text = this.messageInput.value.trim();
    if (!text) return;

    this.messageInput.value = '';
    try {
      const resp = await fetchWithCsrf(`/api/chats/${this.conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text })
      });

      if (resp.ok) {
        const result = await resp.json();
        if (result && result.data) {
          this.appendMessage(result.data);
          this.scrollToBottom();
        }
      } else {
        const data = await resp.json();
        if (typeof showToast === 'function') {
          showToast(data.error || "Failed to send message.", "error");
        } else {
          alert(data.error || "Failed to send message.");
        }
      }
    } catch (err) {
      console.error("Error sending message:", err);
      if (typeof showToast === 'function') {
        showToast("Failed to send message. Please check connection.", "error");
      }
    }
  }

  async uploadImageFile(fileOrBlob, filename = 'image.jpg') {
    if (!this.conversationId) {
      if (typeof showToast === 'function') showToast("Conversation is not ready.", "error");
      return;
    }

    const formData = new FormData();
    formData.append('image', fileOrBlob, filename);

    try {
      const resp = await fetchWithCsrf(`/api/chats/${this.conversationId}/images`, {
        method: 'POST',
        body: formData
      });

      if (resp.ok) {
        const result = await resp.json();
        if (result && result.data) {
          this.appendMessage(result.data);
          this.scrollToBottom();
          if (typeof showToast === 'function') showToast("Ephemeral photo sent!", "success");
        }
      } else {
        const data = await resp.json();
        if (typeof showToast === 'function') {
          showToast(data.error || "Failed to send image.", "error");
        } else {
          alert(data.error || "Failed to send image.");
        }
      }
    } catch (err) {
      console.error("Error uploading image:", err);
      if (typeof showToast === 'function') {
        showToast("Image upload failed.", "error");
      }
    }
  }

  async openEphemeralImage(imageId) {
    if (!imageId) return;

    try {
      // Set image source to access-controlled endpoint
      this.ephemeralImg.src = `/media/ephemeral/${imageId}?t=${Date.now()}`;
      this.ephemeralModal.classList.add('open');

      // Countdown timer (20 seconds reveal)
      let secondsLeft = 20;
      if (this.ephemeralTimer) this.ephemeralTimer.textContent = `${secondsLeft}s`;

      clearInterval(this.countdownInterval);
      this.countdownInterval = setInterval(() => {
        secondsLeft--;
        if (this.ephemeralTimer) this.ephemeralTimer.textContent = `${secondsLeft}s`;
        if (secondsLeft <= 0) {
          this.closeEphemeralModal();
        }
      }, 1000);
    } catch (err) {
      console.error("Could not load image:", err);
      alert("This ephemeral image is no longer accessible.");
    }
  }

  closeEphemeralModal() {
    clearInterval(this.countdownInterval);
    if (this.ephemeralModal) this.ephemeralModal.classList.remove('open');
    if (this.ephemeralImg) this.ephemeralImg.src = '';
  }

  updateImageState(imageId, state) {
    const card = document.getElementById(`img-card-${imageId}`);
    if (card) {
      if (state === 'DELETED' || state === 'EXPIRED') {
        card.className = 'ephemeral-card ephemeral-expired';
        card.onclick = null;
        card.innerHTML = `
          <div class="ephemeral-icon">✕</div>
          <div class="ephemeral-text">Ephemeral Photo Expired & Deleted</div>
        `;
      } else if (state === 'SEEN') {
        const sub = card.querySelector('.ephemeral-subtext');
        if (sub) sub.textContent = 'Viewed • Will delete on next reply';
      }
    }
  }

  async deleteMessage(messageId) {
    if (!confirm("Permanently delete this message for everyone?")) return;
    try {
      const resp = await fetchWithCsrf(`/api/messages/${messageId}`, { method: 'DELETE' });
      if (!resp.ok) {
        const data = await resp.json();
        alert(data.error || "Failed to delete message.");
      }
    } catch (err) {
      console.error("Error deleting message:", err);
    }
  }

  async clearChat() {
    if (!confirm("Are you sure you want to clear this conversation history? All ephemeral content will be purged.")) return;
    try {
      const resp = await fetchWithCsrf(`/api/chats/${this.conversationId}`, { method: 'DELETE' });
      if (resp.ok) {
        window.location.href = '/chats';
      }
    } catch (err) {
      console.error("Error clearing chat:", err);
    }
  }

  scrollToBottom() {
    if (this.messagesContainer) {
      this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
  }

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
}
