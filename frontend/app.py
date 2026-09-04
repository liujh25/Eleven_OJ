from __future__ import annotations

import base64
import json
import time
from html import escape
from pathlib import Path

import streamlit as st

try:
    from frontend.client import APIError, OJClient
except ModuleNotFoundError as exc:
    if exc.name != "frontend":
        raise
    # Streamlit may prepend the script directory instead of the project root.
    from client import APIError, OJClient

ASSET_ROOT = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Async OJ",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
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


@st.cache_data(show_spinner=False)
def character_data_uri() -> str:
    path = ASSET_ROOT / "home_character.png"
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def set_page(page: str) -> None:
    st.session_state.nav_page = page


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


def dashboard_page() -> None:
    current = st.session_state.get("user")
    profile = {
        "username": "访客",
        "role": "guest",
        "resolve_count": 0,
        "ai_problem_count": 0,
        "level": 1,
    }
    if current:
        try:
            profile = client().get(f"/api/users/{current['user_id']}")
        except Exception as exc:
            show_error(exc)
            profile.update(current)
    image_uri = character_data_uri()
    background = f"url('{image_uri}')" if image_uri else "none"
    st.markdown(
        f"""
        <style>
        .block-container {{max-width:1500px;padding-top:1.1rem;padding-bottom:1rem}}
        .stApp {{
          background:
            radial-gradient(circle at 72% 12%,rgba(37,99,235,.2),transparent 28%),
            linear-gradient(115deg,#05080d 0%,#111923 58%,#dfe4e8 58.1%,#f8fafc 100%);
        }}
        .operator-visual {{
          min-height:760px;position:relative;overflow:hidden;
          background-image:linear-gradient(180deg,transparent 60%,rgba(4,8,13,.96)),{background};
          background-size:contain;background-repeat:no-repeat;background-position:center bottom;
          border:1px solid rgba(148,163,184,.2);box-shadow:0 22px 70px rgba(0,0,0,.42);
          clip-path:polygon(0 0,94% 0,100% 8%,100% 100%,7% 100%,0 92%);
        }}
        .operator-code {{
          position:absolute;top:24px;left:28px;color:#dbeafe;letter-spacing:.2em;
          font:700 13px/1.4 'Segoe UI',sans-serif;border-left:4px solid #f97316;
          padding-left:12px;text-shadow:0 2px 8px #000;
        }}
        .level-ring {{
          position:absolute;left:34px;bottom:82px;width:132px;height:132px;border-radius:50%;
          border:4px solid #f8fafc;box-shadow:0 0 0 7px rgba(37,99,235,.72),0 8px 30px #000;
          display:flex;flex-direction:column;align-items:center;justify-content:center;
          color:white;background:rgba(4,8,13,.78);backdrop-filter:blur(8px);
        }}
        .level-ring strong {{font:800 54px/1 'Segoe UI',sans-serif}}
        .level-ring span {{font:700 15px/1.5 'Segoe UI',sans-serif;letter-spacing:.16em}}
        .operator-name {{
          position:absolute;left:190px;bottom:93px;color:white;
          font:800 30px/1.1 'Segoe UI',sans-serif;
          text-shadow:0 3px 12px #000;border-bottom:3px solid #f97316;padding:0 30px 10px 0;
        }}
        .operator-name small {{display:block;font-size:12px;letter-spacing:.18em;color:#94a3b8}}
        .command-header {{
          padding:20px 24px;margin-bottom:12px;border-top:5px solid #f97316;
          background:rgba(255,255,255,.9);box-shadow:0 12px 32px rgba(15,23,42,.16);
          clip-path:polygon(0 0,97% 0,100% 25%,100% 100%,0 100%);
        }}
        .command-header h1 {{margin:0;color:#111827;font:900 36px/1.1 'Segoe UI',sans-serif}}
        .command-header p {{margin:.4rem 0 0;color:#64748b;letter-spacing:.16em;font-weight:700}}
        .resource-strip {{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0 20px}}
        .resource-item {{
          padding:14px 18px;background:rgba(12,20,30,.9);color:white;border-left:5px solid #2563eb;
          box-shadow:0 8px 24px rgba(15,23,42,.18);
        }}
        .resource-item:nth-child(2) {{border-left-color:#f97316}}
        .resource-item strong {{font:800 32px/1 'Segoe UI',sans-serif;margin-right:10px}}
        .resource-item span {{color:#cbd5e1;font-size:13px}}
        .menu-index {{
          color:#475569;font:800 12px/1 'Segoe UI',sans-serif;letter-spacing:.16em;
          margin:.75rem 0 .3rem;border-left:4px solid #2563eb;padding-left:9px;
        }}
        div[data-testid="stButton"] > button {{
          min-height:74px;justify-content:flex-start;padding:0 24px;border:0;border-radius:2px;
          background:rgba(255,255,255,.94);color:#111827;font-size:1.25rem;font-weight:850;
          border-left:8px solid #f97316;box-shadow:0 10px 25px rgba(15,23,42,.17);
          transition:transform .16s ease,box-shadow .16s ease,background .16s ease;
        }}
        div[data-testid="stButton"] > button:hover {{
          color:#0f172a;background:white;transform:translateX(-6px);
          box-shadow:0 14px 30px rgba(15,23,42,.24);border-left-color:#2563eb;
        }}
        div[data-testid="stButton"] > button:disabled {{
          color:#94a3b8;background:rgba(226,232,240,.84);border-left-color:#94a3b8;
        }}
        .level-rule {{color:#94a3b8;font-size:12px;margin-top:10px;text-align:center}}
        @media (max-width:900px) {{
          .stApp {{background:#0b1119}}
          .operator-visual {{min-height:520px}}
          .command-header {{margin-top:14px}}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    visual_column, command_column = st.columns([1.18, 1], gap="large")
    with visual_column:
        st.markdown(
            f"""
            <div class="operator-visual">
              <div class="operator-code">ASYNC OJ // OPERATOR PROFILE</div>
              <div class="level-ring"><strong>{int(profile["level"])}</strong><span>LV</span></div>
              <div class="operator-name">{escape(str(profile["username"]))}
                <small>{escape(str(profile["role"]).upper())} // CODER</small>
              </div>
            </div>
            <div class="level-rule">难度升级规则：简单 +1 · 中等 +2 · 困难 +3</div>
            """,
            unsafe_allow_html=True,
        )
    with command_column:
        st.markdown(
            f"""
            <div class="command-header">
              <h1>作战终端</h1><p>ONLINE JUDGE CONTROL DECK</p>
            </div>
            <div class="resource-strip">
              <div class="resource-item"><strong>{int(profile["resolve_count"])}</strong>
                <span>已完成题目</span></div>
              <div class="resource-item"><strong>{int(profile["ai_problem_count"])}</strong>
                <span>AI 出题总数</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="menu-index">01 / EXERCISE & JUDGE</div>', unsafe_allow_html=True)
        st.button(
            "▰ 习题与评测　进入做题工作区  ›",
            key="home-workspace",
            width="stretch",
            on_click=set_page,
            args=("题目与评测",),
        )
        account_column, admin_column = st.columns(2)
        with account_column:
            st.markdown('<div class="menu-index">02 / PROFILE</div>', unsafe_allow_html=True)
            target = "个人信息" if current else "账户"
            label = "◈ 个人信息  ›" if current else "◈ 登录 / 注册  ›"
            st.button(
                label,
                key="home-account",
                width="stretch",
                on_click=set_page,
                args=(target,),
            )
        with admin_column:
            st.markdown('<div class="menu-index">ADMIN / USERS</div>', unsafe_allow_html=True)
            is_admin = bool(current and current["role"] == "admin")
            st.button(
                "⬡ 用户管理  ›" if is_admin else "⬡ 用户管理（锁定）",
                key="home-admin",
                width="stretch",
                disabled=not is_admin,
                on_click=set_page if is_admin else None,
                args=("用户管理",) if is_admin else None,
            )
        st.markdown('<div class="menu-index">03 / AI AUTHORING</div>', unsafe_allow_html=True)
        st.button(
            "✦ AI 智能命题　生成、复核与导入  ›",
            key="home-ai",
            width="stretch",
            on_click=set_page,
            args=("AI 智能命题",),
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
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("用户名", data["username"])
        c2.metric("等级", f"LV {data['level']}")
        c3.metric("角色", data["role"])
        c4.metric("提交次数", data["submit_count"])
        c5.metric("完成题目", data["resolve_count"])
        c6.metric("AI 出题", data["ai_problem_count"])
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


def render_problem_statement(problem: dict) -> None:
    st.subheader(f"{problem['id']} · {problem['title']}")
    metadata = [
        f"难度：{problem.get('difficulty') or '未设置'}",
        f"时限：{problem['time_limit']} 秒",
        f"内存：{problem['memory_limit']} MB",
    ]
    if problem.get("tags"):
        metadata.append(f"标签：{' · '.join(problem['tags'])}")
    st.caption("　|　".join(metadata))
    st.markdown(problem["description"] or "暂无题目描述。")
    st.markdown("#### 输入格式")
    st.markdown(problem["input_description"])
    st.markdown("#### 输出格式")
    st.markdown(problem["output_description"])
    st.markdown("#### 样例")
    for number, sample in enumerate(problem.get("samples", []), start=1):
        with st.container(border=True):
            st.caption(f"样例 {number}")
            input_column, output_column = st.columns(2)
            input_column.markdown("**输入**")
            input_column.code(sample.get("input", ""), language=None)
            output_column.markdown("**输出**")
            output_column.code(sample.get("output", ""), language=None)
    st.markdown("#### 数据范围")
    st.markdown(problem["constraints"])
    if problem.get("hint"):
        st.info(f"提示：{problem['hint']}")
    if problem.get("source") or problem.get("author"):
        st.caption(
            f"来源：{problem.get('source') or '未设置'} · 作者：{problem.get('author') or '未设置'}"
        )


def render_submission_result(submission_id: str, auto_refresh: bool = False) -> None:
    result = client().get(f"/api/submissions/{submission_id}")
    state = {"pending": "running", "success": "complete", "error": "error"}.get(
        result["status"], "complete"
    )
    st.status(f"状态：{result['status']}", state=state)
    if result["status"] == "pending":
        if auto_refresh:
            time.sleep(1)
            st.rerun()
        return
    score_column, total_column = st.columns(2)
    score_column.metric("得分", result.get("score", 0))
    total_column.metric("总分", result.get("counts", 0))
    st.write("编译信息", result.get("compile_info"))
    st.write("运行信息", result.get("run_info"))
    if result.get("error_info"):
        st.error(result["error_info"])
    try:
        log = client().get(f"/api/submissions/{submission_id}/log")
        st.dataframe(log["details"], width="stretch", hide_index=True)
    except APIError as exc:
        st.info(f"测试点日志不可见：{exc}")


def problem_management(items: list[dict]) -> None:
    overview_tab, create_tab, edit_tab = st.tabs(["题库概览", "新增题目", "编辑题目"])
    with overview_tab:
        if items:
            st.dataframe(items, width="stretch", hide_index=True)
        else:
            st.info("题库为空，请新增第一道题。")
    with create_tab:
        try:
            payload = problem_payload("create", st.session_state.pop("ai_problem", None))
            if payload:
                client().post("/api/problems/", json=payload)
                st.success("题目已新增")
                st.rerun()
        except Exception as exc:
            show_error(exc)
    with edit_tab:
        if not items:
            st.info("暂无可编辑题目。")
            return
        selected = st.selectbox("选择题目", [item["id"] for item in items])
        try:
            existing = client().get(f"/api/problems/{selected}")
            payload = problem_payload("edit", existing)
            if payload:
                client().put(f"/api/problems/{selected}", json=payload)
                st.success("题目已更新")
                st.rerun()
            if st.button("删除题目", key=f"delete-{selected}", type="secondary"):
                client().delete(f"/api/problems/{selected}")
                st.success("题目已删除")
                st.rerun()
        except Exception as exc:
            show_error(exc)


def workspace_page() -> None:
    user = require_login()
    if not user:
        return
    st.header("题目与评测")
    try:
        all_problems = client().get("/api/problems/")
        languages = client().get("/api/languages/")["name"]
    except Exception as exc:
        show_error(exc)
        return
    tab_names = ["在线做题", "提交记录", "结果详情"]
    if user["role"] == "admin":
        tab_names.append("题目管理")
    tabs = st.tabs(tab_names)
    with tabs[0]:
        try:
            if not all_problems:
                st.info("暂无题目。")
            else:
                all_tags = sorted(
                    {tag for problem in all_problems for tag in problem.get("tags", [])}
                )
                filter_column, selector_column = st.columns([1, 2])
                selected_tag = filter_column.selectbox(
                    "按标签查找", ["全部标签", *all_tags], key="problem_tag"
                )
                visible_problems = all_problems
                if selected_tag != "全部标签":
                    visible_problems = client().get("/api/problems/", params={"tag": selected_tag})
                if not visible_problems:
                    st.warning("没有找到包含该标签的题目。")
                else:
                    problem_ids = [item["id"] for item in visible_problems]
                    if st.session_state.get("workspace_problem") not in problem_ids:
                        st.session_state.workspace_problem = problem_ids[0]
                    selected = selector_column.selectbox(
                        "选择题目",
                        problem_ids,
                        key="workspace_problem",
                        format_func=lambda problem_id: next(
                            f"{item['id']} · {item['title']}"
                            for item in visible_problems
                            if item["id"] == problem_id
                        ),
                    )
                    problem = client().get(f"/api/problems/{selected}")
                    statement_column, judge_column = st.columns([1.15, 1], gap="large")
                    with statement_column:
                        render_problem_statement(problem)
                    with judge_column:
                        st.subheader("提交代码")
                        submitted_now = False
                        with st.form(f"submit-code-{selected}"):
                            language = st.selectbox("语言", languages, key=f"language-{selected}")
                            code = st.text_area(
                                "代码",
                                height=440,
                                key=f"code-{selected}",
                                placeholder="在这里编写并提交你的程序……",
                            )
                            if st.form_submit_button("提交评测", type="primary"):
                                data = client().post(
                                    "/api/submissions/",
                                    json={
                                        "problem_id": selected,
                                        "language": language,
                                        "code": code,
                                    },
                                )
                                st.session_state.last_submission = data["submission_id"]
                                st.session_state.last_problem = selected
                                submitted_now = True
                                st.success(f"提交成功：{data['submission_id']}")
                        latest = st.session_state.get("last_submission")
                        if latest and st.session_state.get("last_problem") == selected:
                            st.markdown("#### 本题最新提交")
                            auto = st.checkbox(
                                "自动刷新结果", value=submitted_now, key=f"auto-{selected}"
                            )
                            render_submission_result(latest, auto_refresh=auto)
        except Exception as exc:
            show_error(exc)
    with tabs[1]:
        try:
            data = client().get(
                "/api/submissions/",
                params={"user_id": user["user_id"], "page": 1, "page_size": 100},
            )
            st.metric("提交总数", data["total"])
            st.dataframe(data["submissions"], width="stretch", hide_index=True)
        except Exception as exc:
            show_error(exc)
    with tabs[2]:
        submission_id = st.text_input(
            "Submission ID", value=st.session_state.get("last_submission", "")
        )
        auto = st.checkbox("自动刷新结果", value=False, key="detail-auto")
        if st.button("查询结果") or (auto and submission_id):
            try:
                render_submission_result(submission_id, auto_refresh=auto)
            except Exception as exc:
                show_error(exc)
    if user["role"] == "admin":
        with tabs[3]:
            problem_management(all_problems)


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
            st.success("已导入。请前往“题目与评测 → 题目管理 → 新增题目”审阅并保存。")
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


current = st.session_state.get("user")
st.sidebar.caption(
    f"已登录：{current['username']} ({current['role']})" if current else "当前未登录"
)
pages = ["首页", "账户", "个人信息", "题目与评测", "AI 智能命题"]
if current and current["role"] == "admin":
    pages.append("用户管理")
if st.session_state.get("nav_page") not in pages:
    st.session_state.nav_page = "首页"
page = st.sidebar.radio("导航", pages, key="nav_page")
if page != "首页":
    hero()
{
    "首页": dashboard_page,
    "账户": auth_page,
    "个人信息": profile_page,
    "题目与评测": workspace_page,
    "AI 智能命题": ai_page,
    "用户管理": admin_page,
}[page]()
