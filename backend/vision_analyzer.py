import io
import json
import time
import base64
import logging
import threading
from typing import Optional, Literal
from pydantic import BaseModel
import mss
from PIL import Image

logger = logging.getLogger("chronospet.vision")

winrt_available = False
try:
    import winrt.windows.media.ocr as ocr
    import winrt.windows.graphics.imaging as imaging
    import winrt.windows.storage.streams as streams
    winrt_available = True
except ImportError:
    logger.warning("winrt modules not available. Local OCR will not function.")

class VisionResult(BaseModel):
    status: Literal["focused", "distracted", "neutral"]
    d_weight: float          # 0.0 = fully on task, 1.0 = completely off task
    activity_description: str  # e.g. "Watching 'How to download GTA V' on YouTube"
    reasoning: str           # e.g. "The screen shows a YouTube video unrelated to the task"
    confidence: float        # 0.0-1.0 — how sure the LLM is

class VisionCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_result: Optional[VisionResult] = None
        self._last_timestamp: float = 0.0

    def get(self, min_interval_seconds: int) -> Optional[VisionResult]:
        with self._lock:
            if self._last_result and (time.time() - self._last_timestamp < min_interval_seconds):
                return self._last_result
            return None

    def set(self, result: VisionResult):
        with self._lock:
            self._last_result = result
            self._last_timestamp = time.time()

vision_cache = VisionCache()

