# auth/utils/sessions

Store delle sessioni di refresh.

## A cosa serve

Ricorda il refresh token, lo ruota al rinnovo e revoca la famiglia se un token già usato ritorna.

## Cosa gestisce

- `RefreshSessionService`: Redis come store di default (`KEY_PREFIX=tn`), Postgres come fallback.
- Il token in chiaro non si salva: si persiste l'hash pepperato.
- Rotazione Redis con Lua: consume, successore, replay e grace (`REFRESH_ROTATION_GRACE_SECONDS`). Riuso oltre la grace revoca la famiglia.

## Con chi comunica

- `services.redis` per le chiavi di sessione.
- `auth.models` per fallback Postgres e utente legato al token.
- `auth.utils.tokens` per generare e fare l'hash del refresh.
- Login, refresh, logout, reset password e revoca totale da account admin.