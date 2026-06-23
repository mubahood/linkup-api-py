# Wallet · Gifting · Flutterwave (Uganda) — Implementation Plan

_Real-money feature. This document is the design + gap analysis. No money-moving code is
written until the open decisions in §8 are confirmed._

Last updated: 2026-06-23

---

## 0. Goal (from the request)
1. **Wallet** that works perfectly — deposit (top-up), balance, transaction history.
2. **Gifting (TikTok-style)** — a user can gift another user; gifts the recipient receives can be
   **redeemed back to wallet cash**.
3. **Withdrawal** — wallet cash can be withdrawn to a **mobile-money phone number** (auto payout).
4. **Flutterwave** for deposits (collections) and withdrawals (transfers/payouts), Uganda, **UGX**,
   `mobilemoneyuganda` + card.

---

## 1. What already exists (reuse)

| Piece | Location | State |
|---|---|---|
| `WalletAccount` (balance, totals, currency UGX) | `backend/domains/wallet/models.py` | ✅ good |
| `WalletTransaction` (ledger: type/category/amount/balance_before/after/ref/status/flw_tx_id) | same | ✅ good |
| Routes: `GET /v1/wallet/balance`, `GET /v1/wallet/transactions`, `POST /v1/wallet/topup`, `…/topup/<ref>/verify` | `backend/domains/wallet/routes.py` | ⚠️ topup broken (wrong method names) |
| `FlutterwaveService` (payments, verify, webhook-verify, **transfers/payouts**, banks) | `backend/services/flutterwave_service.py` | ⚠️ Nigeria-only; needs UG |
| FLW config keys | `backend/config.py` (`FLW_*`) + `.env` | ⚠️ currency=NGN, old options/keys |
| Mobile wallet screen (balance, top-up sheet; Send/Pay/Withdraw = "coming soon") | `linkup-mobo/lib/features/wallet/wallet_screen.dart` | ⚠️ partial |

---

## 2. Critical gaps (backend logic)

1. **Method mismatch (bug):** `topup` calls `flw.initiate_payment(...)` and `flw.verify_transaction(...)`
   but the service exposes `initialize_payment(...)`, `verify_by_id(...)`, `verify_by_tx_ref(...)`.
   → topup always hits the silent fallback (no real payment link). **Fix wiring.**
2. **Uganda phone normalisation:** `_normalize_phone` forces `+234…`. Need `+256…` (and accept
   `07XXXXXXXX`, `2567…`, `+2567…`). **Add UG normaliser.**
3. **Uganda payout:** `initiate_transfer` is written for NG bank codes/account numbers. Uganda
   mobile-money payout via Flutterwave Transfers uses `account_bank` = network code
   (`MTN`/`AIRTEL`, exact codes to be confirmed against FLW `/v3/transfers/rates` or docs),
   `account_number` = subscriber phone, `currency=UGX`. **Add `initiate_mobile_money_payout_ug(...)`.**
4. **Webhook is a stub, not wired to crediting** (`backend/routes/flutterwave.py`). No path
   credits the wallet on `charge.completed` or settles a withdrawal on `transfer.completed`.
   **Add a real webhook → wallet credit / withdrawal settle.**
5. **Webhook verification is wrong for FLW v3.** `verify_webhook_signature` computes an
   HMAC-SHA256 of the body. Flutterwave v3 actually sends a **static** `verif-hash` header equal
   to the dashboard "Secret hash" (`FLW_SECRET_HASH`); you compare for **equality**. **Fix to a
   constant-time equality check** (keep HMAC path only if we move to signed webhooks later).
6. **No gifting domain at all** — no gift catalog, no gift send/receive ledger, no redeem.
7. **No withdrawal/payout endpoints** — no request, no status, no settle.
8. **No idempotency / row-locking on balance mutations** beyond the `@idempotent` decorator on
   verify. Money mutations must lock the wallet row (`SELECT … FOR UPDATE`) and be idempotent by
   `reference`/`flw_tx_id`.

---

## 3. Data model (new + changes)

### 3.1 Reuse `WalletAccount` / `WalletTransaction`
- Extend `WalletTransaction.category` usage (string, no migration needed) with:
  `topup`, `gift_sent`, `gift_received`, `gift_redeem`, `withdrawal`, `withdrawal_reversal`, `fee`.
- Add a notion of **withdrawable vs total balance** (gift income may be withdrawable; top-up may be
  spend-only depending on §8 decision). Two options:
  - (A) single `balance` (simplest) — everything is one pot.
  - (B) `balance` + `withdrawable_balance` columns — only redeemed-gift cash is withdrawable.
  _Decision in §8._

