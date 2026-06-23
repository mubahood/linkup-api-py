"""
Comprehensive end-to-end coverage harness — exercises the /v1 endpoints NOT
already covered by audit.py (posts, photos, sparks profile, jobs extras, hubs
member mgmt, comments, interests, links status, notifications, reference,
threads, auth extras, profile extras, admin events, endorsements, mentorship).

Creates its own dummy data through the public APIs. Run while the server is up:
    python e2e_full.py
"""
import io
import time
import requests

from backend.domains.identity.service import DEV_OTP

BASE = "http://localhost:5001"
R = {"pass": [], "fail": []}


def call(method, path, body=None, token=None, files=None, form=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, headers=h, timeout=15)
        elif method == "POST":
            if files is not None:
                r = requests.post(url, headers=h, files=files, data=form or {}, timeout=15)
            elif form is not None:
                r = requests.post(url, headers=h, data=form, timeout=15)
            else:
                r = requests.post(url, headers=h, json=body, timeout=15)
        elif method == "PUT":
            r = requests.put(url, headers=h, json=body, timeout=15)
        elif method == "PATCH":
            r = requests.patch(url, headers=h, json=body, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, headers=h, json=body, timeout=15)
        else:
            return None, f"bad method {method}"
        try:
            return r.json(), r.status_code
        except Exception:
            return {"_nonjson": r.text[:120]}, r.status_code
    except Exception as e:
        return None, str(e)


def chk(name, method, path, body=None, token=None, files=None, form=None, allow=(1,)):
    d, status = call(method, path, body, token, files, form)
    if d is None:
        R["fail"].append((name, f"exception: {status}"))
        print(f"  ❌ {name} — exception {status}")
        return None
    code = d.get("code")
    if code in allow:
        R["pass"].append(name)
        print(f"  ✅ {name} (code={code})")
        return d.get("data")
    R["fail"].append((name, f"code={code} http={status} msg={d.get('message','')[:80]}"))
    print(f"  ❌ {name} — code={code} http={status} | {d.get('message','')[:90]}")
    return None


def sec(t):
    print(f"\n── {t} " + "─" * (56 - len(t)))


def auth(phone):
    call("POST", "/v1/auth/otp/request", {"phone": phone, "purpose": "login"})
    d, _ = call("POST", "/v1/auth/login", {"phone": phone, "code": DEV_OTP})
    return (d or {}).get("data", {}).get("access_token"), (d or {}).get("data", {}).get("id")


print("Authenticating…")
TK, MY_ID = auth("+256700000001")          # samuel-ocen (admin + premium)
TK2, ID2 = auth("+256700000011")           # a second member
if not TK:
    print("FATAL: cannot authenticate"); raise SystemExit(1)
print(f"  samuel id={MY_ID}  | second id={ID2}")

# ─────────────────────────────────────────────────────────────────────────────
sec("POSTS")
_pd = chk("POST /v1/posts (text)", "POST", "/v1/posts", token=TK,
          form={"post_type": "text", "body": "E2E hello from the test harness #linkup",
                "audience": "public", "mode": "professional", "tags": "linkup,testing"},
          allow=(1,))
