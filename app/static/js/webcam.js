// Desktop Webcam Capture Module for Ephemeral Chat

class WebcamManager {
  constructor(options = {}) {
    this.modal = document.getElementById('webcam-modal');
    this.video = document.getElementById('webcam-video');
    this.canvas = document.getElementById('webcam-canvas');
    this.captureBtn = document.getElementById('webcam-capture-btn');
    this.retakeBtn = document.getElementById('webcam-retake-btn');
    this.sendBtn = document.getElementById('webcam-send-btn');
    this.closeBtn = document.getElementById('webcam-close-btn');
    this.onSendCallback = options.onSend || null;

    this.stream = null;
    this.capturedBlob = null;

    this.initEvents();
  }

  initEvents() {
    if (this.captureBtn) {
      this.captureBtn.addEventListener('click', () => this.takeSnapshot());
    }
    if (this.retakeBtn) {
      this.retakeBtn.addEventListener('click', () => this.retake());
    }
    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => this.sendSnapshot());
    }
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => this.close());
    }
  }

  async open() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Webcam is not supported or accessible in this browser.");
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false
      });

      this.video.srcObject = this.stream;
      this.video.style.display = 'block';
      this.canvas.style.display = 'none';

      this.captureBtn.style.display = 'inline-flex';
      this.retakeBtn.style.display = 'none';
      this.sendBtn.style.display = 'none';

      if (this.modal) this.modal.classList.add('open');
    } catch (err) {
      console.error("Camera access error:", err);
      alert("Could not access webcam. Please verify camera permissions in your browser.");
    }
  }

  takeSnapshot() {
    if (!this.stream) return;

    this.canvas.width = this.video.videoWidth || 640;
    this.canvas.height = this.video.videoHeight || 480;
    const ctx = this.canvas.getContext('2d');
    ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

    this.canvas.toBlob((blob) => {
      this.capturedBlob = blob;
      this.video.style.display = 'none';
      this.canvas.style.display = 'block';

      this.captureBtn.style.display = 'none';
      this.retakeBtn.style.display = 'inline-flex';
      this.sendBtn.style.display = 'inline-flex';
    }, 'image/jpeg', 0.9);
  }

  retake() {
    this.capturedBlob = null;
    this.video.style.display = 'block';
    this.canvas.style.display = 'none';

    this.captureBtn.style.display = 'inline-flex';
    this.retakeBtn.style.display = 'none';
    this.sendBtn.style.display = 'none';
  }

  async sendSnapshot() {
    if (!this.capturedBlob) return;

    if (this.onSendCallback) {
      this.sendBtn.disabled = true;
      this.sendBtn.textContent = 'Sending...';
      try {
        await this.onSendCallback(this.capturedBlob, 'webcam_capture.jpg');
        this.close();
      } catch (err) {
        alert("Failed to send image: " + err.message);
      } finally {
        this.sendBtn.disabled = false;
        this.sendBtn.textContent = 'Send Ephemeral Photo';
      }
    }
  }

  close() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.video) this.video.srcObject = null;
    if (this.modal) this.modal.classList.remove('open');
    this.capturedBlob = null;
  }
}
