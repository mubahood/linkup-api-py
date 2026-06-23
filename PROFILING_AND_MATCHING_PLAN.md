# LinkUp — Deep Profiling & Preference-Matching Plan

> **Living document.** A deeply-researched upgrade to **self-profiling** (who I am)
> and **preferences** (who I'm looking for), plus a **bidirectional compatibility
> engine** and a **motivating, wizard-style** capture flow. Spans backend
> (`linkup-api-py`) + mobile (`linkup-mobo`). Preserves the core idea (one
> identity · two lenses · Interest Graph) and **mode separation** (this is the
> **Sparks / dating** surface; professional data never bleeds in).
>
> **Created**: 2026-06-13 · status legend: 🔴 not started · 🟡 in progress · 🟢 done · ⚪ blocked

---

## 1. Research — what the best dating products capture

Synthesised from how the leading apps structure profiles & matching:

| App | Profile philosophy | Notable fields | Matching |
|---|---|---|---|
| **Hinge** | "Designed to be deleted" — depth + prompts | height, ethnicity, children, **family plans**, religion, politics, drinking, smoking, weed, drugs, education, job, **dating intentions**, relationship type, languages | **Per-field dealbreakers** (age, distance, ethnicity, religion, height, children, education, politics, vices) |
| **Bumble** | Women-first, structured "basics" | height, exercise, education, drinking, smoking, kids, **star sign**, politics, religion, pets | "Looking for" + interest badges |
| **Tinder** | Fast, visual + lifestyle tags | orientation, "looking for", lifestyle (pets, drinking, smoking, workout, diet, social media, sleep), zodiac, education, **family plans**, personality type, communication/love style | distance, age, "relationship goals" |
| **OkCupid** | Values-driven, deep | orientation, monogamy, religion, **politics**, diet, drugs, smoking, kids (have/want), pets, languages, education, ethnicity, height + thousands of match questions | algorithmic % from weighted questions |
| **Match.com** | Intent-serious | relationship goals, kids, religion, education, profession, income, smoking, drinking, ethnicity, body type, height | preference filters as hard/soft |

**Distilled principles for LinkUp (Uganda-first):**
1. **Two symmetric halves:** *attributes* ("who I am") and *preferences* ("who I want"). Matching is **bidirectional** — does my profile satisfy yours, and yours mine?
2. **Dealbreakers vs. preferences:** any preference can be a **hard filter** (exclude) or a **soft boost** (rank). This is the single most powerful idea (Hinge) and what we'll surface.
3. **Sensitive fields are opt-in & match-only** (religion, tribe/ethnicity, politics) — never shown publicly unless the member opts in (`ARCHITECTURE.md §7.6`; we already have `sensitive_optin`).
4. **Capture must be a delightful wizard**, not a form wall — grouped steps, one decision per screen, **save per step**, a moving completeness ring, and a nudge to finish.
5. **Standard, content-rich dropdowns** served by the backend so the app and the matcher always agree on the option set (Uganda-localised where it matters).

---

## 2. Current state (measured 2026-06-13)

- **`lu_dating_profiles` (35 cols)** already covers a strong base: `gender, looking_for_gender, birth_year, height_cm, relationship_goal, has_children, wants_children, smoking, drinking, religion, religiosity, tribe_ethnicity, education_level, love_languages, personality_type, diet, exercise, pets, voice_prompt_url, deal_breakers, sensitive_optin, intent, lifestyle(JSON), prompts(JSON), photos(JSON), bio, age_min, age_max, max_distance_km`.
- **Gaps in attributes:** `sexual_orientation, marijuana, politics, body_type, zodiac, languages_spoken, communication_style, job/industry, region_id/district_id (location)`.
- **Preferences are minimal:** only `age_min/age_max, looking_for_gender, max_distance_km`. **No structured "looking for"** (preferred religion/education/height/kids/vices…), **no dealbreaker flags**.
- **Locations:** only **7 countries + 38 cities** — **no Uganda region→district hierarchy** (table supports it via `level` enum + `parent_id`, but it's unseeded).
- **Matching:** Interest-Graph overlap only (`recommend.service`); **no preference/attribute compatibility, no bidirectional %**.
- **Mobile:** monolithic `sparks_onboarding_screen` (1376 lines) + `dating_profile_screen` (974); no preference UI, no compatibility view.

---

## 3. Target design

### 3.1 Canonical option catalog (backend-served — `GET /v1/reference/dating-options`)
One source of truth for every dropdown (value + label), so app & matcher never drift. Catalogs:

`gender, orientation, relationship_goal, smoking, drinking, marijuana, diet, exercise, pets,
religion, religiosity, politics, has_children, wants_children, education_level, body_type,
zodiac, personality_type (MBTI), love_languages, communication_style, languages, tribe (UG, sensitive),
industry (job)`. Uganda-localised content for religion, tribe, languages, industry.

### 3.2 Attribute schema additions (migration `0032`)
Add to `lu_dating_profiles`: `sexual_orientation, marijuana, politics, body_type, zodiac,
communication_style, languages_spoken (JSON), industry, region_id, district_id, country_code`.
(Existing columns are reused; nothing duplicated.)

### 3.3 Preferences ("looking for") — `preferences` JSON on `lu_dating_profiles`
A structured object, each entry `{value(s), is_dealbreaker}`, **≥15 fields**:

1. `interested_in` (gender list) · 2. `age` `{min,max}` · 3. `distance_km` · 4. `height_cm` `{min,max}`
5. `relationship_goal` (list) · 6. `wants_children` · 7. `open_to_children` (date someone with kids?)
8. `religion` (list) · 9. `education_min` · 10. `smoking` (tolerance) · 11. `drinking` (tolerance)
12. `diet` · 13. `languages` (list) · 14. `tribe` (list, sensitive/opt-in) · 15. `politics`
+ `dealbreakers: [field…]` (derived from per-field `is_dealbreaker`).
Updatable any time via `PUT /v1/sparks/preferences`.

### 3.4 Bidirectional compatibility engine (`backend/domains/recommend/preference_match.py`)
For viewer **V** and candidate **C** return:
- `they_match_me` — % of **my** profile that satisfies **C's** preferences
- `i_match_them` — % of **C's** profile that satisfies **my** preferences
- `mutual_pct` — blended (harmonic mean) + Interest-Graph overlap weighting
- `breakdown[]` — per-criterion `{field, mine, theirs, status: match|miss|dealbreaker}`
- **Dealbreaker rule:** a violated dealbreaker on either side → hard-excluded from the deck and flagged in detail views.
Exposed at `GET /v1/sparks/compatibility/<account_id>` and embedded in deck cards + match detail.

### 3.5 Location hierarchy
Seed **4 UG regions + ~130 districts** (parent_id chain country→region→district). Endpoint already supports `?level=` and we add `?parent_id=` for cascading dropdowns (region → its districts).

---

## 4. Backend tasks

| ID | Task | Status |
|---|---|---|
| `P-API-01` ✅ | **Option catalog** module + `GET /v1/reference/dating-options` (all dropdown value/label sets, UG-localised) | 🟢 |
| `P-API-02` ✅ | **Uganda location hierarchy seed** (regions + districts, parent chain) + `?parent_id=` cascading filter on `/reference/locations` | 🟢 |
| `P-API-03` ✅ | **Attribute schema** migration `0032` (sexual_orientation, marijuana, politics, body_type, zodiac, communication_style, languages_spoken, industry, region_id, district_id, country_code) + model/`to_dict`/PUT validation | 🟢 |
| `P-API-04` ✅ | **Preferences** `preferences` JSON column + `GET`/`PUT /v1/sparks/preferences` (per-field value + `is_dealbreaker`), updatable anytime | 🟢 |
| `P-API-05` ✅ | **Wizard step API** — `PUT /v1/sparks/profile/step` saves a single step's fields + returns updated completion (sectioned, reuses T-API-102) so each wizard screen persists independently | 🟢 |
| `P-API-06` ✅ | **Bidirectional compatibility engine** (`preference_match.py`) + `GET /v1/sparks/compatibility/<id>` (they_match_me, i_match_them, mutual_pct, breakdown, dealbreaker flags) | 🟢 |
| `P-API-07` ✅ | **Wire into deck & match** — deck cards carry `compatibility` + dealbreaker exclusion; match detail shows the full breakdown | 🟢 |
| `P-API-08` ✅ | **Dummy data** — fill new attributes + realistic `preferences` for **≥50** dating profiles (UG-context) via the factory; seed validator covers them | 🟢 |
| `P-API-09` ✅ | **Tests** — extend `e2e_full.py` (options catalog, preferences GET/PUT, compatibility, location cascade) → green | 🟢 |

## 5. Mobile tasks

| ID | Task | Status |
|---|---|---|
| `P-MOB-01` ✅ | **Dropdown/option infra** — fetch & cache `dating-options`; reusable `LUOptionPicker` (single/multi) + `LULocationPicker` (region→district cascade), all on tokens | 🟢 |
| `P-MOB-02` ✅ | **Profile wizard** — grouped, one-decision-per-screen, resumable, **saves each step** (`P-API-05`), progress bar + completeness ring, friendly copy. Steps: About → Origin → Work/Education → Lifestyle → Values → Family → Personality → Photos/Prompts | 🟢 |
| `P-MOB-03` ✅ | **"What you're looking for" wizard** — ≥15 preference fields, each with a **dealbreaker toggle**, saved to `preferences` (`P-API-04`), editable any time from settings | 🟢 |
| `P-MOB-04` ✅ | **Completion nudge** — a persistent, non-annoying "complete your profile to appear in more decks" card driven by the journey/completion API; deep-links into the exact unfinished step | 🟢 |
| `P-MOB-05` ✅ | **Compatibility view** — on each profile/match: "**You & them**" — `i_match_them` vs `they_match_me` rings, `mutual_pct`, and a scrollable breakdown ("You both want long-term ✓ · They smoke, your dealbreaker ✗"). Professional, scannable. | 🟢 |
| `P-MOB-06` ✅ | **Deck integration** — surface `mutual_pct` + top reason on swipe cards; respect dealbreaker exclusion | 🟢 |
| `P-MOB-07` ✅ | **Polish & QA** — every screen uses `LU` components + tokens, loading/empty/error states, motion; verified on device | 🟢 |

---

## 6. Execution order
```
Backend:  P-API-01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09
Mobile:   P-MOB-01 → 02 → 03 → 04 → 05 → 06 → 07
```
Backend first (the option catalog + schema + engine are the contract the app builds against), each verified against the running server with ≥50 dummy records, then the mobile wizard + compatibility UI.

## 7. Definition of done (per task)
Backend: migration applied · endpoint returns correct shape · ≥50 dummy records flow through · `e2e_full.py` probe green · no 500s · mode separation intact (dating-only).
Mobile: `LU` components + tokens only · loading/empty/error trio · saves per step · resumable · verified on device with believable data.

## 8. Changelog
| Date | Change |
|---|---|
| 2026-06-13 | **Mobile profiling + preference UI complete (P-MOB-01…07).** Built a **data-driven wizard engine** (`lu_wizard.dart` + models, one engine for both wizards) with editors for single/multi/range/slider/year/text/bool/region→district-location; the **profile wizard** (7 steps, saves each step via `/v1/sparks/profile/step`); the **preferences wizard** (15+ fields, each with a **dealbreaker toggle**, saves to `/v1/sparks/preferences`); the **completion nudge** (matches screen → wizard); the **deck `mutual_pct` heart chip**; and the **compatibility view** wired into the match screen. Entry points added to Sparks settings. `flutter analyze` **0 errors / 0 warnings** (info unchanged); **debug APK builds**. |
| 2026-06-13 | **Mobile foundation (P-MOB-01 partial, P-MOB-05).** Built & compile-verified: `DatingOptions` service (caches the option catalog + region/district cascade), reusable `LUOptionPicker` (single/multi bottom sheet), and `LUCompatibilityView` (mutual % ring + two directional rings + per-criterion breakdown + dealbreaker banner) **wired into the match profile screen**. `flutter analyze` 0 errors / 0 warnings; **debug APK builds**. _Remaining (device-iteration screen work):_ the full profile wizard (P-MOB-02), preferences wizard (P-MOB-03), completion nudge (P-MOB-04), deck `mutual_pct` chip (P-MOB-06), polish (P-MOB-07) — backend contracts + components are ready. |
| 2026-06-13 | **Backend complete (P-API-01…09).** Option catalog (24 dropdowns) + `dating-options` endpoint; Uganda region→district seed (4 regions, 133 districts, deduped) + cascade; migration `0032` (12 deep attribute + `preferences` cols); `GET/PUT /v1/sparks/preferences`; wizard step API; **bidirectional compatibility engine** (`preference_match.py`) + `GET /v1/sparks/compatibility/:id` (i_match_them / they_match_me / mutual_pct / dealbreakers); deck cards now carry `mutual_pct`; 60+ dummy profiles with prefs. **E2E 78/78, audit 370/370.** |
| 2026-06-13 | Plan created from research (Hinge/Bumble/Tinder/OkCupid/Match) + live audit of current schema, locations, and mobile dating screens. 9 backend + 7 mobile tasks defined. |
