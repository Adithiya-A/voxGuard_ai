const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

export class CallWebSocket {
  constructor(callId, onMessage, onError) {
    this.callId = callId;
    this.onMessage = onMessage;
    this.onError = onError;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.connect();
  }

  connect() {
    try {
      this.ws = new WebSocket(`${WS_BASE}/ws/call/${this.callId}`);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (this.onMessage) this.onMessage(data);
        } catch (e) {
          console.error("WS Parse error", e);
        }
      };

      this.ws.onerror = (err) => {
        if (this.onError) this.onError(err);
      };

      this.ws.onclose = () => {
        // Soft reconnect attempts
        if (this.reconnectAttempts < 3) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), 2000);
        }
      };
    } catch (e) {
      if (this.onError) this.onError(e);
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
