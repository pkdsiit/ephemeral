// Public Chat Controller for Ephemeral Chat

class PublicChatApp {
  constructor(config = {}) {
    this.roomCode = config.roomCode;
    this.currentUserId = config.currentUserId;
    this.isAdmin = config.isAdmin || false;

    this.messagesContainer = document.getElementById('public-messages');
    this.messageInput = document.getElementById('public-input');
    this.sendBtn = document.getElementById('public-send-btn');

    this.socket = null;
    this.initSocket();
    this.initEvents();
    this.loadMessages();
  }

  initSocket() {
    if (typeof io !== 'undefined') {
      try {
        this.socket = io();

        this.socket.on('connect', () => {
          if (this.roomCode) {
            this.socket.emit('join_public_room', { room_code: this.roomCode });
          }
        });

        this.socket.on('new_public_message', (msg) => {
          this.appendMessage(msg);
          this.scrollToBottom();
        });

        this.socket.on('public_message_deleted', (data) => {
          const msgEl = document.getElementById(`pmsg-${data.message_id}`);
          if (msgEl) {
            msgEl.querySelector('.message-body').textContent = '[ Message deleted ]';
            const actionBtn = msgEl.querySelector('.message-actions');
            if (actionBtn) actionBtn.remove();
          }
        });
      } catch (err) {
        console.warn("Public socket init skipped/failed:", err);
      }
    }
  }

  initEvents() {
    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => this.sendMessage());
    }

    if (this.messageInput) {
      this.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }
  }

  async loadMessages() {
    if (!this.roomCode) return;
    try {
      const resp = await fetchWithCsrf(`/api/public/rooms/${this.roomCode}/messages`);
      if (resp.ok) {
        const data = await resp.json();
        this.renderAllMessages(data.messages || []);
        this.scrollToBottom();
      }
    } catch (err) {
      console.error("Failed to load public messages:", err);
    }
  }

  renderAllMessages(messages) {
    if (!this.messagesContainer) return;
    this.messagesContainer.innerHTML = '';
    messages.forEach(msg => this.appendMessage(msg));
  }

  appendMessage(msg) {
    if (!this.messagesContainer) return;
    if (document.getElementById(`pmsg-${msg.id}`)) return;

    const isAuthor = msg.user_id === this.currentUserId || msg.is_author;
    const bubble = document.createElement('div');
    bubble.id = `pmsg-${msg.id}`;
    bubble.className = `message-bubble ${isAuthor ? 'message-sent' : 'message-received'}`;

    let deleteBtnHtml = '';
    if ((isAuthor || this.isAdmin) && !msg.is_deleted) {
      deleteBtnHtml = `
        <div class="message-actions">
          <button class="btn btn-sm btn-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="publicChatApp.deleteMessage('${msg.id}')">Delete</button>
        </div>
      `;
    }

    const timeStr = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const authorHeader = !isAuthor ? `<div style="font-size:0.75rem; font-weight:bold; color:var(--accent-cyan); margin-bottom:2px;">@${this.escapeHtml(msg.username)}</div>` : '';

    bubble.innerHTML = `
      ${deleteBtnHtml}
      ${authorHeader}
      <div class="message-body">${this.escapeHtml(msg.content)}</div>
      <div class="message-meta">
        <span>${timeStr}</span>
      </div>
    `;

    this.messagesContainer.appendChild(bubble);
  }

  async sendMessage() {
    if (!this.roomCode) {
      if (typeof showToast === 'function') showToast("Room code missing.", "error");
      return;
    }
    if (!this.messageInput) return;
    const text = this.messageInput.value.trim();
    if (!text) return;

    this.messageInput.value = '';
    try {
      const resp = await fetchWithCsrf(`/api/public/rooms/${this.roomCode}/messages`, {
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
      console.error("Error sending public message:", err);
      if (typeof showToast === 'function') {
        showToast("Failed to send message. Please check connection.", "error");
      }
    }
  }

  async deleteMessage(messageId) {
    if (!confirm("Delete this public message?")) return;
    try {
      const resp = await fetchWithCsrf(`/api/public/messages/${messageId}`, { method: 'DELETE' });
      if (!resp.ok) {
        const data = await resp.json();
        alert(data.error || "Failed to delete message.");
      }
    } catch (err) {
      console.error("Error deleting message:", err);
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
