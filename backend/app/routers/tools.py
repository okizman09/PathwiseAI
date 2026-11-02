from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db import get_db
from app.schemas.card_import import CardImportBatch, CardImportResponse
from app.schemas.tool import (
    AdminToolCreateRequest,
    PasteLogoUrlRequest,
    ToolMetricResponse,
    ToolPublicResponse,
    ToolResponse,
    ToolStatus,
    ToolUpdate,
)
from app.services import catalog as catalog_service
from app.services.importer import CardImporterService
from app.services.research.logos import (
    MAX_IMAGE_SIZE,
    detect_and_validate_image,
    fetch_binary_safe,
    process_tool_logo,
    upload_image_to_storage,
)

router = APIRouter(tags=["tools"])


# ---------------------------------------------------------------------------
# Admin Endpoints (Require X-Admin-Token)
# ---------------------------------------------------------------------------
@router.post(
    "/admin/tools/import-cards",
    response_model=CardImportResponse,
    dependencies=[Depends(get_current_admin_user)],
)
async def import_tool_cards(
    batch: CardImportBatch,
    db: Session = Depends(get_db),
):
    """Import researched Catalog v3 tool cards from JSON (Admin only)."""
    return await CardImporterService.import_batch(
        db=db,
        cards=batch.cards,
        expected_tool_names=batch.expected,
    )

@router.post(
    "/admin/tools",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin_user)],
)
async def create_admin_tool(
    req: AdminToolCreateRequest,
    db: Session = Depends(get_db),
):
    """Step 4: Create tool. If docs_url is provided, fetch page and extract card with Meta (draft)."""
    try:
        return await catalog_service.create_admin_tool_from_request(db=db, req=req)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except httpx.HTTPError as he:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to fetch documentation from {req.docs_url}: {str(he)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error extracting tool card: {str(e)}",
        )


@router.get(
    "/admin/tools/metrics",
    response_model=list[ToolMetricResponse],
    dependencies=[Depends(get_current_admin_user)],
)
async def list_admin_tool_metrics(db: Session = Depends(get_db)):
    """List per-tool usage signals and success rates (Admin only)."""
    return catalog_service.get_tool_metrics(db=db)


@router.get(
    "/admin/tools/stale",
    response_model=list[ToolResponse],
    dependencies=[Depends(get_current_admin_user)],
)
async def list_stale_admin_tools(db: Session = Depends(get_db)):
    """List verified tools whose pricing_checked_at is older than 30 days or not set."""
    return catalog_service.list_stale_tools(db=db)


@router.get(
    "/admin/tools",
    response_model=list[ToolResponse],
    dependencies=[Depends(get_current_admin_user)],
)
async def list_admin_tools(
    status: ToolStatus | None = Query(None, description="Filter by status"),
    category: str | None = Query(None, description="Filter by category"),
    domain: str | None = Query(None, description="Filter by domain"),
    db: Session = Depends(get_db),
):
    """List all tools (draft, verified, hidden) for administration."""
    return catalog_service.list_admin_tools(db=db, status=status, category=category, domain=domain)


