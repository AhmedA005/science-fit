"""
User repository — all DB queries related to users.

Returns Pydantic schemas, not raw ORM objects.
The service layer never touches SQLAlchemy directly.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User, UserPreferences
from src.schemas.user_schema import FullUserContext, UserPreferencesSchema, UserProfileSchema


async def get_user_by_id(session: AsyncSession, user_id: int) -> UserProfileSchema | None:
    """Fetch a user by primary key. Returns None if not found."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    return UserProfileSchema.model_validate(user)


async def get_user_by_email(session: AsyncSession, email: str) -> UserProfileSchema | None:
    """Fetch a user by email address."""
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    return UserProfileSchema.model_validate(user)


async def get_user_preferences(
    session: AsyncSession, user_id: int
) -> UserPreferencesSchema | None:
    """Fetch preferences for a user."""
    result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if prefs is None:
        return None
    return UserPreferencesSchema.model_validate(prefs)


async def get_full_user_context(
    session: AsyncSession, user_id: int
) -> FullUserContext | None:
    """
    Fetch a user + preferences in one call.
    This is the standard entry point for the training engine.
    """
    profile = await get_user_by_id(session, user_id)
    if profile is None:
        return None

    prefs = await get_user_preferences(session, user_id)
    if prefs is None:
        prefs = UserPreferencesSchema()  # safe defaults

    return FullUserContext(profile=profile, preferences=prefs)
