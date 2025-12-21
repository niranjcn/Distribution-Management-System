from fastapi import APIRouter, Depends
from app.services import dashboard_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics based on user role"""
    stats = await dashboard_service.get_dashboard_stats(current_user)
    
    return {
        "success": True,
        "message": "Dashboard stats retrieved successfully",
        "data": stats
    }


@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get recent activities for dashboard"""
    activities = await dashboard_service.get_recent_activities(current_user, limit)
    
    return {
        "success": True,
        "message": "Recent activities retrieved successfully",
        "data": activities
    }


@router.get("/charts/distributions")
async def get_distribution_chart_data(
    current_user: dict = Depends(get_current_user)
):
    """Get distribution chart data"""
    data = await dashboard_service.get_distribution_chart_data()
    
    return {
        "success": True,
        "message": "Distribution chart data retrieved successfully",
        "data": data
    }


@router.get("/charts/defects")
async def get_defect_chart_data(
    current_user: dict = Depends(get_current_user)
):
    """Get defect chart data"""
    data = await dashboard_service.get_defect_chart_data()
    
    return {
        "success": True,
        "message": "Defect chart data retrieved successfully",
        "data": data
    }


@router.get("/alerts")
async def get_system_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Get system alerts for dashboard"""
    alerts = await dashboard_service.get_system_alerts(current_user)
    
    return {
        "success": True,
        "message": "System alerts retrieved successfully",
        "data": alerts
    }
