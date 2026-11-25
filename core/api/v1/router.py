from fastapi import APIRouter

from core.api.v1 import (
    connections,
    interests,
    me,
    member_search,
    users,
)

router = APIRouter()
router.include_router(me.router)
router.include_router(member_search.router, prefix="/users/search")
router.include_router(users.router, prefix="/users")
router.include_router(connections.router, prefix="/connections")
router.include_router(interests.router, prefix="/interests")
