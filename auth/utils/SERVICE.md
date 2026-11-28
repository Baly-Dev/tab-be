# auth/utils

Funzioni di auth usate dalle route e dagli altri moduli.

## A cosa serve

Tiene password, token, utente corrente, OAuth e rate limit fuori dai file delle route.

## Cosa gestisce

- `helpers.py`: bearer, `AuthenticatedUser`, `user_from_access_token`.
- `rate_limit.py`: finestre Redis (IP e identità) da `settings.rate_limit`.
- `tokens.py`: JWT, refresh pepperato, reset password, revoca famiglia.
- `passwords.py`: bcrypt TN, hash WP/phppass; MD5 esadecimale rifiutato.
- `registration.py`, `username.py`, `account_status.py`, `login_methods.py`, `invites.py`.
- `oauth.py` e `oauth_handoff.py`: sign-in social; redirect con `#handoff=` e chiave `tn:auth:oauth_handoff`.
- `webauthn.py`: challenge e verifica passkey.
- `session.py`: emissione coppia token dopo login.
- `sessions/`: store refresh (Redis default).

## Con chi comunica

- `services.redis`, `services.brevo` e client OAuth in `services`.
- `core.utils.roles` per ruoli JWT; `core` per profilo/inviti in signup.
- `notifications` (scaffolding) per eventi futuri dopo login/signup.