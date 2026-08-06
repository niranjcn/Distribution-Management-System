import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.models.approval_request import ApprovalRequestCreate, ApprovalDecision
from app.middleware.auth_middleware import (
    get_current_user,
    require_approval_requester,
    require_approval_reviewer,
)
from app.services import approval_request_service
from app.core.activity_logger import log_business_activity

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/stage-bulk", summary="Parse an uploaded bulk file into an approval-request payload")
async def stage_bulk(
    kind: str = Form(...),
    file: UploadFile = File(...),
    role: Optional[str] = Form(None),
    parent_id: Optional[str] = Form(None),
    to_user_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    date_of_distribution: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        contents = await file.read()
        payload = await approval_request_service.stage_bulk_payload(
            requester=current_user,
            kind=kind,
            contents=contents,
            filename=file.filename or "",
            role=role,
            parent_id=parent_id,
            to_user_id=to_user_id,
            notes=notes,
            date_of_distribution=date_of_distribution,
        )
        return {
            "success": True,
            "message": "File parsed successfully",
            "data": {"payload": payload, "row_count": len(payload.get("rows") or [])},
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.post("", status_code=201, summary="Submit an employee approval request")
async def submit_request(
    data: ApprovalRequestCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await approval_request_service.submit_request(
            requester=current_user,
            request_type=data.request_type.value,
            payload=data.payload,
            summary=data.summary,
        )
        await log_business_activity(
            user=current_user,
            path="/activity/approval-requests/submit",
            description=(
                f"{current_user.get('name') or current_user.get('email')} submitted "
                f"{data.request_type.value} approval request ({result['data']['request_id']})"
            ),
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/my", summary="List the current employee's approval requests")
async def my_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_approval_requester),
):
    try:
        return {
            "success": True,
            "message": "Requests retrieved successfully",
            **await approval_request_service.get_my_requests(
                requester=current_user,
                page=page,
                page_size=page_size,
                status=status,
            ),
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/pending", summary="List approval requests awaiting the current approver")
async def pending_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: Optional[str] = Query(None),
    request_type: Optional[str] = Query(None, alias="type"),
    current_user: dict = Depends(require_approval_reviewer),
):
    try:
        return {
            "success": True,
            "message": "Requests retrieved successfully",
            **await approval_request_service.get_requests_for_approver(
                approver=current_user,
                page=page,
                page_size=page_size,
                status=status,
                request_type=request_type,
            ),
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.get("/{request_id}", summary="Get a single approval request")
async def request_detail(request_id: str, current_user: dict = Depends(get_current_user)):
    try:
        item = await approval_request_service.get_request_detail(request_id, current_user)
        return {"success": True, "message": "Request retrieved successfully", "data": item}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.post("/{request_id}/decide", summary="Approve or reject an employee approval request")
async def decide(
    request_id: str,
    decision: ApprovalDecision,
    current_user: dict = Depends(get_current_user),
):
    try:
        result = await approval_request_service.decide_request(
            approver=current_user,
            request_id=request_id,
            action=decision.action,
            review_note=decision.review_note,
        )
        await log_business_activity(
            user=current_user,
            path="/activity/approval-requests/decide",
            description=(
                f"{current_user.get('name') or current_user.get('email')} "
                f"{decision.action}d approval request ({request_id})"
            ),
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")


@router.post("/{request_id}/cancel", summary="Cancel a pending approval request (requester only)")
async def cancel(
    request_id: str,
    current_user: dict = Depends(require_approval_requester),
):
    try:
        return await approval_request_service.cancel_request(request_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
