from fastapi import APIRouter

from app.api.v1.endpoints import video

routers = APIRouter(prefix="/api/v1")
router_list = [video.router]

for router in router_list:
	router.tags = (router.tags or []) + ["v1"]
	routers.include_router(router)

v1_router = routers
