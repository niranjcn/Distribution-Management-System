from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback


def add_exception_handlers(app: FastAPI):
    """Add global exception handlers to the app"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "details": exc.detail
                }
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle Starlette HTTP exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": str(exc.detail),
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "details": str(exc.detail)
                }
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors"""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"]
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Validation error",
                "error": {
                    "code": "VALIDATION_ERROR",
                    "details": errors
                }
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle value errors (business logic errors)"""
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": str(exc),
                "error": {
                    "code": "BAD_REQUEST",
                    "details": str(exc)
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions"""
        # Log the error
        print(f"Unhandled error: {exc}")
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "details": "An unexpected error occurred"
                }
            }
        )
