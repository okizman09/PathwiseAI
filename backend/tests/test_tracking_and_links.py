import pytest

from app.db import SessionLocal
from app.models.event import Event
from app.models.profile import Profile
from app.models.tool import Tool
from app.models.workflow import Workflow, WorkflowStep
from app.schemas.tool import ToolStatus
from tests.test_auth import generate_token


@pytest.fixture
def link_test_setup(client):
    db = SessionLocal()
    u1 = Profile(id="user_owner", email="owner@test.com", role="user")
    u2 = Profile(id="user_other", email="other@test.com", role="user")
    db.merge(u1)
    db.merge(u2)

    t1 = Tool(
        id=101,
        name="Tracked Tool",
        url="https://official.trackedtool.com",
        affiliate_url="https://affiliate.trackedtool.com?ref=pathwise",
        status=ToolStatus.VERIFIED.value,
        link_status="ok",
        category="design",
        jobs=["UI Design"],
    )
    t2 = Tool(
        id=102,
        name="Alternative Tool",
        url="https://alttool.com",
        affiliate_url=None,
        status=ToolStatus.VERIFIED.value,
        link_status="ok",
        category="design",
        jobs=["UI Design"],
    )
    t_unrelated = Tool(
        id=103,
        name="Unrelated Tool",
        url="https://unrelated.com",
        status=ToolStatus.VERIFIED.value,
        link_status="ok",
        category="dev",
        jobs=["Code"],
    )
    db.merge(t1)
    db.merge(t2)
    db.merge(t_unrelated)

    wf = Workflow(
        id=50,
        user_id="user_owner",
        title="Tracking Workflow",
        brief={
            "what_being_made": "Tracking test app",
            "purpose": "Testing",
            "target_audience": "Devs",
            "constraints": [],
            "must_haves": [],
            "nice_to_haves": [],
            "assumptions": [],
            "skill_level": "beginner",
            "budget_preference": "free_only",
        },
    )
    db.merge(wf)
    db.commit()

    step1 = WorkflowStep(
        workflow_id=50,
        position=1,
        job="Design the interface",
        why_step="Essential first step",
        primary_tool_id=101,
        alternative_tool_ids=[102],
        kind="tool",
        job_tags=[],
        input_types=[],
        output_types=[],
    )
    step_no_tool = WorkflowStep(
        workflow_id=50,
        position=2,
        job="Obscure Niche Job",
        why_step="Waiting for verification",
        primary_tool_id=None,
        alternative_tool_ids=[],
        kind="no_tool",
        job_tags=[],
        input_types=[],
        output_types=[],
    )
    db.merge(step1)
    db.merge(step_no_tool)
    db.commit()
    db.close()

    owner_token = generate_token(subject="user_owner", email="owner@test.com", email_verified=True)
    other_token = generate_token(subject="user_other", email="other@test.com", email_verified=True)

    return {
        "owner_token": owner_token,
        "other_token": other_token,
        "tool_id": 101,
        "alt_tool_id": 102,
        "unrelated_tool_id": 103,
        "workflow_id": 50,
    }


