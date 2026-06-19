import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File
from typing import Optional
from app.models.defect import (
    DefectCreate,
    DefectUpdate,
    DefectResolve,
    DefectStatusUpdate,
    DefectPaymentConfirmRequest,
    ReplaceDeviceRequest,
    ReplacementConfirmationRequest,
    DefectEnquiryRequest,
    DefectActionRequest,
)
from app.services import defect_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_manager, require_management, require_any_role
from app.core.activity_logger import build_field_change_summary, log_business_activity

router = APIRouter()

logger = logging.getLogger(__name__)
PAYMENT_BILL_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "defect_payments"
PAYMENT_BILL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_not_md_director(current_user: dict) -> None:
    if current_user.get("role") == "md_director":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MD/Director has read-only access to defects"
        )


def _get_defect_activity_device_identifier(defect: dict) -> str:
    device_type = str(defect.get("device_type") or "").strip().lower()
    normalized_type = device_type.replace("-", " ")
    is_set_top_box = normalized_type in {"set top box", "setup box", "sb", "stb"}

    nuid = str(defect.get("device_nuid") or defect.get("nuid") or "").strip()
    serial_number = str(defect.get("device_serial") or "").strip()

    if is_set_top_box and nuid:
        return nuid
    if serial_number:
        return serial_number
    if nuid:
        return nuid
    return str(defect.get("device_id") or "unknown").strip()


