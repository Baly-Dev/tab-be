"""Schemi risposta overview console admin."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminOverviewUsers(BaseModel):
    """Contatori account."""

    total: int = 0
    active: int = 0
    pending: int = 0
    suspended: int = 0
    deleted: int = 0
    new_7d: int = 0
    new_30d: int = 0
    connectors: int = 0
    invited: int = 0


class AdminOverviewNetwork(BaseModel):
    """Contatori connessioni 1° grado."""

    accepted: int = 0
    pending: int = 0
    blocked: int = 0


class AdminOverviewSeriesPoint(BaseModel):
    """Punto di una serie giornaliera."""

    date: str
    count: int = 0


class AdminOverviewResponse(BaseModel):
    """KPI dashboard staff."""

    can_write: bool = Field(description="True se il viewer può mutare (super_admin).")
    users: AdminOverviewUsers
    network: AdminOverviewNetwork
    signups_30d: list[AdminOverviewSeriesPoint] = Field(default_factory=list)
