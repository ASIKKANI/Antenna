import base64
import json
import logging
import time
from typing import Literal, List
from pydantic import BaseModel
from models import TaskEntity

logger = logging.getLogger("chronospet.agents")

class CognitiveResult(BaseModel):
    status: Literal["focused", "distracted", "neutral"]
    d_weight: float
    animation: Literal["nagging_severe", "nagging_mild", "focus_mode_active", "idle_loop"]
    dialogue: str
    reasoning: str

async def run_perception_agent(
    image_bytes: bytes,
    window_title: str,
    llm_router
) -> str:
    """
    Agent 1: Perception Agent (Visual Context Parser).
    Uses local multimodal model (MiniCPM) to parse screen screenshot into objective description.
    """
    if not llm_router:
        raise ValueError("LLM Router not available")
        
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    prompt = (
        "Describe in one objective sentence what is visible on this desktop screen. "
        "Mention specific open applications, websites, code files, or video games. "
        "Do not make any value judgments or call things productive/distracting. Simply report the facts."
    )
    
    try:
        response = llm_router.completion(
            model="chronospet-llm",
            messages=[
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
            ]
        )
        description = response.choices[0].message.content.strip()
        logger.info(f"Perception Agent: {description}")
        return description
    except Exception as e:
        logger.error(f"Perception Agent failed: {e}")
        # Fallback to window title
        return f"Active window title: '{window_title}'"

async def run_cognitive_agent(
    activity_description: str,
    active_tasks: List[TaskEntity],
    persona: str,
    llm_router
) -> CognitiveResult:
    """
    Agent 2: Cognitive Supervisor Agent.
    Evaluates the perception description against active tasks, remaining time, and companion persona,
    returning focus status, d_weight, animation, and dynamic companion dialogue.
    """
    if not llm_router:
        raise ValueError("LLM Router not available")
        
    now = int(time.time())
    formatted_tasks = []
    for t in active_tasks:
        remaining_sec = t.deadline_epoch - now
        if remaining_sec < 0:
            time_str = "PASSED DEADLINE"
        else:
            hours = remaining_sec // 3600
            mins = (remaining_sec % 3600) // 60
            time_str = f"{hours}h {mins}m remaining"
        formatted_tasks.append(
            f"- Task: \"{t.clean_title}\" | Priority: {t.priority_level} | Time left: {time_str}"
        )
        
    tasks_text = "\n".join(formatted_tasks)
    
    prompt = (
        f"You are the Cognitive Supervisor Agent of ChronosPet, a productivity assistant companion.\n"
        f"Your active persona profile is: \"{persona}\" (cybernetic = cold, robotic, logical; rival = competitive, strict, nagging; zen = mindful, gentle, relaxed).\n\n"
        f"Judge the user's productivity status and determine compliance weights:\n"
        f"- status \"focused\" (d_weight = 0.0 to 0.1) if the user's action directly helps complete their tasks.\n"
        f"- status \"distracted\" (d_weight = 0.8 to 1.0) if the user is gaming, on social media, or watching entertainment.\n"
        f"- status \"neutral\" (d_weight = 0.2 to 0.5) for general browsing, meetings, music, or ambiguous activities.\n\n"
        f"CRITICAL DEADLINE RATIONALIZATION:\n"
        f"- If any task has a near deadline (e.g. less than 24 hours), be EXTREMELY strict. Distractions (even minor ones) must result in a high d_weight (0.8+) and 'nagging_severe' animation. Nag the user heavily.\n"
        f"- If all task deadlines are far away (e.g. days/weeks), you must be lenient. Do not nag them severely for brief entertainment. Praise them if they are working.\n\n"
        f"Active Task List:\n"
        f"{tasks_text}\n\n"
        f"Current Screen Activity: \"{activity_description}\"\n\n"
        f"Respond ONLY with a valid JSON object matching this schema:\n"
        f"{{\n"
        f"  \"status\": \"focused\" | \"distracted\" | \"neutral\",\n"
        f"  \"d_weight\": <float between 0.0 and 1.0>,\n"
        f"  \"animation\": \"nagging_severe\" | \"nagging_mild\" | \"focus_mode_active\" | \"idle_loop\",\n"
        f"  \"dialogue\": \"<dynamic dialogue in your active persona voice, nagging or encouraging the user>\",\n"
        f"  \"reasoning\": \"<one sentence explaining why you made this decision based on task deadlines>\"\n"
        f"}}\n"
        f"Do not include any markdown layout (like ```json). Return raw JSON text."
    )
    
    try:
        response = llm_router.completion(
            model="chronospet-llm",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        return parse_cognitive_json(content)
    except Exception as e:
        logger.error(f"Cognitive Agent call failed: {e}")
        # Fallback to local heuristic (handled at higher level)
        raise e

def parse_cognitive_json(content: str) -> CognitiveResult:
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    try:
        data = json.loads(content)
        return CognitiveResult(**data)
    except Exception as e:
        logger.error(f"Failed to parse CognitiveResult JSON: {e}. Raw content: {content}")
        raise e
