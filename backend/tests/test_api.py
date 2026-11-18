import json
import os
import tempfile

os.environ["PARPTE_DISABLE_ML"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["ADMIN_EMAILS"] = "dev@parpte.test"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _client():
    c = TestClient(app)
    c.__enter__()
    return c


c = _client()


def _auth(email, pw="password123"):
    r = c.post("/api/auth/register", json={"email": email, "password": pw})
    if r.status_code == 409:
        r = c.post("/api/auth/login", json={"email": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def test_meta_lists_22_scored_tasks():
    m = c.get("/api/meta").json()
    assert len([t for t in m["tasks"] if t["scored"]]) == 22


def test_admin_gets_premium_and_free_user_quota():
    h, u = _auth("dev@parpte.test")
    assert u["role"] == "admin" and u["plan"] == "premium"
    h2, u2 = _auth("student@parpte.test")
    assert u2["plan"] == "free"
    for i in range(15):
        r = c.post("/api/score/wfd-001", headers=h2, data={"response": json.dumps({"text": "x"})})
        assert r.status_code == 200  # objective tasks never consume quota
    q = c.get("/api/questions/swt-001", headers=h2).json()
    assert "key_points" not in q
    for i in range(15):
        assert c.post("/api/score/swt-001", headers=h2, data={"response": json.dumps({"text": "Short one."})}).status_code == 200
    assert c.post("/api/score/swt-001", headers=h2, data={"response": json.dumps({"text": "Short one."})}).status_code == 402


def test_score_and_progress():
    h, _ = _auth("dev@parpte.test")
    r = c.post("/api/score/mcsa-001", headers=h, data={"response": json.dumps({"answer": "B"})}).json()
    assert r["score"] == 1 and r["reveal"]["answer"] == "B"
    p = c.get("/api/progress", headers=h).json()
    assert p["predicted"]["skills"]["reading"] == 90 and p["streak"] >= 1


def test_mock_flow():
    h, _ = _auth("dev@parpte.test")
    m = c.post("/api/mock", headers=h, json={"kind": "mini", "module": "reading"}).json()
    assert m["count"] >= 5 and all(q["task"] in {"rw_fill_blanks", "mcq_multiple_reading", "reorder_paragraphs", "reading_fill_blanks",
                                                 "mcq_single_reading"} for q in m["questions"])
    first = m["questions"][0]
    r = c.post(f"/api/mock/{m['id']}/answer/{first['id']}", headers=h, data={"response": "{}"})
    assert r.json() == {"ok": True, "attempt_id": r.json()["attempt_id"]}
    done = c.post(f"/api/mock/{m['id']}/finish", headers=h).json()
    assert done["result"]["skills"]["reading"] is not None
    _, _ = _auth("student@parpte.test")
    h2, _ = _auth("student@parpte.test")
    assert c.post("/api/mock", headers=h2, json={"kind": "full"}).status_code == 402


def test_admin_add_question_and_plan_change():
    h, _ = _auth("dev@parpte.test")
    r = c.post("/api/admin/questions", headers=h, json={"task": "write_from_dictation", "data": {"text": "Practice makes perfect."}})
    assert r.status_code == 200, r.text
    assert any(q["id"] == r.json()["id"] for q in c.get("/api/questions?task=write_from_dictation", headers=h).json())
    users = c.get("/api/admin/users", headers=h).json()
    sid = next(u["id"] for u in users if u["email"] == "student@parpte.test")
    assert c.patch(f"/api/admin/users/{sid}", headers=h, json={"plan": "pro"}).json()["plan"] == "pro"
    h2, _ = _auth("student@parpte.test")
    assert c.get("/api/admin/users", headers=h2).status_code == 403