POST_ID = (_pd or {}).get("id")
chk("GET /v1/posts/feed", "GET", "/v1/posts/feed", token=TK)
chk("GET /v1/posts/trending", "GET", "/v1/posts/trending", token=TK)
chk("GET /v1/posts/saved", "GET", "/v1/posts/saved", token=TK)
chk("GET /v1/posts/by/:id", "GET", f"/v1/posts/by/{MY_ID}", token=TK)
if POST_ID:
    chk("GET /v1/posts/:id", "GET", f"/v1/posts/{POST_ID}", token=TK)
    chk("PATCH /v1/posts/:id", "PATCH", f"/v1/posts/{POST_ID}", token=TK,
        body={"body": "E2E edited body"})
    chk("POST /v1/posts/:id/view", "POST", f"/v1/posts/{POST_ID}/view", token=TK2)
    chk("POST /v1/posts/:id/like", "POST", f"/v1/posts/{POST_ID}/like", token=TK2,
        body={"reaction_type": "like"})
    chk("GET /v1/posts/:id/likes", "GET", f"/v1/posts/{POST_ID}/likes", token=TK)
    chk("POST /v1/posts/:id/save", "POST", f"/v1/posts/{POST_ID}/save", token=TK2)
    chk("POST /v1/posts/:id/share", "POST", f"/v1/posts/{POST_ID}/share", token=TK2,
        body={"body": "Worth a read"})
    _cd = chk("POST /v1/posts/:id/comments", "POST", f"/v1/posts/{POST_ID}/comments",
              token=TK2, body={"body": "Great post! 👏"})
    CMT_ID = (_cd or {}).get("id")
    chk("GET /v1/posts/:id/comments", "GET", f"/v1/posts/{POST_ID}/comments", token=TK)
    if CMT_ID:
        chk("POST /v1/comments/:id/like", "POST", f"/v1/comments/{CMT_ID}/like", token=TK)
        chk("PATCH /v1/comments/:id", "PATCH", f"/v1/comments/{CMT_ID}", token=TK2,
            body={"body": "Great post! (edited)"})
        chk("DELETE /v1/comments/:id", "DELETE", f"/v1/comments/{CMT_ID}", token=TK2)

# Poll post + vote
_pp = chk("POST /v1/posts (poll)", "POST", "/v1/posts", token=TK,
          form=[("post_type", "poll"), ("poll_question", "Best Ugandan dish?"),
                ("poll_options", "Rolex"), ("poll_options", "Luwombo"),
                ("poll_options", "Matoke"), ("audience", "public"), ("mode", "professional")],
          allow=(1,))
POLL_ID = (_pp or {}).get("id")
if POLL_ID:
    _poll = (_pp or {}).get("poll") or {}
    opts = _poll.get("options") or []
    if opts:
        chk("POST /v1/posts/:id/poll/vote", "POST", f"/v1/posts/{POLL_ID}/poll/vote",
            token=TK2, body={"option_id": opts[0]["id"]})
    chk("DELETE /v1/posts/:id (poll cleanup)", "DELETE", f"/v1/posts/{POLL_ID}", token=TK)
if POST_ID:
    chk("DELETE /v1/posts/:id", "DELETE", f"/v1/posts/{POST_ID}", token=TK)

# ─────────────────────────────────────────────────────────────────────────────
sec("PHOTOS")
_png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
_phd = chk("POST /v1/photos (upload)", "POST", "/v1/photos", token=TK,
           files={"photo": ("e2e.png", io.BytesIO(_png), "image/png")},
           form={"caption": "E2E test photo"})
PHOTO_ID = (_phd or {}).get("id") if isinstance(_phd, dict) else None
chk("GET /v1/photos", "GET", "/v1/photos", token=TK)
chk("GET /v1/photos/account/:id", "GET", f"/v1/photos/account/{MY_ID}", token=TK)
chk("GET /v1/photos/counts", "GET", "/v1/photos/counts", token=TK)
if PHOTO_ID:
    chk("PATCH /v1/photos/:id", "PATCH", f"/v1/photos/{PHOTO_ID}", token=TK,
        body={"caption": "E2E updated caption"})
    chk("DELETE /v1/photos/:id", "DELETE", f"/v1/photos/{PHOTO_ID}", token=TK)

# ─────────────────────────────────────────────────────────────────────────────
sec("SPARKS PROFILE")
chk("GET /v1/sparks/profile", "GET", "/v1/sparks/profile", token=TK)
chk("PUT /v1/sparks/profile", "PUT", "/v1/sparks/profile", token=TK,
    body={"bio": "E2E dating bio", "intent": "serious", "relationship_goal": "long_term"})
