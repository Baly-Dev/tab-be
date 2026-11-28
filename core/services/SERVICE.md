# core/services

Use case core più articolati (avatar, connessioni, ricerca).

## A cosa serve

Orchestrazione tra più tabelle e `services` esterni; le route chiamano qui invece di accumulare logica.

## Cosa gestisce

- `connection_service.py`: richieste, accettazione, rifiuto connessioni.
- `member_search_service.py` e `member_search_policy.py`: discovery con filtri e permessi `Permission`.
- `avatar_service.py` e `provider_avatar.py`: upload, resize, URL pubblici.
- `signup_invitees_service.py`: invitati collegati al connector.

## Con chi comunica

- `core.utils` e `core.permissions`.
- `services.storage`, `services.images`, `services.uploads`.
- `notifications` (scaffolding) per eventi futuri.