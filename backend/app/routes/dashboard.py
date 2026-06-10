import logging
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel
from app.services import dashboard_service
from app.middleware.auth_middleware import get_current_user, require_admin_or_md, require_any_role

router = APIRouter()

logger = logging.getLogger(__name__)


class ClientActivityTrackRequest(BaseModel):
    action: str
    description: str
    context: str | None = None


@router.get("/scope-users")
async def get_scope_users(
    current_user: dict = Depends(get_current_user)
):
    """Get users visible in the hierarchy scope selector."""
    try:
        data = await dashboard_service.get_scope_users(current_user)
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/user-kpi/{user_id}")
async def get_user_kpi(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get KPI data for a specific user in the hierarchy."""
    try:
        data = await dashboard_service.get_user_kpi(current_user, user_id)
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics based on user role"""
    try:
        stats = await dashboard_service.get_dashboard_stats(current_user)

        return {
            "success": True,
            "message": "Dashboard stats retrieved successfully",
            "data": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get recent activities for dashboard"""
    try:
        activities = await dashboard_service.get_recent_activities(current_user, limit)

        return {
            "success": True,
            "message": "Recent activities retrieved successfully",
            "data": activities
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/charts/distributions")
async def get_distribution_chart_data(
    current_user: dict = Depends(get_current_user)
):
    """Get distribution chart data"""
    try:
        data = await dashboard_service.get_distribution_chart_data()

        return {
            "success": True,
            "message": "Distribution chart data retrieved successfully",
            "data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/charts/defects")
async def get_defect_chart_data(
    current_user: dict = Depends(get_current_user)
):
    """Get defect chart data"""
    try:
        data = await dashboard_service.get_defect_chart_data()

        return {
            "success": True,
            "message": "Defect chart data retrieved successfully",
            "data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/alerts")
async def get_system_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Get system alerts for dashboard"""
    try:
        alerts = await dashboard_service.get_system_alerts(current_user)

        return {
            "success": True,
            "message": "System alerts retrieved successfully",
            "data": alerts
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/advanced-metrics")
async def get_advanced_dashboard_metrics(
    current_user: dict = Depends(get_current_user)
):
    """Get advanced management analytics for graph-heavy dashboards."""
    try:
        data = await dashboard_service.get_advanced_dashboard_metrics(current_user)

        return {
            "success": True,
            "message": "Advanced dashboard metrics retrieved successfully",
            "data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/activities")
async def get_admin_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    actor: str | None = None,
    category: str | None = None,
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    current_user: dict = Depends(require_admin_or_md),
):
    """Get admin-wide activities with filtering."""
    try:
        result = await dashboard_service.get_admin_activities(
            page=page,
            page_size=page_size,
            actor=actor,
            category=category,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "success": True,
            "message": "Activities retrieved successfully",
            "data": result["data"],
            "pagination": result["pagination"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.post("/activities/track")
async def track_client_activity(
    payload: ClientActivityTrackRequest,
    current_user: dict = Depends(require_any_role),
):
    """Track explicit client-side actions like local export clicks."""
    try:
        await dashboard_service.track_client_activity(
            user=current_user,
            action=payload.action,
            description=payload.description,
            context=payload.context,
        )
        return {
            "success": True,
            "message": "Client activity tracked",
        }
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )



