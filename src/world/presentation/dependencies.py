from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from world.application.service import WorldService
from world.wiring import build_world_service


async def get_world_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorldService:
    return build_world_service(session)


WorldServiceDep = Annotated[WorldService, Depends(get_world_service)]
