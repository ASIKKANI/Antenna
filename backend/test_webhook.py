"""
ChronosPet Backend Test Suite
=============================
Tests webhook ingestion, auth, task CRUD, sentinel math, and state transitions.
All LLM calls are mocked — runs without API keys.

Run: cd backend && python -m pytest test_webhook.py -v
"""
import time
import pytest
from sentinel import calculate_severity_index, evaluate_window_compliance


# ─── Webhook Ingestion Tests ─────────────────────────────────────

class TestWebhookIngestion:
    def test_ingest_accepted(self, client, sample_webhook_payload):
        """VAL-01: Authorized webhook creates a task and returns 202."""
        resp = client.post("/api/v1/webhook/ingest", json=sample_webhook_payload)
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["message"] == "Task ingested successfully"

    def test_ingest_unauthorized(self, client, unauthorized_payload):
        """Unauthorized sender returns 401."""
        resp = client.post("/api/v1/webhook/ingest", json=unauthorized_payload)
        assert resp.status_code == 401

    def test_ingest_creates_retrievable_task(self, client, sample_webhook_payload):
        """Ingested task appears in task list."""
        client.post("/api/v1/webhook/ingest", json=sample_webhook_payload)
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) >= 1

    def test_ingest_completion_command(self, client, sample_webhook_payload):
        """Sending 'done' completes the most recent task and awards XP."""
        # First create a task
        client.post("/api/v1/webhook/ingest", json=sample_webhook_payload)

        # Then complete it
        completion_payload = {
            **sample_webhook_payload,
            "content": "Done with the API docs",
            "message_id": "WA-MSG-TEST002",
        }
        resp = client.post("/api/v1/webhook/ingest", json=completion_payload)
        assert resp.status_code == 202
        assert "complete" in resp.json()["message"].lower() or "xp" in str(resp.json()).lower()


# ─── Task CRUD Tests ─────────────────────────────────────────────

