# config

Configurazione di processo: env, costanti e infrastruttura condivisa.

## A cosa serve

Ogni modulo legge da qui secret, URL e enum, invece di spargere `os.environ` nel codice.

## Cosa gestisce

- `settings.py`: database, JWT, Redis, refresh store, Brevo, OAuth, WebAuthn, storage S3/locale, eventi, CRM Brevo. Legge `.env` poi `.env.local`.
- `rate_limit.py`: finestre `RATE_LIMIT_*` e policy (`settings.rate_limit`, prefix default `tn:rl`).
- `constants.py`: `AppRole`, stati utente, connessioni, generi, tipi notifica.
- `sentry.py`: init e middleware che oscura token ed email.
- `config/db`: engine SQLAlchemy e `Base`.
- `config/errors`: errori HTTP condivisi.

## Con chi comunica

La usono `auth`, `core` e `services`. Non chiama i moduli di dominio.

## Async API stack (Railway)

FastAPI route handlers are **fully async**: `get_async_db` (`asyncpg`) for Postgres and `get_async_redis_service()` for Redis. Sync `config/db/session.py` (`get_db`, psycopg) remains for Alembic and one-off scripts.

**Horizontal replicas** on Railway: run multiple stateless API containers behind one load balancer; they share `DATABASE_URL` / `REDIS_URL`. Tune pool size per replica via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT_SECONDS` so total connections stay within Postgres limits. Connect async Redis in app lifespan (`main.py`).

Blocking I/O (boto3 storage, PIL) runs via `asyncio.to_thread` from async routes.