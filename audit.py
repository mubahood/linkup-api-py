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

# ── Legacy /api/ routes ────────────────────────────────────────────────────
sec("LEGACY /api/ (backward compat)")

# Get old-style token
call("POST", "/v1/auth/otp/request", {"phone": "+256700000001", "purpose": "login"})
d_old, _ = call("POST", "/v1/auth/otp/verify",
                {"phone": "+256700000001", "code": "123456", "purpose": "login"})
OLD_TK = d_old["data"]["access_token"] if d_old else TK

test("GET /api/admin/system/health", "GET", "/api/admin/system/health", token=OLD_TK)
test("GET /api/admin/dashboard", "GET", "/api/admin/dashboard", token=OLD_TK)

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