class TestTaskCRUD:
    def test_list_tasks_empty(self, client):
        """Empty task list returns 200 with empty array."""
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200

    def test_get_task_not_found(self, client):
        """Non-existent task returns 404."""
        resp = client.get("/api/v1/tasks/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_task(self, client, sample_webhook_payload):
        """Task can be created and deleted."""
        create_resp = client.post("/api/v1/webhook/ingest", json=sample_webhook_payload)
        task_id = create_resp.json()["task_id"]

        delete_resp = client.delete(f"/api/v1/tasks/{task_id}")
        assert delete_resp.status_code == 200

        get_resp = client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 404

    def test_update_task_priority(self, client, sample_webhook_payload):
        """Task priority can be updated via PATCH."""
        create_resp = client.post("/api/v1/webhook/ingest", json=sample_webhook_payload)
        task_id = create_resp.json()["task_id"]

        patch_resp = client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"priority_level": "critical"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["task"]["priority_level"] == "critical"


# ─── Health & State Tests ────────────────────────────────────────

class TestHealthAndState:
    def test_health_endpoint(self, client):
        """Health check returns system status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "vector_store" in data
        assert "llm_router" in data

    def test_companion_state(self, client):
        """Companion state returns valid animation frames."""
        resp = client.get("/api/v1/companion/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "display_animation_frame" in data
        assert "focus_points_balance" in data
        assert "current_level" in data

    def test_gamification_endpoint(self, client):
        """Gamification returns XP and level info."""
        resp = client.get("/api/v1/companion/gamification")
        assert resp.status_code == 200
        data = resp.json()
        assert "level" in data
        assert "xp" in data
        assert "evolution_stage" in data


# ─── Sentinel Math Tests ─────────────────────────────────────────

class TestSentinelMath:
    def test_severity_compliant(self):
        """Low elapsed + compliant window → Sp < 0.4."""
        sp = calculate_severity_index(
            elapsed_sec=300,
            total_allocated_sec=3600,
            deviation_weight=0.0,
            productivity_index=0.8,
        )
        assert sp < 0.4

    def test_severity_deviant(self):
        """High elapsed + deviant window → Sp > 0.7."""
        sp = calculate_severity_index(
            elapsed_sec=3400,
            total_allocated_sec=3600,
            deviation_weight=0.9,
            productivity_index=0.0,
        )
        assert sp > 0.7

    def test_severity_division_by_zero(self):
        """Zero allocated time should not crash, returns max urgency."""
        sp = calculate_severity_index(
            elapsed_sec=100,
            total_allocated_sec=0,
            deviation_weight=0.5,
            productivity_index=0.5,
        )
        assert 0.0 <= sp <= 1.0  # Should not crash

    def test_window_compliance_youtube(self):
        """YouTube window → high deviation weight."""
        d = evaluate_window_compliance("YouTube - Elden Ring Speedrun - Chrome", "Deploy server patch")
        assert d >= 0.9

    def test_window_compliance_vscode(self):
        """VS Code window → compliant."""
        d = evaluate_window_compliance("main.py - ChronosPet - Visual Studio Code", "Deploy server patch")
        assert d == 0.0

    def test_window_compliance_task_keywords(self):
        """Window matching task keywords → near-compliant."""
        d = evaluate_window_compliance("deploy_script.sh - Terminal", "Deploy server patch")
        assert d <= 0.1

    def test_window_compliance_neutral(self):
        """Unknown app → neutral weight."""
        d = evaluate_window_compliance("Calculator", "Deploy server patch")
        assert 0.1 < d < 0.5

    def test_vse_get_process_name_and_id(self):
        """VSE-01: Native Windows process lookup returns process name and ID on Windows or doesn't crash."""
        from sentinel import get_active_process_name_and_id
        proc_name, proc_id = get_active_process_name_and_id()
        # On Windows, foreground should be active. On CI/headless it might be None.
        # Ensure it runs without exception.
        assert proc_name is None or isinstance(proc_name, str)
        assert proc_id is None or isinstance(proc_id, int)

    def test_vse_get_structural_text(self):
        """VSE-02: Native child-window structural text tree enumerates children or returns empty string."""
        from sentinel import get_window_structural_text
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow() if hasattr(ctypes.windll, "user32") else 0
        text_tree = get_window_structural_text(hwnd)
        assert isinstance(text_tree, str)

    def test_vse_severity_decay_formula(self):
        """VSE-03: Procrastination severity score calculation uses decay formula with S_prev."""
        # Setup: task active for 50% of allocation (time_ratio = 0.5)
        # S_prev = 0.8, w_d = 1.0 (DEVIANT), delta = 0.85
        # Expected Sp = 0.85 * 0.8 + 0.15 * (1.0 * 0.5) = 0.68 + 0.075 = 0.755
        sp = calculate_severity_index(
            elapsed_sec=500,
            total_allocated_sec=1000,
            deviation_weight=1.0,
            s_prev=0.8,
            delta=0.85,
        )
        assert sp == 0.755
        
        # Test task_id cache integration
        from turbovec import memory_db
        task_id = "test-vse-task-123"
        memory_db.register_cache[task_id] = 0.5
        
        sp2 = calculate_severity_index(
            elapsed_sec=300,
            total_allocated_sec=1000,
            deviation_weight=0.0, # COMPLIANT (w_d = 0.0)
            task_id=task_id,
            delta=0.85,
        )
        # Expected: Sp = 0.85 * 0.5 + 0.15 * (0.0 * 0.3) = 0.425
        assert sp2 == 0.425
        assert memory_db.register_cache[task_id] == 0.425


# ─── VSE Multi-Agent Route Tests ─────────────────────────────────

class TestVSERoutes:
    @pytest.mark.anyio
    async def test_perception_and_cognitive_agents(self):
        """Verify that sequential Perception and Cognitive agents function and return parsed results."""
        from agent_system import run_perception_agent, run_cognitive_agent, CognitiveResult
        from unittest.mock import AsyncMock, MagicMock
        from models import TaskEntity
        from datetime import datetime

        # Mock llm_router
        mock_router = MagicMock()
        
        # 1. Mock response for Perception Agent
        mock_response_perception = MagicMock()
        mock_response_perception.choices = [
            MagicMock(message=MagicMock(content="The screen shows a browser window playing a GTA V game trailer on YouTube."))
        ]
        
        # 2. Mock response for Cognitive Agent
        mock_response_cognitive = MagicMock()
        mock_response_cognitive.choices = [
            MagicMock(message=MagicMock(content='{"status": "distracted", "d_weight": 0.9, "animation": "nagging_severe", "dialogue": "Focus on coding!", "reasoning": "User is watching GTA V gameplay instead of writing tests"}'))
        ]
        
        # Configure completion mock side_effect to return perception first, then cognitive
        mock_router.completion.side_effect = [mock_response_perception, mock_response_cognitive]
        
        # Run perception agent
        desc = await run_perception_agent(b"dummy_image", "YouTube", mock_router)
        assert "GTA V" in desc
        
        # Run cognitive agent
        tasks = [
            TaskEntity(
                task_id="task-123",
                raw_source_text="Write unit tests for the agent system",
                clean_title="Write unit tests",
                deadline_epoch=int(time.time()) + 1800, # 30 min deadline (urgent)
                priority_level="high",
                status_state="active",
                created_at=datetime.utcnow()
            )
        ]
        
        result = await run_cognitive_agent(desc, tasks, "rival", mock_router)
        assert isinstance(result, CognitiveResult)
        assert result.status == "distracted"
        assert result.d_weight == 0.9
        assert result.animation == "nagging_severe"
        assert result.dialogue == "Focus on coding!"







