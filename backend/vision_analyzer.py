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
import ctypes
from ctypes import wintypes

logger = logging.getLogger("chronospet.vision")

try:
    user32 = ctypes.windll.user32
except AttributeError:
    user32 = None

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
    Captures the primary monitor screen, resizes it to 640px max dimension, and returns compressed JPEG bytes in memory.
    Screenshots are never saved to disk.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        sct_img = sct.grab(monitor)
        
        # Convert raw pixels from bgra format to RGB PIL Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        # Resize to max 640px to optimize VVL model VRAM footprint and execution speed
        max_dim = 640
        w, h = img.size
        if w > max_dim or h > max_dim:
            if w > h:
                new_width = max_dim
                new_height = int(h * (max_dim / w))
            else:
                new_height = max_dim
                new_width = int(w * (max_dim / h))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Compress and save to in-memory bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=75)
        return buffer.getvalue()

def capture_window_screenshot(hwnd: int) -> bytes:
    """
    Captures the coordinates of a specific window handle, crops the primary monitor capture to it,
    and resizes it to 640px max dimension to optimize memory usage and VRAM during vision model inference.
    """
    if not hwnd or not user32:
        return capture_screen()
        
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        width = right - left
        height = bottom - top
        
        if width > 0 and height > 0:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    sct_img = sct.grab(monitor)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # Bounds checking relative to the captured screenshot size
                    crop_left = max(0, min(img.width, left))
                    crop_top = max(0, min(img.height, top))
                    crop_right = max(0, min(img.width, right))
                    crop_bottom = max(0, min(img.height, bottom))
                    
                    if crop_right > crop_left and crop_bottom > crop_top:
                        cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
                        
                        # Resize to max 640px
                        max_dim = 640
                        w, h = cropped.size
                        if w > max_dim or h > max_dim:
                            if w > h:
                                new_width = max_dim
                                new_height = int(h * (max_dim / w))
                            else:
                                new_height = max_dim
                                new_width = int(w * (max_dim / h))
                            cropped = cropped.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        
                        buffer = io.BytesIO()
                        cropped.save(buffer, format="JPEG", quality=75)
                        return buffer.getvalue()
            except Exception as e:
                logger.warning(f"Failed to capture window crop for hwnd {hwnd}, using full screenshot: {e}")
                       
    return capture_screen()

def analyze_screen(
    image_bytes: bytes,
    task_title: str,
    window_title: str,
    llm_router
) -> VisionResult:
    """
    Calls Gemini / Local Vision model via the LiteLLM router with screen context and returns a VisionResult.
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