_spd = chk("POST /v1/sparks/profile/photos", "POST", "/v1/sparks/profile/photos", token=TK,
           body={"url": "https://picsum.photos/seed/e2e/600/800", "caption": "E2E"})
_nphotos = len((_spd or {}).get("photos") or [])
# Reorder needs a valid permutation of all current indices.
_order = list(range(_nphotos))[::-1] if _nphotos else [0]
chk("PUT /v1/sparks/profile/photos/reorder", "PUT", "/v1/sparks/profile/photos/reorder",
    token=TK, body={"order": _order})
chk("DELETE /v1/sparks/profile/photos/:idx", "DELETE", "/v1/sparks/profile/photos/0", token=TK)
chk("GET /v1/sparks/likes", "GET", "/v1/sparks/likes", token=TK)
chk("GET /v1/sparks/standout-count", "GET", "/v1/sparks/standout-count", token=TK)
chk("GET /v1/sparks/stats", "GET", "/v1/sparks/stats", token=TK)

# ─────────────────────────────────────────────────────────────────────────────
sec("JOBS EXTRAS")
chk("GET /v1/jobs/for-you", "GET", "/v1/jobs/for-you", token=TK)
# Create a job to exercise stats / reopen / close lifecycle
_jd = chk("POST /v1/jobs (for e2e)", "POST", "/v1/jobs", token=TK,
          body={"title": "E2E QA Engineer", "description": "Testing the LinkUp API end to end thoroughly.",
                "employment_type": "full_time", "work_mode": "remote"})
JOB_ID = (_jd or {}).get("id")
if JOB_ID:
    chk("GET /v1/jobs/:id/stats", "GET", f"/v1/jobs/{JOB_ID}/stats", token=TK)
    chk("POST /v1/jobs/:id/contact-poster", "POST", f"/v1/jobs/{JOB_ID}/contact-poster",
        token=TK2, body={"message": "Hi, I'm interested in this role."})
    chk("POST /v1/jobs/:id/close", "POST", f"/v1/jobs/{JOB_ID}/close", token=TK)
    chk("POST /v1/jobs/:id/reopen", "POST", f"/v1/jobs/{JOB_ID}/reopen", token=TK)
    # apply as TK2 then withdraw
    call("POST", f"/v1/jobs/{JOB_ID}/apply", {"cover_note": "interested"}, token=TK2)
    chk("POST /v1/jobs/:id/withdraw", "POST", f"/v1/jobs/{JOB_ID}/withdraw", token=TK2)
    chk("DELETE /v1/jobs/:id", "DELETE", f"/v1/jobs/{JOB_ID}", token=TK)

# ─────────────────────────────────────────────────────────────────────────────
sec("HUBS MEMBER MGMT")
_hd = chk("POST /v1/hubs (for e2e)", "POST", "/v1/hubs", token=TK,
          body={"name": f"E2E Hub {int(time.time())}", "description": "End-to-end test hub.",
                "category": "interest"})
HUB_ID = (_hd or {}).get("id")
if HUB_ID:
    call("POST", f"/v1/hubs/{HUB_ID}/join", token=TK2)
    chk("GET /v1/hubs/:id/members", "GET", f"/v1/hubs/{HUB_ID}/members", token=TK)
    chk("PUT /v1/hubs/:id/members/:m/role", "PUT",
        f"/v1/hubs/{HUB_ID}/members/{ID2}/role", token=TK, body={"role": "moderator"})
    chk("DELETE /v1/hubs/:id/members/:m", "DELETE",
        f"/v1/hubs/{HUB_ID}/members/{ID2}", token=TK)
    chk("DELETE /v1/hubs/:id", "DELETE", f"/v1/hubs/{HUB_ID}", token=TK)