@router.post("/upload-photo", tags=["Defects"])
async def upload_defect_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a defect photo to rclone and return its accessible URL."""
    _ensure_not_md_director(current_user)
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_ext = Path(file.filename).suffix
    unique_filename = f"{uuid4().hex}{file_ext}"
    
    try:
        content = await file.read()
        from app.services.rclone_storage import upload_file_to_rclone
        await upload_file_to_rclone("defect_photos", unique_filename, content)
        
        from app.config import settings
        return {"url": f"{settings.API_V1_PREFIX}/uploads/defect_photos/{unique_filename}"}
    except Exception as e:
        logger.error(f"Error uploading defect photo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload defect photo: {str(e)}"
        )


def _get_device_identifier_for_activity(device: dict, *, fallback: str = "unknown") -> str:
    device_type = str(device.get("device_type") or "").strip().lower().replace("-", " ")
    is_set_top_box = device_type in {"set top box", "setup box", "sb", "stb"}

    serial_number = str(device.get("serial_number") or "").strip()
    nuid = str(device.get("nuid") or device.get("device_nuid") or "").strip()

    if is_set_top_box and nuid:
        return nuid
    if serial_number:
        return serial_number
    if nuid:
        return nuid
    return str(fallback or "unknown").strip() or "unknown"


@router.get("/replacements")
async def get_replacement_defects(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1),
    current_user: dict = Depends(require_any_role)
):
    """Get all replacement mappings (defects with replacement_device_id), scoped by hierarchy."""
    try:
        result = await defect_service.get_replacement_defects(
            current_user=current_user,
            page=page,
            page_size=page_size
        )

        return {
            "success": True,
            "message": "Replacement mappings retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/replacements/pending")
async def get_pending_replacement_defects(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1),
    current_user: dict = Depends(require_any_role)
):
    """Get defective devices waiting for replacement assignment."""
    try:
        result = await defect_service.get_pending_replacement_defects(
            current_user=current_user,
            page=page,
            page_size=page_size
        )

        return {
            "success": True,
            "message": "Pending replacement defects retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/pending-dues/users")
async def get_pending_due_users(
    current_user: dict = Depends(require_any_role)
):
    """Get hierarchy-scoped pending dues summary for returned defective devices."""
    try:
        rows = await defect_service.get_pending_dues_users(current_user=current_user)
        return {
            "success": True,
            "message": "Pending dues users retrieved successfully",
            "data": rows,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/pending-dues/users/{user_id}")
async def get_pending_dues_for_user(
    user_id: str,
    current_user: dict = Depends(require_any_role)
):
    """Get hierarchy-scoped pending due items for a specific user."""
    try:
        payload = await defect_service.get_pending_dues_for_user(user_id, current_user=current_user)
        return {
            "success": True,
            "message": "Pending dues details retrieved successfully",
            "data": payload,
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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


@router.get("/pending-dues/me")
async def get_my_pending_dues(
    current_user: dict = Depends(require_any_role)
):
    """Get pending due items for the authenticated field user."""
    _ensure_not_md_director(current_user)
    role = str(current_user.get("role") or "").lower()
    if role not in {"sub_distributor", "cluster", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is available for sub distributor, cluster, and operator roles only",
        )

    try:
        user_id = str(current_user.get("id") or current_user.get("_id") or "")
        payload = await defect_service.get_pending_dues_for_user(user_id, current_user=current_user)
        return {
            "success": True,
            "message": "Pending payments retrieved successfully",
            "data": payload,
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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


@router.get("")
async def get_defects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    defect_status: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    defect_type: Optional[str] = None,
    search: Optional[str] = None,
    search_by: Optional[str] = Query("all"),
    current_user: dict = Depends(get_current_user)
):
    """Get all defect reports with pagination and filters"""
    try:
        # Determine scope based on user role.
        # Always cast id to str to avoid SQLite integer/text type mismatches (422 cause).
        user_id_str = str(current_user["id"])
        reported_by = None
        holder_user_id = None

        role = current_user.get("role", "")
        if role == "operator":
            # holder_user_id condition in the service already covers:
            # "defects reported by me" OR "defects where my device is the holder"
            # Setting both reported_by AND holder_user_id would AND them, over-filtering.
            holder_user_id = user_id_str
        elif role in ["cluster", "sub_distribution_manager", "sub_distributor"]:
            # Hierarchy roles are scoped in service-side visibility logic.
            pass
        elif role not in ["super_admin", "md_director", "manager", "pdic_staff"]:
            # Any other non-management role: show only their own reported defects
            reported_by = user_id_str

        result = await defect_service.get_defects(
            page=page,
            page_size=page_size,
            status=defect_status,
            severity=severity,
            defect_type=defect_type,
            reported_by=reported_by,
            holder_user_id=holder_user_id,
            search=search,
            search_by=search_by,
            visibility_user=current_user
        )

        return {
            "success": True,
            "message": "Defect reports retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/forward-to-management")
async def forward_defect_to_management(
    defect_id: str,
    action_data: DefectActionRequest,
    current_user: dict = Depends(require_any_role)
):
    """Allow sub distributor to forward a routed defect to manager/admin queue."""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.forward_defect_to_management(
            defect_id=defect_id,
            forwarder=current_user,
            notes=action_data.notes
        )
        return {
            "success": True,
            "message": "Defect forwarded to manager/admin successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/{defect_id}")
async def get_defect(
    defect_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get defect report by ID"""
    try:
        defect = await defect_service.get_defect_by_id(defect_id)

        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect report not found"
            )

        return {
            "success": True,
            "message": "Defect report retrieved successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_defect(
    defect_data: DefectCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new defect report"""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.create_defect(
            defect_data=defect_data,
            reporter=current_user
        )

        if not defect:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create defect report"
            )

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        device_identifier = _get_defect_activity_device_identifier(defect)
        await log_business_activity(
            user=current_user,
            path="/activity/defects/create",
            description=(
                f"{actor_name} reported defect {defect.get('report_id') or defect.get('id')} "
                f"for device {device_identifier}"
            ),
        )

        return {
            "success": True,
            "message": "Defect report created successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.put("/{defect_id}")
async def update_defect(
    defect_id: str,
    defect_data: DefectUpdate,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Update defect report"""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.update_defect(defect_id, defect_data)

        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect report not found"
            )

        return {
            "success": True,
            "message": "Defect report updated successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.delete("/{defect_id}")
async def delete_defect(
    defect_id: str,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Delete defect report"""
    _ensure_not_md_director(current_user)

    try:
        success = await defect_service.delete_defect(defect_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect report not found"
            )

        return {
            "success": True,
            "message": "Defect report deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.patch("/{defect_id}/status")
async def update_defect_status(
    defect_id: str,
    status_update: DefectStatusUpdate,
    current_user: dict = Depends(require_management)
):
    """Update defect status"""
    _ensure_not_md_director(current_user)

    try:
        before = await defect_service.get_defect_by_id(defect_id)
        defect = await defect_service.update_defect_status(
            defect_id=defect_id,
            status=status_update.status.value,
            user=current_user,
            notes=status_update.notes,
            return_amount=status_update.return_amount,
            payment_bill_url=status_update.payment_bill_url,
        )

        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect report not found"
            )

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        edited_fields = ["status"]
        if status_update.notes is not None:
            edited_fields.append("notes")
        if status_update.return_amount is not None:
            edited_fields.append("return_amount")
        if status_update.payment_bill_url is not None:
            edited_fields.append("payment_bill_url")

        change_summary = build_field_change_summary(
            before=before or {},
            after=defect or {},
            fields=edited_fields,
            exclude_fields={"updated_at"},
        )
        await log_business_activity(
            user=current_user,
            path="/activity/defects/status-update",
            description=(
                f"{actor_name} updated defect status for "
                f"{defect.get('report_id') or defect_id}; changes: {change_summary}"
            ),
        )

        return {
            "success": True,
            "message": "Defect status updated successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/payment-bill")
async def upload_defect_payment_bill(
    defect_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin_or_manager),
):
    """Upload bill/proof file for a defect-related payment due."""
    _ensure_not_md_director(current_user)

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG, WEBP, and PDF files are allowed"
        )

    try:
        content = await file.read()
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be 8MB or less")

        file_name = f"defect_{defect_id}_{datetime.now().replace(tzinfo=None).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}{suffix}"
        
        from app.services.rclone_storage import upload_file_to_rclone
        await upload_file_to_rclone("defect_payments", file_name, content)

        bill_url = f"/api/uploads/defect_payments/{file_name}"
        defect = await defect_service.set_defect_payment_bill_url(defect_id=defect_id, bill_url=bill_url)
        if not defect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defect report not found")

        return {
            "success": True,
            "message": "Payment bill uploaded successfully",
            "data": {
                "payment_bill_url": bill_url,
                "defect": defect,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/confirm-payment")
async def confirm_defect_payment(
    defect_id: str,
    payload: DefectPaymentConfirmRequest,
    current_user: dict = Depends(require_admin_or_manager),
):
    """Confirm that user payment for defective return has been received."""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.confirm_defect_payment(
            defect_id=defect_id,
            confirmer=current_user,
            notes=payload.notes,
        )
        if not defect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defect report not found")

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        amount = float(defect.get("return_amount") or 0)
        await log_business_activity(
            user=current_user,
            path="/activity/pending-dues/payment-confirmed",
            description=(
                f"{actor_name} confirmed pending due payment for defect "
                f"{defect.get('report_id') or defect_id} ({amount:.2f})"
            ),
        )

        return {
            "success": True,
            "message": "Defect payment confirmed successfully",
            "data": defect,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.patch("/{defect_id}/resolve")
async def resolve_defect(
    defect_id: str,
    resolve_data: DefectResolve,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Resolve a defect report"""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.resolve_defect(
            defect_id=defect_id,
            resolution=resolve_data.resolution,
            resolver=current_user
        )

        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect report not found"
            )

        return {
            "success": True,
            "message": "Defect resolved successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/replace")
async def replace_defect_device(
    defect_id: str,
    replace_data: ReplaceDeviceRequest,
    current_user: dict = Depends(require_management)
):
    """Replace a defective device by selecting an existing device or registering a new one."""
    if not any([
        replace_data.replacement_device_id,
        replace_data.mac_address,
        replace_data.serial_number,
        replace_data.register_device
    ]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide replacement_device_id, mac_address, serial_number, or register_device"
        )
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.replace_defect_device(
            defect_id=defect_id,
            replacement_device_id=replace_data.replacement_device_id,
            mac_address=replace_data.mac_address,
            serial_number=replace_data.serial_number,
            register_device=replace_data.register_device.model_dump() if replace_data.register_device else None,
            notes=replace_data.notes,
            return_amount=replace_data.return_amount,
            service_charge=replace_data.service_charge,
            payment_bill_url=replace_data.payment_bill_url,
            resolver=current_user
        )

        actor_name = current_user.get("name") or current_user.get("email") or "User"
        defective_device = defect.get("defective_device") or {}
        replacement_device = defect.get("replacement_device") or {}
        old_ref = _get_device_identifier_for_activity(
            defective_device,
            fallback=(defect.get("device_serial") or defect.get("device_id") or "unknown"),
        )
        new_ref = _get_device_identifier_for_activity(
            replacement_device,
            fallback=(
                defect.get("replacement_device_serial")
                or defect.get("replacement_device_nuid")
                or defect.get("replacement_device_id")
                or "unknown"
            ),
        )
        amount = float(defect.get("return_amount") or 0)
        amount_note = f"; bill amount {amount:.2f}" if amount > 0 else ""
        await log_business_activity(
            user=current_user,
            path="/activity/defects/replacement-assigned",
            description=(
                f"{actor_name} assigned replacement device {new_ref} for defective device {old_ref}"
                f" on defect {defect.get('report_id') or defect_id}{amount_note}"
            ),
        )

        return {
            "success": True,
            "message": "Device replaced successfully and assigned to the original operator",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/replacement/confirm")
async def confirm_replacement_receipt(
    defect_id: str,
    confirmation_data: ReplacementConfirmationRequest,
    current_user: dict = Depends(require_any_role)
):
    """Confirm replacement device receipt (operator confirmation)."""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.confirm_replacement_receipt(
            defect_id=defect_id,
            confirmer=current_user,
            notes=confirmation_data.notes
        )
        return {
            "success": True,
            "message": "Replacement receipt confirmed successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/enquire")
async def enquire_replacement_status(
    defect_id: str,
    enquiry_data: DefectEnquiryRequest,
    current_user: dict = Depends(require_any_role)
):
    """Operator sends replacement-status enquiry to management users."""
    if current_user.get("role") not in {"operator", "cluster", "sub_distributor"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only operator, cluster, or sub distributor users can send replacement enquiries"
        )

    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.enquire_replacement_status(
            defect_id=defect_id,
            enquirer=current_user,
            message=enquiry_data.message
        )
        return {
            "success": True,
            "message": "Replacement enquiry sent successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/resend-confirmation")
async def resend_replacement_confirmation(
    defect_id: str,
    current_user: dict = Depends(require_management)
):
    """Resend replacement confirmation reminder to the operator."""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.resend_replacement_confirmation(
            defect_id=defect_id,
            sender=current_user
        )
        return {
            "success": True,
            "message": "Replacement confirmation resent successfully",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/{defect_id}/mark-waiting")
async def mark_replacement_waiting(
    defect_id: str,
    action_data: DefectActionRequest,
    current_user: dict = Depends(require_management)
):
    """Mark replacement status as waiting for PDIC shipment."""
    _ensure_not_md_director(current_user)

    try:
        defect = await defect_service.mark_replacement_waiting(
            defect_id=defect_id,
            manager=current_user,
            notes=action_data.notes
        )
        return {
            "success": True,
            "message": "Replacement status updated to waiting",
            "data": defect
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )




