import ctypes
import time
import logging
import re
from typing import Optional, List

logger = logging.getLogger(__name__)

# ─── Windows API Setup ────────────────────────────────────────────
try:
    user32 = ctypes.windll.user32
except AttributeError:
    user32 = None
    logger.warning("Windows user32 API not available. Window tracking will not function on this OS.")

def get_active_window_title() -> Optional[str]:
    """Uses Windows native APIs to get the text of the foreground window (Req-D.1)."""
    if not user32:
        return None

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return None

    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)

    return buff.value if buff.value else None


def calculate_severity_index(
    elapsed_sec: int,
    total_allocated_sec: int,
    deviation_weight: float,
    productivity_index: float,
    alpha: float = 0.4,
    beta: float = 0.4,
    gamma: float = 0.2,
) -> float:
    """
    Procrastination Severity Index (PRD Section 7.1):
    Sp = α*(T_elapsed / (T_deadline - T_start)) + β*D_weight + γ*(1 - η)

    Weights are configurable per persona profile:
    - Cybernetic: α=0.4, β=0.4, γ=0.2 (balanced)
    - Rival:      α=0.3, β=0.5, γ=0.2 (punishes deviation harder)
    - Zen:        α=0.5, β=0.2, γ=0.3 (focuses on time + wellbeing)
    """
    # Guard against division by zero (task with 0 allocated time)
    if total_allocated_sec <= 0:
        time_ratio = 1.0  # Treat as fully elapsed = maximum urgency
    else:
        time_ratio = min(1.0, max(0.0, elapsed_sec / total_allocated_sec))

    # Clamp inputs to valid ranges
    deviation_weight = min(1.0, max(0.0, deviation_weight))
    productivity_index = min(1.0, max(0.0, productivity_index))

    sp = (alpha * time_ratio) + (beta * deviation_weight) + (gamma * (1.0 - productivity_index))
    return round(sp, 4)


# ─── Deviation Classification ────────────────────────────────────

# Keyword banks for window compliance evaluation
DEVIANT_KEYWORDS = [
    "youtube", "twitter", "reddit", "netflix", "twitch", "instagram",
    "facebook", "tiktok", "discord", "game", "steam", "epic games",
    "spotify", "hulu", "disney+", "crunchyroll", "anime",
    "cyberpunk", "elden ring", "valorant", "minecraft", "fortnite",
]

COMPLIANT_KEYWORDS = [
    "code", "visual studio", "vs code", "vscode", "terminal",
    "cmd", "powershell", "bash", "git", "github", "gitlab",
    "stackoverflow", "stack overflow", "docs", "documentation",
    "jira", "confluence", "notion", "obsidian", "figma",
    "postman", "insomnia", "pgadmin", "datagrip", "mongodb",
    "jupyter", "notebook", "pycharm", "intellij", "webstorm",
    "sublime", "vim", "neovim", "emacs", "atom",
]

NEUTRAL_WEIGHT = 0.3


def extract_task_keywords(task_title: str) -> List[str]:
    """Extract meaningful keywords from a task title for dynamic compliance matching."""
    # Remove common stop words
    stop_words = {"the", "a", "an", "to", "by", "for", "in", "on", "at", "of", "and", "or", "is", "it", "my"}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', task_title.lower())
    return [w for w in words if w not in stop_words]


def evaluate_window_compliance(window_title: str, task_title: str) -> float:
    """
    Returns a deviation weight D_weight between 0.0 (compliant) and 1.0 (deviant).
    Uses keyword matching + dynamic task-keyword extraction (PRD Req-D.3).
    """
    title_lower = window_title.lower()

    # Check deviant keywords first (high priority)
    if any(k in title_lower for k in DEVIANT_KEYWORDS):
        return 0.9

    # Check compliant keywords
    if any(k in title_lower for k in COMPLIANT_KEYWORDS):
        return 0.0

    # Dynamic: check if any task-specific keywords appear in the window title
    task_keywords = extract_task_keywords(task_title)
    if task_keywords and any(k in title_lower for k in task_keywords):
        return 0.05  # Very likely on-task

    # Neutral / unknown application
    return NEUTRAL_WEIGHT
