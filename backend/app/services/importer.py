"""Card Importer service (Catalog v3 - Slice C2).

Handles validation, consistency rules, evidence verification against official domains,
quote checking with SSRF-safe page fetching, review flag generation, and database upsert.
"""
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.tool import Tool
from app.schemas.card_import import (
    CardImport,
    CardImportResponse,
    CardImportResult,
    EvidenceItem,
)
from app.services.research.fetcher import fetch_page_safe
from app.services.research.logos import process_tool_logo
from app.taxonomy.loader import is_valid_job

logger = logging.getLogger(__name__)

MULTI_PART_TLDS = {"co", "com", "org", "gov", "edu", "ac", "net"}


def extract_domains_from_url(url: str | None) -> set[str]:
    """Extract full hostname and registrable domain from a URL."""
    if not url:
        return set()
    parsed = urlparse(url)
    host = (parsed.hostname or url).lower().strip()
    if not host:
        return set()
    domains = {host}
    parts = host.split(".")
    if len(parts) >= 2:
        if (
            len(parts) >= 3
            and parts[-2] in MULTI_PART_TLDS
            and len(parts[-1]) == 2
        ):
            registrable = ".".join(parts[-3:])
        else:
            registrable = ".".join(parts[-2:])
        domains.add(registrable)
    return domains


def is_on_official_domain(url: str, official_domains: set[str]) -> bool:
    """Check if URL's hostname matches or is a subdomain of any official domain."""
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().strip()
    if not host:
        return False
    for d in official_domains:
        d = d.lower().strip()
        if host == d or host.endswith("." + d):
            return True
    return False


def normalize_for_quote_match(text: str) -> str:
    """Normalize text for quote matching by stripping markdown, table symbols, and collapsing whitespace."""
    if not text:
        return ""
    # Strip markdown and table symbols: | # * _ ` [ ] ( ) check marks, bullets, dashes
    chars_to_replace = "|#*_`[]()✓✔✅•–—"
    trans = str.maketrans({ch: " " for ch in chars_to_replace})
    cleaned = text.translate(trans)
    return " ".join(cleaned.lower().split())