def test_open_link_returns_signed_go_url(client, link_test_setup):
    """Calling open-link returns a signed /go/{tool_id}?ref=... URL."""
    headers = {"Authorization": f"Bearer {link_test_setup['owner_token']}"}
    wf_id = link_test_setup["workflow_id"]

    res = client.post(
        f"/api/v1/workflows/{wf_id}/steps/step-1/open-link",
        json={"tool_id": 101},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "go_url" in data
    assert data["go_url"].startswith("/go/101?ref=")


def test_open_link_rejects_unrelated_tool(client, link_test_setup):
    """Requesting an unrelated tool not in the step's primary or alternatives returns 400."""
    headers = {"Authorization": f"Bearer {link_test_setup['owner_token']}"}
    wf_id = link_test_setup["workflow_id"]

    res = client.post(
        f"/api/v1/workflows/{wf_id}/steps/step-1/open-link",
        json={"tool_id": 103},
        headers=headers,
    )
    assert res.status_code == 400
    assert "not associated" in res.json()["detail"]


def test_open_link_enforces_workflow_ownership(client, link_test_setup):
    """Another user trying to generate an open-link for a workflow gets 404."""
    headers = {"Authorization": f"Bearer {link_test_setup['other_token']}"}
    wf_id = link_test_setup["workflow_id"]

    res = client.post(
        f"/api/v1/workflows/{wf_id}/steps/step-1/open-link",
        json={"tool_id": 101},
        headers=headers,
    )
    assert res.status_code == 404


def test_go_redirect_with_signed_ref_logs_event_with_user_and_step(client, link_test_setup):
    """Clicking /go/{tool_id}?ref=... with a valid signed ref logs the user, workflow, and step."""
    headers = {"Authorization": f"Bearer {link_test_setup['owner_token']}"}
    wf_id = link_test_setup["workflow_id"]

    link_res = client.post(
        f"/api/v1/workflows/{wf_id}/steps/step-1/open-link",
        headers=headers,
    )
    go_url = link_res.json()["go_url"]

    # Now make the GET request to /go/... (without auth headers, exactly like a browser click)
    redirect_res = client.get(go_url, follow_redirects=False)
    assert redirect_res.status_code == 302
    assert redirect_res.headers["location"] == "https://affiliate.trackedtool.com?ref=pathwise"

    # Verify event logged in database with user_id, workflow_id, and step_id
    db = SessionLocal()
    event = (
        db.query(Event)
        .filter(Event.kind == "tool_opened", Event.tool_id == 101)
        .order_by(Event.id.desc())
        .first()
    )
    assert event is not None
    assert event.user_id == "user_owner"
    assert event.workflow_id == 50
    assert event.step_id is not None
    db.close()


def test_go_redirect_without_ref_logs_anonymous(client, link_test_setup):
    """Clicking /go/{tool_id} without ref still redirects but logs as anonymous."""
    res = client.get("/go/101", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "https://affiliate.trackedtool.com?ref=pathwise"

    db = SessionLocal()
    event = (
        db.query(Event)
        .filter(Event.kind == "tool_opened", Event.tool_id == 101)
        .order_by(Event.id.desc())
        .first()
    )
    assert event is not None
    assert event.user_id is None
    assert event.workflow_id is None
    db.close()


def test_public_schemas_contain_no_affiliate_urls(client, link_test_setup):
    """Public tools and step schemas return go_path and NEVER leak affiliate_url."""
    # 1. Public tools list
    tools_res = client.get("/api/v1/tools")
    assert tools_res.status_code == 200
    tools_data = tools_res.json()
    assert len(tools_data) > 0
    for t in tools_data:
        assert "go_path" in t
        assert t["go_path"].startswith("/go/")
        assert "affiliate_url" not in t
        assert "open_url" not in t

    # 2. Workflow response steps
    headers = {"Authorization": f"Bearer {link_test_setup['owner_token']}"}
    wf_res = client.get(f"/api/v1/workflows/{link_test_setup['workflow_id']}", headers=headers)
    assert wf_res.status_code == 200
    wf_data = wf_res.json()
    assert "steps" in wf_data
    for s in wf_data["steps"]:
        if s.get("primary_tool"):
            assert "go_path" in s["primary_tool"]
            assert s["primary_tool"]["go_path"].startswith("/go/")
            assert "affiliate_url" not in s["primary_tool"]
            assert "open_url" not in s["primary_tool"]


def test_no_tool_step_renders_without_crash(client, link_test_setup):
    """Step with kind='no_tool' has null primary_tool and does not crash serialization."""
    headers = {"Authorization": f"Bearer {link_test_setup['owner_token']}"}
    wf_res = client.get(f"/api/v1/workflows/{link_test_setup['workflow_id']}", headers=headers)
    assert wf_res.status_code == 200
    steps = wf_res.json()["steps"]
    no_tool_step = next(s for s in steps if s["step_id"] == "step-2")
    assert no_tool_step["kind"] == "no_tool"
    assert no_tool_step["primary_tool"] is None
    assert no_tool_step["job"] == "Obscure Niche Job"
    assert "why_step" in no_tool_step
