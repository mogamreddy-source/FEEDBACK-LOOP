"""Phase 2 tests: seed, AI sentiment, team invites, locations, roles, tenant isolation."""
import os, uuid, time, requests, pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


def _register(session, email_prefix="user"):
    email = f"test_{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = session.post(f"{API}/auth/register", json={"full_name": "Test User", "email": email, "password": "testing123"})
    assert r.status_code == 200, r.text
    return email, r.json()["access_token"]


def _auth(tok): return {"Authorization": f"Bearer {tok}"}


# ---------------- Seed ----------------
class TestSeed:
    def test_demo_login_and_data(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": "demo@example.com", "password": "Demo1234!"})
        assert r.status_code == 200
        tok = r.json()["access_token"]; h = _auth(tok)
        ws = s.get(f"{API}/workspaces", headers=h).json()
        assert any(w["name"] == "ABC Restaurant" for w in ws)
        locs = s.get(f"{API}/locations", headers=h).json()
        assert len(locs) == 2
        tpls = s.get(f"{API}/templates", headers=h).json()
        assert any(t["public_slug"] == "abc-restaurant-experience" and len(t["questions"]) == 5 for t in tpls)
        resps = s.get(f"{API}/responses", headers=h).json()
        assert len(resps) >= 8
        assert all((r.get("ai") or {}).get("sentiment") in ("positive","neutral","negative") for r in resps)


# ---------------- AI sentiment ----------------
class TestSentimentAI:
    def test_submit_triggers_ai_and_detail_endpoint(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": "demo@example.com", "password": "Demo1234!"})
        tok = s.cookies.get("access_token")
        h = {"Authorization": f"Bearer {tok}"}
        tpls = s.get(f"{API}/templates", headers=h).json()
        tpl = next(t for t in tpls if t["public_slug"] == "abc-restaurant-experience")
        slug = tpl["public_slug"]
        pub = s.get(f"{API}/public/feedback/{slug}").json()
        assert pub["location"] is not None  # location attached
        qs = pub["template"]["questions"]
        values = [5, 5, 5, "Yes", "The food was absolutely delicious and the service was incredibly warm. We really loved every bite."]
        r = s.post(f"{API}/public/feedback/{slug}/responses", json={"answers":[{"question_id":q["id"],"value":v} for q,v in zip(qs,values)]})
        assert r.status_code == 200
        rid = r.json()["response_id"]
        ai = None
        for _ in range(20):
            detail = s.get(f"{API}/responses/{rid}", headers=h)
            assert detail.status_code == 200
            body = detail.json()
            assert "response" in body and "template" in body and "location" in body
            ai = body["response"].get("ai")
            if ai and ai.get("sentiment") in ("positive","neutral","negative"):
                break
            time.sleep(1)
        assert ai, "AI payload never populated"
        assert ai["sentiment"] in ("positive","neutral","negative"), f"got {ai}"
        assert "summary" in ai and isinstance(ai.get("topics"), list)
        # reanalyze
        rr = s.post(f"{API}/responses/{rid}/reanalyze", headers=h)
        assert rr.status_code == 200

    def test_analytics_and_dashboard_sentiment(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": "demo@example.com", "password": "Demo1234!"})
        tok = s.cookies.get("access_token"); h = {"Authorization": f"Bearer {tok}"}
        a = s.get(f"{API}/analytics", headers=h).json()
        assert "sentiment" in a and set(a["sentiment"].keys()) == {"positive","neutral","negative"}
        assert isinstance(a.get("topics"), list) and len(a["topics"]) > 0
        d = s.get(f"{API}/dashboard/summary", headers=h).json()
        assert set(d.get("sentiment",{}).keys()) == {"positive","neutral","negative"}
        assert sum(d["sentiment"].values()) >= 8


# ---------------- Team / Invites ----------------
class TestTeam:
    def test_invite_flow_and_role_access(self):
        s_owner = requests.Session()
        owner_email, otok = _register(s_owner, "owner")
        s_owner.post(f"{API}/workspaces", headers=_auth(otok), json={"name":"Inv Co","business_type":"Other"})

        # invite self -> 400
        r = s_owner.post(f"{API}/team/invites", headers=_auth(otok), json={"email":owner_email,"role":"editor"})
        assert r.status_code == 400

        invitee_email = f"test_invitee_{uuid.uuid4().hex[:8]}@example.com"
        r = s_owner.post(f"{API}/team/invites", headers=_auth(otok), json={"email":invitee_email,"role":"editor"})
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv.get("token") and inv.get("link") and inv.get("email_sent") is False

        # duplicate -> 409
        r2 = s_owner.post(f"{API}/team/invites", headers=_auth(otok), json={"email":invitee_email,"role":"editor"})
        assert r2.status_code == 409

        # public view
        pub = requests.get(f"{API}/team/invites/{inv['token']}")
        assert pub.status_code == 200
        assert pub.json()["invite"]["email"] == invitee_email
        assert pub.json()["workspace"]["name"] == "Inv Co"
        assert requests.get(f"{API}/team/invites/badtoken").status_code == 404

        # register invitee + accept
        s_inv = requests.Session()
        r = s_inv.post(f"{API}/auth/register", json={"full_name":"Inv","email":invitee_email,"password":"testing123"})
        itok = r.json()["access_token"]
        # wrong-email user cannot accept
        s_other = requests.Session(); _, otok2 = _register(s_other, "other")
        bad = s_other.post(f"{API}/team/invites/{inv['token']}/accept", headers=_auth(otok2))
        assert bad.status_code == 403
        acc = s_inv.post(f"{API}/team/invites/{inv['token']}/accept", headers=_auth(itok))
        assert acc.status_code == 200

        # invitee sees owner's workspace
        wss = s_inv.get(f"{API}/workspaces", headers=_auth(itok)).json()
        assert any(w["name"]=="Inv Co" for w in wss)

        # editor can create templates
        t = s_inv.post(f"{API}/templates", headers=_auth(itok), json={"name":"T1","description":"","questions":[{"question_text":"q","question_type":"rating"}]})
        assert t.status_code == 200

        # members list
        ml = s_owner.get(f"{API}/team/members", headers=_auth(otok)).json()
        assert ml["owner"]["email"] == owner_email
        assert len(ml["members"]) == 1
        member_id = ml["members"][0]["id"]

        # patch to viewer
        p = s_owner.patch(f"{API}/team/members/{member_id}", headers=_auth(otok), json={"role":"viewer"})
        assert p.status_code == 200
        # viewer gets 403 on create
        vt = s_inv.post(f"{API}/templates", headers=_auth(itok), json={"name":"T2","description":"","questions":[{"question_text":"q","question_type":"rating"}]})
        assert vt.status_code == 403

        # non-owner cannot patch
        np = s_inv.patch(f"{API}/team/members/{member_id}", headers=_auth(itok), json={"role":"editor"})
        assert np.status_code == 403

        # owner removes member
        d = s_owner.delete(f"{API}/team/members/{member_id}", headers=_auth(otok))
        assert d.status_code == 200


# ---------------- Locations ----------------
class TestLocations:
    def test_crud_and_role_perms(self):
        s_owner = requests.Session()
        owner_email, otok = _register(s_owner, "locown")
        s_owner.post(f"{API}/workspaces", headers=_auth(otok), json={"name":"Loc Co","business_type":"Other"})
        # create
        r = s_owner.post(f"{API}/locations", headers=_auth(otok), json={"name":"HQ","address":"1 st","city":"X","phone":"1"})
        assert r.status_code == 200; lid = r.json()["id"]
        # patch
        p = s_owner.patch(f"{API}/locations/{lid}", headers=_auth(otok), json={"name":"HQ2","address":"","city":"","phone":""})
        assert p.status_code == 200 and p.json()["name"] == "HQ2"
        # template with location
        t = s_owner.post(f"{API}/templates", headers=_auth(otok), json={"name":"TL","description":"","location_id":lid,"questions":[{"question_text":"q","question_type":"rating"}]})
        assert t.status_code == 200
        tid = t.json()["id"]
        # delete location nullifies template location
        d = s_owner.delete(f"{API}/locations/{lid}", headers=_auth(otok))
        assert d.status_code == 200
        tt = s_owner.get(f"{API}/templates/{tid}", headers=_auth(otok)).json()
        assert tt.get("location_id") in (None, "")

        # viewer cannot create
        s_v = requests.Session(); vemail, _ = _register(s_v, "locviewer")
        inv = s_owner.post(f"{API}/team/invites", headers=_auth(otok), json={"email":vemail,"role":"viewer"}).json()
        s_v2 = requests.Session()
        r = s_v2.post(f"{API}/auth/login", json={"email":vemail,"password":"testing123"})
        vtok = r.json()["access_token"]
        s_v2.post(f"{API}/team/invites/{inv['token']}/accept", headers=_auth(vtok))
        rr = s_v2.post(f"{API}/locations", headers=_auth(vtok), json={"name":"X"})
        assert rr.status_code == 403


# ---------------- Tenant isolation ----------------
class TestIsolation:
    def test_second_user_cannot_access_first_data(self):
        s1 = requests.Session(); _, t1 = _register(s1, "iso1")
        s1.post(f"{API}/workspaces", headers=_auth(t1), json={"name":"Alpha","business_type":"Other"})
        resp = s1.post(f"{API}/templates", headers=_auth(t1), json={"name":"T","description":"","questions":[{"question_text":"q","question_type":"rating"}]})
        assert resp.status_code == 200, resp.text
        tpl = resp.json()
        s2 = requests.Session(); _, t2 = _register(s2, "iso2")
        s2.post(f"{API}/workspaces", headers=_auth(t2), json={"name":"Bravo","business_type":"Other"})
        r = s2.get(f"{API}/templates/{tpl['id']}", headers=_auth(t2))
        assert r.status_code == 404
        assert s2.get(f"{API}/templates", headers=_auth(t2)).json() == []
