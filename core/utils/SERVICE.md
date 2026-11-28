# core/utils

Regole e helper di dominio core senza route.

## A cosa serve

Profilo, connessioni, visibilità, età e ruoli usati da `core/api` e da `auth` in signup.

## Cosa gestisce

- `me.py` / `update_me.py`: lettura e aggiornamento profilo autenticato.
- `connections.py`: ordinamento coppie, stati connessione.
- `profile_visibility.py` e `profile_stats.py`: cosa esporre in pubblico e conteggi.
- `age.py`: validazione maggiore età in signup.
- `roles.py`: `load_user_roles`, inviti piattaforma, helper ruolo.

## Con chi comunica

- `core.models` e `auth.models`.
- `core.permissions` per gate su inviti e search.
- `auth.utils.invites` in fase registrazione.