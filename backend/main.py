"""
ChronosPet Backend Core — FastAPI Orchestration Engine
=====================================================
Handles webhook ingestion, LLM task parsing with fallback routing,
ambient window monitoring, gamification state, and WebSocket IPC
to the Tauri desktop companion.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    HTTPException, status, File, UploadFile, Form,
)
from fastapi.middleware.cors import CORSMiddleware

from litellm import Router as LiteLLMRouter
from turbovec import memory_db
from models import (
    TaskEntity, TaskUpdatePayload, WebhookPayload,
    UserConfigSchema, CompanionState, LLMParsedTask,
)
from sentinel import (
    get_active_window_title, calculate_severity_index,
    evaluate_window_compliance, get_rich_activity_description,
    extract_browser_context,
)
from vision_analyzer import capture_screen, analyze_screen, analyze_screen_local_ocr, VisionResult, vision_cache
from dotenv import load_dotenv

# Load environment variables from the root .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chronospet")

# ─── Configuration ────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent.parent / "config.json"

try:
    with open(CONFIG_PATH, "r") as f:
        config_data = json.load(f)
        system_config = UserConfigSchema(**config_data)
    logger.info(f"Config loaded from {CONFIG_PATH}")
except FileNotFoundError:
    system_config = UserConfigSchema()
    logger.warning(f"Config not found at {CONFIG_PATH}, using defaults.")

# ─── LiteLLM Router with Fallback Chain (PRD Req-B.4) ─────────────
def build_llm_router(config: UserConfigSchema) -> Optional[LiteLLMRouter]:
    """
    Build a LiteLLM Router with ordered fallback models.
    If primary returns 429/503, it steps down through the chain.
    """
    model_list = []
    for model_name in config.llm_fallback_models:
        model_list.append({
            "model_name": "chronospet-llm",
            "litellm_params": {"model": model_name},
        })

    if not model_list:
        # Single model fallback
        model_list.append({
            "model_name": "chronospet-llm",
            "litellm_params": {"model": config.target_model_name},
        })

    try:
        router = LiteLLMRouter(
            model_list=model_list,
            num_retries=2,
            retry_after=5,
            fallbacks=[],  # All models share "chronospet-llm" name so Router load-balances automatically
            set_verbose=False,
        )
        logger.info(f"LLM Router initialized with {len(model_list)} model(s): "
                     f"{[m['litellm_params']['model'] for m in model_list]}")
        return router
    except Exception as e:
        logger.error(f"LLM Router init failed: {e}")
        return None

llm_router = build_llm_router(system_config)

# ─── In-Memory Task Database ─────────────────────────────────────
db_tasks: Dict[str, TaskEntity] = {}

# ─── Gamification State ──────────────────────────────────────────
gamification = {
    "level": system_config.gamification_level,
    "xp": system_config.accumulated_experience,
    "evolution_stage": "drone",
}

EVOLUTION_STAGES = ["drone", "scout", "sentinel", "guardian", "titan"]

def calculate_level(xp: int) -> int:
    """Determine level from XP using configured thresholds."""
    thresholds = system_config.xp_level_thresholds
    level = 1
    for i, threshold in enumerate(thresholds):
        if xp >= threshold:
            level = i + 1
        else:
            break
    return level

def calculate_evolution(level: int) -> str:
    """Map level to evolution stage."""
    idx = min((level - 1) // 2, len(EVOLUTION_STAGES) - 1)
    return EVOLUTION_STAGES[idx]

def calculate_xp_progress(xp: int, level: int) -> float:
    """Calculate XP progress percentage within current level."""
    thresholds = system_config.xp_level_thresholds
    if level >= len(thresholds):
        return 100.0
    current_threshold = thresholds[level - 1] if level > 0 else 0
    next_threshold = thresholds[level] if level < len(thresholds) else thresholds[-1] + 500
    if next_threshold <= current_threshold:
        return 100.0
    return round(((xp - current_threshold) / (next_threshold - current_threshold)) * 100, 1)

def award_xp(amount: int):
    """Award XP and recalculate level/evolution."""
    gamification["xp"] += amount
    gamification["level"] = calculate_level(gamification["xp"])
    gamification["evolution_stage"] = calculate_evolution(gamification["level"])
    logger.info(f"XP awarded: +{amount} → Total: {gamification['xp']}, "
                f"Level: {gamification['level']}, Stage: {gamification['evolution_stage']}")


# ─── WebSocket Connection Manager ────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"UI connected via WebSocket ({len(self.active_connections)} total)")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"UI disconnected ({len(self.active_connections)} remaining)")

    async def broadcast_state(self, state: dict):
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_json(state)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

manager = ConnectionManager()


# ─── Build Current Companion State ───────────────────────────────
def build_companion_state(
    animation: str = "idle_loop",
    dialogue: str = "",
    focus: int = 100,
) -> dict:
    """Build a complete companion state payload for WebSocket broadcast."""
    active_count = len([t for t in db_tasks.values() if t.status_state in ("pending", "active")])
    return CompanionState(
        display_animation_frame=animation,
        active_bubble_dialogue=dialogue,
        focus_points_balance=focus,
        current_level=gamification["level"],
        experience_progress_percentage=calculate_xp_progress(gamification["xp"], gamification["level"]),
        evolution_stage=gamification["evolution_stage"],
        active_tasks_count=active_count,
    ).model_dump()


# ─── Persona Dialogue Templates ──────────────────────────────────
PERSONA_TEMPLATES = {
    "cybernetic": {
        "compliant": "Operational efficiency nominal. Target: {task}.",
        "warning": "Alert: Deviation detected. Return to {task}. Sp={sp:.0%}.",
        "critical": "CRITICAL: Sp={sp:.0%}. Terminate {window} immediately. Objective: {task}.",
        "idle": "Systems nominal. Awaiting task assignment.",
        "celebrate": "Task resolved. +{xp}XP awarded. Performance: optimal.",
    },
    "rival": {
        "compliant": "Not bad... keep it up with {task}. Don't slack off.",
        "warning": "Seriously? {window}? Get back to {task} before I lose respect.",
        "critical": "Pathetic! Sp={sp:.0%}! Is {window} going to finish {task} for you?! CLOSE IT!",
        "idle": "Waiting around, huh? Bet you can't even handle a real task.",
        "celebrate": "Fine, +{xp}XP. I'll admit it—you actually finished something.",
    },
    "zen": {
        "compliant": "You're in flow with {task}. Breathe deeply. You're doing great.",
        "warning": "Gently notice: you've drifted to {window}. Return to {task} when you're ready.",
        "critical": "Take a breath. {window} isn't serving you right now. {task} awaits with patience.",
        "idle": "Be present. When a task calls, you'll be ready.",
        "celebrate": "Wonderful. +{xp}XP. Celebrate this moment of completion.",
    },
}

def get_dialogue(state: str, **kwargs) -> str:
    """Get persona-appropriate dialogue for a given state."""
    persona = system_config.active_persona_profile
    templates = PERSONA_TEMPLATES.get(persona, PERSONA_TEMPLATES["cybernetic"])
    template = templates.get(state, "")
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


# ─── Productivity Index Calculator ────────────────────────────────
def calculate_productivity_index() -> float:
    """
    η = ratio of completed tasks in the last 30 minutes to total active tasks.
    Returns value between 0.0 and 1.0.
    """
    now = time.time()
    thirty_min_ago = now - 1800

    recent_completions = sum(
        1 for t in db_tasks.values()
        if t.status_state == "completed"
        and t.resolved_at
        and t.resolved_at.timestamp() >= thirty_min_ago
    )
    total_active = sum(
        1 for t in db_tasks.values()
        if t.status_state in ("pending", "active", "completed")
    )

    if total_active == 0:
        return 1.0  # No tasks = fully productive (nothing to procrastinate on)

    return min(1.0, recent_completions / max(1, total_active))


# ─── Persona Weights for Sp Calculation ───────────────────────────
PERSONA_WEIGHTS = {
    "cybernetic": (0.4, 0.4, 0.2),
    "rival": (0.3, 0.5, 0.2),
    "zen": (0.5, 0.2, 0.3),
}


# ─── Ambient Activity Logger ─────────────────────────────────────
def log_activity(window_title: str, d_weight: float, sp_score: float, task_title: str, vision_result: Optional[VisionResult] = None):
    """
    Write a human-readable ambient activity entry to logs/activity.log.
    Uses the smart sentinel classifier for per-browser-tab and per-app descriptions.
    """
    try:
        status_label, description = get_rich_activity_description(window_title, task_title, d_weight, vision_result)
    except Exception:
        status_label = "🟡 NEUTRAL"
        description = f"Active: \"{window_title.strip()[:60]}\""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = (
        f"{timestamp} │ {status_label:<18} │ Sp={sp_score:.2f} │ "
        f"Task: [{task_title[:30]}] │ {description}\n"
    )
    if vision_result and vision_result.reasoning:
        log_line += f"          \033[90mLLM: \"{vision_result.reasoning}\"\033[0m\n"

    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    activity_log_path = logs_dir / "activity.log"

    try:
        with open(activity_log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
        logger.info(f"ACTIVITY │ {status_label} │ {description}")
    except Exception as e:
        logger.error(f"Failed to write to activity.log: {e}")


# ─── Sentinel Background Loop ────────────────────────────────────
async def process_sentinel_loop():
    """
    Non-blocking polling loop (PRD Req-D.1) that runs every N seconds,
    checks the foreground window, computes Sp, and broadcasts state to UI.
    """
    logger.info("Sentinel loop started.")
    try:
        while True:
            # Always fetch window title at the top so it's available in all branches
            window_title = get_active_window_title() or "Unknown"
            active_tasks = [t for t in db_tasks.values() if t.status_state in ("pending", "active")]

            if active_tasks:
                current_time = int(time.time())

                # Use the most recent active task
                active_task = active_tasks[-1]

                # Time calculations (PRD Section 7.1)
                elapsed = current_time - int(active_task.created_at.timestamp())
                total_alloc = active_task.deadline_epoch - int(active_task.created_at.timestamp())

                # If vision or local OCR is enabled, we check the cache or call analyzer
                vision_result = None
                if system_config.vision_enabled or system_config.ocr_enabled:
                    vision_result = vision_cache.get(system_config.vision_min_interval_seconds)
                    if not vision_result:
                        try:
                            # Capture screen first
                            image_bytes = await asyncio.to_thread(capture_screen)
                            
                            if system_config.vision_enabled:
                                # Gemini multimodal LLM analysis
                                vision_result = await asyncio.to_thread(
                                    analyze_screen,
                                    image_bytes,
                                    active_task.clean_title,
                                    window_title,
                                    llm_router
                                )
                            else:
                                # Native local OCR analysis (runs async)
                                vision_result = await analyze_screen_local_ocr(
                                    image_bytes,
                                    active_task.clean_title,
                                    window_title
                                )
                            
                            vision_cache.set(vision_result)
                        except Exception as e:
                            logger.warning(f"Screen context analysis failed, falling back to keyword: {e}")

                # Deviation weight from window compliance
                d_weight = evaluate_window_compliance(window_title, active_task.clean_title, vision_result)

                # Real productivity index
                eta = calculate_productivity_index()

                # Persona-specific weights
                alpha, beta, gamma_w = PERSONA_WEIGHTS.get(
                    system_config.active_persona_profile, (0.4, 0.4, 0.2)
                )

                sp_score = calculate_severity_index(
                    elapsed, total_alloc, d_weight, eta,
                    alpha=alpha, beta=beta, gamma=gamma_w,
                )

                # Log to the dedicated ambient activity log
                try:
                    log_activity(window_title, d_weight, sp_score, active_task.clean_title, vision_result)
                except Exception as ex:
                    logger.error(f"Failed to log ambient activity: {ex}")

                # State transitions per PRD Section 8.3
                if sp_score > 0.7:
                    state = build_companion_state(
                        animation="nagging_severe",
                        dialogue=get_dialogue("critical",
                            task=active_task.clean_title,
                            window=window_title,
                            sp=sp_score,
                        ),
                        focus=max(0, 100 - int(sp_score * 100)),
                    )
                    logger.warning(f"STATE_CRITICAL | Sp={sp_score} | Window='{window_title}'")
                elif sp_score > 0.4:
                    state = build_companion_state(
                        animation="nagging_mild",
                        dialogue=get_dialogue("warning",
                            task=active_task.clean_title,
                            window=window_title,
                            sp=sp_score,
                        ),
                        focus=max(0, 100 - int(sp_score * 50)),
                    )
                else:
                    state = build_companion_state(
                        animation="focus_mode_active",
                        dialogue=get_dialogue("compliant", task=active_task.clean_title),
                        focus=100,
                    )

                await manager.broadcast_state(state)
            else:
                # No active tasks — log idle window + broadcast idle state
                try:
                    log_activity(window_title, 0.3, 0.0, "(idle — no active task)")
                except Exception as ex:
                    logger.error(f"Failed to log idle ambient activity: {ex}")

                await manager.broadcast_state(
                    build_companion_state(
                        animation="idle_loop",
                        dialogue=get_dialogue("idle"),
                    )
                )

            await asyncio.sleep(system_config.polling_frequency_seconds)
    except asyncio.CancelledError:
        logger.info("Sentinel loop terminated.")


def load_tasks_from_vector_db():
    """Load all task vectors from ChromaDB into the in-memory database on startup."""
    if not memory_db.is_ready:
        logger.warning("ChromaDB not ready, skipping task loading.")
        return
    
    try:
        results = memory_db.collection.get()
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        count = 0
        for idx in range(len(ids)):
            task_id = ids[idx]
            raw_text = documents[idx]
            meta = metadatas[idx] or {}
            
            created_at_val = meta.get("created_at") or time.time()
            resolved_at_val = meta.get("resolved_at")
            
            created_at_dt = datetime.fromtimestamp(float(created_at_val))
            resolved_at_dt = datetime.fromtimestamp(float(resolved_at_val)) if resolved_at_val else None
            
            # Retrieve status: if not present, default to pending
            status_val = meta.get("status_state", "pending")
            
            task = TaskEntity(
                task_id=task_id,
                raw_source_text=raw_text,
                clean_title=meta.get("clean_title", "Untitled Task"),
                deadline_epoch=int(meta.get("deadline", time.time() + 3600)),
                priority_level=meta.get("priority", "medium"),
                status_state=status_val,
                created_at=created_at_dt,
                resolved_at=resolved_at_dt
            )
            db_tasks[task_id] = task
            count += 1
        logger.info(f"Loaded {count} task(s) from ChromaDB vector storage.")
    except Exception as e:
        logger.error(f"Failed to load tasks from ChromaDB: {e}")


# ─── Application Lifespan ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load existing tasks from ChromaDB vector database
    load_tasks_from_vector_db()

    sentinel_task = asyncio.create_task(process_sentinel_loop())
    logger.info("━━━ ChronosPet Backend Online ━━━")
    yield
    sentinel_task.cancel()
    try:
        await sentinel_task
    except asyncio.CancelledError:
        pass


# ─── FastAPI App ──────────────────────────────────────────────────
app = FastAPI(
    title="ChronosPet Core",
    version="1.0.0",
    description="Ambient Desktop Companion — Backend Orchestration Engine",
    lifespan=lifespan,
)

# CORS — allow Tauri webview and local dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health Check ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "vector_store": memory_db.is_ready,
        "llm_router": llm_router is not None,
        "active_tasks": len([t for t in db_tasks.values() if t.status_state in ("pending", "active")]),
        "total_tasks": len(db_tasks),
        "uptime_config": {
            "provider": system_config.selected_provider,
            "model": system_config.target_model_name,
            "persona": system_config.active_persona_profile,
        },
    }


@app.get("/")
async def root():
    return {"status": "ChronosPet Backend Active", "version": "1.0.0"}


# ─── Webhook Ingestion (PRD Req-A.3, Module A) ───────────────────
@app.post("/api/v1/webhook/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_webhook(payload: WebhookPayload):
    """
    Accepts event streams from OpenWA WhatsApp gateway.
    Parses unstructured text into a structured TaskEntity via LLM.
    """
    # Security: verify sender phone (PRD Req-A.2)
    if payload.sender != system_config.authorized_phone_number:
        logger.warning(f"Unauthorized sender rejected: {payload.sender}")
        raise HTTPException(status_code=401, detail="Unauthorized sender")

    logger.info(f"Webhook received: '{payload.content}' from {payload.sender}")

    # Check for task completion commands
    completion_keywords = ["done", "finished", "completed", "resolved"]
    if any(kw in payload.content.lower() for kw in completion_keywords):
        # Try to resolve the most recent active task
        active_tasks = [t for t in db_tasks.values() if t.status_state in ("pending", "active")]
        if active_tasks:
            task = active_tasks[-1]
            task.status_state = "completed"
            task.resolved_at = datetime.utcnow()
            award_xp(system_config.xp_per_task_completion)

            # Update ChromaDB vector metadata
            try:
                resolved_ts = task.resolved_at.timestamp() if task.resolved_at else None
                memory_db.embed_and_store(
                    text=task.raw_source_text,
                    metadata={
                        "task_id": task.task_id,
                        "clean_title": task.clean_title,
                        "deadline": task.deadline_epoch,
                        "priority": task.priority_level,
                        "status_state": task.status_state,
                        "created_at": task.created_at.timestamp(),
                        "resolved_at": resolved_ts,
                    }
                )
            except Exception as ex:
                logger.error(f"Failed to update task vector on completion webhook: {ex}")

            await manager.broadcast_state(
                build_companion_state(
                    animation="celebrating",
                    dialogue=get_dialogue("celebrate", xp=system_config.xp_per_task_completion),
                    focus=100,
                )
            )
            return {"message": f"Task '{task.clean_title}' marked complete!", "task_id": task.task_id, "xp_awarded": system_config.xp_per_task_completion}

    # Parse task via LLM with fallback chain (PRD Req-B.1/B.2/B.3)
    current_time = int(time.time())
    system_prompt = (
        f"You are a task extraction engine. Extract a structured task from the user's message.\n"
        f"Current Unix timestamp: {current_time}\n"
        f"Current datetime: {datetime.utcnow().isoformat()}Z\n"
        f"Rules:\n"
        f"- Convert relative times ('in an hour', 'tonight', 'tomorrow morning') to absolute Unix timestamps.\n"
        f"- 'tonight' = today at 21:00, 'tomorrow morning' = tomorrow at 09:00.\n"
        f"- If no deadline mentioned, default to 1 hour from now ({current_time + 3600}).\n"
        f"- Infer priority from urgency words: 'ASAP'/'urgent'→critical, 'important'→high, default→medium.\n"
        f"- Return clean JSON matching the schema exactly."
    )

    parsed_task_data = None

    if llm_router:
        try:
            # Use LiteLLM Router for automatic fallback (PRD Req-B.4)
            response = llm_router.completion(
                model="chronospet-llm",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": payload.content},
                ],
                response_format={
                    "type": "json_object",
                },
                temperature=0.0,
            )
            raw_content = response.choices[0].message.content
            parsed_task_data = json.loads(raw_content)
            logger.info(f"LLM parsed task: {parsed_task_data}")
        except Exception as e:
            logger.error(f"LLM parsing failed across all fallbacks: {e}")

    # Fallback: create task from raw text if LLM fails
    if not parsed_task_data:
        logger.info("Using local fallback parser (no LLM available)")
        words = payload.content.strip().split()
        parsed_task_data = {
            "clean_title": " ".join(words[:8]) if len(words) > 8 else payload.content.strip(),
            "deadline_epoch": current_time + 3600,
            "priority_level": "high" if any(w.lower() in ("urgent", "asap", "critical") for w in words) else "medium",
        }

    new_task = TaskEntity(
        task_id=str(uuid.uuid4()),
        raw_source_text=payload.content,
        clean_title=parsed_task_data.get("clean_title", "Untitled Task"),
        deadline_epoch=parsed_task_data.get("deadline_epoch", current_time + 3600),
        priority_level=parsed_task_data.get("priority_level", "medium"),
        status_state="pending",
    )

    db_tasks[new_task.task_id] = new_task
    logger.info(f"Task created: [{new_task.priority_level.upper()}] {new_task.clean_title} (id={new_task.task_id[:8]}...)")

    # Store in vector memory (Module C)
    memory_db.embed_and_store(
        text=new_task.raw_source_text,
        metadata={
            "task_id": new_task.task_id,
            "clean_title": new_task.clean_title,
            "deadline": new_task.deadline_epoch,
            "priority": new_task.priority_level,
            "status_state": new_task.status_state,
            "created_at": new_task.created_at.timestamp(),
        }
    )

    # Broadcast to UI
    await manager.broadcast_state(
        build_companion_state(
            animation="focus_mode_active",
            dialogue=f"Target locked: {new_task.clean_title}",
            focus=100,
        )
    )

    return {
        "message": "Task ingested successfully",
        "task_id": new_task.task_id,
        "parsed": {
            "title": new_task.clean_title,
            "deadline": new_task.deadline_epoch,
            "priority": new_task.priority_level,
        },
    }


# ─── Task CRUD ────────────────────────────────────────────────────
@app.get("/api/v1/tasks")
async def list_tasks(status_filter: Optional[str] = None):
    """List all tasks, optionally filtered by status."""
    tasks = list(db_tasks.values())
    if status_filter:
        tasks = [t for t in tasks if t.status_state == status_filter]
    return {"tasks": [t.model_dump() for t in tasks], "total": len(tasks)}


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID."""
    if task_id not in db_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_tasks[task_id].model_dump()


