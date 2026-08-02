import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth_middleware import get_current_user
from app.core.cache_version import bump_cache_version
from app.models.digital_id import DigitalIdentityCreate
from app.services.digital_id_service import (
    create_digital_identity,
    get_digital_identities_by_user,
    delete_digital_identities_by_user,
)

router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create digital identity entry")
async def create_digital_identity_endpoint(data: DigitalIdentityCreate, current_user: dict = Depends(get_current_user)):
    try:
        entry = await create_digital_identity(data)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"success": True, "message": "Digital identity entry created", "data": entry}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.get("/user/{user_id}", summary="Get digital identities by user")
async def get_digital_identities_endpoint(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        entries = await get_digital_identities_by_user(int(user_id))
        return {"success": True, "message": "Digital identities retrieved", "data": entries}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.delete("/user/{user_id}", summary="Delete all digital identities for a user")
async def delete_digital_identities_endpoint(user_id: str, current_user: dict = Depends(get_current_user)):
    try:
        await delete_digital_identities_by_user(int(user_id))
        return {"success": True, "message": "Digital identities deleted"}
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.put("/{identity_id}", summary="Update a digital identity entry")
async def update_digital_identity_endpoint(identity_id: str, data: DigitalIdentityCreate, current_user: dict = Depends(get_current_user)):
    from app.db_models.digital_id import DigitalIdentity
    from app.database_sqlalchemy import async_session_factory
    from app.services.digital_id_service import (
        check_identity_conflicts,
        _identity_conflict_error,
        _identity_to_dict,
        _normalize,
    )
    from sqlalchemy import select
    try:
        async with async_session_factory() as session:
            q = select(DigitalIdentity).where(DigitalIdentity.id == int(identity_id))
            result = await session.execute(q)
            entry = result.scalars().first()
            if not entry:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital identity not found")
            digital_id = _normalize(data.digital_id)
            broadband_id = _normalize(data.broadband_id)
            conflicts = await check_identity_conflicts(
                session,
                [digital_id],
                [broadband_id],
                exclude_identity_id=int(identity_id),
            )
            if conflicts["digital"] or conflicts["broadband"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_identity_conflict_error(conflicts))
            entry.digital_id = digital_id
            entry.broadband_id = broadband_id
            await bump_cache_version(session)
            await session.commit()
            await session.refresh(entry)
            return {"success": True, "message": "Digital identity updated", "data": _identity_to_dict(entry)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")


@router.delete("/{identity_id}", summary="Delete a single digital identity")
async def delete_single_digital_identity_endpoint(identity_id: str, current_user: dict = Depends(get_current_user)):
    from app.db_models.digital_id import DigitalIdentity
    from app.database_sqlalchemy import async_session_factory
    from sqlalchemy import select, delete as sa_delete
    try:
        async with async_session_factory() as session:
            q = select(DigitalIdentity).where(DigitalIdentity.id == int(identity_id))
            result = await session.execute(q)
            entry = result.scalars().first()
            if not entry:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital identity not found")
            await session.execute(sa_delete(DigitalIdentity).where(DigitalIdentity.id == int(identity_id)))
            await bump_cache_version(session)
            await session.commit()
        return {"success": True, "message": "Digital identity deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled route exception")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again later.")