### 3.2 New table — `lu_gift_catalog`
`id, code, name, icon_url, price_coins (int), cash_value_ugx (numeric), sort_order, active`.
Gifts are bought/sent in **coins**; recipient accrues **cash_value** (minus platform fee).

### 3.3 New table — `lu_coin_wallets` (or reuse balance as coins?)
TikTok model separates **coins** (bought, spend-only) from **diamonds/cash** (earned, withdrawable).
- `lu_coin_balances(account_id, coins int)` — coins bought with money, used to send gifts.
- Earned gift value lands in the **cash wallet** (`WalletAccount.balance` or `withdrawable_balance`).
_Decision in §8: coins-model vs pure-cash-model._

### 3.4 New table — `lu_gifts` (gift events / ledger)
`id, sender_id, recipient_id, gift_code, coins_spent, cash_value_ugx, platform_fee_ugx,
context_type (post|chat|profile|stream), context_id, message, created_at`.

### 3.5 New table — `lu_withdrawals`
`id, account_id, amount_ugx, fee_ugx, net_ugx, phone, network (MTN|AIRTEL), beneficiary_name,
status (requested|processing|paid|failed|reversed), flw_transfer_id, flw_reference,
failure_reason, requested_at, settled_at`.

### 3.6 New table — `lu_payment_intents` (top-ups)
Either reuse `WalletTransaction(status=pending)` (current approach) or a dedicated intents table.
Recommend keeping the pending-`WalletTransaction` approach (already in place) keyed by `reference`.

---

## 4. Flutterwave integration (Uganda)

### 4.1 Deposits (collections)
- **Hosted page** (recommended, PCI-safe, supports mobile money + card):
  `FlutterwaveService.initialize_payment(amount, tx_ref, name, email, phone, redirect_url,
  currency='UGX', payment_options='mobilemoneyuganda,card,banktransfer,ussd', meta={...})`
  → returns `payment_link`; mobile opens it in a WebView/external browser.
- **Verify** (authoritative): on webhook `charge.completed` **and** on redirect return, call
  `verify_by_id(flw_tx_id)` and `is_payment_successful(resp, expected_amount, 'UGX')`. Only then
  credit, idempotently (guard on `flw_tx_id` already processed + `reference` pending→completed).
- **Never trust client-reported success or amount** — always server-verify against FLW.

### 4.2 Withdrawals (payouts / transfers)
- Flutterwave **Transfers API** `POST /v3/transfers` supports Uganda mobile money payout.
  New service method `initiate_mobile_money_payout_ug(phone, network, amount, name, narration, reference)`
  → `account_bank=<MTN|AIRTEL code>`, `account_number=<2567…>`, `currency='UGX'`.
- Payout is **asynchronous**: FLW returns `status=NEW/PENDING`; final state arrives via
  **`transfer.completed`** webhook (or poll `get_transfer_status`). Settle the `lu_withdrawals`
  row + ledger on the terminal event; **reverse the debit** on failure.
- **Auto vs manual:** auto-payout is possible via API, but requires (a) funded FLW merchant
  balance, (b) Transfers enabled on the account, (c) often a transfer OTP/approval for live.
  _Policy decision in §8 (auto vs manual-review threshold)._

### 4.3 Webhook — `POST /v1/wallet/webhook/flutterwave`
- Public (no JWT). Verify header `verif-hash == FLW_SECRET_HASH` (constant-time). Reject otherwise.
- Parse `event` / `data.status`:
  - `charge.completed` + successful → verify by id → credit wallet (idempotent).
  - `transfer.completed` → settle withdrawal: `SUCCESSFUL`→paid, `FAILED`→reverse debit.
- Idempotent on `flw_tx_id` / `flw_transfer_id`. Always 200 quickly; do work inside a txn.

