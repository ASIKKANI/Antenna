# PRODUCT REQUIREMENT DOCUMENT (PRD)

## Project Title: Ambient Desktop Companion & Asynchronous Task Ingestor (Project "ChronosPet")

**Target Environment:** Local Cross-Platform Desktop (Windows/macOS/Linux)

**Author:** Product Engineering & Architecture Team

**Version:** 1.0.0

**Date:** June 2026

**Status:** Approved for Scaffolding

---

## 1. Document Overview & Metadata

This document serves as the single source of truth (SSOT) and engineering blueprint for Project **ChronosPet**. It provides high-fidelity technical and functional requirements designed to be parsed directly by AI-assisted coding tools (e.g., VS Code Copilot) to generate boilerplates, implement business logic, and construct data interfaces.

### 1.1 Document Revisions

* **v1.0.0 (Current):** Initial foundational baseline detailing Hybrid Cloud/Local LLM architecture, Tauri frontend configurations, Python background workers, `OpenWA` WhatsApp webhook integrations, and `TurboVec` memory configurations.

### 1.2 Intended AI Copilot Directives

> **System Notice for AI Code Generators:** > When executing files or functions based on this document, adhere strictly to the modular layers outlined in Section 4. Do not tightly couple the UI layer (Tauri/Rust) with the orchestration layer (FastAPI/Python). Ensure all API specifications match the schemas defined in Section 8.

---

## 2. Executive Summary & Strategic Context

### 2.1 Problem Statement

Modern productivity applications fail due to friction and poor visibility. Traditional task managers require intentional interaction: users must consciously launch an application, navigate to a window, and manually enter tasks. During execution, these apps remain hidden behind IDEs, web browsers, and design software, losing top-of-mind awareness. Conversely, automated screen-logging trackers (e.g., Rewind, Screenpipe) collect massive ambient data but act as passive historians rather than active coordinators. They lack interactive gamification, personality, and proactive accountability tools to prevent real-time attention drift.

### 2.2 Proposed Solution: The Ambient Companion

ChronosPet resolves this dilemma by merging **frictionless asynchronous ingestion** with **ambient visual accountability**. Users drop tasks into an active WhatsApp conversation via text or voice. A self-hosted gateway captures these interactions and populates a localized queue. On the desktop, a lightweight, hardware-accelerated, transparent overlay companion (an animated pet, avatar, or robot) lives natively on the user's workspace screen.

The companion actively balances productivity with engagement by monitoring window metadata locally. It visually transforms—evolving, reacting, or nagging—based on whether the user's active window aligns with their self-declared goals.

```
+--------------------+        +---------------------+        +--------------------+
|   WhatsApp User    | ------>|   OpenWA Gateway    | ------>|   FastAPI Core     |
| (Task Ingestion)   |        | (Docker Container)  |        | (Orchestration)    |
+--------------------+        +---------------------+        +--------------------+
                                                                      |
                                                                      v
+--------------------+        +---------------------+        +--------------------+
|  Tauri Desktop UI  | <------| Local OS Observers  | <------|   TurboVec Engine  |
| (Transparent Pet)  |        | (Active Window/OCR) |        | (Semantic Memory)  |
+--------------------+        +---------------------+        +--------------------+

```

### 2.3 Core Product Philosophy

* **Zero Ingestion Friction:** Task registration must require no desktop application context switching. WhatsApp serves as the universal remote input.
* **Unobtrusive Omnipresence:** The desktop companion must occupy zero active workspace bounds; it must float transparently, passing click events through to underlying windows when idle.
* **Radical Resource Efficiency:** The tool must sit in the background during 3D gaming or code compilation without dragging system resources. RAM footprint must remain beneath 100MB on average.
* **Privacy-First Design:** Sensitive raw screen data or application usage streams must never leave the local machine. Cloud LLMs are utilized solely for short, abstract textual transformations.

---

## 3. Product Vision & Persona Framework

### 3.1 Visualizing the Companion

