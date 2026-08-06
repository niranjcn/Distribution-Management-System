import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends, Query, Response, UploadFile, File
from app.services import report_service, dashboard_service
from app.services.backup_vault_service import (
    list_vault_documents,
    upload_vault_document,
    download_vault_document,
)
from app.services.db_backup_scheduler import get_db_backup_schedule, update_db_backup_schedule
from app.middleware.auth_middleware import require_admin_or_manager_or_md_or_staff, require_admin_or_manager_or_md, RoleChecker
from app.core.activity_logger import log_business_activity

router = APIRouter()

logger = logging.getLogger(__name__)

MAX_BACKUP_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024

# Hierarchy reports (sub-distribution / cluster / operator) are available to
# management roles plus the field hierarchy (sub-distribution managers,
# sub-distributors and clusters). Field roles only ever see their own chain.
require_hierarchy_reports = RoleChecker([
    "super_admin",
    "md_director",
    "manager",
    "pdic_staff",
    "sub_distribution_manager",
    "sub_distributor",
    "cluster",
    "sub_distribution_employee",
])


def _sanitize_filename(filename: str) -> str:
    raw_name = Path(filename or "").name.strip()
    if not raw_name:
        raise ValueError("Invalid file name")

    safe = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in raw_name)
    if safe in {"", ".", ".."}:
        raise ValueError("Invalid file name")
    return safe


@router.get("/inventory", summary="Get device inventory report")
async def get_inventory_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get device inventory report"""
    try:
        report = await report_service.get_inventory_report(start_date, end_date)

        return {
            "success": True,
            "message": "Inventory report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/distribution-summary", summary="Get distribution summary report")
async def get_distribution_summary(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get distribution summary report"""
    try:
        report = await report_service.get_distribution_summary(start_date, end_date)

        return {
            "success": True,
            "message": "Distribution summary generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/defect-summary", summary="Get defect summary report")
