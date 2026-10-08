"""Phase 3 backend regression: Actions (auto + manual), Response notes, Per-location analytics, Weekly digest cron."""
import os, time, uuid, requests, pytest
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
CRON_SECRET = os.environ["WEBHOOK_CRON_SECRET"]
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

mongo = MongoClient(MONGO_URL)[DB_NAME]


def _rand(prefix="t"): return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def demo_token():
    r = requests.post(f"{API}/auth/login", json={"email": "demo@example.com", "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def demo_headers(demo_token): return {"Authorization": f"Bearer {demo_token}"}


@pytest.fixture(scope="module")
def demo_workspace(demo_headers):
    r = requests.get(f"{API}/workspaces", headers=demo_headers); r.raise_for_status()
    return r.json()[0]


@pytest.fixture(scope="module")
def demo_template(demo_headers):
    r = requests.get(f"{API}/templates", headers=demo_headers); r.raise_for_status()
    return next(t for t in r.json() if t["status"] == "PUBLISHED")


# ---------- Weekly digest cron ----------
class TestWeeklyDigestCron:
    def test_401_without_auth(self):
        r = requests.post(f"{API}/cron/weekly-digest")
        assert r.status_code == 401

    def test_401_wrong_secret(self):
        r = requests.post(f"{API}/cron/weekly-digest", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_2xx_with_secret_and_db_writes(self):
        run_id = f"test-run-{uuid.uuid4().hex[:10]}"
        r = requests.post(f"{API}/cron/weekly-digest",
                          headers={"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": run_id})
        assert r.status_code == 200, r.text
        data = r.json(); assert data["ok"] is True; assert data["run_id"] == run_id

        # Poll digest_runs for finished_at
        for _ in range(20):
            run = mongo.digest_runs.find_one({"run_id": run_id})
            if run and run.get("finished_at"): break
            time.sleep(0.5)
        assert run is not None, "digest_runs row never created"
        assert run.get("finished_at"), "digest run never finished"

        # digest_sends must have at least one record (demo workspace has responses from last 7 days? seed uses 'now' timestamps)
        sends = list(mongo.digest_sends.find({"run_id": run_id}))
        assert len(sends) >= 1, "expected at least one digest_sends row for demo workspace"
        # RESEND empty -> sent False expected
        for s in sends:
            assert "owner_email" in s and "sent" in s and "total_responses" in s

    def test_dedupe_on_same_run_id(self):
        run_id = f"test-dedupe-{uuid.uuid4().hex[:8]}"
        # Fire twice
        for _ in range(2):
            r = requests.post(f"{API}/cron/weekly-digest",
                              headers={"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": run_id})
            assert r.status_code == 200
        time.sleep(3)
        runs = list(mongo.digest_runs.find({"run_id": run_id}))
        assert len(runs) == 1, f"expected dedupe, got {len(runs)} rows"


# ---------- Auto AI action ----------
class TestAutoAction:
    def test_reanalyze_negative_creates_auto_action_once(self, demo_headers, demo_workspace, demo_template):
        # Find or create a response that will classify as negative.
        # Submit a clearly-negative response via public endpoint first.
        slug = demo_template["public_slug"]
        qmap = {q["id"]: q for q in demo_template["questions"]}
        longtext_q = next(q for q in demo_template["questions"] if q["question_type"] == "longtext")
        rating_q = next(q for q in demo_template["questions"] if q["question_type"] == "rating")
        yesno_q = next((q for q in demo_template["questions"] if q["question_type"] == "yesno"), None)

        answers = [
            {"question_id": rating_q["id"], "value": 1},
            {"question_id": longtext_q["id"], "value": "Absolutely terrible experience. The food was cold, "
                                                        "the service was rude and slow. Will never come back. Very disappointed."}
        ]
        # fill in required other questions
        for q in demo_template["questions"]:
            if q["id"] in (rating_q["id"], longtext_q["id"]): continue
            if q["question_type"] == "rating": answers.append({"question_id": q["id"], "value": 1})
            elif q["question_type"] == "yesno": answers.append({"question_id": q["id"], "value": "No"})
            else: answers.append({"question_id": q["id"], "value": "bad"})

        sub = requests.post(f"{API}/public/feedback/{slug}/responses", json={"answers": answers})
        assert sub.status_code == 200, sub.text
        response_id = sub.json()["response_id"]

        # Wait up to 20s for AI classification
        sentiment = None
        for _ in range(25):
            d = requests.get(f"{API}/responses/{response_id}", headers=demo_headers).json()
            ai = d["response"].get("ai") or {}
            sentiment = ai.get("sentiment")
            if sentiment in ("positive", "neutral", "negative"): break
            time.sleep(1)
        assert sentiment == "negative", f"expected negative, got {sentiment}"

        # Auto action should exist
        actions_before = requests.get(f"{API}/actions", headers=demo_headers).json()
        auto_for_resp = [a for a in actions_before if a.get("response_id") == response_id and a.get("source") == "auto"]
        assert len(auto_for_resp) == 1, f"expected 1 auto action, got {len(auto_for_resp)}"
        assert auto_for_resp[0]["status"] == "open"

        # Reanalyze — should NOT create duplicate
        r = requests.post(f"{API}/responses/{response_id}/reanalyze", headers=demo_headers)
        assert r.status_code == 200
        time.sleep(8)  # wait for background task
        actions_after = requests.get(f"{API}/actions", headers=demo_headers).json()
        auto_for_resp2 = [a for a in actions_after if a.get("response_id") == response_id and a.get("source") == "auto"]
        assert len(auto_for_resp2) == 1, f"duplicate auto action created: {len(auto_for_resp2)}"


# ---------- Actions CRUD + permissions ----------
class TestActionsAPI:
    def test_crud_and_assign(self, demo_headers):
        # Create
        r = requests.post(f"{API}/actions", headers=demo_headers,
                          json={"title": "Call back customer about table 5"})
        assert r.status_code == 200, r.text
        action = r.json(); aid = action["id"]
        assert action["status"] == "open"; assert action["source"] == "manual"

        # List & verify present
        lst = requests.get(f"{API}/actions", headers=demo_headers).json()
        assert any(a["id"] == aid for a in lst)

        # Status transitions
        for status in ("in_progress", "done", "open"):
            r = requests.patch(f"{API}/actions/{aid}", headers=demo_headers, json={"status": status})
            assert r.status_code == 200
            lst = requests.get(f"{API}/actions", headers=demo_headers).json()
            found = next(a for a in lst if a["id"] == aid)
            assert found["status"] == status

        # Assign (self-claim)
        r = requests.post(f"{API}/actions/{aid}/assign", headers=demo_headers); assert r.status_code == 200
        lst = requests.get(f"{API}/actions", headers=demo_headers).json()
        found = next(a for a in lst if a["id"] == aid)
        assert found["assignee_id"] is not None
        assert found.get("assignee") and found["assignee"]["email"] == "demo@example.com"

        # Delete
        r = requests.delete(f"{API}/actions/{aid}", headers=demo_headers); assert r.status_code == 200
        lst = requests.get(f"{API}/actions", headers=demo_headers).json()
        assert not any(a["id"] == aid for a in lst)

    def test_viewer_cannot_write(self, demo_headers):
        # Create viewer via invite
        viewer_email = f"TEST_viewer_{uuid.uuid4().hex[:6]}@example.com"
        inv = requests.post(f"{API}/team/invites", headers=demo_headers,
                            json={"email": viewer_email, "role": "viewer"})
        assert inv.status_code == 200, inv.text
        token = inv.json()["token"]

        # Register viewer and accept
        reg = requests.post(f"{API}/auth/register", json={"full_name": "Vee Viewer", "email": viewer_email, "password": "Pass1234!"})
        assert reg.status_code == 200, reg.text
        vtok = reg.json()["access_token"]
        vhdr = {"Authorization": f"Bearer {vtok}"}
        acc = requests.post(f"{API}/team/invites/{token}/accept", headers=vhdr); assert acc.status_code == 200

        # Viewer can GET
        assert requests.get(f"{API}/actions", headers=vhdr).status_code == 200

        # Viewer cannot create
        r = requests.post(f"{API}/actions", headers=vhdr, json={"title": "nope"})
        assert r.status_code == 403


# ---------- Response notes ----------
class TestResponseNotes:
    def test_crud_and_tenant_isolation(self, demo_headers):
        # pick any response
        rs = requests.get(f"{API}/responses", headers=demo_headers).json()
        assert rs, "no responses to test notes"
        resp_id = rs[0]["id"]

        # Add note
        r = requests.post(f"{API}/responses/{resp_id}/notes", headers=demo_headers,
                          json={"text": "Internal: follow up tomorrow"})
        assert r.status_code == 200, r.text
        note = r.json(); assert note["text"] == "Internal: follow up tomorrow"
        note_id = note["id"]

        # List
        lst = requests.get(f"{API}/responses/{resp_id}/notes", headers=demo_headers).json()
        assert any(n["id"] == note_id for n in lst)

        # Also returned in /responses/{id} payload
        detail = requests.get(f"{API}/responses/{resp_id}", headers=demo_headers).json()
        notes_in_detail = detail["response"].get("notes", [])
        assert any(n["id"] == note_id for n in notes_in_detail), "notes not included in response detail payload"

        # Max 1000 chars validation
        over = requests.post(f"{API}/responses/{resp_id}/notes", headers=demo_headers,
                             json={"text": "x" * 1001})
        assert over.status_code == 422

        # Empty invalid
        empty = requests.post(f"{API}/responses/{resp_id}/notes", headers=demo_headers, json={"text": ""})
        assert empty.status_code == 422

        # Tenant isolation — second user with own workspace shouldn't see
        em = f"TEST_other_{uuid.uuid4().hex[:6]}@example.com"
        reg = requests.post(f"{API}/auth/register", json={"full_name": "Other Owner", "email": em, "password": "Pass1234!"})
        otok = reg.json()["access_token"]; ohdr = {"Authorization": f"Bearer {otok}"}
        requests.post(f"{API}/workspaces", headers=ohdr, json={"name": "Other biz"})
        iso = requests.get(f"{API}/responses/{resp_id}/notes", headers=ohdr)
        assert iso.status_code == 404
        iso2 = requests.post(f"{API}/responses/{resp_id}/notes", headers=ohdr, json={"text": "sneaky"})
        assert iso2.status_code == 404

        # Delete note
        d = requests.delete(f"{API}/responses/{resp_id}/notes/{note_id}", headers=demo_headers)
        assert d.status_code == 200
        lst2 = requests.get(f"{API}/responses/{resp_id}/notes", headers=demo_headers).json()
        assert not any(n["id"] == note_id for n in lst2)


# ---------- Per-location analytics ----------
class TestLocationAnalytics:
    def test_filter_and_by_location(self, demo_headers):
        locs = requests.get(f"{API}/locations", headers=demo_headers).json()
        assert len(locs) >= 1
        loc_id = locs[0]["id"]

        total_all = requests.get(f"{API}/analytics", headers=demo_headers).json()
        total_loc = requests.get(f"{API}/analytics?location_id={loc_id}", headers=demo_headers).json()
        assert total_loc["total"] <= total_all["total"]

        by_loc = requests.get(f"{API}/analytics/by-location", headers=demo_headers).json()
        assert isinstance(by_loc, list) and len(by_loc) >= 1
        # Each row has required keys
        for row in by_loc:
            assert set(["location_id", "location", "total", "average", "sentiment"]).issubset(row.keys())
            assert row["total"] > 0 or row["location_id"] is None  # unassigned bucket may show when has data

        # Unassigned bucket only present when has data
        unassigned_rows = [r for r in by_loc if r["location_id"] is None]
        if unassigned_rows:
            assert unassigned_rows[0]["total"] > 0
