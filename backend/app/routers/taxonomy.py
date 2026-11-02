"""Taxonomy router for Pathwise Catalog v3."""
from typing import Any

from fastapi import APIRouter

from app.taxonomy import get_taxonomy_payload

router = APIRouter(tags=["taxonomy"])


@router.get("/taxonomy")
def get_public_taxonomy() -> dict[str, Any]:
    """Public endpoint returning domains, jobs, and display labels for the catalog."""
    return get_taxonomy_payload()
