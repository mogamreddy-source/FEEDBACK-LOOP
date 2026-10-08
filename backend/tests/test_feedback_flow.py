import os
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://survey-poc.preview.emergentagent.com").rstrip("/")


def test_complete_feedback_flow():
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"full_name": "Test Owner", "email": email, "password": "testing123"})
    assert r.status_code == 200 and r.json()["user"]["email"] == email
    token = r.json()["access_token"]
    assert r.cookies.get("access_token")
    auth = {"Authorization": f"Bearer {token}"}
    assert s.get(f"{BASE_URL}/api/auth/me", headers=auth).status_code == 200
    assert requests.get(f"{BASE_URL}/api/templates").status_code == 401

    r = s.post(f"{BASE_URL}/api/workspaces", headers=auth, json={"name": "Test Restaurant", "business_type": "Restaurant"})
    assert r.status_code == 200
    r = s.post(f"{BASE_URL}/api/templates/from-preset/Restaurant%20Experience", headers=auth)
    assert r.status_code == 200
    template = r.json()
    r = s.post(f"{BASE_URL}/api/templates/{template['id']}/publish", headers=auth)
    assert r.status_code == 200 and r.json()["public_slug"]
    slug = r.json()["public_slug"]
    public = s.get(f"{BASE_URL}/api/public/feedback/{slug}")
    assert public.status_code == 200
    questions = public.json()["template"]["questions"]
    values = [5, 5, 4, "Yes", "Great food and friendly service"]
    r = s.post(f"{BASE_URL}/api/public/feedback/{slug}/responses", json={"answers": [{"question_id": q["id"], "value": v} for q, v in zip(questions, values)]})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert s.get(f"{BASE_URL}/api/responses", headers=auth).json()
    analytics = s.get(f"{BASE_URL}/api/analytics", headers=auth)
    assert analytics.status_code == 200 and analytics.json()["total"] >= 1
    assert analytics.json()["average"] == 4.7