"""Schemi API per interessi (signup, discovery)."""

import uuid

from pydantic import BaseModel, Field


class InterestItem(BaseModel):
    """Interesse selezionabile nel wizard signup."""

    id: uuid.UUID
    name: str = Field(description="Etichetta mostrata in UI.")


class InterestCategoryGroup(BaseModel):
    """Categoria con i relativi interessi attivi."""

    id: uuid.UUID | None = Field(
        default=None,
        description="Null solo per il bucket eventuale interessi senza categoria.",
    )
    name: str
    interests: list[InterestItem]


class InterestListResponse(BaseModel):
    categories: list[InterestCategoryGroup]
