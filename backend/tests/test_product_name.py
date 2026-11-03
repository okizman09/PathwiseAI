"""Prompt-contract tests: product names come from the user, never invented."""

from app.schemas.brief import ProductBrief
from app.services.interview import build_interview_instruction
from app.services.plan import SYNTHESIS_NAME_RULE


def test_interview_instruction_asks_for_product_name():
    instruction = build_interview_instruction(force_ready=False)
    assert "brief.product_name" in instruction
    assert "NEVER invent a name" in instruction


def test_interview_instruction_force_ready_keeps_name_rule():
    instruction = build_interview_instruction(force_ready=True)
    assert "brief.product_name" in instruction
    assert "is_ready=True" in instruction


def test_synthesis_name_rule_forbids_invention():
    assert "brief.product_name" in SYNTHESIS_NAME_RULE
    assert "NEVER invent" in SYNTHESIS_NAME_RULE


def test_product_brief_product_name_defaults_null():
    brief = ProductBrief(
        what_being_made="x", purpose="y", target_audience="z",
    )
    assert brief.product_name is None
    named = ProductBrief(
        what_being_made="x", purpose="y", target_audience="z", product_name="Acme",
    )
    assert named.product_name == "Acme"
