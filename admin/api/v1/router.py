"""Router HTTP v1 del modulo admin."""

from fastapi import APIRouter

from admin.api.v1 import connections, jobs, logs, overview, users

router = APIRouter()
router.include_router(overview.router)
router.include_router(users.router, prefix="/users")
router.include_router(connections.router, prefix="/connections")
router.include_router(logs.router, prefix="/logs")
router.include_router(jobs.router, prefix="/jobs")
