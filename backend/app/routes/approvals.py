import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from app.services import approval_service
from app.middleware.auth_middleware import require_management

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/pending", summary="Get unified pending approvals across distributions, returns, and defects")
async def get_pending_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    item_type: Optional[str] = Query(None, alias="type"),
    current_user: dict = Depends(require_management)
):
    """Get a unified, paginated list of items waiting for approval or confirmation.

    Merges pending distributions, pending/approved returns, and reported defects into a
    single feed sorted by request date, with per-type counts for the tab badges.
    """
    try:
        result = await approval_service.get_pending_approvals(
            current_user=current_user,
            page=page,
            page_size=page_size,
            item_type=item_type,
        )

        return {
            "success": True,
            "message": "Pending approvals retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
            "counts": result["counts"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later."
        )