The desktop companion is rendered on a dedicated transparent canvas layered above all OS windows. It is capable of moving along the periphery of the primary display or anchoring itself to a user-defined screen quad. It features multiple distinct visual presentation states managed by modular CSS sprite-sheet engines or runtime animation layers (e.g., Rive / Three.js).

### 3.2 Personality Configuration Engine

The companion's text outputs and behavioral prompts are driven by distinct, swappable persona templates. The core product supports three foundational templates:

* **The Cybernetic Monitor (Default):** Analytical, direct, robotic, and neutral. Focuses heavily on metric tracking, time-remaining countdowns, and optimal resource distribution.
* **The Sarcastic Rival:** High-energy, biting, witty, and mockingly combative. Inspired by classic JRPG rivals. It leverages sharper dialogue choices when procrastination patterns are detected.
* **The Zen Master:** Calm, encouraging, mindful, and gentle. Focuses on stress reduction, breaking large tasks into micro-steps, and prompting ergonomic or hydration breaks.

### 3.3 The Gamification Loop & Survival Metrics

To encourage behavioral modification, the companion tracks a local state machine representing its "Vitals."

* **Focus Points (FP):** A metric ranging from 0 to 100. FP naturally degrades over time when deadlines are active. It regenerates rapidly when active workspace titles match target keywords.
* **Experience Points (XP) & Level:** Completing tasks parsed via WhatsApp awards XP. Reaching level milestones unlocks alternative animations, asset cosmetics, and new persona modules.
* **Evolution State:** The pet physically transforms (e.g., micro-drone to humanoid mech, or egg to mature beast) across specific XP thresholds, anchoring long-term user retention to real-world task closure.

---

## 4. System Architecture & Technical Stack Specifications

The complete product runs locally on the user's machine as a decoupled, multi-process suite. This layout guarantees that heavy AI transformations or UI updates do not compromise OS stability or user workflows.

| Component | Technology | Implementation Detail | Runtime Context |
| --- | --- | --- | --- |
| **Frontend UI** | Tauri Framework v2, Svelte/Vite, TailwindCSS | Transparent, borderless window with native window click-through event loops via Rust bindings. | Main GUI Process |
| **Ingestion Node** | `rmyndharis/OpenWA` | Headless Puppeteer engine wrapping WhatsApp Web within an independent Docker container. | Local Network Service |
| **Backend Core** | Python 3.11+, FastAPI, Uvicorn | Event routing, state computation, OS shell lifecycle tracking, scheduling, and local IPC. | Local Background Worker |
| **AI Gateway** | LiteLLM | Unified translation layer routing abstract inputs to Gemini, Grok, NVIDIA NIM, or Ollama. | Integrated in Backend |
| **Vector Index** | `RyanCodrai/turbovec` | Embedded TurboQuant compressed vector engine tracking task contexts without external servers. | Memory & Disk Flat File |

---

## 5. Functional Requirements by Module

### 5.1 Module A: Ingestion Layer (WhatsApp Gateway & Webhook Router)

* **Req-A.1:** The system must mount a self-hosted `OpenWA` service instance. Upon initial startup, the desktop client provides an automated wizard displaying the terminal-generated QR code inside a UI frame, enabling immediate mobile link confirmation.
* **Req-A.2:** The gateway must trap incoming text and audio voice messages from authorized telephone numbers specified in the local secure configuration file (`config.json`). Messages from unauthorized phone numbers must be silently dropped.
* **Req-A.3:** Upon event receipt, the gateway must execute an asynchronous HTTP POST mutation payload to the local FastAPI server endpoint (`/api/v1/webhook/ingest`). The payload format must conform strictly to the structure outlined below:

```json
{
  "sender": "919876543210",
  "message_id": "WA-MSG-99812A",
  "timestamp": 1781124300,
  "message_type": "text",
  "content": "Finish documenting the API endpoints by 6 PM today, priority high"
}

```

### 5.2 Module B: Orchestration Brain & LLM Routing Architecture

