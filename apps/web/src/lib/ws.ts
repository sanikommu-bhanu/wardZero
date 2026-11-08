// Connects to the real backend WebSocket at apps/api/main.py's `@app.websocket("/ws")` /
// apps/api/ws_manager.ConnectionManager. Every message this dispatches is exactly what that
// connection manager broadcast — either a /readings notification, or a STEP 12 simulator_manager
// "sim_reading" / "device_event" payload. No message is fabricated client-side.

export type WsMessage = {
  type?: "alert" | "vitals_update" | "sim_reading" | "device_event" | string;
  patient_id?: string;
  [key: string]: any;
};

type Listener = (msg: WsMessage) => void;

const WS_URL = (import.meta as any).env?.VITE_WS_URL ||
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

class WsClient {
  private socket: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private connectionListeners = new Set<(connected: boolean) => void>();
  private reconnectDelay = 1000;
  private manuallyClosed = false;
  private queuedOutbound: string[] = []; // kept for the Offline banner's "queued events" display
  public connected = false;

  connect() {
    this.manuallyClosed = false;
    this._open();
  }

  private _open() {
    try {
      // The backend rejects unauthenticated sockets (close code 1008), so append the same JWT the REST
      // client uses. If there is no token yet, don't open a socket that is guaranteed to be refused.
      const t = localStorage.getItem("wz_token");
      if (!t) { this._scheduleReconnect(); return; }
      this.socket = new WebSocket(`${WS_URL}${WS_URL.includes("?") ? "&" : "?"}token=${encodeURIComponent(t)}`);
    } catch {
      this._scheduleReconnect();
      return;
    }
    this.socket.onopen = () => {
      this.connected = true;
      this.reconnectDelay = 1000;
      this.connectionListeners.forEach((l) => l(true));
    };
    this.socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        this.listeners.forEach((l) => l(msg));
      } catch {
        // non-JSON frame: ignore rather than crash the UI
      }
    };
    this.socket.onclose = () => {
      this.connected = false;
      this.connectionListeners.forEach((l) => l(false));
      if (!this.manuallyClosed) this._scheduleReconnect();
    };
    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  private _scheduleReconnect() {
    setTimeout(() => {
      if (!this.manuallyClosed) this._open();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.6, 15000);
  }

  disconnect() {
    this.manuallyClosed = true;
    this.socket?.close();
  }

  onMessage(fn: Listener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  onConnectionChange(fn: (connected: boolean) => void) {
    this.connectionListeners.add(fn);
    return () => this.connectionListeners.delete(fn);
  }

  get queuedCount() {
    return this.queuedOutbound.length;
  }
}

export const wsClient = new WsClient();
