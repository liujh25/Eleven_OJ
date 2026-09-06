from __future__ import annotations

from sqlalchemy import func, select

from oj.db import SessionFactory
from oj.judge_tasks import run_submission
from oj.models import AccessAudit, AITask, Problem, Submission, TestCaseResult, User
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
    keyword = await api.get("/api/problems/", params={"keyword": "整数 数学"})
    assert [item["id"] for item in keyword.json()["data"]] == ["sum_2"]
    title_keyword = await api.get("/api/problems/", params={"keyword": "两数"})
    assert [item["id"] for item in title_keyword.json()["data"]] == ["sum_2"]
    combined = await api.get("/api/problems/", params={"tag": "基础", "keyword": "sum_2"})
    assert [item["id"] for item in combined.json()["data"]] == ["sum_2"]
    no_keyword_match = await api.get("/api/problems/", params={"keyword": "图论"})
    assert no_keyword_match.json()["data"] == []
    blank_keyword = await api.get("/api/problems/", params={"keyword": "   "})
    assert blank_keyword.status_code == 400
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


async def test_problem_defaults_and_testcases_visible_to_normal_user(api):
    await login(api, "admin", "admintestpassword")
    body = problem_body("inherited_limits")
    body.pop("time_limit")
    body.pop("memory_limit")
    assert (await api.post("/api/problems/", json=body)).status_code == 200
    await api.post("/api/users/", json={"username": "alice", "password": "secret1"})
    api.cookies.clear()
    await login(api, "alice", "secret1")
    detail = (await api.get("/api/problems/inherited_limits")).json()["data"]
    assert detail["time_limit"] == 3.0
    assert detail["memory_limit"] == 128
    assert detail["testcases"] == [
        {"input": "1 2", "output": "3"},
        {"input": "-5 5", "output": "0"},
    ]

    async with SessionFactory() as db:
        stored = await db.get(Problem, "inherited_limits")
        assert stored is not None
        assert stored.time_limit == 0
        assert stored.memory_limit == 0


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
    c_language = await api.post(
        "/api/languages/",
        json={
            "name": "c",
            "file_ext": ".c",
            "compile_cmd": "gcc {src} -std=c11 -O2 -o {exe}",
            "run_cmd": "{exe}",
        },
    )
    assert c_language.status_code == 200
    assert "c" in (await api.get("/api/languages/")).json()["data"]["name"]
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


async def test_problem_submission_scope_and_per_user_counts(api):
    await login(api, "admin", "admintestpassword")
    await api.post("/api/problems/", json=problem_body())
    alice = await api.post("/api/users/", json={"username": "alice", "password": "secret1"})
    bob = await api.post("/api/users/", json={"username": "bobby", "password": "secret1"})
    alice_id = alice.json()["data"]["user_id"]
    bob_id = bob.json()["data"]["user_id"]
    alice_one = Submission(
        user_id=alice_id,
        problem_id="sum_2",
        language="python",
        code="print(3)",
        status="success",
        score=20,
        counts=20,
    )
    alice_two = Submission(
        user_id=alice_id,
        problem_id="sum_2",
        language="python",
        code="print(3)",
        status="success",
        score=20,
        counts=20,
    )
    bob_one = Submission(
        user_id=bob_id,
        problem_id="sum_2",
        language="python",
        code="print(0)",
        status="success",
        score=0,
        counts=20,
    )
    async with SessionFactory() as db:
        db.add_all([alice_one, alice_two, bob_one])
        await db.commit()

    admin_view = (await api.get("/api/submissions/", params={"problem_id": "sum_2"})).json()["data"]
    assert admin_view["total"] == 3
    assert {item["submission_id"] for item in admin_view["submissions"]} == {
        alice_one.id,
        alice_two.id,
        bob_one.id,
    }

    api.cookies.clear()
    await login(api, "alice", "secret1")
    alice_view = (await api.get("/api/submissions/", params={"problem_id": "sum_2"})).json()["data"]
    assert alice_view["total"] == 2
    assert {item["submission_id"] for item in alice_view["submissions"]} == {
        alice_one.id,
        alice_two.id,
    }
    profile = (await api.get(f"/api/users/{alice_id}")).json()["data"]
    assert profile["submit_count"] == 2
    assert profile["resolve_count"] == 1

    api.cookies.clear()
    await login(api, "admin", "admintestpassword")
    bob_profile = (await api.get(f"/api/users/{bob_id}")).json()["data"]
    assert bob_profile["submit_count"] == 1
    assert bob_profile["resolve_count"] == 0


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
    assert {entry["action"] for entry in audits.json()["data"]} == {"view_logs"}


async def test_delete_problem_cascades_all_related_records(api):
    await login(api, "admin", "admintestpassword")
    await api.post("/api/problems/", json=problem_body())
    async with SessionFactory() as db:
        submission = Submission(
            user_id="admin",
            problem_id="sum_2",
            language="python",
            code="print(3)",
            status="success",
            score=10,
            counts=20,
        )
        db.add(submission)
        await db.flush()
        db.add_all(
            [
                TestCaseResult(submission_id=submission.id, case_number=1, result="AC"),
                AccessAudit(
                    user_id="admin",
                    problem_id="sum_2",
                    submission_id=submission.id,
                    action="view_logs",
                    status="200",
                ),
                AITask(
                    user_id="admin",
                    requirement="refine the existing problem",
                    problem_id="sum_2",
                ),
            ]
        )
        await db.commit()

    assert (await api.delete("/api/problems/sum_2")).status_code == 200
    async with SessionFactory() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Submission).where(Submission.problem_id == "sum_2")
            )
            == 0
        )
        assert await db.scalar(select(func.count()).select_from(TestCaseResult)) == 0
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AccessAudit)
                .where(AccessAudit.problem_id == "sum_2")
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(AITask).where(AITask.problem_id == "sum_2")
            )
            == 0
        )


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