* **Req-B.1:** The backend must deploy `LiteLLM` to manage token transmission across diverse remote and local model configurations (Gemini, Grok, NVIDIA NIM, or local Ollama instances).
* **Req-B.2:** When processing inbound unstructured WhatsApp texts, the backend must query LiteLLM with a structured schema constraint system. The system message must explicitly bundle the current localized system timestamp to ground temporal parsing logic.
* **Req-B.3:** The parsing pipeline must process relative terms (e.g., "in an hour", "tonight", "tomorrow morning") and transform them into absolute ISO 8601 timestamps before updating the database.
* **Req-B.4:** The AI gateway must support automated fallback handling. If a preferred cloud model returns an HTTP status code `429` (Rate Limited) or `503` (Service Unavailable), the system must step down through a sequence defined in the application's configuration profile.

```
[Preferred API: Grok] ──(Fail: 429/503)──► [Secondary API: Gemini] ──(Fail)──► [Local Fallback: Ollama/Gemma]

```

### 5.3 Module C: Long-Term Semantic Memory Engine (`turbovec`)

* **Req-C.1:** Task entities, user interactions, and past context summaries must be mapped into dense vector spaces using a lightweight embedding model (e.g., `all-MiniLM-L6-v2`) via LiteLLM or local transformers.
* **Req-C.2:** The resulting vector matrices must be indexed locally using `turbovec` to benefit from its inline quantization algorithms, preserving RAM performance.
* **Req-C.3:** When a user queries their companion via WhatsApp regarding previous actions (e.g., *"What did I finish last Thursday?"*), the backend must execute a cosine similarity search against the local `.tv` file index to extract related contextual payloads and synthesize a response.

### 5.4 Module D: Ambient Tracking & Process Sentinel

* **Req-D.1:** The backend must run a highly optimized, non-blocking polling sequence every 30 seconds. This worker must determine the focused foreground application window using native OS platform hooks:
* **Windows:** `GetForegroundWindow` and `GetWindowTextW` via `ctypes`.
* **macOS:** `NSWorkspace.shared.activeApplication` via PyObjC layer bindings.


* **Req-D.2:** To protect privacy and system performance, full multimodal screen capture operations must remain inactive during normal operation. The system must evaluate workspace compliance based solely on window title string inspection. Full-frame OCR or vision models are restricted exclusively to on-demand troubleshooting queries manually triggered by user hotkeys (`Ctrl + Shift + C`).
* **Req-D.3:** The backend must check window title metadata against the user's active task array using string distance matching and keyword clustering. If an active task is labeled "Refactor Database," and the active window title contains strings like `VS Code`, `PostgreSQL`, or `StackOverflow`, the state is classified as `COMPLIANT`. If the window title reads `Cyberpunk 2077` or `YouTube - Game Stream`, the state scales to `DEVIANT`.

### 5.5 Module E: Transparent Desktop Overlay UI (`Tauri` Host)

* **Req-E.1:** The Tauri application shell must instantiate a single webview with strict display declarations: `transparent: true`, `decorations: false`, `always_on_top: true`, and `resizable: false`.
* **Req-E.2:** The Rust background runtime loop must invoke platform-specific low-level bindings to enforce absolute mouse click-through behavior across transparent pixels:
* **Windows:** Modifying window extended styles using `SetWindowLongW` with `WS_EX_TRANSPARENT` and `WS_EX_LAYERED` flags.
* **macOS:** Setting the window style mask to ignore mouse events via `setIgnoresMouseEvents:YES`.


* **Req-E.3:** The HTML/CSS frontend canvas layer must capture mouse coordinates. When hovering directly over opaque pixel assets representing the animated avatar body, the UI layer must toggle click-through behavior *off* via Tauri IPC, allowing the user to click, drag, or interact with the pet. When the cursor exits the avatar boundaries, click-through behavior must instantly re-engage.

---

## 6. Detailed Implementation Phases & Milestones

```
+---------------------------------------------------------------------------------------+
| PHASE 1: THE FLOATING SHELL (Weeks 1-3)                                               |
| Scaffold Tauri core, establish transparent click-through mechanics, inject mock state. |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| PHASE 2: THE WHATSAPP PIPELINE (Weeks 4-6)                                            |
| Deploy OpenWA container, design FastAPI webhook, map structured LLM schemas.           |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| PHASE 3: THE MONITOR & SENTINEL (Weeks 7-9)                                           |
| Code native OS window observers, implement TurboVec memory, calibrate math metrics.   |
+---------------------------------------------------------------------------------------+
|                                          |
                                           v
+---------------------------------------------------------------------------------------+
| PHASE 4: THE HELPER MATURATION (Weeks 10-12)                                          |
| Integrate on-demand screen grabbers, assemble hotkey hooks, bundle sidecar installer. |
+---------------------------------------------------------------------------------------+

```

### 6.1 Phase 1: Core Lifecycle & Transparent Stage (The Floating Shell)

* **Objective:** Form the core desktop display canvas and ensure flawless cross-platform alpha-channel transparency and input filtering.
* **Deliverables:**
1. Tauri configuration file (`tauri.conf.json`) with specialized multi-window declarations.
2. Rust core window event hooks mapping mouse positional matrices to window intercept configurations.
3. A lightweight Svelte/Vite UI codebase loaded with basic visual assets representing standard state loops (Idle, Move, Cheer).



### 6.2 Phase 2: Asynchronous Messaging Pipeline (The WhatsApp Core)

* **Objective:** Assemble the incoming task parsing topology and bridge the phone-to-desktop communication gap.
* **Deliverables:**
1. Docker multi-container configurations (`docker-compose.yml`) coordinating the automated `OpenWA` service environment.
2. FastAPI endpoint handlers accepting incoming webhook inputs and applying validation keys.
3. LiteLLM integration architecture parsing tasks into structured format layouts via strict temperature-minimized model configurations.



### 6.3 Phase 3: Passive Sentinel & Behavioral Diagnostics (The Monitor)

* **Objective:** Build the local monitoring loops and implement the mathematical scoring mechanics that govern the companion's behavior.
* **Deliverables:**
1. Platform-native C-binding modules tracking application window identifiers without causing system lag.
2. An embedded `turbovec` infrastructure script archiving data entries to local files.
3. A state-computation thread running inside the background worker that calculates the **Procrastination Severity Index ($S_p$)** dynamically every 30 seconds.



### 6.4 Phase 4: Interactive Multimodal Vision & Feature Maturation (The Helper)

* **Objective:** Deploy interactive toolsets and wrap the complete application suite into a unified production distribution build.
* **Deliverables:**
1. Global keyboard shortcut hook implementations catching regional desktop screen slice configurations.
2. Multimodal vision payload handling via LiteLLM using high-performance, low-latency models like `gemini-3.5-flash`.
3. A unified `PyInstaller` sidecar compilation pipeline that packages the Python engine cleanly inside a native Tauri bundle distribution package (`.msi`, `.dmg`).



---

## 7. Comprehensive System Workflow Examples

### 7.1 Mathematical Model for Focus Tracking

To ensure objective, mathematically validated state transitions before running the LLM dialogue generation routines, the system implements a continuous tracking formula. Let $S_p$ represent the calculated **Procrastination Severity Index**:

$$S_p = \alpha \cdot \left(\frac{T_{\text{elapsed}}}{T_{\text{deadline}} - T_{\text{start}}}\right) + \beta \cdot D_{\text{weight}} + \gamma \cdot (1 - \eta)$$

Where:

* $\alpha, \beta, \gamma$ represent normalized weights configured via the active personality profile ($\alpha + \beta + \gamma = 1.0$).
* $T_{\text{elapsed}}$ specifies the total active run duration of the target task in seconds.
* $T_{\text{deadline}} - T_{\text{start}}$ represents the total allocated operational timeframe.
* $D_{\text{weight}}$ represents a static categorical deviation penalty score assigned to the currently focused window group (e.g., Development/IDE = `0.0`, Inactive/Idle = `0.3`, Social Media/Entertainment = `0.9`).
* $\eta$ describes a running operational productivity index generated from task checkpoint updates completed via WhatsApp over the past 30 minutes.

### 7.2 Example Sequence A: Happy Path (Task Logging and Success Loop)