# ─────────────────────────────────────────────────────────────────────────────
sec("MISC /v1")
chk("GET /v1/profile/journey", "GET", "/v1/profile/journey", token=TK)
chk("GET /v1/profile/@samuel-ocen", "GET", "/v1/profile/@samuel-ocen", token=TK2)
chk("GET /v1/profile/@samuel-ocen/posts", "GET", "/v1/profile/@samuel-ocen/posts", token=TK2)
chk("GET /v1/links/status/:id", "GET", f"/v1/links/status/{ID2}", token=TK)
chk("GET /v1/auth/accounts/:id/presence", "GET", f"/v1/auth/accounts/{ID2}/presence", token=TK)
chk("GET /v1/auth/ice", "GET", "/v1/auth/ice", token=TK)
_nd, _ = call("GET", "/v1/notifications?per_page=1", token=TK)
_nitems = ((_nd or {}).get("data") or {})
_nlist = _nitems.get("data") or _nitems.get("items") or []
_nid = _nlist[0]["id"] if _nlist else None
if _nid:
    chk("POST /v1/notifications/read", "POST", "/v1/notifications/read", token=TK, body={"ids": [_nid]})
else:
    chk("POST /v1/notifications/read (no notifs → mark-all fallback)", "POST",
        "/v1/notifications/read-all", token=TK)
chk("GET /v1/admin/events", "GET", "/v1/admin/events", token=TK)
chk("GET /v1/endorsements/@samuel-ocen", "GET", "/v1/endorsements/@samuel-ocen", token=TK2)
chk("GET /v1/mentorship/mentors/@samuel-ocen", "GET",
    "/v1/mentorship/mentors/@samuel-ocen", token=TK2, allow=(1, 0))  # 0 if not a mentor
chk("POST /v1/reference/institutions/suggest", "POST",
    "/v1/reference/institutions/suggest", token=TK,
    body={"name": "E2E Test Institute", "type": "university"})

# Threads clear (needs a thread) — create one with TK2
_td = chk("POST /v1/threads (for e2e)", "POST", "/v1/threads", token=TK,
          body={"participant_id": ID2, "mode": "professional"})
TH_ID = (_td or {}).get("id")
if TH_ID:
    chk("POST /v1/threads/:id/clear", "POST", f"/v1/threads/{TH_ID}/clear", token=TK)

# ─────────────────────────────────────────────────────────────────────────────
sec("AUTH / ADMIN / WALLET / UPLOAD GAPS")

# Admin login (samuel is admin)
chk("POST /v1/admin/login", "POST", "/v1/admin/login",
    body={"phone": "+256700000001", "password": "111111"})

# Interests add + delete (use TK2 so samuel's graph is untouched)
_tax, _ = call("GET", "/v1/interests/taxonomy", token=TK2)
_tags = []
_td2 = (_tax or {}).get("data")
if isinstance(_td2, list):
    _tags = _td2
elif isinstance(_td2, dict):
    for v in _td2.values():
        if isinstance(v, list):
            _tags = v; break
TAG_ID = None
for t in (_tags or []):
    if isinstance(t, dict) and t.get("id"):
        TAG_ID = t["id"]; break
if TAG_ID:
    chk("POST /v1/interests/me (add)", "POST", "/v1/interests/me", token=TK2,
        body={"interests": [{"tag_id": TAG_ID, "weight": 0.8}]})
    chk("DELETE /v1/interests/me/:tag", "DELETE", f"/v1/interests/me/{TAG_ID}", token=TK2)

# Avatar upload (multipart)
chk("POST /v1/profile/me/photo (avatar)", "POST", "/v1/profile/me/photo", token=TK,
    files={"photo": ("av.png", io.BytesIO(_png), "image/png")})

# Thread media upload (multipart) — reuse the e2e thread
if TH_ID:
    chk("POST /v1/threads/:id/media", "POST", f"/v1/threads/{TH_ID}/media", token=TK,
        files={"file": ("m.png", io.BytesIO(_png), "image/png")})

# Wallet topup → verify (POST variant, dev bypass)
_wt = chk("POST /v1/wallet/topup", "POST", "/v1/wallet/topup", token=TK,
          body={"amount": 5000})