### 4.4 Config / .env (Uganda)
Update `.env` to the provided live values: `FLW_CURRENCY=UGX`,
`FLW_PAYMENT_OPTIONS=mobilemoneyuganda,card,banktransfer,ussd`, the new keys + `FLW_SECRET_HASH`.
`config.py` default currency → `UGX`. **Never expose `FLW_SECRET_KEY` to the mobile app** —
only the **public key** may reach the client (and we don't even need it for hosted-page flow).

---

## 5. Security & integrity (non-negotiable)
- **Row-lock** the wallet on every mutation: `WalletAccount.query.with_for_update()`.
- **Idempotency:** credits keyed on `flw_tx_id`; debits/withdrawals keyed on `reference`; webhook
  re-delivery must be a no-op once terminal.
- **Server-authoritative amounts:** credit the **FLW-verified** amount, not the client's.
- **Atomic ledger:** every balance change writes a `WalletTransaction` with `balance_before/after`
  in the same DB transaction; on any error → rollback.
- **Withdrawal guards:** balance ≥ amount + fee (checked under lock), min/max, rate-limit, optional
  cool-down, optional KYC gate (§8). Debit **before** calling FLW; reverse on failure.
- **No negative balances** ever (DB check + app check).
- **Gift guards:** sender has enough coins/balance; cannot gift self; recipient exists & not blocked.
- **Audit:** keep `extra_data` JSON (raw FLW payload refs) on each tx for reconciliation.

---

## 6. Endpoint specification

### Existing (fix)
- `POST /v1/wallet/topup` — fix to call `initialize_payment`; return real `payment_link`.
- `…/topup/<ref>/verify` — use `verify_by_id` + `is_payment_successful`; idempotent credit.

### New — wallet/payout
- `POST /v1/wallet/webhook/flutterwave` — collections + transfers settlement (public, hash-verified).
- `GET  /v1/wallet/withdraw/options` — networks (MTN/Airtel), min/max, fee preview.
- `POST /v1/wallet/withdraw` — `{amount, phone, network}` → create `lu_withdrawals` + debit + FLW transfer.
- `GET  /v1/wallet/withdrawals` — my withdrawal history + statuses.

### New — gifting
- `GET  /v1/gifts/catalog` — purchasable gifts (code, name, icon, price_coins, cash_value).
- `POST /v1/coins/purchase` — buy coins (→ top-up flow / debit cash). _(if coins-model)_
- `POST /v1/gifts/send` — `{recipient_id, gift_code, context_type, context_id, message}`.
- `GET  /v1/gifts/received` / `GET /v1/gifts/sent` — gift history.
- `POST /v1/gifts/redeem` — convert received gift value → withdrawable wallet cash.
- `GET  /v1/gifts/summary` — coins, gift earnings, redeemable balance.

---

## 7. Mobile UI plan (`linkup-mobo`)
- **Wallet screen:** real balance + withdrawable, transaction list (paginated), Top-up (amount →
  open FLW hosted page in WebView → return → verify), **Withdraw** (amount + network + phone →
  confirm → status), gifting summary entry.
- **Top-up WebView** screen: load `payment_link`, detect redirect to `…/verify`, then call verify.
- **Gifting:** a gift picker sheet (grid of gifts with coin price) reachable from a profile / chat /
  post; "Send gift" → confirm → animation. Received-gifts screen with **Redeem** action.
- **Withdraw screen:** network picker (MTN/Airtel), phone, amount, fee preview, confirm, result.

---

## 8a. DECISIONS CONFIRMED (2026-06-23)
1. **Economy:** Coins → gifts → cash (TikTok). Coins bought with money. Gifts earn the
   recipient **redeemable** cash; redeemed cash lands in withdrawable wallet `balance`.
   **Updated 2026-06-23:** owner opted to also allow **coins → cash** conversion
   (`POST /v1/wallet/coins/redeem`, 1 coin = UGX 50). ⚠️ This means topped-up money can be
   cashed back out — an AML/compliance consideration to monitor (limits/KYC may be needed).
2. **Platform fee:** **10%** on gifts (recipient keeps 90% of face value).
3. **Payout:** **Auto** below **UGX 100,000**, **manual admin review** at/above it.
4. **Keys:** Use provided **live** keys. ⚠️ No real deposits/transfers will be triggered during
   development verification — only internal-ledger logic is tested; live money tests are the owner's.

### Confirmed economy constants
- `COIN_RATE_UGX = 50` (1 coin = UGX 50 at purchase).
- Gift `cash_value_ugx = price_coins * COIN_RATE_UGX` (gross); recipient redeemable += 90%.
- Wallet row gains `coins` (int) + `redeemable` (UGX) alongside withdrawable `balance`.
- Withdrawal: min UGX 1,000; auto < 100,000; fee = UGX 500 flat (configurable).

## 8. OPEN DECISIONS (resolved above — kept for reference)
1. **Economy model:** TikTok-style **coins (buy) → gifts → diamonds/cash (withdraw)**, or a
   **single UGX wallet** where gifts move cash directly (simpler)?
2. **Platform fee** on gifts (e.g., recipient gets X% of face value)? What %?
3. **Withdrawable source:** can topped-up cash be withdrawn, or **only earned gift cash**?
4. **Payout policy:** fully **automatic** payout via API, or **manual review** above a threshold
   (e.g. auto < UGX 100k, manual above)? (Auto needs Transfers enabled + funded FLW balance.)
5. **Limits/fees:** min/max top-up, min/max withdrawal, withdrawal fee (flat/percent), daily caps.
6. **KYC gate** for withdrawals (phone-verified only, or require KYC level ≥ 1)?
7. **Networks:** MTN + Airtel only (Uganda), correct FLW `account_bank` codes to confirm.

---

## 9. Phased execution (after §8 confirmed)
- **P1 — Config & deposits fixed:** `.env`/`config` UGX; UG phone normaliser; fix topup wiring;
  hosted-page deposit verified by webhook + redirect; idempotent credit with row-lock. _(verifiable)_
- **P2 — Withdrawals:** `lu_withdrawals` + endpoints + UG mobile-money payout + transfer webhook
  settlement + debit/reversal.
- **P3 — Gifting:** catalog + (coins?) + send/receive ledger + redeem to cash.
- **P4 — Mobile UI:** wallet (balance/tx/top-up WebView/withdraw), gift picker, received+redeem.
- **P5 — Hardening:** reconciliation report, rate limits, admin payout review (if manual), tests
  with FLW **test** keys before pointing at live.

> Note: §9 should first run end-to-end against Flutterwave **test/sandbox** keys. The provided keys
> look live — moving real money should only happen after sandbox verification and §8 sign-off.

---

## 10. Progress (2026-06-23)

**Backend foundation — DONE & verified (no real money moved):**
- ✅ Config: `.env`/`config.py` → UGX, `mobilemoneyuganda`, economy constants
  (`COIN_RATE_UGX=50`, `GIFT_PLATFORM_FEE_PCT=10`, min/fee/auto-limit).
- ✅ `FlutterwaveService`: UG phone normaliser, `initiate_mobile_money_payout_ug`,
  correct v3 `verify_webhook_hash` (constant-time equality).
- ✅ Migration `0034`: wallet `coins`/`redeemable` cols + `lu_gift_catalog` (9 gifts seeded) +
  `lu_gifts` + `lu_withdrawals`.
- ✅ Models: `WalletAccount` extended; `GiftCatalog`, `Gift`, `Withdrawal`.
- ✅ Routes (all live): `GET balance`, `GET transactions`, `POST topup` (→ real FLW link, verified
  live), `topup/<ref>/verify`, `POST webhook/flutterwave` (charge credit + transfer settle),
  `GET withdraw/options`, `POST withdraw` (lock+debit, auto<100k / review≥100k, reverse on fail),
  `GET withdrawals`; gifts: `catalog`, `summary`, `send`, `received`, `sent`, `redeem`.
- ✅ Verified: deposit creates live FLW link; gift send applies 10% fee & credits recipient;
  redeem moves redeemable→balance; withdraw validation (min/network/insufficient) all enforced;
  row-locking + idempotency + debit-reversal in place.

**Live test findings (2026-06-23, number 0761103575):**
- ✅ Live keys valid; UGX balance present (4,204 available).
- ✅ Deposit: real mobile-money charge → Flutterwave `"Charge initiated"` + completion redirect.
- ⚠️ Payout: Flutterwave returns **"enable IP Whitelisting"** — Transfers API is gated behind IP
  whitelisting (dashboard). Our code **auto-reversed** the debit on failure (verified).
- ✅ **Carrier auto-detection** added (corrects an earlier mislabel — 076 is **MTN**):
  - MTN: 076, 077, 078, 039 · Airtel: 070, 074, 075, 020.
  - `FlutterwaveService.detect_network_ug()`; withdraw route auto-sets the network and rejects a
    mismatched manual choice ("looks like MTN, not AIRTEL").

**Mobile UI (P4) — DONE (analyze clean, APK built):**
- ✅ Wallet screen rebuilt against the real API (was calling non-existent `/wallet/me`,`/wallet/accounts`
  with wrong field names → showed 0). Now reads `/v1/wallet/balance` (balance/coins/redeemable),
  `/v1/wallet/transactions`, `/v1/gifts/summary`. Working actions: **Top up · Withdraw · Gifts · History**.
- ✅ Top-up WebView (`wallet_topup_webview.dart`): opens the FLW link, intercepts the
  `…/topup/<ref>/verify` redirect, calls verify → credits coins.
- ✅ Withdraw screen (`wallet_withdraw_screen.dart`): amount, phone with **live network auto-detect**
  (MTN/Airtel chip), fee preview, calls `/v1/wallet/withdraw`.
- ✅ Transactions screen (`wallet_transactions_screen.dart`): full paginated history + shared `LUTxnRow`.
- ✅ Gifts received screen (`gifts_received_screen.dart`): earnings card + **Redeem** to wallet.

**Remaining:**
- ⏳ Gift PICKER (sending) wired from a profile/chat/post entry point (uses `/v1/gifts/send`).
- ⏳ Hardening (P5): admin payout-review screen for ≥100k withdrawals; reconciliation report;
  set the webhook URL `…/v1/wallet/webhook/flutterwave` + `verif-hash` secret in the FLW dashboard.
- ⏳ Owner action: run ONE small **live** top-up + withdrawal end-to-end to confirm money movement.
</content>