async def get_defect_summary(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get defect summary report"""
    try:
        report = await report_service.get_defect_summary(start_date, end_date)

        return {
            "success": True,
            "message": "Defect summary generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/return-summary", summary="Get return summary report")
async def get_return_summary(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get return summary report"""
    try:
        report = await report_service.get_return_summary(start_date, end_date)

        return {
            "success": True,
            "message": "Return summary generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/user-activity", summary="Get user activity report")
async def get_user_activity_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get user activity report"""
    try:
        report = await report_service.get_user_activity_report(start_date, end_date)

        return {
            "success": True,
            "message": "User activity report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/device-utilization", summary="Get device utilization report")
async def get_device_utilization_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get device utilization report"""
    try:
        report = await report_service.get_device_utilization_report(start_date, end_date)

        return {
            "success": True,
            "message": "Device utilization report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/sub-distributions", summary="Get sub-distribution hierarchy report")
async def get_sub_distribution_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Get sub-distribution hierarchy report (operators, clusters, device rollups)."""
    try:
        report = await report_service.get_sub_distribution_report(start_date, end_date)

        return {
            "success": True,
            "message": "Sub-distribution report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/clusters", summary="Get cluster hierarchy report")
async def get_cluster_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_hierarchy_reports)
):
    """Get cluster hierarchy report (operators, device rollups)."""
    try:
        scope = await report_service._resolve_report_scope(current_user)
        report = await report_service.get_cluster_report(scope, start_date, end_date)

        return {
            "success": True,
            "message": "Cluster report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/operators", summary="Get operator hierarchy report")
async def get_operator_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_hierarchy_reports)
):
    """Get operator hierarchy report (parent cluster / sub-distribution, device rollups)."""
    try:
        scope = await report_service._resolve_report_scope(current_user)
        report = await report_service.get_operator_report(scope, start_date, end_date)

        return {
            "success": True,
            "message": "Operator report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/export", summary="Export report (placeholder for actual export functionality)")
async def export_report(
    export_data: dict,
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Export report (placeholder for actual export functionality)"""
    try:
        report_type = export_data.get("report_type", "inventory")
        format_type = export_data.get("format", "csv")

        return {
            "success": True,
            "message": f"{report_type} report exported as {format_type}",
            "data": {
                "report_type": report_type,
                "format": format_type,
                "download_url": f"/api/reports/download/{report_type}.{format_type}"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/device-backup", summary="Download full device backup including each device journey path")
async def download_device_backup(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Download full device backup including each device journey path."""
    try:
        export_data = await report_service.get_device_backup_export(file_format=format)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/reports/device-backup",
            description=f"{actor_name} initiated device backup download ({format})",
        )
        return Response(
            content=export_data["content"],
            media_type=export_data["media_type"],
            headers={
                "Content-Disposition": f"attachment; filename={export_data['filename']}"
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/returns-defects-backup", summary="Download backup for returned devices and defect reports")
async def download_returns_defects_backup(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Download backup for returned devices and defect reports."""
    try:
        export_data = await report_service.get_returns_defects_backup_export(file_format=format)
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/reports/returns-defects-backup",
            description=f"{actor_name} initiated returns and defects backup download ({format})",
        )
        return Response(
            content=export_data["content"],
            media_type=export_data["media_type"],
            headers={
                "Content-Disposition": f"attachment; filename={export_data['filename']}"
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/db-backup-schedule", summary="Get current MySQL backup schedule settings")
async def fetch_db_backup_schedule(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get current MySQL backup schedule settings."""
    try:
        schedule = await get_db_backup_schedule()
        return {
            "success": True,
            "message": "Database backup schedule fetched successfully",
            "data": schedule,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.put("/db-backup-schedule", summary="Update MySQL backup schedule settings")
async def save_db_backup_schedule(
    payload: dict,
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Update MySQL backup schedule settings."""
    try:
        schedule = await update_db_backup_schedule(payload)
        return {
            "success": True,
            "message": "Database backup schedule updated successfully",
            "data": schedule,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/backup-documents", summary="List uploaded backup documents available for download")
async def list_backup_documents(
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """List uploaded backup documents available for download."""
    try:
        files = await list_vault_documents()

        return {
            "success": True,
            "message": "Backup documents fetched successfully",
            "data": files,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/backup-documents", status_code=status.HTTP_201_CREATED, summary="Upload a file to backup documents vault")
async def upload_backup_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Upload a file to backup documents vault."""
    try:
        safe_original_name = _sanitize_filename(file.filename or "")

        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )
        if len(content) > MAX_BACKUP_DOCUMENT_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 25MB limit"
            )

        stored_name = f"{uuid4().hex[:12]}__{safe_original_name}"
        await upload_vault_document(stored_name, content)

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/reports/backup-vault-upload",
            description=f"{actor_name} uploaded backup vault document {safe_original_name}",
        )

        return {
            "success": True,
            "message": "Backup document uploaded successfully",
            "data": {
                "stored_name": stored_name,
                "file_name": safe_original_name,
                "size": len(content),
            },
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/backup-documents/{stored_name}", summary="Download one uploaded backup document by stored name")
async def download_backup_document(
    stored_name: str,
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Download one uploaded backup document by stored name."""
    try:
        safe_stored_name = _sanitize_filename(stored_name)
        original_name = safe_stored_name.split("__", 1)[1] if "__" in safe_stored_name else safe_stored_name
        try:
            content = await download_vault_document(safe_stored_name)
        except RuntimeError as exc:
            message = str(exc)
            if "not found" in message.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to download file"
            ) from exc

        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={original_name}"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/download", summary="Download a comprehensive system report as Excel")
async def download_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
):
    """Download a comprehensive system report as Excel."""
    try:
        export_data = await dashboard_service.generate_report(
            current_user, start_date, end_date
        )
        actor_name = current_user.get("name") or current_user.get("email") or "User"
        await log_business_activity(
            user=current_user,
            path="/activity/reports/download",
            description=f"{actor_name} downloaded system report",
        )
        return Response(
            content=export_data["content"],
            media_type=export_data["media_type"],
            headers={
                "Content-Disposition": f"attachment; filename={export_data['filename']}"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )

