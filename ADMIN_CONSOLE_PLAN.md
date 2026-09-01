# Admin Console — Full Parity Plan

Where this stands today: the admin console has 5 pages (Dashboard, Accounts, Reports, Hubs,
Events) backed by 10 backend routes. The actual product has 248 routes across 20 domains. This
plan closes that gap, in priority order — money and safety first, then structural fixes, then
content moderation.

## What's actually broken right now (not just missing — broken)

1. **Withdrawals can get permanently stuck.** `POST /v1/wallet/withdraw` sets status to `review`
   for any payout at or above the auto-limit, and the code comment says *"admin releases later"*
   — but no route anywhere lists review-status withdrawals or releases them. That money is stuck
   until someone edits the database by hand.
2. **Panic/SOS alerts don't persist anywhere queryable.** `POST /v1/safety/panic` fires
   notifications and sets a boolean flag on a check-in row, but there's no `PanicAlert` model at
   all. If a real safety emergency happens, there is no admin view of "these SOS alerts fired this
   week" — the log doesn't exist to view.
3. **Two competing admin systems are both live.** `/v1/admin/*` (the new one, JWT + `Account`) and
   `/api/admin/*` (the legacy one, `AdminUser` + bcrypt) both work right now, with different logins
   and different account models. This needs a decision, not just more features bolted onto one side.
4. **Nothing splits data by app.** `Account.app_id` (`linkup` | `abanoonya`) is stamped at signup
   and never surfaced anywhere in the admin API or console. Every list mixes both apps' users and
   content with no way to tell them apart — for a console explicitly meant to run two brands, this
   is the core gap.
5. **Account rows are list-only.** `GET /v1/admin/accounts/<id>` exists and works, but the frontend
   never calls it — clicking a row does nothing. There's no way to see a member's professional
   profile, dating profile, photos, or wallet from the console at all.

## Phase 1 — build this now (money, safety, and the foundation everything else needs)

1. **Rebrand.** Real logo (not a "LU" text glyph), favicon, correct title, and an app-aware header
   that shows which brand (LinkUp / Abanoonya Pro) a given record belongs to instead of hardcoding
   "LinkUp" everywhere a console for two apps shouldn't.
2. **Account detail page.** Wire up the account-click that currently does nothing. One page: full
   profile (professional + dating), photos, wallet balance, KYC status, report history, app_id
   badge — everything about one member in one place. Every other admin action (suspend, KYC
   approve, photo removal) hangs off this page.
3. **App segmentation.** `?app_id=` filter added to every admin list route, plus an app switcher in
   the console header (All / LinkUp / Abanoonya Pro) that persists across pages.
4. **Wallet & withdrawals.** New admin routes: list all withdrawals (filter by status), approve or
   reject a `review`-status one, list gift transactions platform-wide, CRUD the gift catalog
   (pricing lives in the DB only today). New console page.
5. **Safety.** New `PanicAlert` model + route so SOS events actually persist and are listable.
   New admin route + page section for blocks (a pattern of many people blocking one account is a
   real abuse signal, currently invisible). Report detail gets richer: pull in the actual reported
   photo/dating-profile/chat-thread inline instead of just names.
6. **KYC review queue.** L2 national-ID submissions sit in `lu_verifications` with
   `status='pending'` and nothing ever lists or resolves them. New route + page: approve/reject.
7. **Institution approval queue.** Same dead-end pattern — user-suggested institutions save with
   `verified=0` and nothing reviews them. New route + page.
8. **App-version config.** I already built the read-only `GET /v1/app/version` endpoint earlier
   this session; there's still no way to *write* the 4 config rows (linkup/abanoonya ×
   android/ios) without touching the database directly. New admin CRUD route + small page — this
   is exactly the "ship an update, flip a switch to force it" tool an admin console should have.

## Phase 2 — content moderation (do after Phase 1 ships)

- Photos: view any member's full gallery, remove a single flagged photo without suspending the
  whole account.
- Hub posts/comments: browse + delete (hub-level roles exist; nothing lets the *platform* admin
  moderate hub content directly today).
- General feed posts: `is_admin`-gated delete already exists on the member route — the missing
  piece is search/browse to find what to act on from a report.
- Jobs: platform-wide browse + takedown for spam/fraudulent postings.
- Sparks/matches: admin visibility into match volume, and the ability to unmatch/ban from Sparks
  specifically without suspending the whole account.
- Mentorship: mentor directory visibility, completion-rate reporting.
- Interest tag taxonomy: CRUD for the tag catalog (currently DB-only).

## Phase 3 — structural cleanup

- Retire or formally deprecate the legacy `/api/admin/*` surface once Phase 1 covers everything it
  did — right now `AdminUser`/`Account` are two parallel identity systems and that's a real
  liability, not just tech debt.
- Broadcast/announcement route — push a notification to a segment of users. Doesn't exist today.
- Dashboard: replace the flat count tiles with real trends (matches/day, revenue/week, signups by
  app) and make every tile clickable through to its filtered list.

---

## Execution log

**Phase 1 shipped and live at abanoonyapro.online** (2026-08-26). What actually landed:

- Rebrand: real logo (SVG, matching the mobile app's actual violet mark — not a leftover generic
  template icon), favicon, "LinkUp Platform" naming that acknowledges both apps instead of just one.
- App Switcher in the header (All / LinkUp / Abanoonya Pro), `app_id` badge on every account row,
  `?app_id=` filter added to accounts/stats routes — the core multi-tenancy gap is closed.
- Account detail drawer — click any account row for full profile, dating profile, wallet, KYC
  history, block counts, report history in one place. `GET /v1/admin/accounts/<id>` enriched
  server-side to actually return all of that.
- Wallet & Withdrawals page — the broken flow is fixed: `PUT /v1/admin/withdrawals/<id>/release`
  approves or rejects (with automatic refund) a review-status withdrawal. Plus platform-wide gift
  transaction ledger and gift-catalog price/active CRUD.
- Safety page — `PanicAlert` model + migration (SOS events now actually persist), admin list +
  resolve route, blocks list + "most-blocked accounts" abuse-pattern view.
- Reviews page — KYC verification queue (approve bumps to L3, reject rolls back to L1) and
  institution-suggestion queue (approve/reject), both closing dead-end database-only tables.
- App Version Config page — the read endpoint from earlier this session now has a real admin write
  UI: bump `latest_build`, raise `min_supported_build` to force an update, edit release notes and
  store links, per app × platform.
- Dashboard: new "Needs your attention" section (pending reports, open panic alerts, withdrawals
  to review, KYC/institution queues) with every tile clickable through to its filtered list.
- "Events" nav item relabeled "Activity Log" — it was always the behavioral-event audit stream, not
  the real calendar-events feature; that mislabeling is fixed rather than left as a landmine.

Verified end-to-end against the live production API (not just locally) for every new route,
including firing and resolving a real panic alert. Confirmed zero impact on the other 4 tenants
sharing this VPS at every step (Truckfully, Jangu, SchoolDynamics, U-LITS all unchanged).

**Not done — deliberately, and listed above as Phase 2/3:** photo moderation, hub-post/feed-post
browse+moderate, jobs takedown, sparks/match admin visibility, mentorship directory, interest-tag
CRUD, the legacy `/api/admin/*` system, broadcast notifications. This was a large single pass;
those are the next slice, not forgotten.
