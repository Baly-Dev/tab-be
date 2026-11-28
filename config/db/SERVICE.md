# config/db

Accesso Postgres condiviso.

## A cosa serve

Un engine e una `Session` per le route FastAPI e per i comandi che aprono `session_scope`, come Alembic.

## Cosa gestisce

- `Base`, da cui derivano i model di `auth` e `core` (`admin` / `notifications` in scaffolding).
- `get_engine` e `get_db`. La URL arriva da `config.settings`.

## Con chi comunica

`db.py` alla root importa i model così Alembic vede tutte le tabelle. Le route ricevono la session da `Depends(get_db)`.