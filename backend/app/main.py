from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import v1_router
from app.util.class_object import singleton


@singleton
class AppCreator:
    """FastAPI application creator with singleton pattern"""

    def __init__(self):
        self.app = FastAPI(
            title="LiveBoost AI API",
            version="0.1.0",
            description="Video analytics and processing API",
        )

        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Health check endpoint
        @self.app.get("/")
        def root():
            return {"message": "service is working"}

        # Include routers
        self.app.include_router(v1_router)


# Create app instance
app_creator = AppCreator()
app = app_creator.app



