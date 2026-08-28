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
    this.initMobileKeyboard();
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

  initMobileKeyboard() {
    if (window.visualViewport) {
      const handleResize = () => {
        const viewportHeight = window.visualViewport.height;
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer && window.innerWidth <= 768) {
          chatContainer.style.height = `${viewportHeight - 65}px`;
          this.scrollToBottom();
        }
      };

      window.visualViewport.addEventListener('resize', handleResize);
      window.visualViewport.addEventListener('scroll', handleResize);
    }

    if (this.messageInput) {
      this.messageInput.addEventListener('focus', () => {
        setTimeout(() => {
          this.scrollToBottom();
          window.scrollTo(0, 0);
        }, 250);
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

    const senderId = (msg.sender && msg.sender.id) || msg.sender_id || msg.user_id;
    const isAuthor = (senderId && senderId === this.currentUserId) || msg.is_author === true;

    // Resolve public sender identity
    let displayName = 'Anonymous';
    let gender = 'Member';

    if (msg.sender) {
      displayName = msg.sender.display_name || (msg.sender.show_username && msg.sender.username ? `@${msg.sender.username}` : 'Anonymous');
      gender = msg.sender.gender || 'Member';
    } else if (msg.username) {
      displayName = `@${msg.username}`;
    }

    const wrapper = document.createElement('div');
    wrapper.id = `pmsg-${msg.id}`;
    wrapper.className = `public-message-wrapper ${isAuthor ? 'sent' : 'received'}`;

    let deleteBtnHtml = '';
    if ((isAuthor || this.isAdmin) && !msg.is_deleted) {
      deleteBtnHtml = `
        <div class="message-actions">
          <button type="button" class="btn btn-sm btn-danger" style="padding:2px 6px; font-size:0.7rem;" onclick="publicChatApp.deleteMessage('${msg.id}')">Delete</button>
        </div>
      `;
    }

    const timeStr = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    wrapper.innerHTML = `
      ${deleteBtnHtml}
      <div class="public-sender-header">
        <span>${this.escapeHtml(displayName)}</span>
        <span>·</span>
        <span class="public-sender-gender">${this.escapeHtml(gender)}</span>
      </div>
      <div class="public-bubble ${isAuthor ? 'sent' : 'received'}">
        <div class="message-body">${this.escapeHtml(msg.content)}</div>
        <div class="message-meta">
          <span>${timeStr}</span>
        </div>
      </div>
    `;

    this.messagesContainer.appendChild(wrapper);
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
