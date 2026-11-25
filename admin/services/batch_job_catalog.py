"""Catalogo dei job automatici configurabili dalla console."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobFieldSpec:
    """Parametro intero modificabile in console."""

    key: str
    label: str
    help: str
    default: int
    minimum: int
    maximum: int


@dataclass(frozen=True)
class JobSpec:
    """Definizione stabile di un job. La riga DB ne tiene stato e override."""

    key: str
    title: str
    description: str
    fields: tuple[JobFieldSpec, ...] = ()
    default_interval_seconds: int = 300


MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 86_400
RUN_HISTORY_LIMIT = 50

JOBS: tuple[JobSpec, ...] = ()

JOBS_BY_KEY = {spec.key: spec for spec in JOBS}


class JobConfigError(ValueError):
    """Configurazione rifiutata prima di toccare il database."""


def default_config(spec: JobSpec) -> dict[str, int]:
    return {field.key: field.default for field in spec.fields}


def normalize_interval(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise JobConfigError("L’intervallo deve essere un numero intero di secondi.")
    if value < MIN_INTERVAL_SECONDS or value > MAX_INTERVAL_SECONDS:
        raise JobConfigError("L’intervallo deve essere tra 1 minuto e 24 ore.")
    return value


def normalize_config(spec: JobSpec, raw: dict) -> dict[str, int]:
    """Accetta solo i campi del catalogo, nei limiti dichiarati."""
    if not isinstance(raw, dict):
        raise JobConfigError("La configurazione non è valida.")
    unknown = set(raw) - {field.key for field in spec.fields}
    if unknown:
        names = ", ".join(sorted(unknown))
        raise JobConfigError(f"Parametri non previsti: {names}.")
    missing = [field.label for field in spec.fields if field.key not in raw]
    if missing:
        raise JobConfigError(f"Manca: {', '.join(missing)}.")
    normalized: dict[str, int] = {}
    for field in spec.fields:
        value = raw[field.key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise JobConfigError(f"{field.label} deve essere un numero intero.")
        if value < field.minimum or value > field.maximum:
            raise JobConfigError(
                f"{field.label} deve essere tra {field.minimum} e {field.maximum}."
            )
        normalized[field.key] = value
    return normalized


def config_int(config: dict | None, key: str, default: int) -> int:
    if not isinstance(config, dict):
        return default
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value