class CardImporterService:
    """Importer for Catalog v3 tool cards."""

    @staticmethod
    def compute_official_domains(card: CardImport) -> set[str]:
        """Compute the set of official domains from official_url, pricing_url, and card.official_domains."""
        domains: set[str] = set()
        domains.update(extract_domains_from_url(card.official_url))
        if card.pricing_url:
            domains.update(extract_domains_from_url(card.pricing_url))
        for d in card.official_domains:
            if d:
                d_clean = d.lower().strip()
                domains.add(d_clean)
                if not d_clean.startswith("http"):
                    domains.update(extract_domains_from_url(f"https://{d_clean}"))
        return domains

    @staticmethod
    def validate_and_flag_consistency(card: CardImport) -> tuple[dict[str, Any], list[str]]:
        """Validate card against business consistency rules and generate review flags.

        Returns cleaned card dictionary and list of review flags.
        """
        flags: list[str] = []
        card_data = card.model_dump()

        # 1. Job slugs: drop any not in taxonomy
        valid_jobs: list[str] = []
        dropped_jobs: list[str] = []
        for job_slug in card.jobs:
            if is_valid_job(job_slug):
                valid_jobs.append(job_slug)
            else:
                dropped_jobs.append(job_slug)

        if dropped_jobs:
            flags.append(f"unknown jobs dropped: {', '.join(dropped_jobs)}")
        if not valid_jobs:
            flags.append("needs_review_no_jobs")
        card_data["jobs"] = valid_jobs

        # 2. Consistency rules
        # - pricing_model free or freemium requires has_free_tier = true
        if card.pricing_model in ("free", "freemium") and card.has_free_tier is not True:
            flags.append(f"consistency: {card.pricing_model} requires has_free_tier=True")

        # - pricing_model paid requires has_free_tier = false (or null)
        if card.pricing_model == "paid" and card.has_free_tier is True:
            flags.append("consistency: paid cannot have has_free_tier=True")

        # - pricing_model free_trial requires has_free_tier = false (or null)
        if card.pricing_model == "free_trial" and card.has_free_tier is True:
            flags.append("consistency: free_trial cannot have has_free_tier=True")

        # - has_free_tier = true requires a non-empty free_tier_summary
        if card.has_free_tier is True and not (card.free_tier_summary and card.free_tier_summary.strip()):
            flags.append("consistency: has_free_tier requires non-empty free_tier_summary")

        # - paid/freemium with starting_price_monthly_usd null gets a flag
        if card.pricing_model in ("paid", "freemium") and card.starting_price_monthly_usd is None:
            flags.append("missing_starting_price")

        # - unknown pricing_model gets a flag
        if card.pricing_model == "unknown":
            flags.append("pricing_model_unknown")

        # - missing pricing_url gets a flag
        if not card.pricing_url:
            flags.append("missing_pricing_url")

        # 3. unknowns list -> review flags
        for u in card.unknowns:
            if u and u.strip():
                flags.append(u.strip())

        return card_data, flags

    @classmethod
    async def process_evidence(
        cls,
        card_data: dict[str, Any],
        official_domains: set[str],
        flags: list[str],
    ) -> None:
        """Validate evidence sources against official domains and verify quotes via SSRF-safe fetch."""
        raw_evidence = card_data.get("evidence") or {}
        cleaned_evidence: dict[str, Any] = {}
        page_cache: dict[str, dict[str, Any]] = {}

        for field, item in raw_evidence.items():
            if not item:
                cleaned_evidence[field] = None
                continue

            # Ensure item is a dict or EvidenceItem
            if isinstance(item, EvidenceItem):
                item_dict = item.model_dump()
            elif isinstance(item, dict):
                item_dict = dict(item)
            else:
                continue

            src_url = item_dict.get("source_url", "")
            quote = item_dict.get("quote", "")

            # Rule: source_url must be on an official domain
            if not is_on_official_domain(src_url, official_domains):
                # Discard evidence, set claimed field to null, flag card
                cleaned_evidence[field] = None
                if field == "pricing_model":
                    card_data["pricing_model"] = "unknown"
                elif field in card_data:
                    card_data[field] = None
                flags.append(f"evidence off-domain: {field}")
                continue

            # Rule: Quote check via SSRF-safe fetcher
            try:
                if src_url not in page_cache:
                    page_cache[src_url] = await fetch_page_safe(src_url)
                fetch_res = page_cache[src_url]
                if not fetch_res.get("ok") or not fetch_res.get("text"):
                    item_dict["checked"] = "unknown"
                else:
                    page_norm = normalize_for_quote_match(fetch_res["text"])
                    quote_norm = normalize_for_quote_match(quote)
                    if quote_norm and quote_norm in page_norm:
                        item_dict["checked"] = True
                    else:
                        item_dict["checked"] = False
                        flags.append(f"quote mismatch: {field}")
            except Exception as e:
                logger.warning(f"Error checking quote for {src_url}: {e}")
                item_dict["checked"] = "unknown"

            cleaned_evidence[field] = item_dict

        card_data["evidence"] = cleaned_evidence

    @classmethod
    async def import_single_card(
        cls,
        db: Session,
        card: CardImport,
        research_provider: str = "perplexity_manual",
        target_tool_id: int | None = None,
    ) -> CardImportResult:
        """Import or update a single tool card."""
        try:
            # 1. Compute official domains
            official_domains = cls.compute_official_domains(card)

            # 2. Consistency validation and initial flags
            card_data, flags = cls.validate_and_flag_consistency(card)

            # 3. Process evidence and quotes
            await cls.process_evidence(card_data, official_domains, flags)

            # 4. Upsert into database
            name_norm = card.name.strip().lower()
            url_norm = card.official_url.strip()

            if target_tool_id:
                existing_tool = db.query(Tool).filter(Tool.id == target_tool_id).first()
            else:
                existing_tool = (
                    db.query(Tool)
                    .filter(
                        (func.lower(Tool.name) == name_norm)
                        | (Tool.url == url_norm)
                    )
                    .first()
                )

            pricing_fields = (
                "pricing_model",
                "has_free_tier",
                "starting_price_monthly_usd",
                "free_tier_summary",
            )

            now = datetime.now(UTC)

            if existing_tool:
                # Existing tool updated
                # If url changed, add review flag
                if existing_tool.url != url_norm:
                    flags.append("url_changed")

                # If a verified tool's pricing fields change, set back to researched
                if existing_tool.status == "verified":
                    pricing_changed = any(
                        getattr(existing_tool, pf) != card_data.get(pf)
                        for pf in pricing_fields
                    )
                    if pricing_changed:
                        flags.append("pricing_changed_reverify")

                # Update fields (Preserve affiliate_url, verified_by, verified_at, logo_url, og_image_url)
                existing_tool.name = card.name.strip()
                existing_tool.url = url_norm
                existing_tool.docs_url = card_data["docs_url"]
                existing_tool.domain = card.domain
                existing_tool.category = card.domain  # DB backward compatibility
                existing_tool.jobs = card_data["jobs"]

                existing_tool.pricing_model = card_data["pricing_model"]
                existing_tool.has_free_tier = card_data["has_free_tier"]
                existing_tool.free_tier_summary = card_data["free_tier_summary"]
                existing_tool.free_tier_limits = card_data["free_tier_limits"]
                existing_tool.starting_price_monthly_usd = card_data["starting_price_monthly_usd"]
                existing_tool.pricing_notes = card_data["pricing_notes"]
                existing_tool.credit_card_required = card_data["credit_card_required"]
                existing_tool.watermark_on_free = card_data["watermark_on_free"]
                existing_tool.commercial_use_on_free = card_data["commercial_use_on_free"]
                existing_tool.pricing_url = card_data["pricing_url"]
                existing_tool.pricing_checked_at = now

                existing_tool.platforms = card_data["platforms"]
                existing_tool.skill_level = card_data["skill_level"]
                existing_tool.tagline = card_data["tagline"]
                existing_tool.summary = card_data["summary"]
                existing_tool.how_it_helps = card_data["how_it_helps"]
                existing_tool.pros = card_data["pros"]
                existing_tool.cons = card_data["cons"]
                existing_tool.best_for = card_data["best_for"]
                existing_tool.not_for = card_data["not_for"]

                existing_tool.prompt_style = card_data.get("prompt_style") or {}
                existing_tool.input_types = card_data["input_types"]
                existing_tool.output_types = card_data["output_types"]

                existing_tool.ecosystem = card_data["ecosystem"]
                existing_tool.kind = card_data["kind"]
                existing_tool.model_id = card_data["model_id"]
                existing_tool.api_snippet = card_data["api_snippet"]

                existing_tool.status = "researched"
                existing_tool.evidence = card_data["evidence"]
                # Deduplicate flags preserving order
                combined_flags = list(dict.fromkeys(flags))
                existing_tool.review_flags = combined_flags
                existing_tool.official_domains = list(official_domains)
                existing_tool.research_provider = research_provider
                existing_tool.researched_at = now

                # Logo pipeline: only if not manually set
                if getattr(existing_tool, "logo_source", None) != "manual":
                    try:
                        resolved_logo, resolved_src, resolved_og = await process_tool_logo(
                            tool_url=existing_tool.url,
                            official_domains=list(official_domains),
                            logo_source_url=card.logo_source_url,
                            current_logo_url=existing_tool.logo_url,
                            current_logo_source=existing_tool.logo_source,
                            current_og_image_url=existing_tool.og_image_url,
                            tool_slug=existing_tool.name.lower(),
                        )
                        if resolved_logo:
                            existing_tool.logo_url = resolved_logo
                            existing_tool.logo_source = resolved_src
                        if resolved_og:
                            existing_tool.og_image_url = resolved_og
                    except Exception as le:
                        logger.warning("Error resolving logo for %s: %s", existing_tool.name, le)
                        existing_tool.logo_url = None
                        existing_tool.logo_source = None
                        flags.append(f"logo upload failed: {str(le)}")
                        combined_flags = list(dict.fromkeys(flags))
                        existing_tool.review_flags = combined_flags

                db.commit()
                db.refresh(existing_tool)

                return CardImportResult(
                    name=card.name,
                    status="updated",
                    tool_id=existing_tool.id,
                    flags=combined_flags,
                    error=None,
                )

            # New tool created
            resolved_logo, resolved_src, resolved_og = None, None, None
            try:
                resolved_logo, resolved_src, resolved_og = await process_tool_logo(
                    tool_url=url_norm,
                    official_domains=list(official_domains),
                    logo_source_url=card.logo_source_url,
                    tool_slug=card.name.strip().lower(),
                )
            except Exception as le:
                logger.warning("Error resolving logo for %s: %s", card.name, le)
                resolved_logo = None
                resolved_src = None
                flags.append(f"logo upload failed: {str(le)}")

            combined_flags = list(dict.fromkeys(flags))

            new_tool = Tool(
                name=card.name.strip(),
                url=url_norm,
                affiliate_url=None,
                docs_url=card_data["docs_url"],
                domain=card.domain,
                category=card.domain,
                jobs=card_data["jobs"],
                pricing_model=card_data["pricing_model"],
                has_free_tier=card_data["has_free_tier"],
                free_tier_summary=card_data["free_tier_summary"],
                free_tier_limits=card_data["free_tier_limits"],
                starting_price_monthly_usd=card_data["starting_price_monthly_usd"],
                pricing_notes=card_data["pricing_notes"],
                credit_card_required=card_data["credit_card_required"],
                watermark_on_free=card_data["watermark_on_free"],
                commercial_use_on_free=card_data["commercial_use_on_free"],
                pricing_url=card_data["pricing_url"],
                pricing_checked_at=now,
                platforms=card_data["platforms"],
                skill_level=card_data["skill_level"],
                tagline=card_data["tagline"],
                summary=card_data["summary"],
                how_it_helps=card_data["how_it_helps"],
                pros=card_data["pros"],
                cons=card_data["cons"],
                best_for=card_data["best_for"],
                not_for=card_data["not_for"],
                prompt_style=card_data.get("prompt_style") or {},
                input_types=card_data["input_types"],
                output_types=card_data["output_types"],
                ecosystem=card_data["ecosystem"],
                kind=card_data["kind"],
                model_id=card_data["model_id"],
                api_snippet=card_data["api_snippet"],
                logo_url=resolved_logo,
                logo_source=resolved_src,
                og_image_url=resolved_og,
                status="researched",
                evidence=card_data["evidence"],
                review_flags=combined_flags,
                official_domains=list(official_domains),
                research_provider=research_provider,
                researched_at=now,
                is_pick=False,
            )
            db.add(new_tool)
            db.commit()
            db.refresh(new_tool)

            return CardImportResult(
                name=card.name,
                status="created",
                tool_id=new_tool.id,
                flags=combined_flags,
                error=None,
            )

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to import card {card.name}: {e}")
            return CardImportResult(
                name=card.name,
                status="error",
                tool_id=None,
                flags=[],
                error=str(e),
            )

    @classmethod
    async def import_batch(
        cls,
        db: Session,
        cards: list[CardImport],
        expected_tool_names: list[str] | None = None,
        research_provider: str = "perplexity_manual",
    ) -> CardImportResponse:
        """Import a batch of cards, collecting results, counts, and missing expected tools."""
        results: list[CardImportResult] = []
        created = 0
        updated = 0
        rejected = 0

        imported_names_lower = set()

        for card in cards:
            imported_names_lower.add(card.name.strip().lower())
            result = await cls.import_single_card(db, card, research_provider=research_provider)
            results.append(result)
            if result.status == "created":
                created += 1
            elif result.status == "updated":
                updated += 1
            elif result.status in ("rejected", "error"):
                rejected += 1

        missing_tools: list[str] = []
        if expected_tool_names:
            for exp in expected_tool_names:
                if exp.strip().lower() not in imported_names_lower:
                    missing_tools.append(exp.strip())

        return CardImportResponse(
            created=created,
            updated=updated,
            rejected=rejected,
            missing_tools=missing_tools,
            results=results,
        )