@app.patch("/api/v1/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdatePayload):
    """Update task fields. Completing a task awards XP."""
    if task_id not in db_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = db_tasks[task_id]
    update_data = update.model_dump(exclude_none=True)

    # Check if we're completing the task
    completing = (
        update_data.get("status_state") == "completed"
        and task.status_state != "completed"
    )

    for field, value in update_data.items():
        setattr(task, field, value)

    if completing:
        task.resolved_at = datetime.utcnow()
        award_xp(system_config.xp_per_task_completion)
        await manager.broadcast_state(
            build_companion_state(
                animation="celebrating",
                dialogue=get_dialogue("celebrate", xp=system_config.xp_per_task_completion),
                focus=100,
            )
        )

    # Update in ChromaDB vector memory
    try:
        resolved_ts = task.resolved_at.timestamp() if task.resolved_at else None
        memory_db.embed_and_store(
            text=task.raw_source_text,
            metadata={
                "task_id": task.task_id,
                "clean_title": task.clean_title,
                "deadline": task.deadline_epoch,
                "priority": task.priority_level,
                "status_state": task.status_state,
                "created_at": task.created_at.timestamp(),
                "resolved_at": resolved_ts,
            }
        )
    except Exception as ex:
        logger.error(f"Failed to update task vector on API update: {ex}")

    return {"message": "Task updated", "task": task.model_dump()}


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its vector."""
    if task_id not in db_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = db_tasks.pop(task_id)
    memory_db.delete(task_id)
    return {"message": f"Task '{task.clean_title}' deleted"}


# ─── Companion State Endpoint (PRD Section 8.2) ──────────────────
@app.get("/api/v1/companion/state")
async def get_companion_state():
    """Returns the current visual and behavioral configuration for the Tauri frontend."""
    active_tasks = [t for t in db_tasks.values() if t.status_state in ("pending", "active")]
    if active_tasks:
        dialogue = f"Tracking {len(active_tasks)} task(s). Primary: {active_tasks[-1].clean_title}"
    else:
        dialogue = get_dialogue("idle")

    return build_companion_state(
        animation="focus_mode_active" if active_tasks else "idle_loop",
        dialogue=dialogue,
    )


# ─── Gamification Endpoint ────────────────────────────────────────
@app.get("/api/v1/companion/gamification")
async def get_gamification():
    """Returns current XP, level, and evolution state."""
    return {
        "level": gamification["level"],
        "xp": gamification["xp"],
        "evolution_stage": gamification["evolution_stage"],
        "xp_progress": calculate_xp_progress(gamification["xp"], gamification["level"]),
        "xp_to_next_level": (
            system_config.xp_level_thresholds[gamification["level"]]
            if gamification["level"] < len(system_config.xp_level_thresholds)
            else None
        ),
    }


# ─── Vector Memory Search ────────────────────────────────────────
@app.get("/api/v1/memory/search")
async def search_memory(q: str, top_k: int = 5):
    """Semantic search over task history (PRD Req-C.3)."""
    results = memory_db.query(q, top_k=top_k)
    return {"query": q, "results": results}


# ─── Debug / Observability Endpoints ─────────────────────────────
@app.post("/api/v1/debug/sentinel-poll")
async def force_sentinel_poll():
    """Force an immediate sentinel window-check and activity log write. Useful for testing without waiting for the poll interval."""
    window_title = get_active_window_title() or "Unknown"
    active_tasks = [t for t in db_tasks.values() if t.status_state in ("pending", "active")]

    if active_tasks:
        active_task = active_tasks[-1]
        current_time = int(time.time())
        elapsed = current_time - int(active_task.created_at.timestamp())
        total_alloc = active_task.deadline_epoch - int(active_task.created_at.timestamp())
        
        # Call screen analysis if enabled
        vision_result = None
        if system_config.vision_enabled or system_config.ocr_enabled:
            try:
                image_bytes = await asyncio.to_thread(capture_screen)
                if system_config.vision_enabled:
                    vision_result = await asyncio.to_thread(
                        analyze_screen,
                        image_bytes,
                        active_task.clean_title,
                        window_title,
                        llm_router
                    )
                else:
                    vision_result = await analyze_screen_local_ocr(
                        image_bytes,
                        active_task.clean_title,
                        window_title
                    )
            except Exception as e:
                logger.warning(f"Screen poll analysis failed: {e}")

        d_weight = evaluate_window_compliance(window_title, active_task.clean_title, vision_result)
        eta = calculate_productivity_index()
        alpha, beta, gamma_w = PERSONA_WEIGHTS.get(system_config.active_persona_profile, (0.4, 0.4, 0.2))
        sp_score = calculate_severity_index(elapsed, total_alloc, d_weight, eta, alpha=alpha, beta=beta, gamma=gamma_w)
        log_activity(window_title, d_weight, sp_score, active_task.clean_title, vision_result)
        return {
            "window": window_title,
            "active_task": active_task.clean_title,
            "d_weight": d_weight,
            "sp_score": sp_score,
            "vision_result": vision_result.model_dump() if vision_result else None,
            "logged": True,
        }
    else:
        log_activity(window_title, 0.3, 0.0, "(idle — no active task)")
        return {"window": window_title, "active_task": None, "logged": True}


@app.get("/api/v1/debug/vision-snapshot")
async def get_vision_snapshot():
    """Takes a screenshot right now, runs vision analysis, and returns the raw VisionResult JSON."""
    active_tasks = [t for t in db_tasks.values() if t.status_state in ("pending", "active")]
    task_title = active_tasks[-1].clean_title if active_tasks else "No active task"
    window_title = get_active_window_title() or "Unknown"
    
    try:
        image_bytes = await asyncio.to_thread(capture_screen)
        vision_result = await asyncio.to_thread(
            analyze_screen,
            image_bytes,
            task_title,
            window_title,
            llm_router
        )
        return {
            "success": True,
            "task_title": task_title,
            "window_title": window_title,
            "result": vision_result.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision snapshot analysis failed: {str(e)}")


@app.get("/api/v1/debug/ocr-snapshot")
async def get_ocr_snapshot():
    """Takes a screenshot right now, runs local WinRT OCR, and returns the analysis."""
    active_tasks = [t for t in db_tasks.values() if t.status_state in ("pending", "active")]
    task_title = active_tasks[-1].clean_title if active_tasks else "No active task"
    window_title = get_active_window_title() or "Unknown"
    
    try:
        image_bytes = await asyncio.to_thread(capture_screen)
        vision_result = await analyze_screen_local_ocr(
            image_bytes,
            task_title,
            window_title
        )
        return {
            "success": True,
            "task_title": task_title,
            "window_title": window_title,
            "result": vision_result.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local OCR snapshot failed: {str(e)}")


@app.get("/api/v1/debug/activity-log")
async def get_activity_log(lines: int = 50):
    """Return last N lines of the ambient activity log for quick inspection."""
    log_path = Path(__file__).parent.parent / "logs" / "activity.log"
    if not log_path.exists():
        return {"exists": False, "lines": []}
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:]
        return {"exists": True, "total_lines": len(all_lines), "lines": [l.rstrip() for l in tail]}
    except Exception as e:
        return {"exists": True, "error": str(e), "lines": []}


# ─── Vision Trigger (PRD Section 8.2) ────────────────────────────
@app.post("/api/v1/companion/vision-trigger")
async def process_vision_trigger(
    prompt: str = Form("Analyze this screen context regarding my current task."),
    file: UploadFile = File(...),
):
    """
    Receives desktop image clips from the Ctrl+Shift+C hotkey.
    Runs multimodal analysis via LLM.
    """
    logger.info(f"Vision trigger: {file.filename} | prompt: {prompt}")

    image_bytes = await file.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    if not llm_router:
        raise HTTPException(status_code=503, detail="LLM Router not available")

    try:
        response = llm_router.completion(
            model="chronospet-llm",
            messages=[
                {
                    "role": "system",
                    "content": "You are ChronosPet, analyzing a user's desktop screenshot to help with their current task.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                },
            ],
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Vision analysis processing failed.")

    await manager.broadcast_state(
        build_companion_state(
            animation="vision_capture",
            dialogue=analysis[:200],  # Truncate for UI bubble
            focus=100,
        )
    )

    return {"analysis_success": True, "remediation_suggestion": analysis}


# ─── WebSocket Endpoint ──────────────────────────────────────────
@app.websocket("/ws/companion")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send initial state on connect
    try:
        state = build_companion_state(
            animation="idle_loop",
            dialogue=get_dialogue("idle"),
        )
        await websocket.send_json(state)
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WS received: {data}")

            # Handle ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
