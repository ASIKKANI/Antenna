/**
 * ChronosPet — Auto-Reconnecting WebSocket Manager
 * ==================================================
 * Provides a robust WebSocket connection to the FastAPI backend
 * with exponential backoff reconnection and typed event handling.
 */

export interface CompanionState {
  display_animation_frame: string;
  active_bubble_dialogue: string;
  focus_points_balance: number;
  current_level: number;
  experience_progress_percentage: number;
  evolution_stage: string;
  active_tasks_count: number;
}

type StateCallback = (state: CompanionState) => void;
type StatusCallback = (status: string) => void;

const WS_URL = "ws://localhost:8000/ws/companion";
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 25000;

export class CompanionWebSocket {
  private ws: WebSocket | null = null;
  private retryMs = INITIAL_RETRY_MS;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private destroyed = false;

  private onState: StateCallback;
  private onStatus: StatusCallback;

  constructor(onState: StateCallback, onStatus: StatusCallback) {
    this.onState = onState;
    this.onStatus = onStatus;
    this.connect();
  }

  private connect() {
    if (this.destroyed) return;

    this.onStatus("Connecting...");

    try {
      this.ws = new WebSocket(WS_URL);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.retryMs = INITIAL_RETRY_MS;
      this.onStatus("Connected");
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Skip pong responses
        if (data === "pong" || event.data === "pong") return;
        this.onState(data as CompanionState);
      } catch {
        // Non-JSON message (like pong text), ignore
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.onStatus("Disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send("ping");
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect() {
    if (this.destroyed) return;

    this.onStatus(`Reconnecting in ${Math.round(this.retryMs / 1000)}s...`);

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, this.retryMs);

    // Exponential backoff with jitter
    this.retryMs = Math.min(this.retryMs * 2 + Math.random() * 500, MAX_RETRY_MS);
  }

  destroy() {
    this.destroyed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
    }
  }
}
