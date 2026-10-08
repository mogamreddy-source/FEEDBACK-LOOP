"""Phase 4 - Template Builder upgrade tests.
Covers: presets, library (with response_count + design), from-preset, PATCH design/multichoice,
duplicate, unpublish, archive, uploads validation, /api/files public read,
public feedback payload with design + logo_url/background_url + multichoice/singlechoice submit.
"""
import os, io, time, struct, zlib, pytest, requests
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://survey-poc.preview.emergentagent.com"
EMAIL = "demo@example.com"
PASSWORD = "Demo1234!"


def _tiny_png_bytes():
    """Build a minimal valid 1x1 PNG."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat_raw = b"\x00\xff\x00\x00"
    idat = zlib.compress(idat_raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestPresets:
    def test_presets_returns_5_with_category(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/templates/presets", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 5
        names = {p["name"] for p in data}
        assert names == {"Restaurant Experience", "Product Review", "Service Feedback", "Hotel Experience", "General Customer Feedback"}
        for p in data:
            assert "category" in p and p["category"]
            assert "question_count" in p and p["question_count"] > 0
            assert isinstance(p["questions"], list) and len(p["questions"]) == p["question_count"]


class TestTemplatesLibrary:
    def test_templates_include_response_count_and_design(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/templates", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        for t in items:
            assert "category" in t
            assert "response_count" in t and isinstance(t["response_count"], int)
            assert "design" in t


class TestFromPreset:
    def test_from_hotel_preset_creates_multichoice(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/templates/from-preset/Hotel%20Experience", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        doc = r.json()
        assert doc["category"] == "Hospitality"
        assert doc["status"] == "DRAFT"
        mcq = [q for q in doc["questions"] if q["question_type"] == "multichoice"]
        assert mcq, "expected a multichoice question"
        assert len(mcq[0]["options"]) >= 3
        # cleanup
        requests.delete(f"{BASE_URL}/api/templates/{doc['id']}", headers=auth_headers)


class TestTemplateCRUDWithDesignAndChoices:
    def test_patch_persists_design_and_choice_questions(self, auth_headers):
        # create
        payload = {"name": "TEST_builder", "description": "x", "category": "Retail",
                   "questions": [{"question_text": "Rate", "question_type": "rating", "options": []}]}
        r = requests.post(f"{BASE_URL}/api/templates", headers=auth_headers, json=payload, timeout=15)
        assert r.status_code == 200
        tid = r.json()["id"]

        patch = {"name": "TEST_builder", "description": "y", "category": "Retail",
                 "design": {"logo_file_id": None, "background_file_id": None,
                            "background_color": "#000000", "primary_color": "#c9622b",
                            "text_color": "#ffffff", "card_background": "#111111", "button_style": "pill"},
                 "questions": [
                     {"question_text": "Rate", "question_type": "rating", "options": []},
                     {"question_text": "Pick one", "question_type": "singlechoice", "options": ["A", "B", "C"]},
                     {"question_text": "Pick many", "question_type": "multichoice", "options": ["X", "Y", "Z"]},
                 ]}
        r = requests.patch(f"{BASE_URL}/api/templates/{tid}", headers=auth_headers, json=patch, timeout=15)
        assert r.status_code == 200, r.text

        # verify via GET
        r = requests.get(f"{BASE_URL}/api/templates/{tid}", headers=auth_headers, timeout=15)
        doc = r.json()
        assert doc["design"]["primary_color"] == "#c9622b"
        assert doc["design"]["button_style"] == "pill"
        qt = [q["question_type"] for q in doc["questions"]]
        assert "singlechoice" in qt and "multichoice" in qt
        mc = next(q for q in doc["questions"] if q["question_type"] == "multichoice")
        assert mc["options"] == ["X", "Y", "Z"]

        # cleanup
        requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=auth_headers)


class TestDuplicateUnpublishArchive:
    def _mk(self, auth_headers):
        payload = {"name": "TEST_dup", "description": "", "category": "General",
                   "questions": [{"question_text": "Rate", "question_type": "rating", "options": []}]}
        r = requests.post(f"{BASE_URL}/api/templates", headers=auth_headers, json=payload, timeout=15)
        return r.json()

    def test_duplicate_creates_draft_with_new_ids(self, auth_headers):
        orig = self._mk(auth_headers)
        # publish original so we can test duplicate drops to DRAFT
        requests.post(f"{BASE_URL}/api/templates/{orig['id']}/publish", headers=auth_headers)
        r = requests.post(f"{BASE_URL}/api/templates/{orig['id']}/duplicate", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        dup = r.json()
        assert dup["id"] != orig["id"]
        assert dup["status"] == "DRAFT"
        assert dup["public_slug"] is None
        assert dup["name"].endswith("- Copy")
        assert dup["questions"][0]["id"] != orig["questions"][0]["id"]
        # cleanup
        requests.delete(f"{BASE_URL}/api/templates/{orig['id']}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/templates/{dup['id']}", headers=auth_headers)

    def test_unpublish_flips_to_draft(self, auth_headers):
        t = self._mk(auth_headers)
        requests.post(f"{BASE_URL}/api/templates/{t['id']}/publish", headers=auth_headers)
        r = requests.post(f"{BASE_URL}/api/templates/{t['id']}/unpublish", headers=auth_headers)
        assert r.status_code == 200
        d = requests.get(f"{BASE_URL}/api/templates/{t['id']}", headers=auth_headers).json()
        assert d["status"] == "DRAFT"
        requests.delete(f"{BASE_URL}/api/templates/{t['id']}", headers=auth_headers)

    def test_archive_nulls_slug(self, auth_headers):
        t = self._mk(auth_headers)
        pub = requests.post(f"{BASE_URL}/api/templates/{t['id']}/publish", headers=auth_headers).json()
        slug = pub["public_slug"]
        # confirm slug reachable first
        assert requests.get(f"{BASE_URL}/api/public/feedback/{slug}").status_code == 200
        r = requests.post(f"{BASE_URL}/api/templates/{t['id']}/archive", headers=auth_headers)
        assert r.status_code == 200
        d = requests.get(f"{BASE_URL}/api/templates/{t['id']}", headers=auth_headers).json()
        assert d["status"] == "ARCHIVED"
        assert d["public_slug"] is None
        # slug no longer reachable
        assert requests.get(f"{BASE_URL}/api/public/feedback/{slug}").status_code == 404
        requests.delete(f"{BASE_URL}/api/templates/{t['id']}", headers=auth_headers)


class TestUploadsAndFiles:
    def test_reject_non_image(self, auth_headers):
        files = {"file": ("note.txt", b"hello", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/uploads?purpose=logo", headers=auth_headers, files=files, timeout=30)
        assert r.status_code == 400

    def test_upload_and_serve_public(self, auth_headers):
        png = _tiny_png_bytes()
        files = {"file": ("tiny.png", png, "image/png")}
        r = requests.post(f"{BASE_URL}/api/uploads?purpose=logo", headers=auth_headers, files=files, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data and "url" in data and data["size"] == len(png)
        assert data["content_type"] == "image/png"
        # public GET (no auth)
        r2 = requests.get(f"{BASE_URL}/api/files/{data['id']}", timeout=30)
        assert r2.status_code == 200
        assert r2.headers.get("content-type", "").startswith("image/")
        # Note: Cloudflare proxy may override Cache-Control; backend sets public,max-age=3600
        assert len(r2.content) == len(png)
        return data["id"]


class TestPublicFeedbackDesign:
    def test_public_feedback_includes_design_and_file_urls(self, auth_headers):
        # upload a logo + bg
        png = _tiny_png_bytes()
        up1 = requests.post(f"{BASE_URL}/api/uploads?purpose=logo", headers=auth_headers,
                            files={"file": ("l.png", png, "image/png")}, timeout=60).json()
        up2 = requests.post(f"{BASE_URL}/api/uploads?purpose=background", headers=auth_headers,
                            files={"file": ("b.png", png, "image/png")}, timeout=60).json()
        # create + patch design + publish
        payload = {"name": "TEST_public_design", "description": "", "category": "General",
                   "questions": [
                       {"question_text": "Rate", "question_type": "rating", "options": []},
                       {"question_text": "Topics", "question_type": "multichoice", "options": ["Food", "Service", "Ambience"]},
                       {"question_text": "Visit", "question_type": "singlechoice", "options": ["First", "Return"]},
                   ]}
        t = requests.post(f"{BASE_URL}/api/templates", headers=auth_headers, json=payload).json()
        tid = t["id"]
        patch = {"name": t["name"], "description": "", "category": "General",
                 "design": {"logo_file_id": up1["id"], "background_file_id": up2["id"],
                            "background_color": "#f5f7f4", "primary_color": "#c9622b",
                            "text_color": "#17352d", "card_background": "#ffffff", "button_style": "pill"},
                 "questions": payload["questions"]}
        r = requests.patch(f"{BASE_URL}/api/templates/{tid}", headers=auth_headers, json=patch)
        assert r.status_code == 200
        pub = requests.post(f"{BASE_URL}/api/templates/{tid}/publish", headers=auth_headers).json()
        slug = pub["public_slug"]
        # fetch public
        r = requests.get(f"{BASE_URL}/api/public/feedback/{slug}", timeout=15)
        assert r.status_code == 200
        design = r.json()["template"]["design"]
        assert design["primary_color"] == "#c9622b"
        assert design["button_style"] == "pill"
        assert design["logo_url"] and up1["id"] in design["logo_url"]
        assert design["background_url"] and up2["id"] in design["background_url"]

        # submit response with multichoice (list) + singlechoice (string)
        qs = r.json()["template"]["questions"]
        qmap = {q["question_type"]: q["id"] for q in qs}
        body = {"answers": [
            {"question_id": qmap["rating"], "value": 5},
            {"question_id": qmap["multichoice"], "value": ["Food", "Service"]},
            {"question_id": qmap["singlechoice"], "value": "Return"},
        ]}
        r = requests.post(f"{BASE_URL}/api/public/feedback/{slug}/responses", json=body, timeout=15)
        assert r.status_code == 200, r.text

        # required empty-array multichoice -> 400
        body_bad = {"answers": [
            {"question_id": qmap["rating"], "value": 5},
            {"question_id": qmap["multichoice"], "value": []},
            {"question_id": qmap["singlechoice"], "value": "Return"},
        ]}
        r = requests.post(f"{BASE_URL}/api/public/feedback/{slug}/responses", json=body_bad, timeout=15)
        assert r.status_code == 400

        # cleanup
        requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=auth_headers)


class TestRegressionPhase123:
    def test_me_and_summary(self, auth_headers):
        assert requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/dashboard/summary", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/responses", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/analytics", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/analytics/by-location", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/team/members", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/locations", headers=auth_headers).status_code == 200
        assert requests.get(f"{BASE_URL}/api/actions", headers=auth_headers).status_code == 200

    def test_cron_auth(self):
        r = requests.post(f"{BASE_URL}/api/cron/weekly-digest", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401
        secret = os.environ.get("WEBHOOK_CRON_SECRET")
        if secret:
            r = requests.post(f"{BASE_URL}/api/cron/weekly-digest", headers={"Authorization": f"Bearer {secret}", "X-Webhook-Id": f"test-{int(time.time())}"})
            assert r.status_code == 200 and r.json()["ok"] is True
