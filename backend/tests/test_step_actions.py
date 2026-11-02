import pytest

from app.core.config import settings
from app.db import SessionLocal
from app.models.profile import Profile
from app.models.tool import Tool
from app.models.workflow import Workflow, WorkflowStep
from tests.test_auth import generate_token


@pytest.fixture
def mock_users_and_tools(client):
    db = SessionLocal()
    u1 = Profile(id="user_A", email="a@test.com", role="user")
    u2 = Profile(id="user_B", email="b@test.com", role="user")

    t1 = Tool(id=1, name="Public Tool", url="https://pub.com", status="verified", link_status="ok", category="design", jobs=["Job 1"])
    t2 = Tool(id=2, name="Draft Tool", url="https://draft.com", status="draft", link_status="ok", category="design", jobs=["Job 1"])

    db.merge(u1)
    db.merge(u2)
    db.merge(t1)
    db.merge(t2)
    db.commit()

    wf = Workflow(id=1, user_id="user_A", title="Test WF", brief={
        "what_being_made": "A test",
        "purpose": "Testing",
        "target_audience": "Devs",
        "constraints": [],
        "must_haves": [],
        "nice_to_haves": [],
        "assumptions": [],
        "skill_level": "beginner",
        "budget_preference": "free_only"
    })
    db.merge(wf)
    db.commit()

    step1 = WorkflowStep(workflow_id=1, position=1, job="Job 1", why_step="Step 1 reason", primary_tool_id=1, alternative_tool_ids=[], job_tags=[], input_types=[], output_types=[])
    step2 = WorkflowStep(workflow_id=1, position=2, job="Job 2", why_step="Step 2 reason", primary_tool_id=1, alternative_tool_ids=[], job_tags=[], input_types=[], output_types=[])
    db.merge(step1)
    db.merge(step2)
    db.commit()

    db.close()

    settings.SUPABASE_JWT_SECRET = "testsecretthatisatleast32characterslong"
    token_a = generate_token(subject="user_A", email="a@test.com", email_verified=True)
    token_b = generate_token(subject="user_B", email="b@test.com", email_verified=True)

    return {"token_a": token_a, "token_b": token_b}

@pytest.mark.asyncio
async def test_another_users_step_returns_404(client, mock_users_and_tools):
    token_b = mock_users_and_tools["token_b"]
    headers = {"Authorization": f"Bearer {token_b}"}

    res = client.post("/api/v1/workflows/1/steps/step-1/regenerate", json={"feedback": "x"}, headers=headers)
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_draft_tools_cannot_be_switched_in(client, mock_users_and_tools):
    token_a = mock_users_and_tools["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.post("/api/v1/workflows/1/steps/step-1/switch-tool", json={"tool_id": 2}, headers=headers)
    assert res.status_code == 400

@pytest.mark.asyncio
async def test_finishing_step_1_changes_step_2(client, mock_users_and_tools, monkeypatch):
    token_a = mock_users_and_tools["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    async def mock_rewrite(next_step, current_step, note, brief):
        next_step.prompt = "REWRITTEN"
        return next_step

    monkeypatch.setattr("app.routers.workflow.prompts_service.rewrite_next_step_prompt", mock_rewrite)

    res = client.post("/api/v1/workflows/1/steps/step-1/finish", json={"note": "done"}, headers=headers)
    assert res.status_code == 200

    db = SessionLocal()
    s2 = db.query(WorkflowStep).filter_by(workflow_id=1, position=2).first()
    assert s2.prompt == "REWRITTEN"

    s1 = db.query(WorkflowStep).filter_by(workflow_id=1, position=1).first()
    assert s1.status == "done"
    assert s1.handoff_note == "done"
    db.close()

@pytest.mark.asyncio
async def test_finish_llm_failure_leaves_db_unchanged(client, mock_users_and_tools, monkeypatch):
    """Verify that a failed LLM call in step finish leaves the database unchanged."""
    token_a = mock_users_and_tools["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    async def mock_fail(*args, **kwargs):
        raise RuntimeError("LLM boom")

    monkeypatch.setattr("app.routers.workflow.prompts_service.rewrite_next_step_prompt", mock_fail)

    db = SessionLocal()
    s1 = db.query(WorkflowStep).filter_by(workflow_id=1, position=1).first()
    s1.status = "pending"
    s1.handoff_note = None
    db.commit()
    db.close()

    res = client.post("/api/v1/workflows/1/steps/step-1/finish", json={"note": "should not save"}, headers=headers)
    assert res.status_code == 502
    assert "Something went wrong" in res.json()["detail"]

    db = SessionLocal()
    s1 = db.query(WorkflowStep).filter_by(workflow_id=1, position=1).first()
    assert s1.status != "done"
    assert s1.handoff_note is None
    db.close()

def test_user_cannot_create_event_for_another_users_workflow(client, mock_users_and_tools):
    """User B cannot log an event against user A's workflow or step."""
    token_b = mock_users_and_tools["token_b"]
    headers = {"Authorization": f"Bearer {token_b}"}

    res = client.post("/api/v1/events", json={"kind": "prompt_copied", "workflow_id": 1, "step_id": "step-1"}, headers=headers)
    assert res.status_code == 404

def test_interview_precheck_blocks_when_workflow_quota_zero(client, mock_users_and_tools, monkeypatch):
    """Starting an interview with 0 remaining workflow quota returns 429."""
    token_a = mock_users_and_tools["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    def mock_usage(db, user, kind):
        return {"code": "ok", "kind": "workflow", "limit": 2, "used": 2, "resets_at": "2026-10-07T00:00:00Z"}

    monkeypatch.setattr("app.routers.interview.quota.get_usage", mock_usage)

    res = client.post("/api/v1/interview", json={"goal": "Build something", "answers": []}, headers=headers)
    assert res.status_code == 429
    body = res.json()
    assert body["code"] == "daily_limit"
    assert body["kind"] == "workflow"
