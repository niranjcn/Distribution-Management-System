import logging
from fastapi import APIRouter, HTTPException, Query, status, Depends, Response
from pydantic import BaseModel
from app.services import dashboard_service, user_service
from app.database import get_db, rows_to_list
from app.middleware.auth_middleware import get_current_user, require_admin_or_md, require_any_role, require_admin_or_manager_or_md_or_staff
from app.core.activity_logger import log_business_activity

router = APIRouter()

logger = logging.getLogger(__name__)


class ClientActivityTrackRequest(BaseModel):
    action: str
    description: str
    context: str | None = None


@router.get("/scope-users", summary="Get users visible in the hierarchy scope selector.")
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


@router.get("/user-kpi/{user_id}", summary="Get KPI data for a specific user in the hierarchy.")
async def get_user_kpi(
    user_id: str,
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get KPI data for a specific user in the hierarchy."""
    try:
        data = await dashboard_service.get_user_kpi(current_user, user_id, start_date, end_date)
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )


@router.get("/stats", summary="Get dashboard statistics based on user role")
async def get_dashboard_stats(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics based on user role"""
    try:
        stats = await dashboard_service.get_dashboard_stats(current_user, start_date, end_date)

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


@router.get("/recent-activities", summary="Get recent activities for dashboard")
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


@router.get("/charts/distributions", summary="Get distribution chart data")
async def get_distribution_chart_data(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get distribution chart data"""
    try:
        data = await dashboard_service.get_distribution_chart_data(start_date, end_date)

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


@router.get("/charts/defects", summary="Get defect chart data")
async def get_defect_chart_data(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get defect chart data"""
    try:
        data = await dashboard_service.get_defect_chart_data(start_date, end_date)

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


@router.get("/alerts", summary="Get system alerts for dashboard")
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


@router.get("/advanced-metrics", summary="Get advanced management analytics for graph-heavy dashboards.")
async def get_advanced_dashboard_metrics(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get advanced management analytics for graph-heavy dashboards."""
    try:
        data = await dashboard_service.get_advanced_dashboard_metrics(current_user, start_date, end_date)

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


@router.get("/distribution-device-analytics", summary="Get distribution device analytics for admin/manager dashboards.")
async def get_distribution_device_analytics(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_md)
):
    """Get distribution device analytics for admin/manager dashboards."""
    try:
        data = await dashboard_service.get_distribution_device_analytics(start_date, end_date)
        return {
            "success": True,
            "message": "Distribution device analytics retrieved successfully",
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


@router.get("/activities", summary="Get admin-wide activities with filtering.")
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


@router.post("/activities/track", summary="Track explicit client-side actions like local export clicks.")
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


@router.get("/view-as/{target_user_id}", summary="Get dashboard data as seen by the target user (admin/manager only).")
async def view_as_dashboard(
    target_user_id: str,
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_md)
):
    """Get dashboard data as seen by the target user (admin/manager only)."""
    try:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, name, email, role FROM users WHERE id = ?",
                (int(target_user_id),)
            )
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            target_role = str(row["role"])
            if target_role not in ("sub_distributor", "cluster", "operator", "sub_distribution_manager"):
                raise HTTPException(status_code=400, detail="Can only view dashboards for sub-distributors, clusters, and operators")

            target_user = {
                "_id": str(row["id"]),
                "id": str(row["id"]),
                "role": target_role,
                "name": str(row.get("name", "")),
                "email": str(row.get("email", "")),
            }

        data = await dashboard_service.get_view_as_dashboard(target_user, start_date, end_date)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again later."
        )
