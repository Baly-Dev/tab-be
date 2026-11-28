# Auth

Identità e sessioni dell'app Tab (consumer). Gli endpoint protetti partono da qui: JWT, ruoli in `core.permissions`, refresh opachi su Redis.

## A cosa serve

Registra gli account, verifica l'email, login, rotazione refresh, OAuth Google/LinkedIn e passkey.

## Cosa gestisce

- Utenti, ruoli (`core_user_roles`: PROFESSIONAL, ADMIN, SUPER_ADMIN), account social, passkey, reset password.
- JWT di accesso e refresh opaco con rotazione atomica su Redis (`KEY_PREFIX=tn`), grace window per refresh paralleli, revoca famiglia al riuso.
- OAuth: redirect al FE con codice monouso nel fragment (`#handoff=`), Redis `tn:auth:oauth_handoff`, `POST /api/v1/auth/oauth/handoff`.
- Password bcrypt cost 12; legacy WordPress/phppass in verifica; hash MD5 esadecimale rifiutati.
- Route sotto `/api/v1/auth`. Rate limit Redis (`RATE_LIMIT_*`, prefix `tn:rl`) su login, signup, reset, verify, OAuth, handoff, passkey, refresh e tetto globale `/api`.

## Con chi comunica

- `services` — Redis, Brevo, client OAuth.
- `config` — secret, TTL token, `REFRESH_ROTATION_GRACE_SECONDS`.
- `core` — `core.permissions` e `core.utils.roles`; auth non definisce i permessi di prodotto oltre al ruolo account.
- `auth/utils` e `auth/utils/sessions` — vedi i rispettivi `SERVICE.md`.