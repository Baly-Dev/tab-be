"""Lista interessi per signup e discovery."""

from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_async_db
from core.models.interest import CoreInterest
from core.models.interest_category import CoreInterestCategory
from core.schemas.interest import InterestCategoryGroup, InterestItem, InterestListResponse

router = APIRouter()


@router.get("", response_model=InterestListResponse)
async def list_interests(db: AsyncSession = Depends(get_async_db)) -> InterestListResponse:
    """Interessi attivi raggruppati per categoria (ordinamento ``sort_order``, poi nome)."""
    categories = (await db.scalars(
        select(CoreInterestCategory).order_by(
            CoreInterestCategory.sort_order,
            CoreInterestCategory.name,
        )
    )).all()
    interests = (await db.scalars(
        select(CoreInterest)
        .where(CoreInterest.is_active.is_(True))
        .order_by(CoreInterest.sort_order, CoreInterest.name)
    )).all()

    by_category: dict[uuid.UUID, list[InterestItem]] = defaultdict(list)
    uncategorized: list[InterestItem] = []
    for row in interests:
        item = InterestItem(id=row.id, name=str(row.name))
        if row.category_id is None:
            uncategorized.append(item)
        else:
            by_category[row.category_id].append(item)

    groups: list[InterestCategoryGroup] = []
    for category in categories:
        items = by_category.get(category.id)
        if not items:
            continue
        groups.append(
            InterestCategoryGroup(
                id=category.id,
                name=str(category.name),
                interests=items,
            )
        )

    if uncategorized:
        groups.append(
            InterestCategoryGroup(id=None, name="Other", interests=uncategorized),
        )

    return InterestListResponse(categories=groups)
