from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal, List

# ─── Core Task Entity ─────────────────────────────────────────────
class TaskEntity(BaseModel):
    task_id: str = Field(default="", description="Unique UUID generated locally for tracking.")
    raw_source_text: str = Field(default="", description="The unprocessed text payload ingested from WhatsApp.")
    clean_title: str = Field(default="Untitled Task", description="The LLM-extracted summary title of the objective.")
    deadline_epoch: int = Field(default=0, description="Absolute target unix timestamp for tracking expiration.")
    priority_level: Literal["low", "medium", "high", "critical"] = "medium"
    status_state: Literal["pending", "active", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

# ─── Task Update (PATCH) ──────────────────────────────────────────
class TaskUpdatePayload(BaseModel):
    clean_title: Optional[str] = None
    priority_level: Optional[Literal["low", "medium", "high", "critical"]] = None
    status_state: Optional[Literal["pending", "active", "completed", "failed"]] = None
    deadline_epoch: Optional[int] = None

# ─── User Configuration ───────────────────────────────────────────
class UserConfigSchema(BaseModel):
    selected_provider: Literal["gemini", "openrouter", "nvidia_nim", "grok", "ollama"] = "gemini"
    target_model_name: str = "gemini-1.5-flash"
    active_persona_profile: Literal["cybernetic", "rival", "zen"] = "cybernetic"
    polling_frequency_seconds: int = 30
    authorized_phone_number: str = Field(default="919876543210", description="Target phone string to filter incoming webhooks.")
    gamification_level: int = 1
    accumulated_experience: int = 0
    vision_enabled: bool = False
    ocr_enabled: bool = False
    vision_min_interval_seconds: int = 30
    # LLM fallback chain
    llm_fallback_models: List[str] = Field(
        default=["gemini/gemini-1.5-flash", "openrouter/google/gemini-flash-1.5", "ollama/gemma2"],
        description="Ordered fallback model list for LiteLLM Router."
    )
    # OpenWA
    openwa_gateway_url: str = "http://localhost:8080"
    # XP thresholds
    xp_per_task_completion: int = 50
    xp_level_thresholds: List[int] = Field(
        default=[0, 100, 300, 600, 1000, 1500, 2200, 3000, 4000, 5500],
        description="Cumulative XP required for each level."
    )

# ─── Webhook Ingest Payload ───────────────────────────────────────
class WebhookPayload(BaseModel):
    sender: str
    message_id: str
    timestamp: int
    message_type: str = "text"
    content: str

# ─── Companion Visual State ───────────────────────────────────────
class CompanionState(BaseModel):
    display_animation_frame: str = "idle_loop"
    active_bubble_dialogue: str = ""
    focus_points_balance: int = 100
    current_level: int = 1
    experience_progress_percentage: float = 0.0
    evolution_stage: str = "drone"  # drone → scout → sentinel → guardian → titan
    active_tasks_count: int = 0

# ─── LLM Parsed Task Schema (for response_format) ─────────────────
class LLMParsedTask(BaseModel):
    """Schema sent to LLM for structured task extraction."""
    clean_title: str = Field(description="A concise 3-8 word summary of the task objective.")
    deadline_epoch: int = Field(description="Absolute unix timestamp for the task deadline. Use the provided current timestamp to resolve relative times.")
    priority_level: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Priority inferred from urgency keywords in the message."
    )
