from __future__ import annotations

from sqlalchemy import select

from oj.db import SessionFactory
from oj.judge_tasks import run_submission
from oj.models import Submission, TestCaseResult, User
from oj.routers.users import difficulty_level_gain
from tests.conftest import login, problem_body


def test_difficulty_level_gain():
    assert difficulty_level_gain("简单") == 1
    assert difficulty_level_gain("medium") == 2
    assert difficulty_level_gain("困难") == 3
    assert difficulty_level_gain("") == 1


async def test_user_auth_and_permissions(api):
    response = await api.get("/api/users/admin")
    assert response.status_code == 401
    assert response.json()["code"] == 401

    registered = await api.post("/api/users/", json={"username": "alice", "password": "secret1"})
    assert registered.status_code == 200
    user_id = registered.json()["data"]["user_id"]
    duplicate = await api.post("/api/users/", json={"username": "alice", "password": "secret1"})
    assert duplicate.status_code == 400

    await login(api, "alice", "secret1")
    mine = await api.get(f"/api/users/{user_id}")
    assert mine.json()["data"]["username"] == "alice"
    denied = await api.get("/api/users/admin")
    assert denied.status_code == 403
    users = await api.get("/api/users/")
    assert users.status_code == 403

    api.cookies.clear()
    await login(api, "admin", "admintestpassword")
    changed = await api.put(f"/api/users/{user_id}/role", json={"role": "banned"})
    assert changed.status_code == 200
    api.cookies.clear()
    banned = await api.post("/api/auth/login", json={"username": "alice", "password": "secret1"})
    assert banned.status_code == 403


async def test_problem_crud_and_validation(api):
    await login(api, "admin", "admintestpassword")
    created = await api.post("/api/problems/", json=problem_body())
    assert created.json() == {"code": 200, "msg": "add success", "data": {"id": "sum_2"}}
    duplicate = await api.post("/api/problems/", json=problem_body())
    assert duplicate.status_code == 409
    listing = await api.get("/api/problems/")
    assert listing.json()["data"] == [
        {
            "id": "sum_2",
            "title": "两数之和",
            "tags": ["基础", "数学"],
            "difficulty": "",
        }
    ]
    tagged = await api.get("/api/problems/", params={"tag": " 数学 "})
    assert [item["id"] for item in tagged.json()["data"]] == ["sum_2"]
    missing_tag = await api.get("/api/problems/", params={"tag": "图论"})
    assert missing_tag.json()["data"] == []
    blank_tag = await api.get("/api/problems/", params={"tag": "   "})
    assert blank_tag.status_code == 400
    detail = (await api.get("/api/problems/sum_2")).json()["data"]
    assert detail["hint"] == ""
    assert detail["time_limit"] == 1.0
    invalid = problem_body()
    invalid["id"] = "other"
    assert (await api.put("/api/problems/sum_2", json=invalid)).status_code == 400
    invalid = problem_body("bad id")
    assert (await api.post("/api/problems/", json=invalid)).status_code == 400
    assert (await api.delete("/api/problems/sum_2")).status_code == 200
    assert (await api.get("/api/problems/sum_2")).status_code == 404


async def test_language_registry_and_auth_precedence(api):
    invalid_without_login = await api.post("/api/problems/", json={})
    assert invalid_without_login.status_code == 401
    await login(api, "admin", "admintestpassword")
    languages = (await api.get("/api/languages/")).json()["data"]["name"]
    assert languages == ["cpp", "python"]
    created = await api.post(
        "/api/languages/",
        json={
            "name": "pypy",
            "file_ext": ".py",
            "run_cmd": "python {src}",
            "time_limit": 2,
            "memory_limit": 256,
        },
    )
    assert created.status_code == 200
    unsafe = await api.post(
        "/api/languages/",
        json={"name": "unsafe", "file_ext": ".py", "run_cmd": "python {src}; whoami"},
    )
    assert unsafe.status_code == 400


