import ctypes
import time
import logging
import re
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from vision_analyzer import VisionResult

logger = logging.getLogger(__name__)

# ─── Windows API Setup ────────────────────────────────────────────
try:
    user32 = ctypes.windll.user32
except AttributeError:
    user32 = None
    logger.warning("Windows user32 API not available. Window tracking will not function on this OS.")

import os
from ctypes import wintypes

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


def get_active_process_name_and_id() -> Tuple[Optional[str], Optional[int]]:
    """Uses Windows native APIs to get the executable name and process ID of the active foreground window."""
    if not user32:
        return None, None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None
    
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_id = pid.value
    if not process_id:
        return None, None
        
    # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_process = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id)
    if not h_process:
        return None, process_id
        
    try:
        size = ctypes.c_ulong(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            full_path = buf.value
            process_name = os.path.basename(full_path)
            return process_name, process_id
    except Exception as e:
        logger.warning(f"Error querying process name for PID {process_id}: {e}")
    finally:
        ctypes.windll.kernel32.CloseHandle(h_process)
        
    return None, process_id


def get_window_structural_text(hwnd: int) -> str:
    """Uses Windows EnumChildWindows to construct a lightweight structural text tree of visible text elements."""
    if not user32 or not hwnd:
        return ""
    
    texts = []
    def enum_child_proc(child_hwnd, lparam):
        # Retrieve window class name
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(child_hwnd, class_name, 256)
        
        # Retrieve window text
        length = user32.GetWindowTextLengthW(child_hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(child_hwnd, buff, length + 1)
            text_val = buff.value.strip()
            if text_val:
                texts.append(f"[{class_name.value}] {text_val}")
        return True
    
    # Callback type definition
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    callback = WNDENUMPROC(enum_child_proc)
    
    # Run enumeration
    user32.EnumChildWindows(hwnd, callback, 0)
    
    # Return a condensed representation (first 50 text snippets to keep it lightweight)
    return "\n".join(texts[:50])


def calculate_severity_index(
    elapsed_sec: int,
    total_allocated_sec: int,
    deviation_weight: float,
    productivity_index: float = 1.0,
    alpha: float = 0.4,
    beta: float = 0.4,
    gamma: float = 0.2,
    delta: float = 0.85,
    task_id: Optional[str] = None,
    s_prev: Optional[float] = None,
) -> float:
    """
    Procrastination Severity Index:
    Uses the new historical decay formula:
    Sp = delta * S_prev + (1 - delta) * [ w_d * (1 - T_remain/T_total) ]
    If task_id or s_prev is not provided, defaults to compliant alpha/beta/gamma formula to preserve backward compatibility.
    """
    if total_allocated_sec <= 0:
        time_ratio = 1.0
    else:
        time_ratio = min(1.0, max(0.0, elapsed_sec / total_allocated_sec))

    deviation_weight = min(1.0, max(0.0, deviation_weight))
    
    # Check if we should use the new decay-based calculation (if task_id or s_prev is given)
    if task_id is not None or s_prev is not None:
        if s_prev is None:
            from turbovec import memory_db
            s_prev = memory_db.register_cache.get(task_id, 0.0) if memory_db else 0.0
            
        sp = delta * s_prev + (1.0 - delta) * (deviation_weight * time_ratio)
        sp = min(1.0, max(0.0, sp))
        
        # Update register cache in turbovec
        if task_id is not None:
            from turbovec import memory_db
            if memory_db:
                memory_db.register_cache[task_id] = sp
        return round(sp, 4)

    # Backward compatibility with the old test suite/scoring formula
    productivity_index = min(1.0, max(0.0, productivity_index))
    sp = (alpha * time_ratio) + (beta * deviation_weight) + (gamma * (1.0 - productivity_index))
    return round(sp, 4)


# ─── Browser Content Extraction ──────────────────────────────────

# Browser suffixes used to strip the browser name from the page title
BROWSER_SUFFIXES = [
    (" - Google Chrome", "Chrome"),
    (" - Chromium", "Chromium"),
    (" - Microsoft Edge", "Edge"),
    (" – Microsoft Edge", "Edge"),
    (" — Mozilla Firefox", "Firefox"),
    (" - Mozilla Firefox", "Firefox"),
    (" - Opera", "Opera"),
    (" - Brave", "Brave"),
    (" - Vivaldi", "Vivaldi"),
]

# YouTube entertainment/distraction signal words (in video titles)
YT_DISTRACTION_SIGNALS = [
    "funny", "meme", "memes", "prank", "fails", "compilation", "shorts",
    "vlog", "reaction", "reacting", "gaming", "gameplay", "playthrough",
    "let's play", "speedrun", "highlights", "music video", "mv", "official video",
    "trailer", "teaser", "interview", "podcast", "asmr", "relaxing",
    "gta", "minecraft", "roblox", "valorant", "fortnite", "cod", "warzone",
    "among us", "chess", "fifa", "nba", "cricket", "ipl", "bollywood",
    "web series", "episode", "season", "netflix", "amazon prime", "hotstar",
    "download", "free", "crack", "hack", "cheat", "mod", "glitch",
    "top 10", "top 5", "ranking", "tier list", "vs", "challenge", "exposed",
    "roast", "drama", "storytime", "explained | hindi", "explained | tamil",
]

# YouTube study/focused signal words
YT_FOCUSED_SIGNALS = [
    "tutorial", "lecture", "course", "explained", "learn", "learning",
    "how to", "programming", "coding", "python", "javascript", "algorithm",
    "data structure", "machine learning", "ai", "neural", "physics", "chemistry",
    "mathematics", "math", "calculus", "algebra", "statistics", "biology",
    "engineering", "circuit", "embedded", "microcontroller", "arduino",
    "raspberry pi", "linux", "networking", "cybersecurity", "database",
    "sql", "docker", "kubernetes", "cloud", "aws", "azure", "gcp",
    "mit", "stanford", "nptel", "nptelhrd", "freecodecamp", "the odin project",
    "computerphile", "3blue1brown", "khan academy", "crashcourse",
    "assignment", "exam", "project", "lab", "practical", "experiment",
    "research", "paper", "thesis", "dissertation", "notes", "study",
    "revision", "university", "college", "school", "iit", "nit",
]

# PDF classification signals
PDF_DISTRACTION_SIGNALS = [
    "recipe", "novel", "fiction", "manga", "comic", "lyrics", "magazine",
]
PDF_FOCUSED_SIGNALS = [
    "textbook", "syllabus", "notes", "lecture", "paper", "report",
    "thesis", "research", "assignment", "manual", "datasheet", "specification",
    "exam", "question", "solution", "numerical", "problem", "chapter",
    "module", "unit", "lab", "practical",
]


def extract_browser_context(window_title: str) -> Optional[Dict]:
    """
    If the foreground window is a browser, extracts the actual page title and
    metadata (domain, content type, is_youtube, is_pdf, etc.)
    
    Returns None if it's not a recognized browser.
    """
    page_title = window_title
    browser_name = None

    for suffix, name in BROWSER_SUFFIXES:
        if suffix in window_title:
            browser_name = name
            page_title = window_title[:window_title.rfind(suffix)].strip()
            break

    if not browser_name:
        return None

    page_lower = page_title.lower()

    # ── YouTube detection ──────────────────────────────────────────
    is_youtube = "youtube" in page_lower
    video_title = None
    if is_youtube:
        # Format: "{video_title} - YouTube" or just "YouTube"
        if " - youtube" in page_lower:
            video_title = re.sub(r"\s*-?\s*youtube\s*$", "", page_title, flags=re.IGNORECASE).strip()
        elif page_lower == "youtube":
            video_title = None  # Home page
        else:
            video_title = page_title

    # ── PDF detection ─────────────────────────────────────────────
    is_pdf = page_title.lower().endswith(".pdf") or " - pdf" in page_lower or "pdf viewer" in page_lower

    # ── Other domain signals ───────────────────────────────────────
    domain_signals = {
        "github.com": "GitHub",
        "stackoverflow": "Stack Overflow",
        "docs.google": "Google Docs",
        "drive.google": "Google Drive",
        "notion.so": "Notion",
        "figma.com": "Figma",
        "reddit.com": "Reddit",
        "twitter.com": "Twitter/X",
        "x.com": "Twitter/X",
        "instagram.com": "Instagram",
        "facebook.com": "Facebook",
        "netflix.com": "Netflix",
        "twitch.tv": "Twitch",
        "discord.com": "Discord",
        "chat.openai": "ChatGPT",
        "claude.ai": "Claude AI",
        "gemini.google": "Gemini AI",
        "leetcode.com": "LeetCode",
        "hackerrank.com": "HackerRank",
        "geeksforgeeks": "GeeksForGeeks",
        "mdn": "MDN Web Docs",
        "w3schools": "W3Schools",
        "arxiv": "arXiv Paper",
        "wikipedia": "Wikipedia",
        "coursera": "Coursera",
        "udemy": "Udemy Course",
        "udacity": "Udacity",
        "medium.com": "Medium Article",
        "dev.to": "Dev.to Article",
        "npmjs": "npm Registry",
        "pypi": "PyPI",
        "hub.docker": "Docker Hub",
        "google.com/search": "Google Search",
    }

    detected_site = None
    for key, label in domain_signals.items():
        if key in page_lower:
            detected_site = label
            break

    return {
        "browser": browser_name,
        "page_title": page_title,
        "is_youtube": is_youtube,
        "video_title": video_title,
        "is_pdf": is_pdf,
        "detected_site": detected_site,
    }


def classify_youtube_video(video_title: str, task_title: str) -> Tuple[str, float, str]:
    """
    Classify a YouTube video title as FOCUSED, DISTRACTED, or NEUTRAL.
    Returns (status_label, d_weight, description)
    """
    title_lower = video_title.lower()
    task_keywords = extract_task_keywords(task_title)

    # Check if video seems task-related via dynamic keyword overlap
    if task_keywords and any(kw in title_lower for kw in task_keywords):
        return ("🟢 FOCUSED", 0.0, f"Watching study video: \"{video_title[:60]}\"")

    # Check focused signals in video title
    focused_matches = [s for s in YT_FOCUSED_SIGNALS if s in title_lower]
    distraction_matches = [s for s in YT_DISTRACTION_SIGNALS if s in title_lower]

    if focused_matches and not distraction_matches:
        return ("🟢 FOCUSED", 0.1, f"Watching educational video: \"{video_title[:60]}\"")
    elif distraction_matches and not focused_matches:
        return ("🔴 DISTRACTED", 0.95, f"Watching: \"{video_title[:60]}\"")
    elif focused_matches and distraction_matches:
        # Mixed signals — lean toward neutral/mild distraction
        return ("🟡 NEUTRAL", 0.45, f"Watching (mixed): \"{video_title[:60]}\"")
    else:
        # Unknown video, treat as mild distraction since YouTube itself is deviant
        return ("🟡 NEUTRAL", 0.6, f"Watching video: \"{video_title[:60]}\"")


def classify_pdf(page_title: str, task_title: str) -> Tuple[str, float, str]:
    """Classify a PDF based on its filename/title."""
    title_lower = page_title.lower()
    task_keywords = extract_task_keywords(task_title)

    if task_keywords and any(kw in title_lower for kw in task_keywords):
        return ("🟢 FOCUSED", 0.0, f"Reading task-related PDF: \"{page_title[:55]}\"")

    focused_matches = [s for s in PDF_FOCUSED_SIGNALS if s in title_lower]
    if focused_matches:
        return ("🟢 FOCUSED", 0.05, f"Reading academic/work PDF: \"{page_title[:55]}\"")

    distraction_matches = [s for s in PDF_DISTRACTION_SIGNALS if s in title_lower]
    if distraction_matches:
        return ("🔴 DISTRACTED", 0.85, f"Reading non-work PDF: \"{page_title[:55]}\"")

    return ("🟡 NEUTRAL", 0.3, f"Reading PDF: \"{page_title[:55]}\"")


def classify_browser_activity(ctx: Dict, task_title: str) -> Tuple[str, float, str]:
    """
    Full browser activity classification using extracted context.
    Returns (status_label, d_weight, human_readable_description)
    """
    page_title = ctx["page_title"]
    browser = ctx["browser"]

    # ── YouTube ───────────────────────────────────────────────────
    if ctx["is_youtube"]:
        video_title = ctx["video_title"]
        if not video_title:
            return ("🟡 NEUTRAL", 0.5, "On YouTube Home Page 📺")
        return classify_youtube_video(video_title, task_title)

    # ── PDF ───────────────────────────────────────────────────────
    if ctx["is_pdf"]:
        return classify_pdf(page_title, task_title)

    # ── Known sites ───────────────────────────────────────────────
    site = ctx.get("detected_site")
    if site:
        distraction_sites = {"Reddit", "Twitter/X", "Instagram", "Facebook", "Netflix", "Twitch", "Discord"}
        focus_sites = {"GitHub", "Stack Overflow", "LeetCode", "HackerRank", "GeeksForGeeks",
                       "MDN Web Docs", "W3Schools", "arXiv Paper", "Coursera", "Udemy Course",
                       "Udacity", "Dev.to Article", "PyPI", "npm Registry", "Docker Hub", "ChatGPT",
                       "Claude AI", "Gemini AI"}
        neutral_sites = {"Google Docs", "Google Drive", "Notion", "Figma", "Wikipedia",
                         "Google Search", "Medium Article"}

        if site in distraction_sites:
            return ("🔴 DISTRACTED", 0.9, f"On {site} ({browser}) — \"{page_title[:45]}\"")
        elif site in focus_sites:
            return ("🟢 FOCUSED", 0.05, f"On {site} ({browser}) — \"{page_title[:45]}\"")
        elif site in neutral_sites:
            # Check if page title relates to task
            task_kws = extract_task_keywords(task_title)
            if task_kws and any(kw in page_title.lower() for kw in task_kws):
                return ("🟢 FOCUSED", 0.1, f"On {site} (task-related) — \"{page_title[:40]}\"")
            return ("🟡 NEUTRAL", 0.3, f"On {site} — \"{page_title[:45]}\"")

    # ── Generic browser: use page title + task keyword matching ───
    title_lower = page_title.lower()
    task_keywords = extract_task_keywords(task_title)

    if task_keywords and any(kw in title_lower for kw in task_keywords):
        return ("🟢 FOCUSED", 0.05, f"Browsing (task-related): \"{page_title[:50]}\"")

    # Check compliant/deviant signals within the page title itself
    if any(k in title_lower for k in DEVIANT_KEYWORDS):
        return ("🔴 DISTRACTED", 0.9, f"Browsing (distraction): \"{page_title[:50]}\"")
    if any(k in title_lower for k in COMPLIANT_KEYWORDS):
        return ("🟢 FOCUSED", 0.1, f"Browsing (work-related): \"{page_title[:50]}\"")

    # Unknown page
    return ("🟡 NEUTRAL", 0.4, f"Browsing in {browser}: \"{page_title[:50]}\"")


# ─── Deviation Classification ────────────────────────────────────

# Keyword banks for window compliance evaluation
DEVIANT_KEYWORDS = [
    "youtube", "twitter", "reddit", "netflix", "twitch", "instagram",
    "facebook", "tiktok", "discord", "game", "steam", "epic games",
    "spotify", "hulu", "disney+", "crunchyroll", "anime",
    "cyberpunk", "elden ring", "valorant", "minecraft", "fortnite",
    "dogma", "gameplay", "trailer", "teaser", "walkthrough", "ign",
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
    stop_words = {"the", "a", "an", "to", "by", "for", "in", "on", "at", "of", "and", "or", "is", "it", "my"}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', task_title.lower())
    return [w for w in words if w not in stop_words]


def evaluate_window_compliance(
    window_title: str,
    task_title: str,
    vision_result: Optional[VisionResult] = None
) -> float:
    """
    Returns a deviation weight D_weight between 0.0 (compliant) and 1.0 (deviant).
    Now browser-aware: extracts actual page content for accurate classification.
    If vision_result is provided, uses its d_weight directly.
    """
    if vision_result is not None:
        return vision_result.d_weight

    # First check: is this a browser? If so, use deep classification
    ctx = extract_browser_context(window_title)
    if ctx:
        _, d_weight, _ = classify_browser_activity(ctx, task_title)
        return d_weight

    title_lower = window_title.lower()

    # Check deviant keywords first (high priority)
    if any(k in title_lower for k in DEVIANT_KEYWORDS):
        return 0.9

    # Dynamic: check if any task-specific keywords appear in the window title
    task_keywords = extract_task_keywords(task_title)
    if task_keywords and any(k in title_lower for k in task_keywords):
        return 0.05

    # Check if the active task is coding-related
    coding_task_indicators = {
        "code", "coding", "program", "programming", "develop", "development",
        "implement", "implementation", "debug", "debugging", "python", "javascript",
        "rust", "java", "cpp", "script", "project", "app", "website", "html", "css",
        "backend", "frontend", "git", "github", "api", "database", "sql", "deploy", "patch", "server", "test", "build"
    }
    is_coding_task = any(kw in task_title.lower() for kw in coding_task_indicators)

    # Check compliant keywords
    if any(k in title_lower for k in COMPLIANT_KEYWORDS):
        if is_coding_task:
            return 0.0
        else:
            # Coding tool active for a non-coding task is not productive
            return 0.6

    return NEUTRAL_WEIGHT


def get_rich_activity_description(
    window_title: str,
    task_title: str,
    d_weight: float,
    vision_result: Optional[VisionResult] = None
) -> Tuple[str, str]:
    """
    Returns (status_emoji_label, human_readable_activity_string) for logging.
    Browser windows get deep page-level analysis. Other apps get fast keyword classification.
    If vision_result is provided, returns its status and description.
    """
    if vision_result is not None:
        status_map = {
            "focused": "🟢 FOCUSED",
            "distracted": "🔴 DISTRACTED",
            "neutral": "🟡 NEUTRAL",
        }
        emoji = status_map.get(vision_result.status, "🟡 NEUTRAL")
        return emoji, vision_result.activity_description

    title_lower = window_title.lower()

    # ── Browser: deep analysis ────────────────────────────────────
    ctx = extract_browser_context(window_title)
    if ctx:
        status_label, _, description = classify_browser_activity(ctx, task_title)
        return status_label, description

    # ── Status label from d_weight ────────────────────────────────
    if d_weight >= 0.9:
        status_label = "🔴 DISTRACTED"
    elif d_weight <= 0.05:
        status_label = "🟢 FOCUSED"
    else:
        status_label = "🟡 NEUTRAL"

    # ── Non-browser apps ──────────────────────────────────────────
    if "antigravity" in title_lower:
        return status_label, "Coding with Antigravity IDE 🤖"
    elif "visual studio code" in title_lower or "vs code" in title_lower:
        # Extract the open file/project from VS Code title: "filename - project - Visual Studio Code"
        parts = [p.strip() for p in window_title.split(" - ") if p.strip()]
        if len(parts) >= 2:
            return status_label, f"Coding in VS Code — {parts[0]} 💻"
        return status_label, "Coding in VS Code 💻"
    elif "pycharm" in title_lower or "intellij" in title_lower or "webstorm" in title_lower:
        parts = [p.strip() for p in window_title.split(" – ") if p.strip()]
        ide_name = "PyCharm" if "pycharm" in title_lower else ("IntelliJ" if "intellij" in title_lower else "WebStorm")
        if len(parts) >= 2:
            return status_label, f"Coding in {ide_name} — {parts[0]} 💻"
        return status_label, f"Coding in {ide_name} 💻"
    elif "powershell" in title_lower or "cmd" in title_lower or "terminal" in title_lower or "bash" in title_lower or "wsl" in title_lower:
        return status_label, f"Working in Terminal ⌨️ — {window_title.strip()[:40]}"
    elif "discord" in title_lower:
        return "🔴 DISTRACTED", f"Chatting on Discord 💬"
    elif "spotify" in title_lower:
        # Spotify title: "Song Name - Artist" or just "Spotify"
        if " - " in window_title and "spotify" not in window_title.lower().split(" - ")[0]:
            song = window_title.split(" - Spotify")[0].strip() if " - Spotify" in window_title else window_title
            return "🟡 NEUTRAL", f"Listening: \"{song[:55]}\" on Spotify 🎵"
        return "🟡 NEUTRAL", "Listening to Spotify 🎵"
    elif "steam" in title_lower or any(g in title_lower for g in ["valorant", "minecraft", "fortnite", "gta", "elden ring", "cyberpunk"]):
        return "🔴 DISTRACTED", f"Gaming 🎮 — {window_title.strip()[:50]}"
    elif "zoom" in title_lower or "teams" in title_lower:
        return "🟡 NEUTRAL", "In a Meeting / Call 📞"
    elif "notion" in title_lower or "obsidian" in title_lower:
        return status_label, f"Writing Notes — {window_title.strip()[:45]} 📝"
    elif "figma" in title_lower:
        return status_label, f"Designing in Figma 🎨"
    elif "postman" in title_lower:
        return "🟢 FOCUSED", "Testing APIs in Postman 🔧"
    else:
        # Generic fallback: show the raw window title, cleaned up
        clean = window_title.strip()
        if len(clean) > 65:
            clean = clean[:62] + "..."
        return status_label, f"Active: \"{clean}\""
