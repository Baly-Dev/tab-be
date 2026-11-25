from fastapi import APIRouter

from auth.api.v1 import (
    account,
    delete_user,
    google_oauth,
    linkedin_oauth,
    login,
    passkeys,
    password_reset,
    signup,
    social_accounts,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])
router.include_router(signup.router)
router.include_router(verify_email.router)
router.include_router(password_reset.router)
router.include_router(account.router)
router.include_router(social_accounts.router)
router.include_router(passkeys.router)
router.include_router(login.router)
router.include_router(google_oauth.router)
router.include_router(linkedin_oauth.router)
router.include_router(delete_user.router)
