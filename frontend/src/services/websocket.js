const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export class CallWebSocket {
  constructor(callId, onMessage, onError, onOpen, onClose) {
    this.callId = callId;
    this.onMessage = onMessage;
    this.onError = onError;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.isIntentionalClose = false;
    this.connect();
  }

  connect() {
    try {
      this.isIntentionalClose = false;
      this.ws = new WebSocket(`${WS_BASE}/ws/call/${this.callId}`);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = (event) => {
        this.reconnectAttempts = 0;
        if (this.onOpen) this.onOpen(event);
      };

      this.ws.onmessage = (event) => {
        try {
          if (typeof event.data === 'string') {
            const data = JSON.parse(event.data);
            if (this.onMessage) this.onMessage(data);
          }
        } catch (e) {
          console.error("WS Parse error", e);
        }
      };

      this.ws.onerror = (err) => {
        if (this.onError) this.onError(err);
      };

      this.ws.onclose = (event) => {
        if (this.onClose) this.onClose(event);
        if (!this.isIntentionalClose && this.reconnectAttempts < 3) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), 2000);
        }
      };
    } catch (e) {
      if (this.onError) this.onError(e);
    }
  }

  send(data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    if (typeof data === 'string') {
      this.ws.send(data);
    } else if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) {
      this.ws.send(data);
    } else {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendControl(actionOrObj) {
    const payload = typeof actionOrObj === 'string' ? { type: actionOrObj } : actionOrObj;
    this.send(JSON.stringify(payload));
  }

  sendAudioChunk(int16Buffer) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    // int16Buffer can be an Int16Array or ArrayBuffer
    if (ArrayBuffer.isView(int16Buffer)) {
      this.ws.send(int16Buffer.buffer);
    } else {
      this.ws.send(int16Buffer);
    }
  }

  isOpen() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  close() {
    this.isIntentionalClose = true;
    if (this.ws) {
      this.ws.close();
    }
  }
}
