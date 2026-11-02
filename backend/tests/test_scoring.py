from app.models.tool import Tool
from app.schemas.brief import ProductBrief
from app.services.plan import JobPlanningItem
from app.services.planner.scoring import shortlist_and_score


def test_scoring_stopwords_never_cause_conflict():
    """Verify words like 'for', 'and', 'the' never cause false exclusions."""
    tool = Tool(
        id=1,
        name="Tool A",
        status="verified",
        link_status="ok",
        category="design",
        jobs=["logo_design"],
        pricing="free",
        not_for="Not for teams and large enterprise",
    )
    brief = ProductBrief(
        what_being_made="Logo",
        purpose="App branding",
        target_audience="Founders",
        constraints=["Fast for the web and mobile"],  # Contains 'for', 'the', 'and'
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="intermediate",
        budget_preference="free_only",
    )
    job_item = JobPlanningItem(
        step_number=1,
        job="design a logo",
        job_tags=["logo_design"],
        input_types=["text"],
        output_types=["image"],
        output_expected="Logo SVG",
    )

    result = shortlist_and_score([tool], job_item, [], brief)
    assert len(result) == 1
    assert result[0].id == 1


def test_scoring_real_clash_lowers_rank_not_deleted():
    """Verify real clash like 'no-code' against not_for 'no-code users' lowers rank."""
    tool_clash = Tool(
        id=1,
        name="Tool With Clash",
        status="verified",
        link_status="ok",
        category="code",
        jobs=["build_app"],
        pricing="free",
        not_for="no-code users",
    )
    tool_clean = Tool(
        id=2,
        name="Tool Without Clash",
        status="verified",
        link_status="ok",
        category="code",
        jobs=["build_app"],
        pricing="free",
        not_for=None,
    )
    brief = ProductBrief(
        what_being_made="Web app",
        purpose="Productivity",
        target_audience="Devs",
        constraints=["Prefers no-code approach"],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="unknown",
        budget_preference="free_only",
    )
    job_item = JobPlanningItem(
        step_number=1,
        job="build code app",
        job_tags=["build_app"],
        input_types=["text"],
        output_types=["code"],
        output_expected="Web app code",
    )

    result = shortlist_and_score([tool_clash, tool_clean], job_item, [], brief)
    # Both tools are candidates, but clean tool ranks first because clash tool was penalized
    assert len(result) == 2
    assert result[0].id == 2
    assert result[1].id == 1


def test_scoring_skill_level_hard_skip():
    """Verify brief's skill_level is a hard skip when explicitly in not_for."""
    tool_advanced_only = Tool(
        id=1,
        name="Tool Expert",
        status="verified",
        link_status="ok",
        category="code",
        jobs=["build_app"],
        pricing="free",
        not_for="beginner programmers",
    )
    brief = ProductBrief(
        what_being_made="Web app",
        purpose="Productivity",
        target_audience="Devs",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="beginner",
        budget_preference="free_only",
    )
    job_item = JobPlanningItem(
        step_number=1,
        job="build code app",
        job_tags=["build_app"],
        input_types=["text"],
        output_types=["code"],
        output_expected="Code",
    )

    result = shortlist_and_score([tool_advanced_only], job_item, [], brief)
    # Hard skip removes it entirely
    assert len(result) == 0


def test_scoring_returns_up_to_four_tools():
    """Verify shortlist_and_score caps returned tools at 4."""
    tools = [
        Tool(
            id=i,
            name=f"Tool {i}",
            status="verified",
            link_status="ok",
            category="design",
            jobs=["logo"],
            pricing="free",
        )
        for i in range(1, 10)
    ]
    brief = ProductBrief(
        what_being_made="Logo",
        purpose="App branding",
        target_audience="Devs",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="intermediate",
        budget_preference="free_only",
    )
    job_item = JobPlanningItem(
        step_number=1,
        job="design logo",
        job_tags=["logo"],
        input_types=["text"],
        output_types=["image"],
        output_expected="Logo",
    )

    result = shortlist_and_score(tools, job_item, [], brief)
    assert len(result) == 4
