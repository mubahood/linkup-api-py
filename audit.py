"""
LinkUp API Audit Script
Runs a comprehensive test of every endpoint, reports pass/fail, and prints a summary.
Usage: source venv/bin/activate && python audit.py
"""
import requests, json, sys

BASE = "http://localhost:5001"
results = {"pass": [], "fail": [], "warn": []}

# ── Core helpers ──────────────────────────────────────────────────────────
def call(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        url = f"{BASE}{path}"
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            r = requests.post(url, json=body, headers=headers, timeout=10)
        elif method == "PUT":
            r = requests.put(url, json=body, headers=headers, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=10)
        else:
            return None, f"unknown method {method}"
        return r.json(), None
    except Exception as e:
        return None, str(e)

def test(name, method, path, body=None, token=None, check=None):
    d, err = call(method, path, body, token)
    if err:
        results["fail"].append((name, f"Exception: {err}"))
        print(f"  ❌ {name} — {err}")
        return None
    code = d.get("code", 0)
    msg = d.get("message", "")
    data = d.get("data")
    if code != 1:
        results["fail"].append((name, f"code={code} | {msg[:100]}"))
        print(f"  ❌ {name}")
        print(f"     code={code} | {msg[:100]}")
        return None
    extra = ""
    if check and data is not None:
        try:
            extra = check(data) or ""
        except Exception as e:
            extra = f"[check error: {e}]"
            results["warn"].append((name, str(e)))
    results["pass"].append(name)
    print(f"  ✅ {name}{' | ' + extra if extra else ''}")
    return data

def sec(title):
    print(f"\n── {title} {'─'*(55-len(title))}")

# ── Step 0: Auth ───────────────────────────────────────────────────────────
sec("AUTH")

call("POST", "/v1/auth/otp/request", {"phone": "+256700000001", "purpose": "login"})
d, err = call("POST", "/v1/auth/otp/verify",
              {"phone": "+256700000001", "code": "123456", "purpose": "login"})

if not d or d.get("code") != 1:
    print(f"FATAL: Cannot authenticate — {err or d}")
    sys.exit(1)

TK = d["data"]["access_token"]
ACCT = d["data"]
print(f"  ✅ Auth token: {ACCT.get('display_name')} (@{ACCT.get('handle')}) kyc={ACCT.get('kyc_level')}")

test("GET /v1/auth/me", "GET", "/v1/auth/me", token=TK,
     check=lambda d: f"modes={d.get('modes_enabled')}")
test("POST /v1/auth/otp/request (for diff phone)", "POST", "/v1/auth/otp/request",
     body={"phone": "+256700000002", "purpose": "login"})

# Register a brand new account — clean up test account first to keep audit idempotent
TEST_PHONE = "+256799999998"
# If account already exists (prior audit run), log in and delete it so register can be re-tested
call("POST", "/v1/auth/otp/request", {"phone": TEST_PHONE, "purpose": "login"})
_pre, _ = call("POST", "/v1/auth/otp/verify",
               {"phone": TEST_PHONE, "code": "123456", "purpose": "login"})
if _pre and _pre.get("code") == 1:
    _del_tk = _pre["data"].get("access_token")
    call("DELETE", "/v1/profile/me", token=_del_tk)  # soft-delete the test account

test("POST /v1/auth/register (new)", "POST", "/v1/auth/register",
     body={"phone": TEST_PHONE, "display_name": "Test User Audit"})
call("POST", "/v1/auth/otp/request", {"phone": TEST_PHONE, "purpose": "register"})
test("POST /v1/auth/otp/verify (new account)", "POST", "/v1/auth/otp/verify",
     body={"phone": TEST_PHONE, "code": "123456", "purpose": "register"},
     check=lambda d: f"is_new={d.get('is_new_account')} token={'yes' if d.get('access_token') else 'no'}")

# ── Profile ────────────────────────────────────────────────────────────────
sec("PROFILE")

test("GET /v1/profile/me", "GET", "/v1/profile/me", token=TK,
     check=lambda d: (
         f"edu={len(d.get('education',[]))} "
         f"exp={len(d.get('experience',[]))} "
         f"comp={d.get('profile',{}).get('completion_score',0)}%"
     ))

test("PUT /v1/profile/me (update)", "PUT", "/v1/profile/me",
     body={"headline": "Senior Software Engineer @ Andela",
           "bio": "Building scalable systems for East Africa. Python, Go, Flutter. Open to mentorship.",
           "seniority": "senior"},
     token=TK)

test("GET /v1/profile/@samuel-ocen", "GET", "/v1/profile/@samuel-ocen", token=TK,
     check=lambda d: f"name={d.get('account',{}).get('display_name','?')}")

test("GET /v1/profile/@aisha-nakayima", "GET", "/v1/profile/@aisha-nakayima", token=TK,
     check=lambda d: f"headline={d.get('profile',{}).get('headline','none')[:40]}")

# Profile not found
d_nf, _ = call("GET", "/v1/profile/@nonexistent-handle", token=TK)
if d_nf and d_nf.get("code") == 0:
    print("  ✅ GET /v1/profile/@nonexistent → correct 404 response")
    results["pass"].append("Profile 404 check")
else:
    print("  ⚠  GET /v1/profile/@nonexistent → unexpected response")

test("GET /v1/profile/completion", "GET", "/v1/profile/completion", token=TK,
     check=lambda d: f"score={d.get('score',0)}% missing={d.get('missing_fields',[])[:2]}")

test("POST /v1/profile/me/education", "POST", "/v1/profile/me/education",
     body={"institution_name": "Makerere University",
           "degree": "MSc Computer Science", "field": "AI & Machine Learning",
           "start_year": 2020, "end_year": 2022},
     token=TK,
     check=lambda d: f"id={d.get('id','?')[:8]}")

test("POST /v1/profile/me/experience", "POST", "/v1/profile/me/experience",
     body={"org_name": "LinkUp Technologies", "title": "Lead Backend Engineer",
           "description": "Leading API development for Uganda's professional network.",
           "start_date": "2024-01-01", "is_current": True},
     token=TK,
     check=lambda d: f"id={d.get('id','?')[:8]}")

# Dating profile
test("GET /v1/profile/me/dating", "GET", "/v1/profile/me/dating", token=TK,
     check=lambda d: f"exists={bool(d)}")

test("PUT /v1/profile/me/dating", "PUT", "/v1/profile/me/dating",
     body={"display_name": "Sam", "bio": "Engineer who loves hiking and good conversations.",
           "age_min": 25, "age_max": 35, "intent": "serious_relationship",
           "lifestyle": {"fitness": "active", "family": "open"},
           "prompts": [{"question": "The most spontaneous thing I've done", "answer": "Hiked Mount Elgon without planning anything"}]},
     token=TK)

# ── Interests ──────────────────────────────────────────────────────────────
sec("INTERESTS")

tax_data = test("GET /v1/interests/taxonomy (public, no auth)", "GET", "/v1/interests/taxonomy",
     check=lambda d: f"dims={len(d)} total={sum(len(v) for v in d.values() if isinstance(v,list))}")

test("GET /v1/interests/search?q=software", "GET", "/v1/interests/search?q=software",
     token=TK, check=lambda d: f"found={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/interests/search?q=makerere", "GET", "/v1/interests/search?q=makerere",
     token=TK, check=lambda d: f"found={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/interests/me", "GET", "/v1/interests/me", token=TK,
     check=lambda d: f"interests={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/interests/suggestions", "GET", "/v1/interests/suggestions", token=TK,
     check=lambda d: f"suggestions={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# Get tag IDs from taxonomy for bulk set
if tax_data and isinstance(tax_data, dict):
    eng_tags = tax_data.get("professional_domain", [])
    geo_tags = tax_data.get("geography_mobility", [])
    hobby_tags = tax_data.get("hobbies_passions", [])
    slug_ids = {}
    for t in eng_tags + geo_tags + hobby_tags:
        slug_ids[t["slug"]] = t["id"]

    interests_payload = [
        {"tag_id": slug_ids.get("software-engineering"), "weight": 1.0},
        {"tag_id": slug_ids.get("data-science"), "weight": 0.8},
        {"tag_id": slug_ids.get("kampala-based"), "weight": 1.0},
        {"tag_id": slug_ids.get("football-soccer"), "weight": 0.6},
        {"tag_id": slug_ids.get("open-to-relocation"), "weight": 0.4},
    ]
    interests_payload = [i for i in interests_payload if i["tag_id"]]
    test("POST /v1/interests/me (bulk update)", "POST", "/v1/interests/me",
         body={"interests": interests_payload}, token=TK,
         check=lambda d: f"updated={d.get('updated',len(interests_payload))}")

# ── Links ──────────────────────────────────────────────────────────────────
sec("LINKS")

test("GET /v1/links (my connections)", "GET", "/v1/links", token=TK,
     check=lambda d: f"links={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/links/requests", "GET", "/v1/links/requests", token=TK,
     check=lambda d: f"sent={len(d.get('sent',[]) if isinstance(d,dict) else [])} received={len(d.get('received',[]) if isinstance(d,dict) else [])}")

test("GET /v1/links/suggestions", "GET", "/v1/links/suggestions", token=TK,
     check=lambda d: f"suggestions={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# Send a link request to Christine — cancel any pending one first to stay idempotent
d_christine, _ = call("GET", "/v1/profile/@christine-akello", token=TK)
if d_christine and d_christine.get("code") == 1:
    cid = d_christine["data"]["account"]["id"]
    # Withdraw any pending request before re-testing
    _req2, _ = call("GET", "/v1/links/requests", token=TK)
    if _req2 and _req2.get("code") == 1:
        for lnk in _req2["data"].get("sent", []):
            if lnk.get("addressee_id") == cid:
                call("DELETE", f"/v1/links/{lnk['id']}", token=TK)
                break
    test("POST /v1/links/request (Christine Akello)", "POST", "/v1/links/request",
         body={"target_id": cid, "note": "Hi Christine, I work in tech and interested in health systems."},
         token=TK)

# Try sending to someone already connected (should fail gracefully)
d_henry, _ = call("GET", "/v1/profile/@henry-kiwanuka", token=TK)
if d_henry and d_henry.get("code") == 1:
    hid = d_henry["data"]["account"]["id"]
    d_dup, _ = call("POST", "/v1/links/request", {"target_id": hid, "note": "dup"}, token=TK)
    if d_dup and d_dup.get("code") == 0:
        print("  ✅ POST /v1/links/request (already linked) → correctly rejected")
        results["pass"].append("Link dup rejection")
    else:
        print("  ⚠  Link dup request not rejected properly")

# ── Hubs ───────────────────────────────────────────────────────────────────
sec("HUBS")

hubs = test("GET /v1/hubs", "GET", "/v1/hubs", token=TK,
     check=lambda d: f"total={d.get('total',0)} hubs={len(d.get('data',[]))}")

if hubs and hubs.get("data"):
    h = hubs["data"][0]
    hid = h["id"]

    test(f"GET /v1/hubs/{h['name'][:20]}", "GET", f"/v1/hubs/{hid}", token=TK,
         check=lambda d: f"name={d.get('name','?')[:25]} members={d.get('member_count',0)}")

    test(f"GET /v1/hubs/{h['name'][:20]}/posts", "GET", f"/v1/hubs/{hid}/posts", token=TK,
         check=lambda d: f"posts={len(d.get('data',[]))}")

    test(f"GET /v1/hubs/{h['name'][:20]}/members", "GET", f"/v1/hubs/{hid}/members", token=TK,
         check=lambda d: f"members={len(d.get('data',[]))}")

    test(f"POST /v1/hubs post", "POST", f"/v1/hubs/{hid}/posts",
         body={"content": "Audit verification post — Phase 1 testing in progress. System is working!"},
         token=TK)

# Join a hub not already a member of
d_agtech, _ = call("GET", "/v1/hubs", token=TK)
if d_agtech and d_agtech.get("code") == 1:
    for h in d_agtech["data"].get("data", []):
        if not h.get("is_member"):
            test(f"POST /v1/hubs/{h['name'][:20]}/join", "POST", f"/v1/hubs/{h['id']}/join",
                 body={}, token=TK)
            break

# Create a new hub
test("POST /v1/hubs (create)", "POST", "/v1/hubs",
     body={"name": "Uganda Data Scientists", "slug": "ug-data-scientists",
           "description": "Community for data scientists and analysts in Uganda.",
           "type": "professional", "is_public": True},
     token=TK,
     check=lambda d: f"id={d.get('id','?')[:8]}")

# ── Jobs ───────────────────────────────────────────────────────────────────
sec("JOBS")

jobs = test("GET /v1/jobs", "GET", "/v1/jobs", token=TK,
     check=lambda d: f"total={d.get('total',0)} jobs={len(d.get('data',[]))}")

if jobs and jobs.get("data"):
    j = jobs["data"][0]
    jid = j["id"]

    test(f"GET /v1/jobs/{j['title'][:25]}", "GET", f"/v1/jobs/{jid}", token=TK,
         check=lambda d: f"title={d.get('title','?')[:30]} referral={d.get('referral_open')}")

    test("POST /v1/jobs/apply", "POST", f"/v1/jobs/{jid}/apply",
         body={"cover_note": "I have 5+ years of relevant experience and would be a great fit for this role."},
         token=TK,
         check=lambda d: f"status={d.get('status','?')}")

    test("POST /v1/jobs/save", "POST", f"/v1/jobs/{jid}/save", body={}, token=TK,
         check=lambda d: f"saved={d.get('saved',True)}")

# Create a test job
test("POST /v1/jobs (create)", "POST", "/v1/jobs",
     body={"title": "Senior Python Developer",
           "description": "We are looking for a Python developer to build backend systems for a Kampala-based fintech startup.",
           "employment_type": "full_time", "seniority": "senior",
           "location_text": "Kampala, Uganda", "referral_open": True,
           "salary_min": 3000000, "salary_max": 5000000, "currency": "UGX"},
     token=TK,
     check=lambda d: f"id={d.get('id','?')[:8]}")

test("GET /v1/jobs/mine", "GET", "/v1/jobs/mine", token=TK,
     check=lambda d: f"mine={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# ── Events ─────────────────────────────────────────────────────────────────
sec("EVENTS")

events = test("GET /v1/events", "GET", "/v1/events", token=TK,
     check=lambda d: f"total={d.get('total',0)} events={len(d.get('data',[]))}")

if events and events.get("data"):
    eid = events["data"][0]["id"]

    test("GET /v1/events/:id", "GET", f"/v1/events/{eid}", token=TK,
         check=lambda d: f"title={d.get('title','?')[:40]}")

    test("POST /v1/events/:id/rsvp going", "POST", f"/v1/events/{eid}/rsvp",
         body={"status": "going"}, token=TK)

    test("POST /v1/events/:id/rsvp maybe", "POST", f"/v1/events/{eid}/rsvp",
         body={"status": "maybe"}, token=TK)

    test("POST /v1/events/:id/rsvp not_going", "POST", f"/v1/events/{eid}/rsvp",
         body={"status": "not_going"}, token=TK)

# Create an event
test("POST /v1/events (create)", "POST", "/v1/events",
     body={"title": "Python Uganda Meetup #12",
           "description": "Monthly gathering of Python developers in Kampala.",
           "event_type": "networking",
           "start_at": "2026-07-15T18:00:00",
           "end_at": "2026-07-15T21:00:00",
           "location_text": "Endiro Coffee, Kampala",
           "is_online": False, "max_attendees": 60},
     token=TK,
     check=lambda d: f"id={d.get('id','?')[:8]}")

# ── Chat / Threads ─────────────────────────────────────────────────────────
sec("CHAT / THREADS")

threads = test("GET /v1/threads", "GET", "/v1/threads", token=TK,
     check=lambda d: f"total={d.get('total',0)} threads={len(d.get('data',[]))}")

if threads and threads.get("data"):
    tid = threads["data"][0]["id"]

    test("GET /v1/threads/:id", "GET", f"/v1/threads/{tid}", token=TK,
         check=lambda d: f"type={d.get('type','?')} mode={d.get('mode','?')}")

    msgs = test("GET /v1/threads/:id/messages", "GET", f"/v1/threads/{tid}/messages", token=TK,
         check=lambda d: f"messages={len(d.get('data',[]) if isinstance(d,dict) else d)}")

    test("POST /v1/threads/:id/messages (text)", "POST", f"/v1/threads/{tid}/messages",
         body={"body": "Hey! Testing the messaging API. Everything looking good on Phase 1 👍", "type": "text"},
         token=TK,
         check=lambda d: f"id={d.get('id','?')[:8]} status={d.get('status','?')}")

    test("POST /v1/threads/:id/read", "POST", f"/v1/threads/{tid}/read", body={}, token=TK)

# Create a new thread with another member
d_grace, _ = call("GET", "/v1/profile/@grace-atim", token=TK)
if d_grace and d_grace.get("code") == 1:
    gid = d_grace["data"]["account"]["id"]
    new_thread = test("POST /v1/threads (new direct)", "POST", "/v1/threads",
         body={"participant_id": gid},
         token=TK,
         check=lambda d: f"id={d.get('id','?')[:8]} type={d.get('type','?')}")

    if new_thread and new_thread.get("id"):
        test("POST first message in new thread", "POST", f"/v1/threads/{new_thread['id']}/messages",
             body={"body": "Hi Grace, great to connect! I'm building health systems too.", "type": "text"},
             token=TK)

# ── Sparks ─────────────────────────────────────────────────────────────────
sec("SPARKS (dating mode)")

# Sparks requires sparks mode enabled
d_me, _ = call("GET", "/v1/auth/me", token=TK)
sparks_enabled = False
if d_me and d_me.get("code") == 1:
    modes = d_me["data"].get("modes_enabled", {})
    sparks_enabled = modes.get("sparks", False)

print(f"  ℹ Sparks mode enabled: {sparks_enabled}")

test("GET /v1/sparks/deck", "GET", "/v1/sparks/deck", token=TK,
     check=lambda d: f"cards={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/sparks/matches", "GET", "/v1/sparks/matches", token=TK,
     check=lambda d: f"matches={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# ── Notifications ──────────────────────────────────────────────────────────
sec("NOTIFICATIONS")

notifs = test("GET /v1/notifications", "GET", "/v1/notifications", token=TK,
     check=lambda d: f"total={d.get('total',0)} unread={d.get('unread_count',0)}")

test("POST /v1/notifications/read-all", "POST", "/v1/notifications/read-all", body={}, token=TK)

# After reading all, check unread count = 0
d_notifs2, _ = call("GET", "/v1/notifications", token=TK)
if d_notifs2 and d_notifs2.get("code") == 1:
    unread = d_notifs2["data"].get("unread_count", 0) if isinstance(d_notifs2["data"], dict) else 0
    if unread == 0:
        print("  ✅ Notification read-all verification — unread=0")
        results["pass"].append("Notification read-all verification")

# ── Safety ─────────────────────────────────────────────────────────────────
sec("SAFETY")

test("GET /v1/safety/blocks", "GET", "/v1/safety/blocks", token=TK,
     check=lambda d: f"blocks={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# Block & unblock a test account
d_noah, _ = call("GET", "/v1/profile/@noah-tumusiime", token=TK)
if d_noah and d_noah.get("code") == 1:
    noah_id = d_noah["data"]["account"]["id"]

    d_block, _ = call("POST", "/v1/safety/block", {"blocked_id": noah_id}, token=TK)
    if d_block and d_block.get("code") == 1:
        print("  ✅ POST /v1/safety/block")
        results["pass"].append("POST /v1/safety/block")

        block_id = d_block["data"].get("id") if isinstance(d_block.get("data"), dict) else None
        if block_id:
            test("DELETE /v1/safety/block (unblock)", "DELETE", f"/v1/safety/block/{block_id}", token=TK)

# Report
d_peter, _ = call("GET", "/v1/profile/@peter-odeke", token=TK)
if d_peter and d_peter.get("code") == 1:
    peter_id = d_peter["data"]["account"]["id"]
    test("POST /v1/safety/report", "POST", "/v1/safety/report",
         body={"target_account_id": peter_id, "reason": "spam",
               "detail": "Test report for audit validation purposes."},
         token=TK,
         check=lambda d: f"id={d.get('id','?')[:8]}")

# ── Search ─────────────────────────────────────────────────────────────────
sec("SEARCH")

test("GET /v1/search/people?q=samuel", "GET", "/v1/search/people?q=samuel", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/search/people?q=aisha", "GET", "/v1/search/people?q=aisha", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/search/hubs?q=makerere", "GET", "/v1/search/hubs?q=makerere", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/search/hubs?q=developer", "GET", "/v1/search/hubs?q=developer", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/search/jobs?q=developer", "GET", "/v1/search/jobs?q=developer", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/search/jobs?q=data", "GET", "/v1/search/jobs?q=data", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# Empty search (should return results or empty gracefully)
test("GET /v1/search/people?q=zzznoresults", "GET", "/v1/search/people?q=zzznoresults", token=TK,
     check=lambda d: f"results={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# ── Reference (public) ─────────────────────────────────────────────────────
sec("REFERENCE (public — no auth)")

test("GET /v1/reference/locations", "GET", "/v1/reference/locations",
     check=lambda d: f"locs={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/reference/locations?country=UG", "GET", "/v1/reference/locations?country=UG",
     check=lambda d: f"locs={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/reference/institutions", "GET", "/v1/reference/institutions",
     check=lambda d: f"insts={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/reference/institutions?q=makerere", "GET", "/v1/reference/institutions?q=makerere",
     check=lambda d: f"insts={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/reference/orgs", "GET", "/v1/reference/orgs",
     check=lambda d: f"orgs={len(d.get('data',[]) if isinstance(d,dict) else d)}")

test("GET /v1/reference/orgs?q=mtn", "GET", "/v1/reference/orgs?q=mtn",
     check=lambda d: f"orgs={len(d.get('data',[]) if isinstance(d,dict) else d)}")

# ── Auth extras ────────────────────────────────────────────────────────────
sec("AUTH EXTRAS")

# Token refresh
call("POST", "/v1/auth/otp/request", {"phone": "+256700000001", "purpose": "login"})
d_rt, _ = call("POST", "/v1/auth/otp/verify",
               {"phone": "+256700000001", "code": "123456", "purpose": "login"})
REFRESH_TK = d_rt["data"]["refresh_token"] if d_rt else None
if REFRESH_TK:
    test("POST /v1/auth/refresh", "POST", "/v1/auth/refresh",
         body={"refresh_token": REFRESH_TK},
         check=lambda d: f"token={'yes' if d.get('access_token') else 'no'}")
else:
    print("  ⚠  Skipping refresh test — no refresh token available")

# Device registration (push notifications)
test("POST /v1/auth/device (register)", "POST", "/v1/auth/device",
     body={"onesignal_player_id": "audit-test-player-001", "platform": "android"},
     token=TK,
     check=lambda d: f"platform={d.get('platform')} pid={d.get('onesignal_player_id','')[:20]}")

# Error cases: register existing player_id again (should update, not fail)
test("POST /v1/auth/device (update existing)", "POST", "/v1/auth/device",
     body={"onesignal_player_id": "audit-test-player-001", "platform": "ios"},
     token=TK,
     check=lambda d: f"platform={d.get('platform')}")

# Missing player_id
d_bad, _ = call("POST", "/v1/auth/device", {"platform": "android"}, token=TK)
if d_bad and d_bad.get("code") == 0:
    print("  ✅ POST /v1/auth/device (missing player_id) → correctly rejected")
    results["pass"].append("Device reg missing player_id rejected")
else:
    print("  ❌ POST /v1/auth/device (missing player_id) → should have failed")
    results["fail"].append(("Device reg missing player_id rejected", "Expected code=0"))

# ── Profile CRUD extras ────────────────────────────────────────────────────
sec("PROFILE CRUD EXTRAS")

# Get current profile for IDs
d_prof_full = test("GET /v1/profile/me (full)", "GET", "/v1/profile/me", token=TK,
     check=lambda d: f"edu={len(d.get('education',[]))} exp={len(d.get('experience',[]))}")

# Education update
if d_prof_full and d_prof_full.get('education'):
    edu_id = d_prof_full['education'][0]['id']
    test("PUT /v1/profile/me/education/:id", "PUT", f"/v1/profile/me/education/{edu_id}",
         body={"degree": "BSc Computer Science (Hons)", "end_year": 2015},
         token=TK,
         check=lambda d: f"degree={d.get('degree','')[:30]}")

# Add + delete education
new_edu = test("POST /v1/profile/me/education (for delete)", "POST", "/v1/profile/me/education",
     body={"institution_name": "Kyambogo University", "degree": "Diploma IT",
           "field": "Information Technology", "start_year": 2018, "end_year": 2020},
     token=TK,
     check=lambda d: f"id={d.get('id','')[:8]}")
if new_edu:
    test("DELETE /v1/profile/me/education/:id", "DELETE", f"/v1/profile/me/education/{new_edu['id']}",
         token=TK)

# Experience update
if d_prof_full and d_prof_full.get('experience'):
    exp_id = d_prof_full['experience'][0]['id']
    test("PUT /v1/profile/me/experience/:id", "PUT", f"/v1/profile/me/experience/{exp_id}",
         body={"description": "Led backend API development across three products.",
               "is_current": True},
         token=TK,
         check=lambda d: f"is_current={d.get('is_current')}")

# Add + delete experience
new_exp = test("POST /v1/profile/me/experience (for delete)", "POST", "/v1/profile/me/experience",
     body={"title": "Freelance Consultant", "org_name": "Self", "start_date": "2023-01-01",
           "is_current": False, "description": "Independent consulting work."},
     token=TK,
     check=lambda d: f"id={d.get('id','')[:8]}")
if new_exp:
    test("DELETE /v1/profile/me/experience/:id", "DELETE", f"/v1/profile/me/experience/{new_exp['id']}",
         token=TK)

# Certification add + delete
new_cert = test("POST /v1/profile/me/certifications", "POST", "/v1/profile/me/certifications",
     body={"name": "AWS Solutions Architect Associate",
           "issuer": "Amazon Web Services",
           "issued_at": "2025-03-01",
           "credential_url": "https://www.credly.com/badges/test"},
     token=TK,
     check=lambda d: f"id={d.get('id','')[:8]} issuer={d.get('issuer','')[:20]}")
if new_cert:
    test("DELETE /v1/profile/me/certifications/:id", "DELETE",
         f"/v1/profile/me/certifications/{new_cert['id']}",
         token=TK)

# Completion with missing_fields
test("GET /v1/profile/completion (missing_fields)", "GET", "/v1/profile/completion", token=TK,
     check=lambda d: f"score={d.get('score')}% missing={d.get('missing_fields',[])} label={d.get('label')}")

# ── Sparks full flow ────────────────────────────────────────────────────────
sec("SPARKS FULL FLOW")

# Deck should have cards
sparks_deck = test("GET /v1/sparks/deck", "GET", "/v1/sparks/deck", token=TK,
     check=lambda d: f"cards={len(d) if isinstance(d, list) else d.get('total',0)}")

# Get Henry's ID for mutual match test (Henry → Samuel already seeded)
d_henry_prof, _ = call("GET", "/v1/profile/@henry-kiwanuka", token=TK)
henry_spark_id = None
if d_henry_prof and d_henry_prof.get("code") == 1:
    henry_spark_id = d_henry_prof["data"]["account"]["id"]

# Spark up on Henry — should produce a match (Henry already sparked Samuel in seed)
if henry_spark_id:
    # Cancel prior spark on Henry if test was run before
    _prior_spark, _ = call("POST", "/v1/sparks/action",
                            {"target_id": henry_spark_id, "action": "undo"}, token=TK)
    d_spark = test("POST /v1/sparks/action (spark_up → match)", "POST", "/v1/sparks/action",
         body={"target_id": henry_spark_id, "action": "spark_up"},
         token=TK,
         check=lambda d: f"is_match={d.get('is_match')} spark={d.get('spark',{}).get('action','?')}")
    if d_spark and d_spark.get("is_match") and d_spark.get("match"):
        match_id = d_spark["match"]["id"]
        test("GET /v1/sparks/matches/:id (new match)", "GET", f"/v1/sparks/matches/{match_id}",
             token=TK,
             check=lambda d: f"thread={str(d.get('thread_id',''))[:8]} other={d.get('other_account',{}).get('display_name','?')[:20]}")
    elif d_spark:
        print("  ⚠  spark_up on Henry did not produce match — Henry may not have sparked back")

# Pass on someone from deck
if sparks_deck and isinstance(sparks_deck, list) and len(sparks_deck) > 0:
    # Find someone not Henry
    pass_target = next((c for c in sparks_deck if c['id'] != (henry_spark_id or '')), sparks_deck[0])
    test("POST /v1/sparks/action (pass)", "POST", "/v1/sparks/action",
         body={"target_id": pass_target["id"], "action": "pass"},
         token=TK,
         check=lambda d: f"is_match={d.get('is_match')}")

# Match list (should now have at least the Aisha match from seed)
matches_data = test("GET /v1/sparks/matches", "GET", "/v1/sparks/matches", token=TK,
     check=lambda d: f"total={d.get('total',0)} matches={len(d.get('data',[]))}")

# Match detail
if matches_data and matches_data.get("data"):
    mid = matches_data["data"][0]["id"]
    test("GET /v1/sparks/matches/:id (detail)", "GET", f"/v1/sparks/matches/{mid}",
         token=TK,
         check=lambda d: f"other={d.get('other_account',{}).get('display_name','?')[:25]} thread={str(d.get('thread_id','none'))[:8]}")

# Spark mode off guard — attempt as an account without sparks
call("POST", "/v1/auth/otp/request", {"phone": "+256700000003", "purpose": "login"})
d_nosparks, _ = call("POST", "/v1/auth/otp/verify",
                     {"phone": "+256700000003", "code": "123456", "purpose": "login"})
# Temporarily disable sparks for this check by using a phone that might not have it
# (All seed accounts have sparks=True, so just check the response format)
if d_nosparks and d_nosparks.get("code") == 1:
    NS_TK = d_nosparks["data"]["access_token"]
    # Sparks should work for all seed accounts (all have sparks=True)
    d_ns_deck, _ = call("GET", "/v1/sparks/deck", token=NS_TK)
    if d_ns_deck and d_ns_deck.get("code") == 1:
        print(f"  ✅ GET /v1/sparks/deck (Brian) | cards={len(d_ns_deck['data']) if isinstance(d_ns_deck['data'], list) else '?'}")
        results["pass"].append("Sparks deck for Brian")

# ── Links CRUD extras ─────────────────────────────────────────────────────
sec("LINKS CRUD EXTRAS")

# Get someone to send/receive requests from
d_oliver, _ = call("GET", "/v1/profile/@olivia-nansubuga", token=TK)
d_robert, _ = call("GET", "/v1/profile/@robert-musinguzi", token=TK)

# Accept an incoming request (first create one from another account)
if d_robert and d_robert.get("code") == 1:
    robert_id = d_robert["data"]["account"]["id"]
    # Robert sends a link request to Samuel
    call("POST", "/v1/auth/otp/request", {"phone": "+256700000019", "purpose": "login"})
    d_rob_auth, _ = call("POST", "/v1/auth/otp/verify",
                          {"phone": "+256700000019", "code": "123456", "purpose": "login"})
    if d_rob_auth and d_rob_auth.get("code") == 1:
        rob_tk = d_rob_auth["data"]["access_token"]
        samuel_acct_id = ACCT["id"]
        # Cancel existing link if any
        _req_r, _ = call("GET", "/v1/links/requests", token=rob_tk)
        if _req_r and _req_r.get("code") == 1:
            for lnk in _req_r["data"].get("sent", []):
                if lnk.get("addressee_id") == samuel_acct_id:
                    call("DELETE", f"/v1/links/{lnk['id']}", token=rob_tk)
        # Also clean up accepted link if any
        _rob_links, _ = call("GET", "/v1/links", token=rob_tk)
        if _rob_links and _rob_links.get("code") == 1:
            for lnk in _rob_links["data"].get("data", []):
                other_id = lnk.get("requester_id") if lnk.get("addressee_id") == robert_id else lnk.get("addressee_id")
                if other_id == samuel_acct_id:
                    call("DELETE", f"/v1/links/{lnk['id']}", token=rob_tk)

        call("POST", "/v1/links/request", {"target_id": samuel_acct_id}, token=rob_tk)
        # Samuel accepts
        _reqs, _ = call("GET", "/v1/links/requests", token=TK)
        if _reqs and _reqs.get("code") == 1:
            for lnk in _reqs["data"].get("received", []):
                if lnk.get("requester_id") == robert_id:
                    test("POST /v1/links/:id/accept", "POST", f"/v1/links/{lnk['id']}/accept",
                         token=TK,
                         check=lambda d: f"status={d.get('status','?')}")
                    break

# Decline: James sends to Samuel, Samuel declines
d_james, _ = call("GET", "/v1/profile/@james-oryem", token=TK)
if d_james and d_james.get("code") == 1:
    james_id = d_james["data"]["account"]["id"]
    call("POST", "/v1/auth/otp/request", {"phone": "+256700000011", "purpose": "login"})
    d_james_auth, _ = call("POST", "/v1/auth/otp/verify",
                            {"phone": "+256700000011", "code": "123456", "purpose": "login"})
    if d_james_auth and d_james_auth.get("code") == 1:
        james_tk = d_james_auth["data"]["access_token"]
        samuel_id2 = ACCT["id"]
        # Clean up existing
        _req_j, _ = call("GET", "/v1/links/requests", token=james_tk)
        if _req_j and _req_j.get("code") == 1:
            for lnk in _req_j["data"].get("sent", []):
                if lnk.get("addressee_id") == samuel_id2:
                    call("DELETE", f"/v1/links/{lnk['id']}", token=james_tk)
        call("POST", "/v1/links/request", {"target_id": samuel_id2}, token=james_tk)
        _reqs2, _ = call("GET", "/v1/links/requests", token=TK)
        if _reqs2 and _reqs2.get("code") == 1:
            for lnk in _reqs2["data"].get("received", []):
                if lnk.get("requester_id") == james_id:
                    test("POST /v1/links/:id/decline", "POST", f"/v1/links/{lnk['id']}/decline",
                         token=TK,
                         check=lambda d: f"status not returned on decline (expected empty)")
                    break

# Remove a link (add one temporarily)
if d_oliver and d_oliver.get("code") == 1:
    oliver_id = d_oliver["data"]["account"]["id"]
    call("POST", "/v1/auth/otp/request", {"phone": "+256700000016", "purpose": "login"})
    d_ol_auth, _ = call("POST", "/v1/auth/otp/verify",
                         {"phone": "+256700000016", "code": "123456", "purpose": "login"})
    if d_ol_auth and d_ol_auth.get("code") == 1:
        ol_tk = d_ol_auth["data"]["access_token"]
        samuel_id3 = ACCT["id"]
        # Clean up existing
        _req_ol, _ = call("GET", "/v1/links/requests", token=ol_tk)
        if _req_ol and _req_ol.get("code") == 1:
            for lnk in _req_ol["data"].get("sent", []):
                if lnk.get("addressee_id") == samuel_id3:
                    call("DELETE", f"/v1/links/{lnk['id']}", token=ol_tk)
        lr = call("POST", "/v1/links/request", {"target_id": samuel_id3}, token=ol_tk)
        _reqs3, _ = call("GET", "/v1/links/requests", token=TK)
        if _reqs3 and _reqs3.get("code") == 1:
            for lnk in _reqs3["data"].get("received", []):
                if lnk.get("requester_id") == oliver_id:
                    # Accept first, then remove
                    call("POST", f"/v1/links/{lnk['id']}/accept", token=TK)
                    test("DELETE /v1/links/:id (remove connection)", "DELETE", f"/v1/links/{lnk['id']}",
                         token=TK)
                    break

# ── Hubs extras ────────────────────────────────────────────────────────────
sec("HUBS EXTRAS")

# Get a hub where Samuel is admin
all_hubs = test("GET /v1/hubs (all)", "GET", "/v1/hubs", token=TK,
     check=lambda d: f"total={d.get('total',0)}")
admin_hub = None
if all_hubs and all_hubs.get("data"):
    for h_item in all_hubs["data"]:
        if h_item.get("my_role") == "admin":
            admin_hub = h_item
            break

if admin_hub:
    test("PUT /v1/hubs/:id (update description)", "PUT", f"/v1/hubs/{admin_hub['id']}",
         body={"description": "Updated description via audit test — community for tech builders across Uganda."},
         token=TK,
         check=lambda d: f"name={d.get('name','')[:30]} desc_len={len(d.get('description') or '')}")

    # Delete a hub post
    posts = test("GET /v1/hubs/:id/posts (pre-delete)", "GET", f"/v1/hubs/{admin_hub['id']}/posts", token=TK,
         check=lambda d: f"count={len(d.get('data',[]))}")
    if posts and posts.get("data"):
        # Create one to delete
        new_post = test("POST /v1/hubs/:id/posts (for delete)", "POST", f"/v1/hubs/{admin_hub['id']}/posts",
             body={"content": "Temporary post for delete test — audit verification only."},
             token=TK,
             check=lambda d: f"id={d.get('id','')[:8]}")
        if new_post:
            test("DELETE /v1/hubs/:id/posts/:id", "DELETE",
                 f"/v1/hubs/{admin_hub['id']}/posts/{new_post['id']}",
                 token=TK)

# Join a hub then leave it — use a different account to create the hub so Samuel starts as non-member
call("POST", "/v1/auth/otp/request", {"phone": "+256700000003", "purpose": "login"})
_d_br, _ = call("POST", "/v1/auth/otp/verify",
                {"phone": "+256700000003", "code": "123456", "purpose": "login"})
if _d_br and _d_br.get("code") == 1:
    _br_tk = _d_br["data"]["access_token"]
    _jl_hub, _ = call("POST", "/v1/hubs",
                       {"name": "Join-Leave Test Hub", "type": "professional", "is_public": True},
                       token=_br_tk)
    if _jl_hub and _jl_hub.get("code") == 1:
        _jl_id = _jl_hub["data"]["id"]
        test("POST /v1/hubs/:id/join (Samuel joins)", "POST", f"/v1/hubs/{_jl_id}/join",
             body={}, token=TK)
        test("POST /v1/hubs/:id/leave (Samuel leaves)", "POST", f"/v1/hubs/{_jl_id}/leave",
             body={}, token=TK)
        # Try joining after leaving — should work again
        test("POST /v1/hubs/:id/join (re-join after leave)", "POST", f"/v1/hubs/{_jl_id}/join",
             body={}, token=TK)
        # Try double-join — should fail gracefully
        _d_dj, _ = call("POST", f"/v1/hubs/{_jl_id}/join", {}, token=TK)
        if _d_dj and _d_dj.get("code") == 0:
            print("  ✅ POST /v1/hubs/:id/join (double-join) → correctly rejected")
            results["pass"].append("Hub double-join rejected")
        else:
            print("  ❌ Hub double-join should have been rejected")
            results["fail"].append(("Hub double-join rejected", "Expected code=0"))

# ── Interest Graph scoring ─────────────────────────────────────────────────
sec("INTEREST GRAPH SCORING")

# Compatibility with self (should be 1.0)
test("GET /v1/profile/compatibility/self", "GET", f"/v1/profile/compatibility/{ACCT['id']}",
     token=TK,
     check=lambda d: f"score={d.get('total_score')} dims={len(d.get('dimensions',[]))}")

# Compatibility with another member
d_henry_c, _ = call("GET", "/v1/profile/@henry-kiwanuka", token=TK)
if d_henry_c and d_henry_c.get("code") == 1:
    henry_id = d_henry_c["data"]["account"]["id"]
    test("GET /v1/profile/compatibility/:henry (professional)", "GET",
         f"/v1/profile/compatibility/{henry_id}?mode=professional",
         token=TK,
         check=lambda d: f"score={d.get('total_score')} top_dim={d.get('dimensions',[{}])[0].get('dimension','?')}")
    test("GET /v1/profile/compatibility/:henry (dating)", "GET",
         f"/v1/profile/compatibility/{henry_id}?mode=dating",
         token=TK,
         check=lambda d: f"score={d.get('total_score')}")

# Deck should show compatibility_score on each card
deck_scored = test("GET /v1/sparks/deck (scored)", "GET", "/v1/sparks/deck", token=TK,
     check=lambda d: f"cards={len(d) if isinstance(d,list) else 0} has_score={'compatibility_score' in (d[0] if isinstance(d,list) and d else {})}")

# Links suggestions should also have compatibility_score (data is a plain list here)
sugg_scored = test("GET /v1/links/suggestions (scored)", "GET", "/v1/links/suggestions", token=TK,
     check=lambda d: f"suggestions={len(d) if isinstance(d,list) else len(d.get('data',[]))} has_score={'compatibility_score' in (d[0] if isinstance(d,list) and d else d.get('data',[{}])[0] if isinstance(d,dict) else {})}")

# 404 for unknown account
_bad_compat, _ = call("GET", "/v1/profile/compatibility/nonexistent-uuid", token=TK)
if _bad_compat and _bad_compat.get("code") == 0:
    print("  ✅ GET /v1/profile/compatibility/:bad → correct 404")
    results["pass"].append("Compatibility 404 for unknown account")
else:
    print("  ❌ Compatibility should 404 for unknown account")
    results["fail"].append(("Compatibility 404 for unknown account", "Expected code=0"))

# ── Account settings ───────────────────────────────────────────────────────
sec("ACCOUNT SETTINGS")

# Update display_name
test("PUT /v1/auth/me (update name)", "PUT", "/v1/auth/me",
     body={"display_name": "Samuel Ocen (Audit Test)"},
     token=TK,
     check=lambda d: f"name={d.get('display_name','')[:30]}")

# Restore name
test("PUT /v1/auth/me (restore name)", "PUT", "/v1/auth/me",
     body={"display_name": "Samuel Ocen"},
     token=TK,
     check=lambda d: f"name={d.get('display_name','')}")

# Update modes — enable both
test("PUT /v1/auth/me (modes both on)", "PUT", "/v1/auth/me",
     body={"modes_enabled": {"professional": True, "sparks": True}},
     token=TK,
     check=lambda d: f"modes={d.get('modes_enabled')}")

# Try to disable all modes — should fail
_no_modes, _ = call("PUT", "/v1/auth/me", {"modes_enabled": {"professional": False, "sparks": False}}, token=TK)
if _no_modes and _no_modes.get("code") == 0:
    print("  ✅ PUT /v1/auth/me (disable all modes) → correctly rejected")
    results["pass"].append("Disable all modes rejected")
else:
    print("  ❌ Should reject disabling all modes")
    results["fail"].append(("Disable all modes rejected", "Expected code=0"))

# Password change
test("POST /v1/auth/password (set new)", "POST", "/v1/auth/password",
     body={"current_password": "linkup2026", "new_password": "Linkup2026!"},
     token=TK,
     check=lambda d: f"{'ok' if d is None else d}")

# Restore password
test("POST /v1/auth/password (restore)", "POST", "/v1/auth/password",
     body={"current_password": "Linkup2026!", "new_password": "linkup2026"},
     token=TK)

# Wrong current password
_wrong_pw, _ = call("POST", "/v1/auth/password",
                    {"current_password": "wrongpassword", "new_password": "newpass123"}, token=TK)
if _wrong_pw and _wrong_pw.get("code") == 0:
    print("  ✅ POST /v1/auth/password (wrong current) → correctly rejected")
    results["pass"].append("Wrong current password rejected")
else:
    print("  ❌ Wrong current password should be rejected")
    results["fail"].append(("Wrong current password rejected", "Expected code=0"))

# Too-short new password
_short_pw, _ = call("POST", "/v1/auth/password",
                    {"current_password": "linkup2026", "new_password": "short"}, token=TK)
if _short_pw and _short_pw.get("code") == 0:
    print("  ✅ POST /v1/auth/password (too short) → correctly rejected")
    results["pass"].append("Too-short password rejected")
else:
    print("  ❌ Too-short password should be rejected")
    results["fail"].append(("Too-short password rejected", "Expected code=0"))

# ── Events extras ──────────────────────────────────────────────────────────
sec("EVENTS EXTRAS")

# Create an event to test update + attendees + cancel
ev_new = test("POST /v1/events (for extras)", "POST", "/v1/events",
     body={"title": "Python UG Meetup Audit Test",
           "description": "Monthly Python developers meetup in Kampala.",
           "event_type": "networking", "start_at": "2026-09-15T18:00:00",
           "end_at": "2026-09-15T21:00:00", "location_text": "Endiro Coffee, Kololo",
           "is_online": False, "max_attendees": 50},
     token=TK,
     check=lambda d: f"id={d.get('id','')[:8]} title={d.get('title','')[:30]}")

if ev_new:
    ev_id = ev_new["id"]

    # Update it
    test("PUT /v1/events/:id", "PUT", f"/v1/events/{ev_id}",
         body={"description": "Updated: Monthly gathering of Kampala Python devs. Networking + talks.",
               "max_attendees": 75},
         token=TK,
         check=lambda d: f"max={d.get('max_attendees')} desc_len={len(d.get('description') or '')}")

    # RSVP to it (so attendees list is non-empty)
    requests.post(f"{BASE}/v1/events/{ev_id}/rsvp",
                  json={"status": "going"},
                  headers={"Authorization": f"Bearer {TK}", "Content-Type": "application/json"})

    # Attendees list
    test("GET /v1/events/:id/attendees", "GET", f"/v1/events/{ev_id}/attendees",
         token=TK,
         check=lambda d: f"total={d.get('total',0)} has_account={'account' in (d.get('data',[{}])[0] if d.get('data') else {})}")

    # Attendees with status filter
    test("GET /v1/events/:id/attendees?status=going", "GET", f"/v1/events/{ev_id}/attendees?status=going",
         token=TK,
         check=lambda d: f"going={d.get('total',0)}")

    # Cancel it (host only)
    test("DELETE /v1/events/:id (cancel)", "DELETE", f"/v1/events/{ev_id}",
         token=TK)

    # Verify it's gone
    _gone, _ = call("GET", f"/v1/events/{ev_id}", token=TK)
    if _gone and _gone.get("code") == 0:
        print("  ✅ GET /v1/events/:id (after cancel) → correctly 404")
        results["pass"].append("Event 404 after cancel")
    else:
        print("  ❌ Event should 404 after cancel")
        results["fail"].append(("Event 404 after cancel", "Expected code=0"))

# Non-host cannot cancel another's event — use another account to create it
call("POST", "/v1/auth/otp/request", {"phone": "+256700000004", "purpose": "login"})
_d_chr, _ = call("POST", "/v1/auth/otp/verify",
                  {"phone": "+256700000004", "code": "123456", "purpose": "login"})
if _d_chr and _d_chr.get("code") == 1:
    _chr_tk = _d_chr["data"]["access_token"]
    _other_ev, _ = call("POST", "/v1/events",
                         {"title": "Christine's Audit Event", "start_at": "2026-10-01T14:00:00"},
                         token=_chr_tk)
    if _other_ev and _other_ev.get("code") == 1:
        _oid = _other_ev["data"]["id"]
        _del_other, _ = call("DELETE", f"/v1/events/{_oid}", token=TK)  # Samuel tries to delete
        if _del_other and _del_other.get("code") == 0:
            print("  ✅ DELETE /v1/events/:id (non-host) → correctly rejected")
            results["pass"].append("Event delete non-host rejected")
        else:
            print("  ❌ Non-host event delete should be rejected")
            results["fail"].append(("Event delete non-host rejected", "Expected code=0"))
        # Clean up: Christine deletes her own event
        call("DELETE", f"/v1/events/{_oid}", token=_chr_tk)

# ── Jobs extras ────────────────────────────────────────────────────────────
sec("JOBS EXTRAS")

# Create a test job to update + close + view applicants
job_new = test("POST /v1/jobs (for extras)", "POST", "/v1/jobs",
     body={"title": "Lead Machine Learning Engineer",
           "description": "Build the Interest Graph matching engine for LinkUp's recommendation system.",
           "employment_type": "full_time", "seniority": "senior",
           "location_text": "Kampala, Uganda (Remote-friendly)",
           "salary_min": 5000000, "salary_max": 8000000, "currency": "UGX",
           "referral_open": True},
     token=TK,
     check=lambda d: f"id={d.get('id','')[:8]} open={d.get('is_open')}")

if job_new:
    jid = job_new["id"]

    # Update it
    test("PUT /v1/jobs/:id", "PUT", f"/v1/jobs/{jid}",
         body={"description": "Updated: Build ML systems for Uganda's professional network.",
               "salary_min": 5500000, "salary_max": 9000000},
         token=TK,
         check=lambda d: f"salary_min={d.get('salary_min')} open={d.get('is_open')}")

    # Apply from another account (henry)
    call("POST", "/v1/auth/otp/request", {"phone": "+256700000009", "purpose": "login"})
    _d_hen, _ = call("POST", "/v1/auth/otp/verify",
                     {"phone": "+256700000009", "code": "123456", "purpose": "login"})
    if _d_hen and _d_hen.get("code") == 1:
        hen_tk = _d_hen["data"]["access_token"]
        call("POST", f"/v1/jobs/{jid}/apply",
             {"cover_note": "I have deep ML experience and would love to build the Interest Graph for LinkUp."},
             token=hen_tk)

    # View applicants (poster)
    test("GET /v1/jobs/:id/applicants", "GET", f"/v1/jobs/{jid}/applicants",
         token=TK,
         check=lambda d: f"total={d.get('total',0)} has_applicant={'applicant' in (d.get('data',[{}])[0] if d.get('data') else {})}")

    # Non-poster cannot view applicants
    call("POST", "/v1/auth/otp/request", {"phone": "+256700000002", "purpose": "login"})
    _d_ai, _ = call("POST", "/v1/auth/otp/verify",
                    {"phone": "+256700000002", "code": "123456", "purpose": "login"})
    if _d_ai and _d_ai.get("code") == 1:
        ai_tk = _d_ai["data"]["access_token"]
        _no_appl, _ = call("GET", f"/v1/jobs/{jid}/applicants", token=ai_tk)
        if _no_appl and _no_appl.get("code") == 0:
            print("  ✅ GET /v1/jobs/:id/applicants (non-poster) → correctly rejected")
            results["pass"].append("Job applicants non-poster rejected")

    # Close the job
    test("POST /v1/jobs/:id/close", "POST", f"/v1/jobs/{jid}/close",
         token=TK,
         check=lambda d: f"open={d.get('is_open')}")

    # Verify closed job is not in open feed
    feed_check, _ = call("GET", f"/v1/jobs/{jid}", token=TK)
    if feed_check and feed_check.get("code") == 1:
        is_open = feed_check["data"].get("is_open", True)
        if not is_open:
            print("  ✅ Job correctly marked closed after close endpoint")
            results["pass"].append("Job marked closed after close")
        else:
            print("  ❌ Job should be closed after close endpoint")
            results["fail"].append(("Job marked closed after close", "is_open should be False"))

# ── Legacy /api/ routes ────────────────────────────────────────────────────
sec("LEGACY /api/ (backward compat)")

# Get old-style token
call("POST", "/v1/auth/otp/request", {"phone": "+256700000001", "purpose": "login"})
d_old, _ = call("POST", "/v1/auth/otp/verify",
                {"phone": "+256700000001", "code": "123456", "purpose": "login"})
OLD_TK = d_old["data"]["access_token"] if d_old else TK

test("GET /api/admin/system/health", "GET", "/api/admin/system/health", token=OLD_TK)
test("GET /api/admin/dashboard", "GET", "/api/admin/dashboard", token=OLD_TK)

# ── Jobs list endpoints ────────────────────────────────────────────────────
sec("JOBS LIST ENDPOINTS")

# Save a job first (toggle to ensure saved)
_jobs_feed, _ = call("GET", "/v1/jobs", token=TK)
_feed_job = None
if _jobs_feed and _jobs_feed.get("code") == 1:
    for j in _jobs_feed["data"].get("data", []):
        if not j.get("is_saved"):
            call("POST", f"/v1/jobs/{j['id']}/save", token=TK)
            _feed_job = j
            break

test("GET /v1/jobs/saved", "GET", "/v1/jobs/saved", token=TK,
     check=lambda d: f"saved={d.get('total',0)} has_job={'title' in (d.get('data',[{}])[0] if isinstance(d,dict) and d.get('data') else {})}")

test("GET /v1/jobs/applications", "GET", "/v1/jobs/applications", token=TK,
     check=lambda d: f"applications={d.get('total',0)}")

# Pagination filter: only applied jobs
test("GET /v1/jobs/applications?status=applied", "GET", "/v1/jobs/applications?status=applied", token=TK,
     check=lambda d: f"applied={d.get('total',0)}")

# ── Events list endpoints ──────────────────────────────────────────────────
sec("EVENTS LIST ENDPOINTS")

# RSVP to an upcoming event first (to populate /going)
_ev_list, _ = call("GET", "/v1/events", token=TK)
_going_ev = None
if _ev_list and _ev_list.get("code") == 1 and _ev_list["data"].get("data"):
    _going_ev = _ev_list["data"]["data"][0]
    call("POST", f"/v1/events/{_going_ev['id']}/rsvp", {"status": "going"}, token=TK)

test("GET /v1/events/mine", "GET", "/v1/events/mine", token=TK,
     check=lambda d: f"mine={d.get('total',0)}")

test("GET /v1/events/going", "GET", "/v1/events/going", token=TK,
     check=lambda d: f"going={d.get('total',0)}")

# ── Notification extras ────────────────────────────────────────────────────
sec("NOTIFICATION EXTRAS")

test("GET /v1/notifications/unread-count", "GET", "/v1/notifications/unread-count", token=TK,
     check=lambda d: f"unread={d.get('unread_count',0)}")

# Mark one notification read (create a notification by sending a link request)
_all_notifs, _ = call("GET", "/v1/notifications", token=TK)
if _all_notifs and _all_notifs.get("code") == 1 and _all_notifs["data"].get("data"):
    _nid = _all_notifs["data"]["data"][0]["id"]
    test(f"POST /v1/notifications/:id/read", "POST", f"/v1/notifications/{_nid}/read",
         token=TK,
         check=lambda d: f"is_read={d.get('is_read')}")
    # 404 for unknown notification
    _bad_notif, _ = call("POST", "/v1/notifications/nonexistent-id/read", token=TK)
    if _bad_notif and _bad_notif.get("code") == 0:
        print("  ✅ POST /v1/notifications/:bad/read → correct 404")
        results["pass"].append("Notification single-read 404")
    else:
        print("  ❌ Notification single-read should 404 for unknown id")
        results["fail"].append(("Notification single-read 404", "Expected code=0"))

# ── Hub post likes ─────────────────────────────────────────────────────────
sec("HUB POST LIKES")

_hub_list, _ = call("GET", "/v1/hubs", token=TK)
_like_hub = None
_like_post = None
if _hub_list and _hub_list.get("code") == 1 and _hub_list["data"].get("data"):
    _like_hub = _hub_list["data"]["data"][0]
    _hub_posts, _ = call("GET", f"/v1/hubs/{_like_hub['id']}/posts", token=TK)
    if _hub_posts and _hub_posts.get("code") == 1 and _hub_posts["data"].get("data"):
        _like_post = _hub_posts["data"]["data"][0]

if _like_hub and _like_post:
    hid = _like_hub["id"]
    pid = _like_post["id"]

    # Like the post
    test("POST /v1/hubs/:id/posts/:id/like (like)", "POST", f"/v1/hubs/{hid}/posts/{pid}/like",
         token=TK,
         check=lambda d: f"liked={d.get('liked')} count={d.get('like_count',0)}")

    # Like again → unlike (toggle)
    test("POST /v1/hubs/:id/posts/:id/like (unlike toggle)", "POST", f"/v1/hubs/{hid}/posts/{pid}/like",
         token=TK,
         check=lambda d: f"liked={d.get('liked')} count={d.get('like_count',0)}")

    # Like again to leave it liked
    test("POST /v1/hubs/:id/posts/:id/like (re-like)", "POST", f"/v1/hubs/{hid}/posts/{pid}/like",
         token=TK,
         check=lambda d: f"liked={d.get('liked')}")

    # List likes
    test("GET /v1/hubs/:id/posts/:id/likes", "GET", f"/v1/hubs/{hid}/posts/{pid}/likes",
         token=TK,
         check=lambda d: f"total={d.get('total',0)} has_account={'account' in (d.get('data',[{}])[0] if d.get('data') else {})}")

    # Like from another account (David)
    call("POST", "/v1/auth/otp/request", {"phone": "+256700000005", "purpose": "login"})
    _d_dav, _ = call("POST", "/v1/auth/otp/verify", {"phone": "+256700000005", "code": "123456", "purpose": "login"})
    if _d_dav and _d_dav.get("code") == 1:
        dav_tk = _d_dav["data"]["access_token"]
        call("POST", f"/v1/hubs/{hid}/posts/{pid}/like", token=dav_tk)
        d_likes2 = test("GET /v1/hubs/:id/posts/:id/likes (after 2nd like)", "GET",
                        f"/v1/hubs/{hid}/posts/{pid}/likes",
                        token=TK,
                        check=lambda d: f"total={d.get('total',0)}")

# ── Message reactions ──────────────────────────────────────────────────────
sec("MESSAGE REACTIONS")

_thr_list, _ = call("GET", "/v1/threads", token=TK)
_react_thread = None
_react_msg = None
if _thr_list and _thr_list.get("code") == 1 and _thr_list["data"].get("data"):
    for thr in _thr_list["data"]["data"]:
        _msgs, _ = call("GET", f"/v1/threads/{thr['id']}/messages", token=TK)
        if _msgs and _msgs.get("code") == 1 and _msgs["data"].get("data"):
            _react_thread = thr
            _react_msg = _msgs["data"]["data"][0]
            break

if _react_thread and _react_msg:
    tid = _react_thread["id"]
    mid = _react_msg["id"]

    # Add reaction
    test("POST /v1/threads/:id/messages/:id/react (❤️)", "POST",
         f"/v1/threads/{tid}/messages/{mid}/react",
         body={"emoji": "❤️"}, token=TK,
         check=lambda d: f"emoji={d.get('emoji')} reacted={d.get('reacted',True)}")

    # Add different emoji
    test("POST /v1/threads/:id/messages/:id/react (👍)", "POST",
         f"/v1/threads/{tid}/messages/{mid}/react",
         body={"emoji": "👍"}, token=TK,
         check=lambda d: f"emoji={d.get('emoji')}")

    # Get grouped reactions
    test("GET /v1/threads/:id/messages/:id/reactions", "GET",
         f"/v1/threads/{tid}/messages/{mid}/reactions",
         token=TK,
         check=lambda d: f"total={d.get('total',0)} groups={len(d.get('summary',[]))}")

    # Toggle off ❤️
    test("POST /v1/threads/:id/messages/:id/react (❤️ toggle off)", "POST",
         f"/v1/threads/{tid}/messages/{mid}/react",
         body={"emoji": "❤️"}, token=TK,
         check=lambda d: f"reacted={d.get('reacted')}")

    # Reactions after toggle-off
    test("GET /v1/threads/:id/messages/:id/reactions (after toggle)", "GET",
         f"/v1/threads/{tid}/messages/{mid}/reactions",
         token=TK,
         check=lambda d: f"total={d.get('total',0)} groups={len(d.get('summary',[]))}")

    # 404 for unknown message
    _bad_react, _ = call("POST", f"/v1/threads/{tid}/messages/nonexistent/react", {"emoji": "👍"}, token=TK)
    if _bad_react and _bad_react.get("code") == 0:
        print("  ✅ POST /v1/threads/.../react (bad msg) → correct 404")
        results["pass"].append("Reaction 404 for unknown message")
    else:
        print("  ❌ Reaction on unknown message should 404")
        results["fail"].append(("Reaction 404 for unknown message", "Expected code=0"))

# ── Interest Graph behavioral signals ──────────────────────────────────────
sec("INTEREST BEHAVIORAL SIGNALS")

# Get tag IDs from taxonomy
_tax, _ = call("GET", "/v1/interests/taxonomy", token=TK)
_signal_tag = None
_signal_tag2 = None
if _tax and _tax.get("code") == 1:
    for dim, tags in _tax["data"].items():
        if tags and not _signal_tag:
            _signal_tag = tags[0]
        elif tags and not _signal_tag2:
            _signal_tag2 = tags[0]
        if _signal_tag and _signal_tag2:
            break

if _signal_tag:
    # First signal on the tag
    test("POST /v1/interests/signal (job_view)", "POST", "/v1/interests/signal",
         body={"tag_id": _signal_tag["id"], "source": "job_view", "strength": 0.15},
         token=TK,
         check=lambda d: f"weight={d.get('weight',0):.3f} source={d.get('source')}")

    # Second signal — weight should increase
    test("POST /v1/interests/signal (reinforce)", "POST", "/v1/interests/signal",
         body={"tag_id": _signal_tag["id"], "source": "hub_visit", "strength": 0.1},
         token=TK,
         check=lambda d: f"weight={d.get('weight',0):.3f}")

if _signal_tag2:
    # Brand-new implicit interest (may not be in profile yet)
    test("POST /v1/interests/signal (new implicit)", "POST", "/v1/interests/signal",
         body={"tag_id": _signal_tag2["id"], "source": "profile_view", "strength": 0.05},
         token=TK,
         check=lambda d: f"weight={d.get('weight',0):.3f} source={d.get('source')}")

# Error: missing tag_id
_no_tag, _ = call("POST", "/v1/interests/signal", {"strength": 0.1}, token=TK)
if _no_tag and _no_tag.get("code") == 0:
    print("  ✅ POST /v1/interests/signal (no tag_id) → correctly rejected")
    results["pass"].append("Interest signal missing tag_id rejected")
else:
    results["fail"].append(("Interest signal missing tag_id", "Expected code=0"))

# Error: invalid tag_id
_bad_tag, _ = call("POST", "/v1/interests/signal", {"tag_id": "fake-uuid", "strength": 0.1}, token=TK)
if _bad_tag and _bad_tag.get("code") == 0:
    print("  ✅ POST /v1/interests/signal (bad tag_id) → correctly rejected")
    results["pass"].append("Interest signal bad tag_id rejected")
else:
    results["fail"].append(("Interest signal bad tag_id", "Expected code=0"))

# ── Dating profile extras ─────────────────────────────────────────────────
sec("DATING PROFILE EXTRAS")

# Update with all new fields
test("PUT /v1/profile/me/dating (birth_year+gender)", "PUT", "/v1/profile/me/dating",
     body={"birth_year": 1997, "gender": "male", "looking_for_gender": "female",
           "discoverability": "discoverable", "age_min": 22, "age_max": 35},
     token=TK,
     check=lambda d: f"age={d.get('age')} gender={d.get('gender')} disc={d.get('discoverability')}")

# Pause discoverability
test("PUT /v1/profile/me/dating (pause)", "PUT", "/v1/profile/me/dating",
     body={"discoverability": "paused"},
     token=TK,
     check=lambda d: f"discoverability={d.get('discoverability')}")

# Restore
test("PUT /v1/profile/me/dating (restore)", "PUT", "/v1/profile/me/dating",
     body={"discoverability": "discoverable"},
     token=TK,
     check=lambda d: f"discoverability={d.get('discoverability')}")

# Invalid discoverability value
_bad_disc, _ = call("PUT", "/v1/profile/me/dating",
                    {"discoverability": "invisible"}, token=TK)
if _bad_disc and _bad_disc.get("code") == 0:
    print("  ✅ PUT /v1/profile/me/dating (bad discoverability) → correctly rejected")
    results["pass"].append("Dating bad discoverability rejected")
else:
    print("  ❌ Bad discoverability should be rejected")
    results["fail"].append(("Dating bad discoverability rejected", "Expected code=0"))

# Verify age derived from birth_year in response
test("GET /v1/profile/me/dating (age derived)", "GET", "/v1/profile/me/dating",
     token=TK,
     check=lambda d: f"age={d.get('age')} birth_year={d.get('birth_year')} disc={d.get('discoverability')}")

# ── Summary ────────────────────────────────────────────────────────────────
total = len(results["pass"]) + len(results["fail"])
print(f"\n{'='*65}")
print(f"AUDIT COMPLETE — {len(results['pass'])}/{total} PASS  |  {len(results['fail'])} FAIL  |  {len(results['warn'])} WARN")
print(f"{'='*65}")

if results["fail"]:
    print(f"\n{'─'*40}")
    print("FAILED ENDPOINTS:")
    for name, reason in results["fail"]:
        print(f"\n  ✗ {name}")
        print(f"    {reason}")

if results["warn"]:
    print(f"\n{'─'*40}")
    print("WARNINGS:")
    for name, reason in results["warn"]:
        print(f"  ⚠  {name}: {reason}")

if not results["fail"]:
    print("\n  All endpoints passed! 🎉")
