from __future__ import annotations

import json
import time

import streamlit as st

try:
    from frontend.client import APIError, OJClient
except ModuleNotFoundError as exc:
    if exc.name != "frontend":
        raise
    # Streamlit may prepend the script directory instead of the project root.
    from client import APIError, OJClient

st.set_page_config(page_title="Async OJ", page_icon="⚡", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.8rem; max-width: 1180px;}
    [data-testid="stMetric"] {
      background:#f7f9fc; border:1px solid #e7eaf0; padding:12px; border-radius:12px;
    }
    .hero {
      padding:1.4rem 1.7rem; border-radius:18px;
      background:linear-gradient(120deg,#172554,#2563eb); color:white; margin-bottom:1.2rem;
    }
    .hero h1 {margin:0;color:white}.hero p {margin:.35rem 0 0;color:#dbeafe}
    </style>
    """,
    unsafe_allow_html=True,
)


def client() -> OJClient:
    if "api" not in st.session_state:
        st.session_state.api = OJClient()
    return st.session_state.api


def show_error(exc: Exception) -> None:
    if isinstance(exc, APIError):
        st.error(f"请求失败（{exc.status or '网络'}）：{exc}")
    else:
        st.error(f"操作失败：{exc}")


def require_login() -> dict | None:
    user = st.session_state.get("user")
    if not user:
        st.info("请先登录后使用此功能。")
        return None
    return user


def hero() -> None:
    st.markdown(
        '<div class="hero"><h1>⚡ Async OJ</h1><p>异步评测 · 细粒度权限 · AI 辅助命题</p></div>',
        unsafe_allow_html=True,
    )


def auth_page() -> None:
    st.header("账户")
    user = st.session_state.get("user")
    if user:
        c1, c2, c3 = st.columns(3)
        c1.metric("用户名", user["username"])
        c2.metric("用户 ID", user["user_id"])
        c3.metric("角色", user["role"])
        if st.button("退出登录", type="primary"):
            try:
                client().post("/api/auth/logout")
            except APIError:
                pass
            st.session_state.pop("user", None)
            st.rerun()
        return
    login_tab, register_tab = st.tabs(["登录", "注册"])
    with login_tab, st.form("login"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        if st.form_submit_button("登录", type="primary"):
            try:
                st.session_state.user = client().post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                st.success("登录成功")
                st.rerun()
            except Exception as exc:
                show_error(exc)
    with register_tab, st.form("register"):
        username = st.text_input("新用户名")
        password = st.text_input("新密码（至少 6 位）", type="password")
        if st.form_submit_button("创建账户"):
            try:
                client().post("/api/users/", json={"username": username, "password": password})
                st.success("注册成功，请返回登录。")
            except Exception as exc:
                show_error(exc)


def profile_page() -> None:
    user = require_login()
    if not user:
        return
    st.header("个人信息")
    try:
        data = client().get(f"/api/users/{user['user_id']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("用户名", data["username"])
        c2.metric("角色", data["role"])
        c3.metric("提交次数", data["submit_count"])
        c4.metric("通过题数", data["resolve_count"])
        st.caption(f"加入时间：{data['join_time']} · 用户 ID：{data['user_id']}")
    except Exception as exc:
        show_error(exc)


def admin_page() -> None:
    user = require_login()
    if not user:
        return
    if user["role"] != "admin":
        st.warning("此页面仅管理员可见。")
        return
    st.header("用户管理")
    try:
        data = client().get("/api/users/", params={"page": 1, "page_size": 100})
        st.dataframe(data["users"], width="stretch", hide_index=True)
        with st.form("role"):
            user_id = st.selectbox(
                "用户",
                [item["user_id"] for item in data["users"]],
                format_func=lambda value: next(
                    f"{item['username']} ({item['role']})"
                    for item in data["users"]
                    if item["user_id"] == value
                ),
            )
            role = st.selectbox("新角色", ["user", "admin", "banned"])
            if st.form_submit_button("更新角色"):
                client().put(f"/api/users/{user_id}/role", json={"role": role})
                st.success("角色已更新")
                st.rerun()
    except Exception as exc:
        show_error(exc)


def problem_payload(prefix: str, existing: dict | None = None) -> dict | None:
    value = existing or {}
    with st.form(f"problem-{prefix}"):
        c1, c2 = st.columns([1, 2])
        problem_id = c1.text_input("题目 ID", value=value.get("id", ""), disabled=bool(existing))
        title = c2.text_input("标题", value=value.get("title", ""))
        description = st.text_area("题目描述", value=value.get("description", ""), height=120)
        input_description = st.text_area("输入格式", value=value.get("input_description", ""))
        output_description = st.text_area("输出格式", value=value.get("output_description", ""))
        constraints = st.text_area("数据范围", value=value.get("constraints", ""))
        samples = st.text_area(
            "样例 JSON",
            value=json.dumps(
                value.get("samples", [{"input": "1 2\n", "output": "3\n"}]),
                ensure_ascii=False,
                indent=2,
            ),
            height=130,
        )
        testcases = st.text_area(
            "测试点 JSON",
            value=json.dumps(
                value.get("testcases", [{"input": "1 2\n", "output": "3\n"}]),
                ensure_ascii=False,
                indent=2,
            ),
            height=160,
        )
        c1, c2, c3 = st.columns(3)
        time_limit = c1.number_input(
            "时间限制（秒）", 0.05, 60.0, float(value.get("time_limit", 3.0))
        )
        memory_limit = c2.number_input(
            "内存限制（MB）", 16, 2048, int(value.get("memory_limit", 128))
        )
        difficulty = c3.text_input("难度", value=value.get("difficulty", ""))
        tags = st.text_input("标签（逗号分隔）", value=", ".join(value.get("tags", [])))
        hint = st.text_input("提示", value=value.get("hint", ""))
        source = st.text_input("来源", value=value.get("source", ""))
        author = st.text_input("作者", value=value.get("author", ""))
        submitted = st.form_submit_button("保存题目", type="primary")
    if not submitted:
        return None
    return {
        "id": value.get("id", problem_id),
        "title": title,
        "description": description,
        "input_description": input_description,
        "output_description": output_description,
        "samples": json.loads(samples),
        "constraints": constraints,
        "testcases": json.loads(testcases),
        "hint": hint,
        "source": source,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
        "time_limit": time_limit,
        "memory_limit": memory_limit,
        "author": author,
        "difficulty": difficulty,
    }


def problems_page() -> None:
    if not require_login():
        return
    st.header("题目中心")
    try:
        items = client().get("/api/problems/")
    except Exception as exc:
        show_error(exc)
        return
    list_tab, create_tab, edit_tab = st.tabs(["题目列表", "新增题目", "编辑题目"])
    with list_tab:
        if not items:
            st.info("题库为空，请新增第一道题。")
        for item in items:
            with st.expander(f"{item['id']} · {item['title']}"):
                try:
                    problem = client().get(f"/api/problems/{item['id']}")
                    st.markdown(problem["description"])
                    st.code(problem["input_description"], language=None)
                    st.write("样例", problem["samples"])
                    limits = f"时限 {problem['time_limit']}s · 内存 {problem['memory_limit']}MB"
                    st.caption(f"{limits} · {', '.join(problem['tags'])}")
                    if st.session_state.user["role"] == "admin" and st.button(
                        "删除", key=f"delete-{item['id']}"
                    ):
                        client().delete(f"/api/problems/{item['id']}")
                        st.rerun()
                except Exception as exc:
                    show_error(exc)
    with create_tab:
        try:
            payload = problem_payload("create", st.session_state.pop("ai_problem", None))
            if payload:
                client().post("/api/problems/", json=payload)
                st.success("题目已新增")
        except Exception as exc:
            show_error(exc)
    with edit_tab:
        if items:
            selected = st.selectbox("选择题目", [item["id"] for item in items])
            try:
                existing = client().get(f"/api/problems/{selected}")
                payload = problem_payload("edit", existing)
                if payload:
                    client().put(f"/api/problems/{selected}", json=payload)
                    st.success("题目已更新")
            except Exception as exc:
                show_error(exc)


def submissions_page() -> None:
    user = require_login()
    if not user:
        return
    st.header("评测中心")
    submit_tab, records_tab, detail_tab = st.tabs(["提交代码", "提交记录", "结果详情"])
    with submit_tab:
        try:
            problems = client().get("/api/problems/")
            languages = client().get("/api/languages/")["name"]
            if not problems:
                st.info("暂无题目。")
            else:
                with st.form("submit-code"):
                    problem_id = st.selectbox("题目", [item["id"] for item in problems])
                    language = st.selectbox("语言", languages)
                    code = st.text_area("代码", height=320)
                    if st.form_submit_button("提交评测", type="primary"):
                        data = client().post(
                            "/api/submissions/",
                            json={"problem_id": problem_id, "language": language, "code": code},
                        )
                        st.session_state.last_submission = data["submission_id"]
                        st.success(f"提交成功：{data['submission_id']}")
        except Exception as exc:
            show_error(exc)
    with records_tab:
        try:
            data = client().get(
                "/api/submissions/",
                params={"user_id": user["user_id"], "page": 1, "page_size": 100},
            )
            st.metric("提交总数", data["total"])
            st.dataframe(data["submissions"], width="stretch", hide_index=True)
        except Exception as exc:
            show_error(exc)
    with detail_tab:
        submission_id = st.text_input(
            "Submission ID", value=st.session_state.get("last_submission", "")
        )
        auto = st.checkbox("自动轮询一次", value=False)
        if st.button("查询结果") or (auto and submission_id):
            try:
                result = client().get(f"/api/submissions/{submission_id}")
                st.status(
                    f"状态：{result['status']}",
                    state="running" if result["status"] == "pending" else "complete",
                )
                if result["status"] != "pending":
                    c1, c2 = st.columns(2)
                    c1.metric("得分", result.get("score", 0))
                    c2.metric("总分", result.get("counts", 0))
                    st.write("编译信息", result.get("compile_info"))
                    st.write("运行信息", result.get("run_info"))
                    if result.get("error_info"):
                        st.error(result["error_info"])
                    try:
                        log = client().get(f"/api/submissions/{submission_id}/log")
                        st.dataframe(log["details"], width="stretch", hide_index=True)
                    except APIError as exc:
                        st.info(f"测试点日志不可见：{exc}")
                elif auto:
                    time.sleep(1)
                    st.rerun()
            except Exception as exc:
                show_error(exc)


def ai_page() -> None:
    if not require_login():
        return
    st.header("AI 智能命题")
    config_tab, author_tab, history_tab = st.tabs(["模型配置", "智能命题", "任务记录"])
    with config_tab:
        st.info("模型密钥加密保存在后端，不会在查询、日志或页面中回显。")
        with st.form("ai-config"):
            provider_url = st.text_input("提供商 URL", placeholder="https://provider.example/v1")
            model = st.text_input("模型名称")
            api_key = st.text_input("模型密钥", type="password")
            c1, c2, c3 = st.columns(3)
            input_price = c1.number_input("输入价格", min_value=0.0, format="%.6f")
            output_price = c2.number_input("输出价格", min_value=0.0, format="%.6f")
            price_unit = c3.number_input("计价 Token 数", min_value=1, value=1_000_000)
            if st.form_submit_button("保存配置", type="primary"):
                try:
                    client().put(
                        "/api/ai/model-config",
                        json={
                            "provider_url": provider_url,
                            "model": model,
                            "api_key": api_key,
                            "input_price": input_price,
                            "output_price": output_price,
                            "price_unit": price_unit,
                        },
                    )
                    st.success("模型配置已安全保存")
                except Exception as exc:
                    show_error(exc)
    with author_tab:
        try:
            problems = client().get("/api/problems/")
        except Exception:
            problems = []
        with st.form("ai-author"):
            requirement = st.text_area(
                "命题需求",
                placeholder="例如：设计一道面向初学者的列表与循环题，难度中等，包含规模边界测试。",
                height=180,
            )
            reference = st.selectbox(
                "参考或修改已有题目（可选）",
                [""] + [item["id"] for item in problems],
            )
            if st.form_submit_button("开始命题", type="primary"):
                try:
                    data = client().post(
                        "/api/ai/problem-tasks/",
                        json={"requirement": requirement, "problem_id": reference or None},
                    )
                    st.session_state.ai_task_id = data["task_id"]
                    st.success(f"任务已创建：{data['task_id']}")
                except Exception as exc:
                    show_error(exc)
        task_id = st.text_input("当前任务 ID", value=st.session_state.get("ai_task_id", ""))
        c1, c2 = st.columns(2)
        if c1.button("刷新进度", disabled=not task_id):
            try:
                task = client().get(f"/api/ai/problem-tasks/{task_id}")
                st.write(f"**{task['status']}** · {task['progress']}")
                u1, u2, u3 = st.columns(3)
                u1.metric("输入 Token", task["usage"]["input_tokens"])
                u2.metric("输出 Token", task["usage"]["output_tokens"])
                u3.metric("费用 USD", f"{task['usage']['cost']:.8f}")
                if task.get("error"):
                    st.error(task["error"])
                if task.get("result"):
                    st.json(task["result"])
                    st.session_state.ai_result = task["result"]
            except Exception as exc:
                show_error(exc)
        if c2.button("中断任务", disabled=not task_id):
            try:
                client().put(f"/api/ai/problem-tasks/{task_id}/cancel")
                st.warning("任务已中断")
            except Exception as exc:
                show_error(exc)
        if st.session_state.get("ai_result") and st.button("导入题目新增表单"):
            st.session_state.ai_problem = st.session_state.ai_result["problem"]
            st.success("已导入。请前往“题目中心 → 新增题目”审阅并保存。")
    with history_tab:
        try:
            tasks = client().get("/api/ai/problem-tasks/")
            rows = [
                {
                    "task_id": item["task_id"],
                    "status": item["status"],
                    "progress": item["progress"],
                    "tokens": item["usage"]["total_tokens"],
                    "cost": item["usage"]["cost"],
                }
                for item in tasks
            ]
            st.dataframe(rows, width="stretch", hide_index=True)
        except Exception as exc:
            show_error(exc)


hero()
current = st.session_state.get("user")
st.sidebar.caption(
    f"已登录：{current['username']} ({current['role']})" if current else "当前未登录"
)
pages = ["账户", "个人信息", "题目中心", "评测中心", "AI 智能命题"]
if current and current["role"] == "admin":
    pages.append("用户管理")
page = st.sidebar.radio("导航", pages)
{
    "账户": auth_page,
    "个人信息": profile_page,
    "题目中心": problems_page,
    "评测中心": submissions_page,
    "AI 智能命题": ai_page,
    "用户管理": admin_page,
}[page]()
