import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.middleware.auth_middleware import get_current_user
from app.services.bulk_upload_service import get_bulk_report_path

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{report_id}", summary="Download bulk upload error report")
async def download_bulk_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a CSV report of the rows that were skipped or failed during a
    bulk upload. The id is an unguessable token returned in the upload response;
    the endpoint validates it strictly to avoid path traversal."""
    path = get_bulk_report_path(report_id)
    if not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or expired",
        )
    return FileResponse(
        path,
        filename=f"bulk-upload-errors-{report_id}.csv",
        media_type="text/csv",
    )