async def test_submission_queries_rejudge_and_rate_limit(api):
    user = await login(api, "admin", "admintestpassword")
    await api.post("/api/problems/", json=problem_body())
    for _ in range(3):
        response = await api.post(
            "/api/submissions/",
            json={
                "problem_id": "sum_2",
                "language": "python",
                "code": "a,b=map(int,input().split());print(a+b)",
            },
        )
        assert response.status_code == 200
    limited = await api.post(
        "/api/submissions/",
        json={"problem_id": "sum_2", "language": "python", "code": "print(3)"},
    )
    assert limited.status_code == 429
    listing = await api.get("/api/submissions/", params={"user_id": user["user_id"]})
    assert listing.json()["data"]["total"] == 3
    assert (await api.get("/api/submissions/")).status_code == 400
    assert (
        await api.get("/api/submissions/", params={"user_id": user["user_id"], "page": 1})
    ).status_code == 400
    submission_id = listing.json()["data"]["submissions"][0]["submission_id"]
    rejudged = await api.put(f"/api/submissions/{submission_id}/rejudge")
    assert rejudged.json()["data"]["status"] == "pending"


async def test_submission_worker_persists_results(api):
    admin = await login(api, "admin", "admintestpassword")
    await api.post("/api/problems/", json=problem_body())
    created = await api.post(
        "/api/submissions/",
        json={
            "problem_id": "sum_2",
            "language": "python",
            "code": "a,b=map(int,input().split());print(a+b)",
        },
    )
    submission_id = created.json()["data"]["submission_id"]
    await run_submission(submission_id)
    detail = (await api.get(f"/api/submissions/{submission_id}")).json()["data"]
    assert detail["status"] == "success"
    assert detail["score"] == detail["counts"] == 20
    log = (await api.get(f"/api/submissions/{submission_id}/log")).json()["data"]
    assert [item["result"] for item in log["details"]] == ["AC", "AC"]
    profile = (await api.get(f"/api/users/{admin['user_id']}")).json()["data"]
    assert profile["resolve_count"] == 1
    assert profile["level"] == 2
    assert profile["level_gain"] == 1


async def test_logs_visibility_and_access_audit(api):
    await login(api, "admin", "admintestpassword")
    await api.post("/api/problems/", json=problem_body())
    registered = await api.post("/api/users/", json={"username": "alice", "password": "secret1"})
    alice_id = registered.json()["data"]["user_id"]
    async with SessionFactory() as db:
        item = Submission(
            user_id="admin",
            problem_id="sum_2",
            language="python",
            code="print(3)",
            status="success",
            score=10,
            counts=20,
        )
        db.add(item)
        await db.flush()
        db.add(TestCaseResult(submission_id=item.id, case_number=1, result="AC"))
        await db.commit()
        submission_id = item.id

    api.cookies.clear()
    await login(api, "alice", "secret1")
    denied = await api.get(f"/api/submissions/{submission_id}/log")
    assert denied.status_code == 403
    api.cookies.clear()
    await login(api, "admin", "admintestpassword")
    visible = await api.put("/api/problems/sum_2/log_visibility", json={"public_cases": True})
    assert visible.status_code == 200
    api.cookies.clear()
    await login(api, "alice", "secret1")
    allowed = await api.get(f"/api/submissions/{submission_id}/log")
    assert allowed.json()["data"]["details"][0]["result"] == "AC"
    api.cookies.clear()
    await login(api, "admin", "admintestpassword")
    audits = await api.get("/api/logs/access/", params={"user_id": alice_id})
    assert {entry["status"] for entry in audits.json()["data"]} == {"200", "403"}


async def test_reset_recreates_initial_state(api):
    await login(api, "admin", "admintestpassword")
    await api.post("/api/users/", json={"username": "alice", "password": "secret1"})
    response = await api.post("/api/reset/")
    assert response.status_code == 200
    assert not api.cookies
    await login(api, "admin", "admintestpassword")
    users = (await api.get("/api/users/")).json()["data"]
    assert users["total"] == 1
    async with SessionFactory() as db:
        assert await db.scalar(select(User.id).where(User.username == "alice")) is None