TXREF = (_wt or {}).get("tx_ref") or (_wt or {}).get("reference")
if TXREF:
    chk("POST /v1/wallet/topup/:ref/verify", "POST", f"/v1/wallet/topup/{TXREF}/verify",
        token=TK, body={"dev_bypass": True}, allow=(1, 0))

# Logout + password reset on a throwaway account (never touch samuel's session)
_lp = f"+256788{(int(time.time()) + 13) % 1000000:06d}"
call("POST", "/v1/auth/register", {"phone": _lp, "display_name": "Logout Test"})
call("POST", "/v1/auth/otp/request", {"phone": _lp, "purpose": "register"})
_ld, _ = call("POST", "/v1/auth/otp/verify", {"phone": _lp, "code": DEV_OTP})
LP_TK = (_ld or {}).get("data", {}).get("access_token")
if LP_TK:
    chk("POST /v1/auth/password/reset/request", "POST", "/v1/auth/password/reset/request",
        body={"phone": _lp})
    chk("POST /v1/auth/password/reset", "POST", "/v1/auth/password/reset",
        body={"phone": _lp, "code": DEV_OTP, "new_password": "Linkup2026!"})
    chk("POST /v1/auth/logout", "POST", "/v1/auth/logout", token=LP_TK)
    call("DELETE", "/v1/profile/me", token=LP_TK)  # cleanup (best-effort)

# ─────────────────────────────────────────────────────────────────────────────
sec("PROFILING & PREFERENCE MATCHING (P-API)")

# Option catalog
_oc = chk("GET /v1/reference/dating-options", "GET", "/v1/reference/dating-options", token=TK)
if isinstance(_oc, dict):
    assert 'religion' in _oc and 'relationship_goal' in _oc, "catalog missing keys"
chk("GET /v1/reference/dating-options (no sensitive)", "GET",
    "/v1/reference/dating-options?include_sensitive=false", token=TK)

# Location cascade: regions → districts
_reg = call("GET", "/v1/reference/locations?level=region", token=TK)[0]
_regions = (_reg or {}).get("data") or []
chk("GET /v1/reference/locations?level=region", "GET",
    "/v1/reference/locations?level=region", token=TK)
if _regions:
    _rid = _regions[0]["id"]
    chk("GET /v1/reference/locations?parent_id= (districts)", "GET",
        f"/v1/reference/locations?parent_id={_rid}", token=TK)

# Deep attributes via the wizard step API
chk("PUT /v1/sparks/profile/step", "PUT", "/v1/sparks/profile/step", token=TK,
    body={"fields": {"smoking": "no", "religion": "catholic", "zodiac": "leo",
                     "industry": "technology", "relationship_goal": "long_term"}})

# Preferences GET/PUT
chk("GET /v1/sparks/preferences", "GET", "/v1/sparks/preferences", token=TK)
chk("PUT /v1/sparks/preferences", "PUT", "/v1/sparks/preferences", token=TK,
    body={"interested_in": ["woman"], "age": {"min": 25, "max": 36},
          "relationship_goal": ["long_term"], "religion": ["catholic"],
          "smoking": "no", "dealbreakers": ["age", "smoking"]})

# Bidirectional compatibility with another member (must have a dating profile)
_cmpt = chk("GET /v1/sparks/compatibility/:id", "GET",
            f"/v1/sparks/compatibility/{ID2}", token=TK, allow=(1, 0))  # 0 if ID2 has no dating profile
if isinstance(_cmpt, dict):
    assert 'mutual_pct' in _cmpt and 'i_match_them' in _cmpt, "compatibility shape"

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
total = len(R["pass"]) + len(R["fail"])
print(f"E2E COVERAGE — {len(R['pass'])}/{total} PASS | {len(R['fail'])} FAIL")
print("=" * 64)
if R["fail"]:
    print("\nFAILURES:")
    for n, why in R["fail"]:
        print(f"  ✗ {n}\n      {why}")
