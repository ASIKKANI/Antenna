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
