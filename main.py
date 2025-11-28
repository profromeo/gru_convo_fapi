import logging
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.api.v1.router import api_router
from app.core.utils.exceptions import APIServiceException, convert_exception_to_http
from app.db.mongodb import init_mongodb, close_mongodb


def setup_logging():
    """Configure logging for the application."""
    settings = get_settings()
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    
    
    if settings.debug:
        logging.getLogger("app").setLevel(logging.DEBUG)

    logging.getLogger("app").setLevel(logging.DEBUG)
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    settings = get_settings()
    logger = logging.getLogger(__name__)
    
    # Startup
    logger.info("🚀 Starting application...")
    
    try:
        # Initialize MongoDB
        logger.info("📊 Initializing MongoDB...")
        await init_mongodb(settings)
        logger.info("✅ MongoDB initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise
    
    logger.info("✅ Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down application...")
    
    try:
        # Close MongoDB
        logger.info("📊 Closing MongoDB connection...")
        await close_mongodb()
        logger.info("✅ MongoDB connection closed")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")
    
    logger.info("✅ Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        debug=settings.debug
    )
    
    # Add security middleware for production
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Configure this properly for production
        )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = asyncio.get_event_loop().time()
        
        # Log request
        logger.info(f"🔄 {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            process_time = asyncio.get_event_loop().time() - start_time
            
            # Log response
            logger.info(
                f"✅ {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s"
            )
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            return response
            
        except Exception as e:
            process_time = asyncio.get_event_loop().time() - start_time
            logger.error(
                f"❌ {request.method} {request.url.path} - "
                f"Error: {str(e)} - "
                f"Time: {process_time:.3f}s"
            )
            raise
    
    # Exception handlers
    @app.exception_handler(APIServiceException)
    async def rag_service_exception_handler(request: Request, exc: APIServiceException):
        """Handle RAG service specific exceptions."""
        logger.error(f"RAG Service Error: {exc.message}", extra={"details": exc.details})
        
        # Convert to appropriate HTTP exception
        http_exc = convert_exception_to_http(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        logger.warning(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Validation error",
                "errors": exc.errors(),
                "body": exc.body
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions."""
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error",
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "path": str(request.url)
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error"
                }
            )
    
    # Include API router
    app.include_router(
        api_router,
        prefix=settings.api_prefix
    )
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with service information."""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment.value,
            "status": "healthy",
            "docs_url": "/docs" if settings.debug else "disabled",
            "api_prefix": settings.api_prefix,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    # Additional utility endpoints
    @app.get("/ping", tags=["Utility"])
    async def ping():
        """Simple ping endpoint for basic health checking."""
        return {"status": "pong", "timestamp": asyncio.get_event_loop().time()}
    
    @app.get("/version", tags=["Utility"])
    async def version():
        """Get service version information."""
        return {
            "version": settings.app_version,
            "environment": settings.environment.value,
            "debug": settings.debug
        }
        
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    templates = Jinja2Templates(directory="templates")

    @app.get("/chat")
    async def chat(request: Request):
        """Serve the chat interface"""
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "api_base_url": f"https://{settings.chat_host}{settings.api_prefix}",
                "app_name": settings.app_name
            }
        )
    
    logger.info(f"📱 FastAPI application created - Environment: {settings.environment}")
    
    return app


# Create the app instance
app = create_app()


def run_server():
    """Run the uvicorn server."""
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers,
        log_level=settings.log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    try:
        run_server()
    except KeyboardInterrupt:
        print("\n🛑 Server shutdown requested by user")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)