from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies.auth import ensure_user_access, get_current_user
from backend.models.personalization import (
    UserPreferenceProfile,
    UserPreferenceProfilePatch,
)
from backend.models.user import User
from backend.services.personalization import UserPreferenceService

router = APIRouter()
service = UserPreferenceService()


@router.get("/{user_id}/profile", response_model=UserPreferenceProfile)
async def get_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> UserPreferenceProfile:
    ensure_user_access(user_id, current_user)
    return await service.get_profile(user_id)


@router.post("/{user_id}/profile/default", response_model=UserPreferenceProfile)
async def create_default_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> UserPreferenceProfile:
    ensure_user_access(user_id, current_user)
    return await service.create_default_profile(user_id)


@router.put("/{user_id}/profile", response_model=UserPreferenceProfile)
async def replace_user_profile(
    user_id: str,
    profile: UserPreferenceProfile,
    current_user: User = Depends(get_current_user),
) -> UserPreferenceProfile:
    ensure_user_access(user_id, current_user)
    if profile.user_id != user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id in the URL and request body must match.",
        )
    return await service.save_profile(profile)


@router.patch("/{user_id}/profile", response_model=UserPreferenceProfile)
async def patch_user_profile(
    user_id: str,
    patch: UserPreferenceProfilePatch,
    current_user: User = Depends(get_current_user),
) -> UserPreferenceProfile:
    ensure_user_access(user_id, current_user)
    return await service.patch_profile(user_id, patch)


@router.delete("/{user_id}/profile")
async def delete_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_user_access(user_id, current_user)
    await service.delete_profile(user_id)
    return {
        "status": "success",
        "message": f"Profile for user '{user_id}' deleted.",
    }


@router.get("/{user_id}/solver-preferences")
async def get_solver_preferences(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    ensure_user_access(user_id, current_user)
    preferences = await service.get_solver_preferences(user_id)
    return preferences.model_dump()
