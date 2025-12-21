from fastapi import APIRouter, HTTPException, status, Depends
from app.services import report_service
from app.middleware.auth_middleware import require_admin_or_manager

router = APIRouter()


@router.get("/inventory")
async def get_inventory_report(
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get device inventory report"""
    report = await report_service.get_inventory_report()
    
    return {
        "success": True,
        "message": "Inventory report generated successfully",
        "data": report
    }


@router.get("/distribution-summary")
async def get_distribution_summary(
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get distribution summary report"""
    report = await report_service.get_distribution_summary()
    
    return {
        "success": True,
        "message": "Distribution summary generated successfully",
        "data": report
    }


@router.get("/defect-summary")
async def get_defect_summary(
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get defect summary report"""
    report = await report_service.get_defect_summary()
    
    return {
        "success": True,
        "message": "Defect summary generated successfully",
        "data": report
    }


@router.get("/return-summary")
async def get_return_summary(
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get return summary report"""
    report = await report_service.get_return_summary()
    
    return {
        "success": True,
        "message": "Return summary generated successfully",
        "data": report
    }


@router.get("/user-activity")
async def get_user_activity_report(
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get user activity report"""
    report = await report_service.get_user_activity_report()
    
    return {
        "success": True,
        "message": "User activity report generated successfully",
        "data": report
    }


@router.get("/device-utilization")
async def get_device_utilization_report(
    current_user: dict = Depends(require_admin_or_manager)
):
    """Get device utilization report"""
    report = await report_service.get_device_utilization_report()
    
    return {
        "success": True,
        "message": "Device utilization report generated successfully",
        "data": report
    }


@router.post("/export")
async def export_report(
    export_data: dict,
    current_user: dict = Depends(require_admin_or_manager)
):
    """Export report (placeholder for actual export functionality)"""
    report_type = export_data.get("report_type", "inventory")
    format_type = export_data.get("format", "csv")
    
    # In a real implementation, this would generate and return a file
    # For now, just return a success message
    
    return {
        "success": True,
        "message": f"{report_type} report exported as {format_type}",
        "data": {
            "report_type": report_type,
            "format": format_type,
            "download_url": f"/api/reports/download/{report_type}.{format_type}"
        }
    }
