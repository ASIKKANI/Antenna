/**
 * ChronosPet — OpenWA WhatsApp Gateway
 * =====================================
 * Connects to WhatsApp Web via Puppeteer, listens for incoming messages,
 * and forwards authorized messages as structured webhook payloads to
 * the local FastAPI backend (PRD Module A — Req-A.1/A.2/A.3).
 *
 * Environment Variables:
 *   BACKEND_WEBHOOK_URL  — FastAPI webhook endpoint (default: http://localhost:8000/api/v1/webhook/ingest)
 *   AUTHORIZED_PHONE     — Phone number filter (default: 919876543210)
 *
 * Usage:
 *   node index.js           (local)
 *   docker-compose up openwa (containerized)
 */

const { create, decryptMedia } = require("@open-wa/wa-automate");
const axios = require("axios");

// ─── Configuration ────────────────────────────────────────────────
const WEBHOOK_URL =
  process.env.BACKEND_WEBHOOK_URL ||
  "http://localhost:8000/api/v1/webhook/ingest";

const AUTHORIZED_PHONE = process.env.AUTHORIZED_PHONE || "919876543210";

console.log("━━━ ChronosPet OpenWA Gateway ━━━");
console.log(`Webhook URL: ${WEBHOOK_URL}`);
console.log(`Authorized Phone: ${AUTHORIZED_PHONE}`);

// ─── Start Client ─────────────────────────────────────────────────
create({
  sessionId: "chronospet",
  sessionDataPath: "./session",
  headless: false,
  qrTimeout: 0,            // Wait indefinitely for QR scan
  authTimeout: 120,
  cacheEnabled: false,
  useChrome: true,
  killProcessOnBrowserClose: true,
  throwErrorOnTosBlock: false,
  chromiumArgs: [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--disable-gpu",
  ],
})
  .then((client) => startListening(client))
  .catch((err) => {
    console.error("Failed to initialize OpenWA client:", err.message);
    process.exit(1);
  });

// ─── Message Handler ──────────────────────────────────────────────
function startListening(client) {
  console.log("WhatsApp client connected. Listening for messages...");

  client.onMessage(async (message) => {
    try {
      // Extract sender phone (strip @c.us suffix)
      const senderRaw = message.from || message.sender?.id || "";
      const senderPhone = senderRaw.replace("@c.us", "").replace("@s.whatsapp.net", "");

      // Security: drop unauthorized senders silently (PRD Req-A.2)
      if (senderPhone !== AUTHORIZED_PHONE) {
        console.log(`[DROPPED] Unauthorized sender: ${senderPhone}`);
        return;
      }

      let content = "";
      let messageType = "text";

      // Handle text messages
      if (message.type === "chat" && message.body) {
        content = message.body;
        messageType = "text";
      }
      // Handle voice/audio messages
      else if (message.type === "ptt" || message.type === "audio") {
        // For now, log audio messages — full STT integration is Phase 4
        console.log(`[AUDIO] Received voice message from ${senderPhone} (${message.duration}s)`);
        content = `[Voice message received - ${message.duration || 0}s duration]`;
        messageType = "audio";
      }
      // Handle image messages with captions
      else if (message.type === "image" && message.caption) {
        content = message.caption;
        messageType = "text";
      }
      // Skip other message types
      else {
        console.log(`[SKIP] Unsupported message type: ${message.type}`);
        return;
      }

      if (!content.trim()) return;

      // Build webhook payload (PRD Req-A.3 format)
      const webhookPayload = {
        sender: senderPhone,
        message_id: message.id || `WA-MSG-${Date.now()}`,
        timestamp: Math.floor(message.timestamp || Date.now() / 1000),
        message_type: messageType,
        content: content.trim(),
      };

      console.log(`[FORWARD] ${senderPhone}: "${content.substring(0, 80)}..."`);

      // Forward to FastAPI backend
      const response = await axios.post(WEBHOOK_URL, webhookPayload, {
        headers: { "Content-Type": "application/json" },
        timeout: 10000,
      });

      console.log(`[OK] Backend responded: ${response.status} — ${JSON.stringify(response.data).substring(0, 100)}`);

      // Send confirmation back to WhatsApp
      if (response.data?.parsed?.title) {
        await client.sendText(
          message.from,
          `✅ Task captured: "${response.data.parsed.title}" [${response.data.parsed.priority}]`
        );
      } else if (response.data?.message?.includes("complete")) {
        await client.sendText(message.from, `🎉 ${response.data.message}`);
      }
    } catch (err) {
      console.error(`[ERROR] Failed to process message:`, err.message);

      // If backend is unreachable, notify user
      if (err.code === "ECONNREFUSED" || err.code === "ETIMEDOUT") {
        console.error("Backend is not running! Start with: cd backend && uvicorn main:app --host 0.0.0.0 --port 8000");
      }
    }
  });

  // Connection state monitoring
  client.onStateChanged((state) => {
    console.log(`[STATE] WhatsApp connection: ${state}`);
    if (state === "CONFLICT" || state === "UNLAUNCHED") {
      client.forceRefocus();
    }
  });

  // Graceful shutdown
  process.on("SIGINT", async () => {
    console.log("\nShutting down gateway...");
    await client.kill();
    process.exit(0);
  });
}
