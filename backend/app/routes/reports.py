from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends, Query, Response, UploadFile, File
from app.services import report_service
from app.middleware.auth_middleware import require_admin_or_manager_or_md

router = APIRouter()

BACKUP_DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "backup_documents"
BACKUP_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
MAX_BACKUP_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024


def _sanitize_filename(filename: str) -> str:
    raw_name = Path(filename or "").name.strip()
    if not raw_name:
        raise ValueError("Invalid file name")

    safe = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in raw_name)
    if safe in {"", ".", ".."}:
        raise ValueError("Invalid file name")
    return safe


@router.get("/inventory")
async def get_inventory_report(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get device inventory report"""
    try:
        report = await report_service.get_inventory_report()

        return {
            "success": True,
            "message": "Inventory report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate inventory report: {str(e)}"
        )


@router.get("/distribution-summary")
async def get_distribution_summary(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get distribution summary report"""
    try:
        report = await report_service.get_distribution_summary()

        return {
            "success": True,
            "message": "Distribution summary generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate distribution summary: {str(e)}"
        )


@router.get("/defect-summary")
async def get_defect_summary(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get defect summary report"""
    try:
        report = await report_service.get_defect_summary()

        return {
            "success": True,
            "message": "Defect summary generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate defect summary: {str(e)}"
        )


@router.get("/return-summary")
async def get_return_summary(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get return summary report"""
    try:
        report = await report_service.get_return_summary()

        return {
            "success": True,
            "message": "Return summary generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate return summary: {str(e)}"
        )


@router.get("/user-activity")
async def get_user_activity_report(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get user activity report"""
    try:
        report = await report_service.get_user_activity_report()

        return {
            "success": True,
            "message": "User activity report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate user activity report: {str(e)}"
        )


@router.get("/device-utilization")
async def get_device_utilization_report(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Get device utilization report"""
    try:
        report = await report_service.get_device_utilization_report()

        return {
            "success": True,
            "message": "Device utilization report generated successfully",
            "data": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate device utilization report: {str(e)}"
        )


@router.post("/export")
async def export_report(
    export_data: dict,
    current_user: dict = Depends(require_admin_or_manager_or_md)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )


@router.get("/device-backup")
async def download_device_backup(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Download full device backup including each device journey path."""
    try:
        export_data = await report_service.get_device_backup_export(file_format=format)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download device backup: {str(e)}"
        )


@router.get("/returns-defects-backup")
async def download_returns_defects_backup(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Download backup for returned devices and defect reports."""
    try:
        export_data = await report_service.get_returns_defects_backup_export(file_format=format)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download returns/defects backup: {str(e)}"
        )


@router.get("/backup-documents")
async def list_backup_documents(
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """List uploaded backup documents available for download."""
    try:
        files = []
        for entry in BACKUP_DOCUMENTS_DIR.iterdir():
            if not entry.is_file():
                continue

            if "__" in entry.name:
                _, original_name = entry.name.split("__", 1)
            else:
                original_name = entry.name

            stat = entry.stat()
            files.append(
                {
                    "stored_name": entry.name,
                    "file_name": original_name,
                    "size": stat.st_size,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    .replace(tzinfo=None)
                    .isoformat(),
                }
            )

        files.sort(key=lambda item: item["uploaded_at"], reverse=True)

        return {
            "success": True,
            "message": "Backup documents fetched successfully",
            "data": files,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch backup documents: {str(e)}"
        )


@router.post("/backup-documents", status_code=status.HTTP_201_CREATED)
async def upload_backup_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin_or_manager_or_md)
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
        file_path = BACKUP_DOCUMENTS_DIR / stored_name
        file_path.write_bytes(content)

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload backup document: {str(e)}"
        )


@router.get("/backup-documents/{stored_name}")
async def download_backup_document(
    stored_name: str,
    current_user: dict = Depends(require_admin_or_manager_or_md)
):
    """Download one uploaded backup document by stored name."""
    try:
        safe_stored_name = _sanitize_filename(stored_name)
        file_path = (BACKUP_DOCUMENTS_DIR / safe_stored_name).resolve()
        if BACKUP_DOCUMENTS_DIR.resolve() not in file_path.parents:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        original_name = safe_stored_name.split("__", 1)[1] if "__" in safe_stored_name else safe_stored_name
        content = file_path.read_bytes()

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download backup document: {str(e)}"
        )