1. **Ingestion:** The user sends a text message to their phone's WhatsApp client: *"Need to deploy the server patch by 3 PM today."*
2. **Processing:** OpenWA intercepts the transmission. The message drops into the FastAPI backend. LiteLLM routes it to `gemini-3.5-flash` with a current datetime context string. The system outputs a clean database entity: `Task(title="Deploy server patch", target="15:00", status="pending")`.
3. **Synchronization:** FastAPI passes this entity payload to Tauri via a local websocket channel. The UI companion switches from its resting configuration to its "Focused Workspace" configuration. A small text overlay displays near the pet: *"Target locked: Server Patch deployment due at 3:00 PM."*
4. **Monitoring:** The user launches their terminal emulator and opens their codebase inside an active editor window. The background tracking thread records window identifiers like `bash - deploy_script.sh` and `VS Code`. The process matching algorithm registers a high programmatic coherence score.
5. **Reinforcement:** The pet transitions into an encouraging animation state (e.g., sitting down with protective tracking goggles on). It refrains from pushing intrusive text notifications to the display.
6. **Resolution:** The user completes their deployment and texts their WhatsApp bot account: *"Done with the patch."* The task status changes to `RESOLVED` in the database, the local vector index updates, and the desktop pet executes an optimistic celebration sequence while adding 50 XP to the user's focus profile.

### 7.3 Example Sequence B: Negative Path (Procrastination Detection and Escallation Loop)

```
[User Opens YouTube Game Stream] 
       │
       ▼
[Sentinel Engine Tracks Title Change] ──(30-Second Interval Check)──► [Matches Active Task: "Deploy Server Patch"]
                                                                                   │
                                                                                   ▼
[Tauri Forces Avatar to Center Display] ◄── (Calculates High Sp Score) ◄── [Window Flags Deviancy: Weight 0.9]

```

1. **Deviation:** While working on the server patch, the user opens a browser tab to view a gaming stream. The window title switches to `YouTube - Elden Ring Speedrun - Google Chrome`.
2. **Interception:** The process observer thread polls the foreground window title 30 seconds later and extracts this string. It compares the token attributes against the active goal ("Deploy server patch"). The matching matrix flags an optimization mismatch, setting the deviation weight $D_{\text{weight}}$ to `0.9`.
3. **Calculation:** The background manager computes the Procrastination Severity score ($S_p$). Because the 3:00 PM deadline is rapidly approaching, the time-delta variable amplifies the output, pushing $S_p$ beyond the critical escalation threshold of `0.75`.
4. **Dialogue Selection:** The backend passes the system state context array to the chosen personality provider (e.g., Grok using `xai/grok-2` or a similar conversational layer). The target instruction set restricts generation parameters to a short, humorous, yet sharp intervention comment matching the selected "Sarcastic Rival" persona.
5. **Intervention execution:** The backend pushes the chosen interaction token down the websocket pipeline. The Tauri desktop container overrides its click-through properties for the duration of the notification event. The avatar icon jumps directly to the center-right section of the display, fires a pulsing visual particle sequence, and spawns a styled dialogue element: *"Hey! Is that Elden Ring boss going to write your deployment scripts for you? Close the tab!"*
6. **Return to Compliance:** The user closes the browser tab and returns to their terminal screen. The observer records the title adjustment on its next execution check, lowers the severity classification value, and commands the desktop avatar to move back to its peripheral tracking spot.

---

## 8. Data Schemas, API Endpoints & State Machine Definitions

To facilitate code building by AI tools, this section outlines the database entities, interface definitions, and state machine transitions exactly.

### 8.1 Core Data Entity Schemas (SQLAlchemy / Pydantic Baseline)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

class TaskEntity(BaseModel):
    task_id: str = Field(description="Unique UUID generated locally for tracking.")
    raw_source_text: str = Field(description="The unprocessed text payload ingested from WhatsApp.")
    clean_title: str = Field(description="The LLM-extracted summary title of the objective.")
    deadline_epoch: int = Field(description="Absolute target unix timestamp for tracking expiration.")
    priority_level: Literal["low", "medium", "high", "critical"] = "medium"
    status_state: Literal["pending", "active", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

class UserConfigSchema(BaseModel):
    selected_provider: Literal["gemini", "openrouter", "nvidia_nim", "grok", "ollama"] = "gemini"
    target_model_name: str = "gemini-3.5-flash"
    active_persona_profile: Literal["cybernetic", "rival", "zen"] = "cybernetic"
    polling_frequency_seconds: int = 30
    authorized_phone_number: str = Field(description="Target phone string to filter incoming webhooks.")
    gamification_level: int = 1
    accumulated_experience: int = 0

```

### 8.2 API Router Architecture (FastAPI Declarations)

#### `POST /api/v1/webhook/ingest`

* **Purpose:** Accepts event streams routed from the `OpenWA` WhatsApp container.
* **Payload Signature:**
```json
{
  "sender": "string",
  "message_id": "string",
  "timestamp": 1781124300,
  "message_type": "text",
  "content": "string"
}

```


* **Response Codes:**
* `202 Accepted`: Payload verified and dispatched to the ingestion worker.
* `401 Unauthorized`: Sender phone sequence validation mismatch.



#### `GET /api/v1/companion/state`

* **Purpose:** Returns the current visual and behavioral configuration data requested by the Tauri frontend UI layer.
* **Response Payload Structure:**
```json
{
  "display_animation_frame": "nagging_critical",
  "active_bubble_dialogue": "Close that web browser window immediately!",
  "focus_points_balance": 34,
  "current_level": 4,
  "experience_progress_percentage": 68.5
}

```



#### `POST /api/v1/companion/vision-trigger`

* **Purpose:** Receives localized desktop image clips captured during explicit hotkey operations to run contextual RAG analyses.
* **Payload Signature:** Multipart Form Data containing a binary image blob alongside an optional explicit prompt text string.
* **Response Payload Structure:**
```json
{
  "analysis_success": true,
  "remediation_suggestion": "The compilation error is caused by a missing semicolon on line 42 of main.rs. Click here to apply the fix."
}

```



### 8.3 Companion UI State Chart

The Tauri application switches its layout rendering components based on state directives transmitted via the local system event loop:

| Base State | Transition Trigger | Target Sub-State | Window Parameters |
| --- | --- | --- | --- |
| **`STATE_IDLE`** | Application start; empty task database queues. | `idle_loop` | Click-Through: `TRUE`. Window Transparency: `100%`. Window Level: Native Desktop Layer. |
| **`STATE_WORKING`** | Active task initialized; system observes compliant window title paths. | `focus_mode_active` | Click-Through: `TRUE`. Window Transparency: `80%`. Pet renders with structural focus indicators. |
| **`STATE_WARNING`** | Procrastination index scores evaluate between `0.4` and `0.7`. | `nagging_mild` | Click-Through: `FALSE` on avatar boundaries only. Short screen pokes and dialogue loops execute. |
| **`STATE_CRITICAL`** | Procrastination index scores evaluate above `0.7`. | `nagging_severe` | Click-Through: `FALSE` completely for 3 seconds. Companion blocks screen elements via shake animations. |
| **`STATE_INTERACTIVE`** | Hotkey sequence intercept (`Ctrl + Shift + C`). | `vision_capture` | Click-Through: `FALSE`. Screen background darkens with a crosshair cursor selector frame. |

---

## 9. Non-Functional Requirements & Guardrails

### 9.1 Performance Metrics & Target Budgets

To maintain continuous background operations without interfering with performance-heavy user activities like gaming or software compilation, the software package must operate within strict resource budgets:

* **Memory Footprint:** The combined background footprint of the Tauri front-end process, Rust core, and Python worker threads must not exceed **120MB of RAM** during idle or monitoring cycles.
* **Processor Utilization:** Continuous system polling loops must consume less than **1.5% of total CPU utilization** on standard modern hardware profiles (e.g., AMD Ryzen 5 or Intel Core i5 architectures from 2024 onwards).
* **Inter-Process Communication (IPC) Latency:** System event messages flowing across the Python FastAPI core web-socket loop to the Rust/Tauri window renderer must process in under **45 milliseconds**.
* **Model Execution Latency:** Dialogue generation passes routed via LiteLLM to selected cloud providers must optimize token counts to ensure text presentation occurs within **600 milliseconds** of a deviation event flag.

### 9.2 Privacy Protocols & Local-First Isolation

Given the sensitive nature of background application monitoring and personal data collection, the codebase must enforce absolute privacy guardrails:

* **Local Event Scope:** Raw strings parsed from window headers or operating system metadata must reside strictly within volatile application process memory bounds. These strings must never be serialized to permanent disk logs or transmitted over external network sockets.
* **Data Minimization:** Text packages transmitted to cloud inference endpoints (e.g., Gemini, Grok) must be minimized to filter out personal identifiable identifiers (PII), local folder path naming conventions, or sensitive financial sequences before submission.
* **Vector Isolation:** The `turbovec` binary vector dataset files (`.tv`) containing historical task archives, interaction summaries, and workspace context indexes must be saved exclusively onto the user's localized encrypted user profile directories.

### 9.3 Open Source Contribution & Distribution Protocols

To scale the app into a mature open-source product, the project layout must conform to standardized distribution rules:

* **Sidecar Compilation Pipeline:** The deployment script must leverage Tauri's native sidecar capabilities. The entire Python execution suite, along with its dependent virtual libraries, must be frozen via a `PyInstaller` process into a self-contained binary file. This file must package cleanly within the final Tauri installer envelope (`.msi` for Windows, `.dmg` for macOS platforms).
* **Zero-Config Executables:** End-users must not be forced to install independent system dependencies, standalone python environments, or manual runtime engines. Double-clicking the native application package must provision the entire operational surface, launch the isolated background workers, and spawn the transparent companion canvas immediately.
* **Open Testing Coverage:** The backend test pipeline must enforce rigorous mock configurations for all cloud components. Contributors must be capable of executing localized testing suites (`pytest`) and verifying system state tracking engines using synthetic webhook inputs without connecting to actual live premium WhatsApp instances or paid cloud AI API endpoints.

---

## 10. Verification & Quality Assurance Matrix

The following table defines the functional validation criteria that must be passed before any automated build is promoted to an alpha release stage:

| Test Reference | Targeted Component | Verification Strategy | Expected Pass Condition |
| --- | --- | --- | --- |
| **VAL-01** | Ingestion Pipeline | Fire a synthetic JSON mock payload matching an `OpenWA` webhook message into `/api/v1/webhook/ingest`. | The task is cleanly written to the local database, and a structured, parsed JSON representation appears in the log streams within 500ms. |
| **VAL-02** | Alpha Transparency | Boot the Tauri UI bundle above an open video player or graphics benchmarking engine. | The desktop avatar renders cleanly with zero artifact borders or alpha blending defects. Visual elements below the transparent zones remain perfectly visible. |
| **VAL-03** | Click Penetration | Position the avatar image on top of a desktop shortcuts array or an active IDE window. Click directly through a transparent region of the app window. | The click passes through instantly, focusing the underlying folder or line of code. Clicking directly on an opaque pixel of the avatar opens the pet profile menu. |
| **VAL-04** | Failover Matrix | Revoke local network access to the primary preferred API endpoint (e.g., Grok) while keeping an alternate provider (e.g., Gemini) active. Trigger a task event. | The system catches the connectivity exception, switches endpoints via the LiteLLM fallback tree, and processes the text without dropping the task. |

---

## 11. Final Directives for VS Code Copilot Engineering

When instructed by the user to begin implementation, follow the steps below precisely:

1. **Initialize the Project Root:** Construct a monorepo containing a `/src-tauri` workspace folder for the Rust UI runtime alongside an isolated `/backend` path for the FastAPI engine.
2. **Generate the Configuration Profile:** Construct the baseline `config.json` system properties payload according to the specifications in Section 8.1.
3. **Establish the Local IPC Interface:** Implement the WebSocket channel framework connecting the Svelte frontend canvas to the Python background observer layer before adding advanced visual character sprites.

**This document represents the complete, frozen specification profile for Project ChronosPet v1.0.0.** Proceed directly to repository scaffolding.