"""SQLAlchemy ORM model — tools catalog (Catalog v3)."""
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text, func

from app.db import Base


class Tool(Base):
    """Tool card in the Pathwise catalog."""

    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    url = Column(String(1024), nullable=False)
    affiliate_url = Column(String(1024), nullable=True)
    docs_url = Column(String(1024), nullable=True)

    # Taxonomy & categorization
    domain = Column(String(50), nullable=True, index=True)
    category = Column(String(100), nullable=False, default="", index=True)  # Kept DB column
    jobs = Column(JSON, nullable=False, default=list)  # Taxonomy slugs only

    # Pricing & monetization
    pricing_model = Column(String(50), nullable=True, default="unknown")
    has_free_tier = Column(Boolean, nullable=True)
    free_tier_summary = Column(String(140), nullable=True)
    free_tier_limits = Column(Text, nullable=True)
    starting_price_monthly_usd = Column(Float, nullable=True)
    pricing_notes = Column(Text, nullable=True)
    credit_card_required = Column(Boolean, nullable=True)
    watermark_on_free = Column(Boolean, nullable=True)
    commercial_use_on_free = Column(Boolean, nullable=True)
    pricing_url = Column(String(1024), nullable=True)
    pricing_checked_at = Column(DateTime(timezone=True), nullable=True)
    pricing = Column(String(255), nullable=False, default="freemium")  # Legacy column preserved

    # Target & audience
    platforms = Column(JSON, nullable=True, default=list)  # [web, desktop, mobile, cli, api, extension]
    skill_level = Column(String(50), nullable=True, default="all")  # beginner | intermediate | advanced | all

    # Explanations & copy
    tagline = Column(String(90), nullable=True)
    summary = Column(Text, nullable=True)
    how_it_helps = Column(Text, nullable=True)
    pros = Column(JSON, nullable=True, default=list)  # exactly 3
    cons = Column(JSON, nullable=True, default=list)  # exactly 3
    best_for = Column(Text, nullable=False, default="")
    not_for = Column(Text, nullable=False, default="")

    # Media assets
    logo_url = Column(Text, nullable=True)
    og_image_url = Column(Text, nullable=True)
    logo_source = Column(String(50), nullable=True)  # manual | official | page | og | favicon_service

    # Prompt style & I/O
    prompt_style = Column(JSON, nullable=False, default=dict)
    input_types = Column(JSON, nullable=False, default=list)
    output_types = Column(JSON, nullable=False, default=list)

    # Provenance, verification & signals
    status = Column(String(50), nullable=False, default="draft", index=True)  # draft | researched | verified | hidden
    evidence = Column(JSON, nullable=True, default=dict)
    review_flags = Column(JSON, nullable=True, default=list)
    official_domains = Column(JSON, nullable=True, default=list)
    research_provider = Column(String(50), nullable=True)
    researched_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(255), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_pick = Column(Boolean, nullable=False, default=False, server_default="false")

    # Links & monitoring
    link_status = Column(String(20), nullable=False, default="unknown")  # ok | dead | unknown
    link_checked_at = Column(DateTime(timezone=True), nullable=True)
    sources = Column(JSON, nullable=True, default=list)
    research_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )
