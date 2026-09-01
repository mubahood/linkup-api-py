# Subscription / Premium-Tier Monetization — Implementation Plan

## Progress Log

**Phase 0 + Phase 1 — DONE, verified locally (2026-08-28).**

- Migration `0041_subscription_plans.py`: `lu_subscription_plans` (5 rows × 2
  apps, seeded) + `lu_subscriptions` ledger + `lu_accounts.subscription_plan_id`/
  `subscription_expires_at`. Applied locally, confirmed via direct DB query.
- `backend/domains/subscriptions/{models,service,routes}.py` — registered in
  `backend/app.py` and `backend/models/__init__.py`. `Account.to_dict()`
  extended with the two new fields.
- Verified end-to-end against the local server: `GET /plans`, `POST /purchase`
  (hit the real Flutterwave API, got a real payment link back), `POST
  /<tx_ref>/verify` with `DEV_BYPASS`, `GET /me` — confirmed `is_premium`,
  `subscription_plan_id`, `subscription_expires_at`, and the `lu_subscriptions`
  ledger row all update correctly on activation, and `usage_today` limits
  reflect the newly-active plan immediately.

**Phase 2 — DONE, verified locally (2026-08-28).**

- `sparks/routes.py:action` — swipe (`spark_up`/`pass`) and standout daily
  limits enforced server-side via `check_and_consume`, `402` + upsell payload
  on block. Proved with a direct-API test (bypassing any client): 5
  standouts succeeded against a weekly-plan account, the 6th correctly
  rejected — this closes the pre-existing gap where the limit was
  client-side only and trivially bypassable.
- `standout_count` now sources `daily_limit` from `get_limits()` instead of
  the hardcoded `5`; fixed the `remaining` calc for the `-1` (unlimited) case
  the hardcoded version never had to handle.
- `incoming_likes` — implemented the gating its own docstring already
  promised: `can_view_likers` unlocks the full list, otherwise items carry
  `locked: true` with no `actor_account` sent to the client at all (not just
  client-side blurred).
- New `GET /v1/sparks/profile-viewers` — reuses the already-populated
  `BehavioralEvent` table (zero new tracking code), same locked-list shape as
  `incoming_likes`. Verified against real historical view-event data already
  in the local DB.
- `chat/routes.py:post_message` — `chats_per_day` check before `send_message`,
  same `402` + upsell shape.
- New `GET /v1/sparks/matches/<match_id>/contact` — requires an active match
  the caller is a party to (mirrors `match_detail`'s auth pattern) AND
  `can_reveal_contact`; 404 with `reason: not_matched` / 403 with
  `reason: upgrade_required` as appropriate. `whatsapp` falls back to `phone`
  (confirmed no separate WhatsApp field exists anywhere in the profile models).

**Phase 3 — DONE, verified locally (2026-08-28).**

- Migration `0042_subscription_gamification.py`: `lu_accounts.streak_days` /
  `streak_updated_at` / `first_match_bonus_available`, `lu_subscription_plans
  .discount_price_ugx` / `discount_ends_at`. Applied and verified.
- `touch_streak()` — real consecutive-day tracking, called from
  `check_and_consume` (fires only on genuine swipe/chat engagement, not
  app-open). Verified: 0 → 1 on the first real action of the day.
- Streak bonus (+5 at 3 days, +10 at 7 days, tiered not additive) applied to
  `swipes_per_day` inside `check_and_consume`.
- First-match milestone: `grant_first_match_bonus()` wired into
  `sparks/routes.py:action`'s match-creation block (checked independently for
  each party's own first-ever match). The bonus is only actually spent — and
  the flag only cleared — the moment it's needed to cross the daily wall, not
  the instant it's granted, so it stays banked until useful.
- `nudge`/`bonus` now surfaced in real responses: `sparks/action` and
  `chat/.../messages` success payloads carry post-action quota state (fixed a
  pre-action staleness bug caught during testing — the quota check runs
  before the action is recorded, so the raw check result was one action
  behind what the client should display).
- Discount pricing (`discount_price_ugx`/`discount_ends_at` on a plan row,
  `effective_price_ugx` computed property) — verified `GET /plans` reflects
  an active discount and reverts correctly once cleared. `purchase` charges
  `effective_price_ugx`, not the base price.
- "Why upgrade" comparison table — already covered by Phase 1's `GET /plans`
  returning `free_limits` alongside every paid plan.

**Phase 5 — DONE, verified locally (2026-08-28).**

- 4 new routes added to `backend/domains/admin/routes.py` (mirrors the
  gift-catalog CRUD pattern exactly — `_admin_required`, `db.session.get` +
  404, per-field `if field in data: setattr(...)` on PUT, uuid + 201 on
  POST): `GET/POST /v1/admin/subscription-plans`, `PUT
  /v1/admin/subscription-plans/<id>`, `GET /v1/admin/subscriptions`.
  `SubscriptionPlan`/`Subscription` imported at the top of the file per the
  brief; no new blueprint registration needed (lives inside the existing
  `admin_v1_bp`).
- Plan list returns everything (active + inactive), `?app_id=` filter,
  ordered `app_id, sort_order`. Create enforces `(app_id, code)` uniqueness
  matching the DB's `uq_plan_app_code` constraint. Update rejects touching
  `app_id`/`code` (only accepts them silently ignored, not applied — proved
  via curl: posting `{"app_id":"abanoonya","code":"hacked"}` on a `linkup`
  plan left both fields unchanged). `discount_ends_at` accepts an ISO string
  (with or without seconds — both `datetime-local` input format and full
  ISO tested) or `null` to clear.
- `GET /v1/admin/subscriptions` joins `Account` + `SubscriptionPlan` for a
  flat admin row shape, supports `?status=&app_id=&page=&per_page=`, and
  returns `revenue_summary` (`total_active_subscribers`,
  `total_revenue_ugx`) as a sibling key inside the paginated envelope
  (extends `paginated_response`'s shape manually since that helper doesn't
  take extra kwargs).
- Frontend: `frontend/src/components/SubscriptionsPage.jsx` (Plans tab —
  card grid grouped by the header's app-scope switcher, always-editable
  fields per card `AppVersionsPage`-style, an expandable 12-field limits
  editor split into numeric/-1-unlimited and boolean groups, a "New plan"
  modal; Subscribers tab — stat-card row + paginated table + status
  filter). Wired into `frontend/src/App.jsx` (lazy route) and
  `frontend/src/components/Sidebar.jsx` (`FiCreditCard` nav item). 4 new
  `adminAPI` methods added to `frontend/src/services/api.js`.
- Verified end-to-end against the real local server + MySQL DB via curl:
  list (10 seeded plans across both apps), `app_id` filter, create,
  duplicate-code rejection, update (price/limits/discount set + clear),
  app_id/code immutability, 404 on a bad id, and the subscriber list +
  revenue_summary (1 real active subscription in the local DB, matching
  `total_active_subscribers: 1` / `total_revenue_ugx: 5000.0`). All test
  rows cleaned up afterward (test plan deleted, test limit-toggle reverted).
- Frontend verified two ways: (1) an isolated `esbuild` bundle of
  `SubscriptionsPage.jsx` and of the full `App.jsx` resolved cleanly with no
  syntax/import errors; (2) a Playwright run against the real `npm run dev`
  server — logged in, loaded both tabs, expanded the limits editor, toggled
  a checkbox, saved (confirmed via curl it persisted), opened and cancelled
  the "New plan" modal — zero console errors, zero page errors, screenshots
  confirm correct rendering in both tabs.
- **Not fully clean**: `npm run build` fails, but on a pre-existing,
  unrelated break in `AccountsPage.jsx` (`import CreateAccountModal from
  './CreateAccountModal'` — that file doesn't exist; a concurrent
  in-progress rename to `AccountFormModal.jsx` with a different prop
  signature was mid-edit in this same working tree while Phase 5 was being
  built, confirmed by file mtimes). Not a Phase 5 regression — isolated
  `esbuild` bundling of `App.jsx` shows that one unresolved import as the
  *only* error anywhere in the tree. Needs a follow-up once that unrelated
  Accounts refactor lands.

**Phase 4 — DONE, verified locally (2026-08-28).**

- New `lib/shared/widgets/lu_upsell_sheet.dart` — the shared paywall bottom
  sheet, replacing the bare `SnackBar` dead-ends at every limit-hit point
  (was the standout limit's only feedback before this).
- New `lib/features/subscriptions/subscription_plans_screen.dart` — 4 paid
  cards (+ free-tier baseline for comparison), discount price shown with a
  strikethrough on the base price when `discount_active`, perks list derived
  from each plan's `limits`. New
  `lib/features/subscriptions/subscription_checkout_webview.dart` generalizes
  `LUTopUpWebView`'s redirect-interception pattern (parameterized match path)
  rather than duplicating the WebView plumbing.
- `sparks_screen.dart` — added `_swipesRemaining` (loaded from the new
  `GET /v1/subscriptions/me`, mirroring the existing `_standoutsRemaining`/
  `standout-count` pattern) and pre-gates `_pass()`/`_spark()` the same way
  `_standout()` already pre-gated. Also fixed two real bugs caught while
  wiring this up: (1) the standout badge and both remaining-counters used
  `<= 0` to block, which would have permanently blocked any account on an
  unlimited (`-1`) plan — changed to `== 0`, and the badge now renders `∞`
  instead of the literal `-1`; (2) `_recordAction` now handles a `402`
  response from the server (belt-and-suspenders — the server is always
  authoritative even though the client pre-gates) by reverting the local
  counter to 0 and showing the upsell sheet instead of silently doing
  nothing.
- `likes_screen.dart` — locked items (`locked: true`, no `actor_account`)
  now render a distinct blurred/lock-icon card instead of falling through to
  the normal card with "Unknown"/blank fields, which is what would have
  happened silently without this change. An upgrade banner shows above the
  grid whenever the first item is locked.
- New `lib/features/sparks/profile_viewers_screen.dart` — same locked-teaser
  pattern for `GET /v1/sparks/profile-viewers`, wired into a new "Profile
  views" entry in `sparks_settings_screen.dart` (alongside a new "Upgrade"
  entry, both matching the existing `_Card`/`ListTile` convention in that
  file).
- `chat_thread_screen.dart` — both `_send()` (text) and `_sendMedia()` now
  handle a `402` from `POST /messages`: the optimistically-added message is
  removed again (it never actually sent), the typed text is restored to the
  input field, and the upsell sheet opens — the previous code sent
  optimistically and never checked the response at all, so a blocked message
  would have silently vanished from the thread with no feedback.
- `match_profile_screen.dart` — new "Contact" section: locked by default,
  "Reveal" calls the new contact route; on `reason: upgrade_required` shows
  the upsell sheet, on success shows the phone number with `tel:`/`wa.me:`
  quick-launch buttons via `url_launcher` (already a project dependency, not
  previously used in any feature screen).
- Verified: `dart analyze` clean on every touched/new file individually and
  across the whole project (1664 pre-existing issues, same baseline as
  before this phase — zero new issues introduced).

**All phases (0-5) complete.** Full-stack verification: backend routes for
member (`/v1/subscriptions/*`), enforcement retrofits, and admin
(`/v1/admin/subscription*`) all confirmed working together against the same
live local server + MySQL DB in one pass — health check, catalog listing
every new route, `GET /v1/admin/subscriptions` revenue summary (1 active
subscriber, 5,000 UGX, matching the test purchase from Phase 1's
verification), `GET /v1/subscriptions/me` — all HTTP 200.

**Known follow-up, not introduced by this work:** `frontend/npm run build`
fails on an unrelated, pre-existing break in `AccountsPage.jsx` from a
concurrent in-progress rename elsewhere in this working tree (see Phase 5's
note above) — needs resolving separately before any frontend deploy.

---

## 0. What this is

LinkUp/Abanoonya Pro has no real dating-side monetization today — `Account.is_premium`
is a bare boolean with no expiry, no tiers, no payment link, and it gates exactly one
thing (incognito mode). This plan adds a free-but-limited tier plus 4 paid packages
(UGX 5,000–50,000, spanning 1 week to 5 months), gating swipes, chats, "who liked me",
"who viewed my profile", and WhatsApp/contact reveal, paid for via Flutterwave, with
gamification (streaks, near-limit nudges, milestone unlocks) so upgrading feels earned
rather than just a paywall.

Two things already in this codebase shape the whole design — reuse, don't rebuild:

1. **Payment plumbing is fully built and live** (`WALLET_GIFTING_FLUTTERWAVE_PLAN.md`,
   shipped 2026-06-23): `backend/services/flutterwave_service.py`'s `FlutterwaveService`,
   the wallet ledger pattern (`WalletTransaction`), and a working mobile checkout webview
   (`lib/features/wallet/wallet_topup_webview.dart`'s `LUTopUpWebView`).
2. **A working daily-quota pattern already exists** — `standout_count`
   (`backend/domains/sparks/routes.py:500-517`) counts today's `Spark` rows since
   midnight and compares to a hardcoded `daily_limit = 5`. It's currently **client-side
   only** — no server enforcement — and the same shape generalizes cleanly into
   per-plan, server-enforced limits for swipes/day, chats/day, and standouts/day.

## 1. Data model

**`lu_subscription_plans`** — migration `backend/database/migrations/0041_subscription_plans.py`
(raw-SQL, matching `0035_app_versions.py`'s style): `id`, `app_id`, `code`, `name`,
`tagline`, `price_ugx DECIMAL(14,2)`, `duration_days` (0 = free), `sort_order`, `active`,
`badge_color`, `limits JSON`, timestamps. `UNIQUE(app_id, code)`.

Seed 5 rows per app: `free` (0, 0d), `weekly` (5,000 UGX, 7d), `biweekly` (15,000, 14d),
`monthly` (30,000, 30d), `five_month` (50,000, 150d).

`limits` JSON (admin-editable per plan, no deploy needed to retune):
```json
{
  "swipes_per_day": 50, "standouts_per_day": 5, "chats_per_day": -1,
  "can_view_likers": false, "can_view_profile_viewers": false,
  "can_reveal_contact": false, "rewinds_per_day": 0,
  "boosts_per_month": 0, "priority_deck": false,
  "read_receipts": true, "advanced_filters": false,
  "streak_freeze_per_month": 0
}
```
(`-1` = unlimited.)

**`lu_subscriptions`** (ledger, same migration, mirrors `WalletTransaction`): `id`,
`account_id`, `plan_id`, `status` (`pending|active|expired|cancelled`), `starts_at`,
`expires_at`, `amount_paid_ugx`, `tx_ref UNIQUE`, `flw_tx_id`, `extra_data JSON`,
`created_at`.

**`lu_accounts`** gets `subscription_plan_id`, `subscription_expires_at` (fast
per-request lookup). `is_premium` stays synced automatically so
`profile/routes.py:282` (incognito gate) keeps working untouched.

No scheduler exists in this codebase. Expiry is a **lazy self-healing check**: every
read of the active plan checks if `subscription_expires_at` has passed and, if so,
flips the account back to `free` and marks the ledger row `expired` before returning.

## 2. Phase 1 — Core subscriptions domain

New `backend/domains/subscriptions/{models.py,service.py,routes.py}`, registered in
`backend/app.py` next to `wallet_v1_bp`.

- [ ] `service.get_active_plan(account)` — lazy-expiry function; returns `free` if nothing active.
- [ ] `service.get_limits(account)` — `get_active_plan(account).limits`.
- [ ] `service.check_and_consume(account, key, counter_fn)` — generic quota check.
- [ ] `service.activate_subscription(sub)` — idempotent completion (mirrors `_complete_topup`
      in `wallet/routes.py:140`), additive renewal.
- [ ] `GET /v1/subscriptions/plans`
- [ ] `POST /v1/subscriptions/purchase`
- [ ] `GET|POST /v1/subscriptions/<tx_ref>/verify`
- [ ] `POST /v1/subscriptions/webhook`
- [ ] `GET /v1/subscriptions/me`

## 3. Phase 2 — Enforcement retrofits

- [ ] `sparks/routes.py:action` — swipe/standout daily limits via `check_and_consume`,
      402 + `{used, limit, upsell: true}` on block. `standout_count`'s `daily_limit`
      now sourced from `get_limits()` instead of hardcoded `5`.
- [ ] `sparks/routes.py:incoming_likes` — free tier capped/blurred + `{total, locked}`.
- [ ] New `GET /v1/sparks/profile-viewers` — reuses the already-populated
      `BehavioralEvent` table (`verb='profile.view'`), same gating shape.
- [ ] `chat/routes.py:post_message` — `chats_per_day` check before `send_message`.
- [ ] New `GET /v1/sparks/matches/<match_id>/contact` — requires active match +
      requester is a party + `can_reveal_contact`. Never bypasses the match requirement.

## 4. Phase 3 — Gamification

- [ ] Streak bonus (3-day/7-day) — transient addend in `check_and_consume`.
- [ ] Near-limit nudge at `remaining <= 1`.
- [ ] "Why upgrade" comparison table in `GET /plans`.
- [ ] Scarcity/promo fields in `extra_data` for time-boxed campaigns.
- [ ] Milestone unlocks (first match, first 10 likes) → one-off temporary boost.

## 5. Phase 4 — Mobile (`linkup-mobo`)

- [ ] `lib/features/subscriptions/subscription_plans_screen.dart`
- [ ] `lib/features/subscriptions/subscription_checkout_webview.dart` (generalizes `LUTopUpWebView`)
- [ ] Shared upsell bottom sheet replacing the bare `SnackBar` at `sparks_screen.dart:370-376`
- [ ] "Who liked me" / "who viewed me" screens with blurred teaser cards
- [ ] "Reveal contact" action on the match detail screen

## 6. Phase 5 — Admin console (`frontend/`)

- [ ] `frontend/src/pages/SubscriptionsPage.jsx` — plan CRUD (mirrors gift-catalog pattern,
      `backend/domains/admin/routes.py:522-570`)
- [ ] New admin routes: `GET/POST /v1/admin/subscription-plans`, `PUT .../<id>`
- [ ] Subscriber list + revenue view + Dashboard stat card

## Verification

- `dart analyze` on every touched mobile file.
- Local end-to-end purchase→verify→activate flow against local MySQL + test-mode Flutterwave.
- Confirm swipe/standout/chat limits reject server-side via direct `curl`, bypassing the client.
- Confirm `incoming_likes`/`profile-viewers` blur for free, unlock for premium test accounts.
- Confirm contact-reveal 403s when not matched, succeeds only for an active match + entitlement.
- Admin: create/edit a plan via `SubscriptionsPage.jsx`, confirm it round-trips through the DB.

## Open question

The original brief's bullet "relevant perfect names" is unclear (likely a typo) —
folded into `priority_deck` as the closest reasonable interpretation pending clarification.
