# Core

Dominio dell'app consumer: profilo, connessioni, ricerca membri, interessi e matrice permessi statica per ruolo account.

## A cosa serve

È il cuore del prodotto Tab dopo il login. Le route pubbliche e autenticate sotto `/api/v1/core` servono il FE con `me`, profili, connessioni, inviti e discovery.

## Cosa gestisce

- Modelli `core_profiles`, `core_organizations`, `core_venues`, connessioni, interessi e ruoli (`core_user_roles`).
- Persona consumer: `professional`. Host di un tavolo non è un ruolo. `admin` / `super_admin` sono stewardship TAB.
- `core_organization_affiliations`: un professional lavora in un'organization.
- `core_venues` + `core_venue_memberships`: scheda locale e operatori (`owner`, `manager`, `staff`).
- `core_venue_images`: galleria del locale, ordine del carosello in `sort_order`. `cover_url` resta la miniatura della card.
- `core_venue_menus`: prezzo, prezzo di confronto (flash), cosa include, limite coperti e finestra dell'offerta. `core_venue_menu_windows`: giorni e orari in cui la carta è prenotabile.
- `core_venue_shifts` e `core_venue_shift_overrides`: coperti ricorrenti e eccezione del giorno. I posti impegnati si contano dagli ordini con `seat_committed`.
- Sul venue: `commission_rate` e canone (`subscription_*`). Sull'ordine: importo, metodo (`pay_at_venue`, `card`, `meal_voucher`), stato pagamento, commissione e netto per il locale.
- Sul gruppo: `share_code` per il link. L'invito può puntare a un utente oppure a un'email.
- `core_bookings` + `core_orders`: prenotazione al locale (`solo` o `group`) e ordine sul menu. Il libro del ristoratore è `core_bookings.venue_id` letto da chi ha `core_venue_memberships` (`can_manage_bookings`). `handled_by_user_id` è l'operatore che ha risposto. `declined` è il rifiuto del locale, `cancelled` l'annullamento dell'ospite.
- `core_groups`, `core_group_members`, `core_group_invites`: tavolo condiviso, chi è dentro, invito a un altro professional. Il solo non ha gruppo.
- API: `/me`, `/users`, `/users/search`, `/connections`, `/interests`.
- Media avatar/cover via `services.storage` (route `/media` in `main.py`).

## Con chi comunica

- `auth` per identità, signup (interessi, profilo) e refresh.
- Moduli `notifications` e `admin` in scaffolding (da reintrodurre).
- `services.storage`, `services.images` per upload e resize.