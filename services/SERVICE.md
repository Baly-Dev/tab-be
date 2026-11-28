# services

Integrazioni esterne condivise. Si importa il submodule (`from services.redis import get_redis_service`), così non si crea un ciclo con `auth`.

## A cosa serve

Un solo posto per Redis, Brevo, OAuth, storage file e immagini. I moduli di dominio non aprono questi client da soli.

## Cosa gestisce

- `redis.py`: connessione, ping e chiusura nel lifecycle. Auth lo usa per refresh, handoff OAuth e rate limit.
- `brevo.py` e `brevo_contacts.py`: email transazionali e liste CRM.
- `google_oauth.py` e `linkedin_oauth.py`: scambio codice, stato CSRF, profilo e redirect con handoff.
- `storage.py`, `uploads.py`, `images.py`: avatar e media in locale o su bucket S3/Railway.

## Con chi comunica

- `config` per URL, chiavi, template e backend storage.
- `auth` per sign-in, email di verifica/reset.
- `core` e `admin` per upload e export.
- `auth/utils/sessions` usa Redis per i refresh token.