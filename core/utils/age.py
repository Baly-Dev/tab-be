"""Età anagrafica minima per la registrazione."""

from __future__ import annotations

from datetime import date

MINIMUM_SIGNUP_AGE = 18
MAXIMUM_SIGNUP_AGE = 120


def age_in_years(birth_date: date, *, today: date | None = None) -> int:
    """Età in anni compiuti alla data ``today``."""
    current = today or date.today()
    age = current.year - birth_date.year
    if (current.month, current.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def require_adult_birth_date(value: date, *, today: date | None = None) -> date:
    """Rifiuta date future, minori di 18 anni e date implausibili."""
    current = today or date.today()
    if value > current:
        raise ValueError("La data di nascita non può essere nel futuro")
    age = age_in_years(value, today=current)
    if age < MINIMUM_SIGNUP_AGE:
        raise ValueError("Devi avere almeno 18 anni")
    if age > MAXIMUM_SIGNUP_AGE:
        raise ValueError("Data di nascita non valida")
    return value