def capture_screen() -> bytes:
    """
    Captures the primary monitor screen and returns compressed JPEG bytes in memory.
    Screenshots are never saved to disk.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        sct_img = sct.grab(monitor)
        
        # Convert raw pixels from bgra format to RGB PIL Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        # Compress and save to in-memory bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        return buffer.getvalue()

def analyze_screen(
    image_bytes: bytes,
    task_title: str,
    window_title: str,
    llm_router
) -> VisionResult:
    """
    Calls Gemini vision model via the LiteLLM router with screen context and returns a VisionResult.
    """
    if not llm_router:
        raise ValueError("LLM Router not initialized")

    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        f"Analyze this desktop screenshot. Determine productivity compliance.\n"
        f"Current Task the user is working on: \"{task_title}\"\n"
        f"Current Active Window Title: \"{window_title}\"\n\n"
        f"Respond ONLY with a valid JSON object matching this schema:\n"
        f"{{\n"
        f"  \"status\": \"focused\" | \"distracted\" | \"neutral\",\n"
        f"  \"d_weight\": <float from 0.0 (perfect compliance) to 1.0 (total distraction)>,\n"
        f"  \"activity_description\": \"<one-sentence specific description of what the user is doing/watching, naming specific websites/videos/files seen on screen>\",\n"
        f"  \"reasoning\": \"<one-sentence reasoning explaining the status/d_weight relative to the task>\",\n"
        f"  \"confidence\": <float from 0.0 to 1.0>\n"
        f"}}\n"
        f"Do not include any markdown syntax wrapper like ```json. Return raw JSON text."
    )

    try:
        response = llm_router.completion(
            model="chronospet-llm",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict productivity monitor AI. You analyze screenshots to determine if the user is working "
                        "on their active task or if they are distracted (watching games/movies/social media/memes etc.). "
                        "You must return ONLY the requested JSON block."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        
        # Clean any accidental markdown wrap
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        result = VisionResult(**data)
        logger.info(f"Vision analysis completed successfully: {result.status} (d_weight={result.d_weight})")
        return result

    except Exception as e:
        logger.error(f"Vision analysis LLM/parsing call failed: {e}")
        raise

async def analyze_screen_local_ocr(
    image_bytes: bytes,
    task_title: str,
    window_title: str
) -> VisionResult:
    """
    Performs Windows native local OCR on screen, then runs keyword heuristics to evaluate compliance.
    """
    if not winrt_available:
        return VisionResult(
            status="neutral",
            d_weight=0.3,
            activity_description="Local OCR unavailable (winrt package not installed)",
            reasoning="WinRT dependencies are missing on this system.",
            confidence=1.0
        )
        
    try:
        # Create InMemoryRandomAccessStream
        stream = streams.InMemoryRandomAccessStream()
        writer = streams.DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(image_bytes)
        await writer.store_async()
        await writer.flush_async()
        
        stream.seek(0)
        decoder = await imaging.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        
        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            return VisionResult(
                status="neutral",
                d_weight=0.3,
                activity_description="Local OCR Engine failed to initialize",
                reasoning="Windows OcrEngine TryCreate failed.",
                confidence=1.0
            )
            
        start_time = time.time()
        result = await engine.recognize_async(bitmap)
        elapsed = time.time() - start_time
        
        ocr_text = result.text
        logger.info(f"Local WinRT OCR completed in {elapsed:.3f}s. Text length: {len(ocr_text)} chars.")
        
        # Run classification heuristics
        return evaluate_ocr_text_heuristics(ocr_text, task_title, window_title)
        
    except Exception as e:
        logger.error(f"Local OCR analysis failed: {e}")
        return VisionResult(
            status="neutral",
            d_weight=0.3,
            activity_description="Local OCR failed to analyze screen",
            reasoning=f"Error occurred during OCR: {str(e)}",
            confidence=0.0
        )

def evaluate_ocr_text_heuristics(ocr_text: str, task_title: str, window_title: str) -> VisionResult:
    from sentinel import (
        DEVIANT_KEYWORDS, COMPLIANT_KEYWORDS, extract_task_keywords,
        YT_DISTRACTION_SIGNALS, YT_FOCUSED_SIGNALS,
        PDF_DISTRACTION_SIGNALS, PDF_FOCUSED_SIGNALS
    )
    
    text_lower = ocr_text.lower()
    win_lower = window_title.lower()
    
    # Extract keywords from active task
    task_kws = extract_task_keywords(task_title)
    task_matches = [kw for kw in task_kws if kw in text_lower]
    
    # Check general deviant / compliant keywords on screen
    deviant_matches = [kw for kw in DEVIANT_KEYWORDS if kw in text_lower]
    compliant_matches = [kw for kw in COMPLIANT_KEYWORDS if kw in text_lower]
    
    # ── YouTube check ──────────────────────────────────────────────
    is_youtube = "youtube" in text_lower or "youtube" in win_lower
    yt_focused = False
    yt_distracted = False
    
    if is_youtube:
        focused_yt_matches = [s for s in YT_FOCUSED_SIGNALS if s in text_lower]
        distracted_yt_matches = [s for s in YT_DISTRACTION_SIGNALS if s in text_lower]
        if focused_yt_matches:
            yt_focused = True
        if distracted_yt_matches:
            yt_distracted = True
            
        if yt_distracted and not yt_focused:
            return VisionResult(
                status="distracted",
                d_weight=0.9,
                activity_description="Watching entertainment / deviant content on YouTube 📺",
                reasoning="OCR matched distraction signals (e.g. gameplay, gaming, download, funny) on YouTube page.",
                confidence=0.85
            )
        elif yt_focused:
            return VisionResult(
                status="focused",
                d_weight=0.05,
                activity_description="Watching educational tutorial / lecture on YouTube 📚",
                reasoning="OCR matched learning/lecture/tutorial keywords in the YouTube video context.",
                confidence=0.85
            )
        else:
            return VisionResult(
                status="neutral",
                d_weight=0.5,
                activity_description="Browsing YouTube 📺",
                reasoning="YouTube is open but screen text contains no definitive focus or distraction signals.",
                confidence=0.7
            )

    # ── PDF check ──────────────────────────────────────────────────
    is_pdf = ".pdf" in win_lower or "pdf viewer" in win_lower
    if is_pdf:
        focused_pdf_matches = [s for s in PDF_FOCUSED_SIGNALS if s in text_lower]
        distracted_pdf_matches = [s for s in PDF_DISTRACTION_SIGNALS if s in text_lower]
        
        if focused_pdf_matches:
            return VisionResult(
                status="focused",
                d_weight=0.05,
                activity_description="Reading study or work-related PDF 📖",
                reasoning="OCR matched academic/work terms (textbook, lecture, chapter, datasheet) on the page.",
                confidence=0.8
            )
        elif distracted_pdf_matches:
            return VisionResult(
                status="distracted",
                d_weight=0.8,
                activity_description="Reading non-work PDF / novel 📖",
                reasoning="OCR matched fiction/manga/novel terms in the PDF viewer.",
                confidence=0.8
            )

    # ── Social Media & Entertainment sites ──────────────────────────
    social_media = ["reddit", "twitter", "x.com", "instagram", "facebook", "netflix", "twitch", "discord", "tiktok"]
    for site in social_media:
        if site in text_lower or site in win_lower:
            return VisionResult(
                status="distracted",
                d_weight=0.85,
                activity_description=f"Browsing {site.capitalize()} 💬",
                reasoning=f"OCR detected '{site}' branding or page context on screen.",
                confidence=0.9
            )

    # ── Coding / Developer tools ───────────────────────────────────
    coding_signals = ["visual studio code", "vs code", "pycharm", "intellij", "terminal", "powershell", "cmd.exe", "github"]
    is_coding = any(sig in text_lower or sig in win_lower for sig in coding_signals) or len(compliant_matches) >= 3
    
    if task_matches and (is_coding or len(compliant_matches) >= 1):
        return VisionResult(
            status="focused",
            d_weight=0.0,
            activity_description=f"Working on: {task_title} 💻",
            reasoning=f"Active coding environment showing task-specific keywords: {', '.join(task_matches[:3])}.",
            confidence=0.95
        )
    
    if is_coding:
        return VisionResult(
            status="focused",
            d_weight=0.05,
            activity_description="Coding in developer environment 💻",
            reasoning="OCR detected active IDE or command line terminal on screen.",
            confidence=0.95
        )

    if task_matches:
        return VisionResult(
            status="focused",
            d_weight=0.1,
            activity_description=f"Researching / Reading content for task: {task_title}",
            reasoning=f"Screen text contains active task keywords: {', '.join(task_matches[:3])}.",
            confidence=0.85
        )

    # ── Default Fallback based on Keyword Density ──────────────────
    if len(deviant_matches) > len(compliant_matches):
        return VisionResult(
            status="distracted",
            d_weight=0.75,
            activity_description="Browsing distracting content 🌐",
            reasoning=f"OCR found deviant keywords: {', '.join(deviant_matches[:3])}.",
            confidence=0.75
        )
    elif len(compliant_matches) > 0:
        return VisionResult(
            status="focused",
            d_weight=0.1,
            activity_description="Productive screen content active",
            reasoning=f"OCR found productive terms: {', '.join(compliant_matches[:3])}.",
            confidence=0.75
        )

    # Ambient default
    return VisionResult(
        status="neutral",
        d_weight=0.3,
        activity_description="Ambient screen activity",
        reasoning="Screen text is general and contains no strong focus or distraction signals.",
        confidence=0.6
    )