@router.patch(
    "/admin/tools/{tool_id}",
    response_model=ToolResponse,
)
async def update_admin_tool(
    tool_id: int,
    tool_update: ToolUpdate,
    admin_user=Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Update fields of an existing tool or set status to verified."""
    tool = catalog_service.get_tool_by_id(db=db, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )
    try:
        return await catalog_service.update_tool(
            db=db,
            db_tool=tool,
            tool_update=tool_update,
            verified_by_user=getattr(admin_user, "email", "admin"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/admin/tools/{tool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin_user)],
)
async def delete_admin_tool(
    tool_id: int,
    db: Session = Depends(get_db),
):
    """Delete a tool from the catalog."""
    tool = catalog_service.get_tool_by_id(db=db, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )
    catalog_service.delete_tool(db=db, db_tool=tool)
    return None


@router.post(
    "/admin/tools/{tool_id}/recheck",
    dependencies=[Depends(get_current_admin_user)],
)
async def recheck_admin_tool(
    tool_id: int,
    body: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
):
    """Re-run research or diff a freshly pasted card JSON before applying."""
    try:
        if body and "card" in body and isinstance(body["card"], dict):
            return await catalog_service.diff_tool_card(
                db=db,
                tool_id=tool_id,
                fresh_card_data=body["card"],
                apply=bool(body.get("apply", False)),
            )
        return await catalog_service.recheck_tool(db=db, tool_id=tool_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recheck failed: {str(e)}")


@router.post(
    "/admin/tools/{tool_id}/fetch-logo",
    response_model=ToolResponse,
    dependencies=[Depends(get_current_admin_user)],
)
async def fetch_tool_logo(
    tool_id: int,
    db: Session = Depends(get_db),
):
    """Admin endpoint to automatically discover or fallback-fetch a tool's logo."""
    tool = catalog_service.get_tool_by_id(db=db, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )

    try:
        logo_url, logo_source, og_image_url = await process_tool_logo(
            tool_url=tool.url,
            official_domains=tool.official_domains or [],
            current_logo_url=tool.logo_url,
            current_logo_source=tool.logo_source,
            current_og_image_url=tool.og_image_url,
            tool_slug=tool.name.lower(),
            force_override=True,
        )
        tool.logo_url = logo_url
        tool.logo_source = logo_source
        if og_image_url:
            tool.og_image_url = og_image_url
        db.commit()
        db.refresh(tool)
        return tool
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fetch logo: {str(e)}")


@router.post(
    "/admin/tools/{tool_id}/paste-logo-url",
    response_model=ToolResponse,
    dependencies=[Depends(get_current_admin_user)],
)
async def paste_tool_logo_url(
    tool_id: int,
    req: PasteLogoUrlRequest,
    db: Session = Depends(get_db),
):
    """Admin endpoint to paste a direct logo URL. Downloads server-side, validates, and stores."""
    tool = catalog_service.get_tool_by_id(db=db, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )

    try:
        data, _ = await fetch_binary_safe(req.url)
        clean_bytes, mime, ext = detect_and_validate_image(data)
        public_url = await upload_image_to_storage(
            clean_bytes, mime, ext, path_prefix="logos", filename_hint=tool.name.lower()
        )
        tool.logo_url = public_url
        tool.logo_source = "manual"
        db.commit()
        db.refresh(tool)
        return tool
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process pasted logo URL: {str(e)}")


@router.post(
    "/admin/tools/{tool_id}/upload-logo",
    response_model=ToolResponse,
    dependencies=[Depends(get_current_admin_user)],
)
async def upload_tool_logo(
    tool_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Admin endpoint to upload a logo image (PNG, JPG, WebP, SVG, ICO, max 1 MB).
    Enforces 1 MB limit while streaming the request body.
    """
    tool = catalog_service.get_tool_by_id(db=db, tool_id=tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool with ID {tool_id} not found",
        )

    try:
        chunks: list[bytes] = []
        total_size = 0
        chunk_size = 64 * 1024
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File exceeds maximum allowed size of 1 MB ({MAX_IMAGE_SIZE} bytes)",
                )
            chunks.append(chunk)

        raw_bytes = b"".join(chunks)
        clean_bytes, mime, ext = detect_and_validate_image(raw_bytes)
        public_url = await upload_image_to_storage(
            clean_bytes, mime, ext, path_prefix="logos", filename_hint=tool.name.lower()
        )
        tool.logo_url = public_url
        tool.logo_source = "manual"
        db.commit()
        db.refresh(tool)
        return tool
    except HTTPException:
        db.rollback()
        raise
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")



def verify_cron_or_admin(
    x_cron_secret: str | None = Header(None, alias="X-Cron-Secret"),
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """Verify that request comes from Render cron (X-Cron-Secret header) or an admin user."""
    from app.core.config import settings
    if settings.CRON_SECRET:
        if x_cron_secret and x_cron_secret == settings.CRON_SECRET:
            return "cron"
        if authorization and authorization == f"Bearer {settings.CRON_SECRET}":
            return "cron"
    try:
        from app.api.deps import get_current_user
        current_u = get_current_user(authorization=authorization, db=db)
        return get_current_admin_user(current_user=current_u)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid CRON_SECRET or administrator token required.",
        )


@router.post(
    "/admin/jobs/check-links",
    dependencies=[Depends(verify_cron_or_admin)],
)
@router.post(
    "/admin/tools/check-links",
    dependencies=[Depends(verify_cron_or_admin)],
)
async def check_all_admin_links(
    db: Session = Depends(get_db),
):
    """Check all verified tool URLs; dead links set link_status=dead and hide the tool."""
    try:
        return await catalog_service.check_all_links(db=db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Link check failed: {str(e)}")



# ---------------------------------------------------------------------------
# Public Endpoints (No Token Required)
# ---------------------------------------------------------------------------
@router.get(
    "/tools",
    response_model=list[ToolPublicResponse],
)
async def list_public_tools(
    category: str | None = Query(None, description="Filter by category"),
    domain: str | None = Query(None, description="Filter by domain"),
    ecosystem: str | None = Query(None, description="Filter by ecosystem (e.g. meta)"),
    db: Session = Depends(get_db),
):
    """Public catalog: returns VERIFIED tools only."""
    return catalog_service.list_public_tools(db=db, category=category, domain=domain, ecosystem=ecosystem)

