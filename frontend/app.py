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
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
      display:none !important;
    }
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
    if page == "题目与评测":
        st.session_state.workspace_view = "library"


def open_problem(problem_id: str) -> None:
    st.session_state.workspace_problem = problem_id
    st.session_state.workspace_view = "judge"


def show_problem_library() -> None:
    st.session_state.workspace_view = "library"


def show_judge_workspace() -> None:
    st.session_state.workspace_view = "judge"


def show_problem_management(mode: str = "overview") -> None:
    st.session_state.workspace_view = "manage"
    st.session_state.problem_management_mode = mode


def stage_ai_problem(problem: dict) -> None:
    st.session_state.ai_problem = problem
    st.session_state.problem_management_mode = "create"
    st.session_state.workspace_view = "manage"
    st.session_state.nav_page = "题目与评测"


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


def subpage_shell(title: str) -> None:
    section_codes = {
        "账户": "ACCOUNT ACCESS",
        "个人信息": "OPERATOR PROFILE",
        "题目与评测": "EXERCISE & JUDGE",
        "AI 智能命题": "AI AUTHORING",
        "用户管理": "ADMINISTRATION",
    }
    st.markdown(
        """
        <style>
        .block-container {max-width:1380px;padding-top:1rem;padding-bottom:3rem}
        .stApp {
          background:
            linear-gradient(118deg,#07101a 0%,#111d2a 13%,#e5eaf0 13.1%,#f8fafc 100%);
        }
        .subpage-head {
          margin:.6rem 0 1.35rem;padding:21px 28px 20px 34px;color:white;
          background:linear-gradient(100deg,rgba(8,18,30,.98),rgba(25,44,64,.94));
          border-left:8px solid #f97316;border-bottom:3px solid #2563eb;
          box-shadow:0 14px 34px rgba(15,23,42,.24);
          clip-path:polygon(0 0,97% 0,100% 35%,100% 100%,0 100%);
        }
        .subpage-head small {color:#93c5fd;letter-spacing:.2em;font-weight:800}
        .subpage-head h1 {margin:5px 0 0;color:white;font:900 34px/1.15 'Segoe UI',sans-serif}
        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
          border-radius:2px;border:1px solid #cbd5e1;border-left:5px solid #f97316;
          background:white;color:#0f172a;font-weight:800;box-shadow:0 5px 14px rgba(15,23,42,.1);
        }
        div[data-testid="stButton"] > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
          border-color:#2563eb;border-left-color:#2563eb;color:#1d4ed8;
          transform:translateY(-1px);
        }
        div[data-testid="stForm"], div[data-testid="stExpander"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
          background:rgba(255,255,255,.92);border-radius:2px!important;
          border-color:#cbd5e1!important;box-shadow:0 9px 24px rgba(15,23,42,.08);
        }
        [data-baseweb="tab-list"] {
          gap:4px;background:#111c29;padding:5px 8px;border-left:5px solid #2563eb;
        }
        [data-baseweb="tab"] {color:#cbd5e1;font-weight:750;padding:9px 16px}
        [data-baseweb="tab"][aria-selected="true"] {color:white;background:#243449}
        [data-testid="stMetric"] {
          background:rgba(255,255,255,.95);border-radius:2px;border-left:5px solid #2563eb;
          box-shadow:0 8px 20px rgba(15,23,42,.1);
        }
        [data-baseweb="input"], [data-baseweb="select"] > div,
        [data-baseweb="textarea"] {
          border-radius:2px!important;background:#f8fafc!important;
        }
        h2, h3 {color:#0f172a}
        hr {border-color:#94a3b8}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.button(
        "← 返回首页",
        key=f"back-home-{title}",
        on_click=set_page,
        args=("首页",),
    )
    st.markdown(
        f"""
        <div class="subpage-head">
          <small>ASYNC OJ // {section_codes.get(title, "CONTROL")}</small>
          <h1>{escape(title)}</h1>
        </div>
        """,
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
        if st.button("退出登录", key="profile-logout"):
            try:
                client().post("/api/auth/logout")
            except APIError:
                pass
            st.session_state.pop("user", None)
            st.session_state.nav_page = "首页"
            st.rerun()
    except Exception as exc:
        show_error(exc)


def admin_page() -> None:
    user = require_login()
    if not user:
        return
    if user["role"] != "admin":
        st.warning("此页面仅管理员可见。")
        return
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
    try:
        result = client().get(f"/api/submissions/{submission_id}")
    except APIError as exc:
        if exc.status != 403:
            raise
        public_log = client().get(f"/api/submissions/{submission_id}/log")
        st.status("该提交的公开测试日志", state="complete")
        st.info("你只能查看公开的测试点日志；用户代码、编译信息和运行摘要仍不可见。")
        score_column, total_column = st.columns(2)
        score_column.metric("得分", public_log.get("score", 0))
        total_column.metric("总分", public_log.get("counts", 0))
        st.dataframe(public_log["details"], width="stretch", hide_index=True)
        return
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
        if log["details"]:
            st.dataframe(log["details"], width="stretch", hide_index=True)
        else:
            st.info("该题尚未公开测试点明细；你可以查看总得分，但暂时看不到逐点状态。")
    except APIError as exc:
        st.info(f"测试点日志不可见：{exc}")


def problem_management(items: list[dict], *, can_delete: bool) -> None:
    staged_problem = st.session_state.get("ai_problem")
    create_first = (
        bool(staged_problem) or st.session_state.get("problem_management_mode") == "create"
    )
    labels = (
        ["新增题目", "题库概览", "编辑题目"]
        if create_first
        else ["题库概览", "新增题目", "编辑题目"]
    )
    sections = dict(zip(labels, st.tabs(labels), strict=True))
    overview_tab = sections["题库概览"]
    create_tab = sections["新增题目"]
    edit_tab = sections["编辑题目"]
    with overview_tab:
        if items:
            st.dataframe(items, width="stretch", hide_index=True)
        else:
            st.info("题库为空，请新增第一道题。")
    with create_tab:
        if staged_problem:
            st.success(
                f"已载入 AI 题目：{staged_problem['id']} · {staged_problem['title']}。"
                "请审阅后点击保存，保存成功会自动打开新题。"
            )
        try:
            form_suffix = f"ai-{staged_problem['id']}" if staged_problem else "manual"
            payload = problem_payload(f"create-{form_suffix}", staged_problem)
            if payload:
                client().post("/api/problems/", json=payload)
                st.session_state.pop("ai_problem", None)
                st.session_state.problem_management_mode = "overview"
                st.session_state.workspace_problem = payload["id"]
                st.session_state.workspace_view = "judge"
                st.session_state.problem_notice = f"题目 {payload['id']} 已新增并进入题库。"
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
            if can_delete:
                if st.button("删除题目", key=f"delete-{selected}", type="secondary"):
                    client().delete(f"/api/problems/{selected}")
                    st.success("题目已删除")
                    st.rerun()
            else:
                st.caption("普通用户可以编辑题目；删除题目仅限管理员。")
        except Exception as exc:
            show_error(exc)


def problem_library_page(all_problems: list[dict]) -> None:
    st.markdown(
        """
        <style>
        .library-intro {
          padding:18px 22px;margin-bottom:14px;background:rgba(15,30,45,.96);color:white;
          border-left:7px solid #2563eb;border-bottom:3px solid #f97316;
          box-shadow:0 10px 26px rgba(15,23,42,.16);
        }
        .library-intro h2 {color:white;margin:0 0 5px;font-size:25px}
        .library-intro p {color:#cbd5e1;margin:0}
        .problem-index {font:800 12px/1 'Segoe UI',sans-serif;color:#2563eb;letter-spacing:.14em}
        .problem-title {font:850 20px/1.35 'Segoe UI',sans-serif;color:#0f172a;margin:5px 0}
        .problem-meta {color:#64748b;font-size:13px}
        </style>
        <div class="library-intro">
          <h2>习题列表</h2>
          <p>滚动浏览完整题库，或使用题号、标题、题面、标签、难度与来源关键词快速定位。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    user = st.session_state.get("user") or {}
    st.markdown("#### 题库管理入口")
    create_column, manage_column, status_column = st.columns([1.2, 1.2, 3])
    create_column.button(
        "＋ 新增题目",
        key="library-create-problem",
        type="primary",
        width="stretch",
        on_click=show_problem_management,
        args=("create",),
    )
    manage_column.button(
        "⚙ 管理题库",
        key="library-manage-problems",
        width="stretch",
        on_click=show_problem_management,
        args=("overview",),
    )
    permission_text = "新增、编辑和删除" if user.get("role") == "admin" else "新增和编辑"
    status_column.info(f"当前题库共 {len(all_problems)} 道题，你可以{permission_text}题目。")
    all_tags = sorted({tag for item in all_problems for tag in item.get("tags", [])})
    search_column, tag_column, action_column = st.columns([3, 1.4, 1.1])
    keyword = search_column.text_input(
        "关键词查找",
        placeholder="例如：动态规划、数组、sum_2……",
        key="library_keyword",
    )
    selected_tag = tag_column.selectbox("标签筛选", ["全部标签", *all_tags], key="library_tag")
    action_column.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    action_column.button(
        "进入评测控制台",
        key="library-console",
        width="stretch",
        on_click=show_judge_workspace,
    )

    params = {}
    if keyword.strip():
        params["keyword"] = keyword.strip()
    if selected_tag != "全部标签":
        params["tag"] = selected_tag
    try:
        visible_problems = client().get("/api/problems/", params=params) if params else all_problems
    except Exception as exc:
        show_error(exc)
        return

    count_column, guide_column = st.columns([1, 4])
    count_column.metric("匹配题目", len(visible_problems))
    guide_column.caption("列表区域可独立滚动；点击“开始作答”会进入题目与代码评测同屏页面。")
    if not visible_problems:
        st.warning("没有找到相关题目，请尝试更换关键词或标签。")
        return

    with st.container(height=610, border=False):
        for index, problem in enumerate(visible_problems, start=1):
            with st.container(border=True):
                text_column, action_column = st.columns([5, 1], vertical_alignment="center")
                with text_column:
                    tags = " · ".join(problem.get("tags", [])) or "暂无标签"
                    difficulty = problem.get("difficulty") or "未设置"
                    safe_id = escape(str(problem["id"]))
                    safe_title = escape(str(problem["title"]))
                    safe_difficulty = escape(str(difficulty))
                    safe_tags = escape(tags)
                    safe_metadata = f"难度：{safe_difficulty}　|　标签：{safe_tags}"
                    st.markdown(
                        f"""
                        <div class="problem-index">PROBLEM {index:02d} // {safe_id}</div>
                        <div class="problem-title">{safe_title}</div>
                        <div class="problem-meta">{safe_metadata}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                action_column.button(
                    "开始作答 ›",
                    key=f"library-open-{problem['id']}",
                    width="stretch",
                    type="primary",
                    on_click=open_problem,
                    args=(problem["id"],),
                )


def workspace_page() -> None:
    user = require_login()
    if not user:
        return
    try:
        all_problems = client().get("/api/problems/")
    except Exception as exc:
        show_error(exc)
        return
    workspace_view = st.session_state.get("workspace_view", "library")
    if workspace_view == "library":
        problem_library_page(all_problems)
        return

    if workspace_view == "manage":
        st.button(
            "← 返回题目列表",
            key="back-library-from-management",
            on_click=show_problem_library,
        )
        st.markdown("### 题目管理")
        st.caption("所有登录用户均可新增、编辑题目；删除题目仅限管理员。")
        problem_management(all_problems, can_delete=user["role"] == "admin")
        return

    nav_left, nav_right = st.columns([4, 1])
    nav_left.button("← 返回题目列表", key="back-problem-library", on_click=show_problem_library)
    nav_right.button(
        "⚙ 题目管理",
        key="judge-problem-management",
        width="stretch",
        on_click=show_problem_management,
        args=("overview",),
    )
    if notice := st.session_state.pop("problem_notice", None):
        st.success(notice)
    try:
        languages = client().get("/api/languages/")["name"]
    except Exception as exc:
        show_error(exc)
        return
    tab_names = ["在线做题", "提交记录", "结果详情", "语言配置"]
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
                    st.markdown("#### 本题提交记录")
                    st.caption("管理员可查看所有用户在本题的提交；普通用户仅能查看自己的提交。")
                    problem_submissions = client().get(
                        "/api/submissions/",
                        params={"problem_id": selected, "page": 1, "page_size": 100},
                    )
                    st.metric("本题可见提交数", problem_submissions["total"])
                    st.dataframe(
                        problem_submissions["submissions"], width="stretch", hide_index=True
                    )
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
    with tabs[3]:
        st.subheader("动态添加语言")
        st.info("服务器已安装对应编译器或解释器后即可注册语言。下面预填了 GCC 的 C11 配置。")
        st.caption("命令以参数数组安全执行，仅支持 {src} 与 {exe} 占位符。")
        with st.form("language-registration"):
            first, second = st.columns(2)
            language_name = first.text_input("语言名称", value="c")
            file_ext = second.text_input("源文件扩展名", value=".c")
            compile_cmd = st.text_input("编译命令", value="gcc {src} -std=c11 -O2 -o {exe}")
            run_cmd = st.text_input("运行命令", value="{exe}")
            limit_left, limit_right = st.columns(2)
            custom_time = limit_left.checkbox("设置语言时间限制", value=False)
            custom_memory = limit_right.checkbox("设置语言内存限制", value=False)
            time_limit = limit_left.number_input(
                "时间限制（秒）", 0.05, 60.0, 3.0, disabled=not custom_time
            )
            memory_limit = limit_right.number_input(
                "内存限制（MB）", 16, 2048, 128, disabled=not custom_memory
            )
            if st.form_submit_button("注册语言", type="primary"):
                payload = {
                    "name": language_name,
                    "file_ext": file_ext,
                    "compile_cmd": compile_cmd or None,
                    "run_cmd": run_cmd,
                }
                if custom_time:
                    payload["time_limit"] = time_limit
                if custom_memory:
                    payload["memory_limit"] = memory_limit
                try:
                    client().post("/api/languages/", json=payload)
                    st.success(f"语言 {language_name} 注册成功")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)
        st.markdown("#### 当前可用语言")
        st.write("、".join(languages))


AI_TEST_STRATEGIES = {
    "basic": ("简单测试点", "样例附近的小规模输入，用于发现基础实现错误"),
    "normal": ("普通测试点", "约束中段的典型数据，用于检验完整算法逻辑"),
    "boundary": ("边界条件测试点", "最小值、最大值、空数据与临界转折"),
    "performance": ("时间限制测试点", "约束上界数据，用于卡掉未优化的低效算法"),
    "corner": ("特殊情形测试点", "单元素、重复、有序、逆序与退化结构"),
    "overflow": ("数值溢出测试点", "32 位整数边界与中间结果溢出风险"),
    "adversarial": ("易错对抗测试点", "针对常见错误算法构造最小反例"),
    "randomized": ("多样数据测试点", "不同分布与组合形态，降低数据单一性"),
}

AI_TASK_NAMES = {
    "authoring": "初始命题",
    "iteration": "迭代改进",
    "test_refinement": "测试点增强",
    "luogu_similar": "洛谷相似题",
    "luogu_extension": "洛谷扩展题",
}
AI_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def test_plan_fields(prefix: str) -> dict:
    defaults = {
        "basic": 2,
        "normal": 3,
        "boundary": 2,
        "performance": 1,
        "corner": 1,
        "overflow": 0,
        "adversarial": 1,
        "randomized": 0,
    }
    st.markdown("#### 测试点配额")
    st.caption("逐项设置生成数量；数量为 0 表示本轮不生成该类型，所有类型合计最多 50 个。")
    case_counts: dict[str, int] = {}
    for strategy, (name, description) in AI_TEST_STRATEGIES.items():
        label_column, count_column = st.columns([5, 1], vertical_alignment="center")
        label_column.markdown(f"**{name}**  \n{description}")
        count = count_column.number_input(
            f"{name}数量",
            min_value=0,
            max_value=20,
            value=defaults[strategy],
            step=1,
            key=f"{prefix}-{strategy}-count",
            label_visibility="collapsed",
        )
        if count:
            case_counts[strategy] = int(count)
    total_count = sum(case_counts.values())
    st.caption(f"当前合计：{total_count} / 50 个测试点")
    preserve_existing = st.checkbox(
        "保留并复核已有有效测试点", value=True, key=f"{prefix}-preserve"
    )
    custom_requirements = st.text_area(
        "测试点补充要求（可选）",
        placeholder="例如：重点检查重复边、负权值；性能点应区分 O(n log n) 与 O(n²)。",
        height=90,
        key=f"{prefix}-custom",
    )
    return {
        "strategies": list(case_counts),
        "target_count": total_count,
        "case_counts": case_counts,
        "preserve_existing": preserve_existing,
        "custom_requirements": custom_requirements,
    }


def render_ai_problem_result(task_id: str, result: dict) -> None:
    problem = result.get("problem")
    if not isinstance(problem, dict):
        st.warning("模型结果中缺少可预览的题目结构。")
        st.json(result)
        return

    st.markdown("### AI 新题可视化")
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("题目 ID", problem.get("id", "-"))
    metric2.metric("难度", problem.get("difficulty") or "未设置")
    metric3.metric("测试点", len(problem.get("testcases") or []))
    metric4.metric(
        "资源限制",
        f"{problem.get('time_limit', '-')}s / {problem.get('memory_limit', '-')}MB",
    )

    statement_tab, testcase_tab, design_tab, raw_tab = st.tabs(
        ["题面预览", "测试点预览", "测试设计", "原始数据"]
    )
    with statement_tab:
        render_problem_statement(problem)
    with testcase_tab:
        testcases = problem.get("testcases") or []
        if not testcases:
            st.info("该题暂时没有测试点。")
        else:
            rows = [
                {
                    "序号": index,
                    "输入": case.get("input", ""),
                    "预期输出": case.get("output", ""),
                    "输入字符数": len(case.get("input", "")),
                }
                for index, case in enumerate(testcases, start=1)
            ]
            st.dataframe(rows, width="stretch", hide_index=True)
            for index, case in enumerate(testcases, start=1):
                with st.expander(f"测试点 {index} · 完整输入输出"):
                    input_column, output_column = st.columns(2)
                    input_column.code(case.get("input", ""), language=None)
                    output_column.code(case.get("output", ""), language=None)
    with design_tab:
        coverage = result.get("coverage")
        st.markdown("#### 覆盖说明")
        if isinstance(coverage, list):
            for item in coverage:
                st.markdown(f"- {item}")
        elif coverage:
            st.markdown(str(coverage))
        else:
            st.info("模型未提供测试覆盖说明。")
        if notes := result.get("notes"):
            st.markdown("#### 生成备注")
            st.info(str(notes))
        if plan := result.get("test_plan"):
            st.markdown("#### 测试点配置")
            st.json(plan)
    with raw_tab:
        st.json(result)

    review = result.get("review") or {}
    requires_manual_review = review.get("status") == "fallback" or (
        "已保留通过结构校验的草稿" in str(result.get("notes") or "")
    )
    if requires_manual_review:
        st.warning("该结果使用了已校验草稿回退，请先载入题目管理表单并人工审阅测试点。")
    direct_column, review_column = st.columns(2)
    if direct_column.button(
        "导入题库并立即打开",
        key=f"ai-direct-import-{task_id}",
        type="primary",
        width="stretch",
        disabled=requires_manual_review,
    ):
        try:
            client().post("/api/problems/", json=problem)
            st.session_state.pop("ai_problem", None)
            st.session_state.problem_notice = f"AI 题目 {problem['id']} 已导入正式题库。"
            st.session_state.workspace_problem = problem["id"]
            st.session_state.workspace_view = "judge"
            st.session_state.nav_page = "题目与评测"
            st.rerun()
        except Exception as exc:
            show_error(exc)
    if review_column.button(
        "载入题目管理表单",
        key=f"ai-stage-import-{task_id}",
        width="stretch",
    ):
        stage_ai_problem(problem)
        st.rerun()
    st.caption("复核通过的结果可直接导入；载入表单可在保存前继续修改题面和测试点。")


def ai_task_live_panel(task_id: str, refresh_seconds: float, auto_refresh: bool) -> None:
    @st.fragment(
        run_every=refresh_seconds if auto_refresh and task_id else None,
        key="ai-task-live-fragment",
    )
    def live_panel() -> None:
        if not task_id:
            st.info("创建任务或输入任务 ID 后，这里会显示实时状态。")
            return
        try:
            task = client().get(f"/api/ai/problem-tasks/{task_id}")
        except Exception as exc:
            show_error(exc)
            return

        status = task["status"]
        st.write(
            f"**{AI_TASK_NAMES.get(task['task_type'], task['task_type'])} · "
            f"第 {task['iteration_number']} 版 · {status}** · {task['progress']}"
        )
        st.caption(
            f"最近刷新：{time.strftime('%H:%M:%S')} · "
            f"{'自动刷新中' if auto_refresh else '自动刷新已关闭'}"
        )
        if task.get("parent_task_id"):
            st.caption(f"父任务：{task['parent_task_id']}")
        u1, u2, u3, u4 = st.columns(4)
        u1.metric("输入 Token", task["usage"]["input_tokens"])
        u2.metric("输出 Token", task["usage"]["output_tokens"])
        u3.metric("总 Token", task["usage"]["total_tokens"])
        u4.metric("费用 USD", f"{task['usage']['cost']:.8f}")
        st.caption("Token 为模型服务已确认的用量；单次请求完成前可能暂时保持不变。")

        action1, action2 = st.columns(2)
        action1.button("立即刷新", key="ai-refresh-now", width="stretch")
        if action2.button(
            "中断任务",
            key="ai-cancel-live",
            width="stretch",
            disabled=status in AI_TERMINAL_STATUSES,
        ):
            try:
                client().put(f"/api/ai/problem-tasks/{task_id}/cancel")
                st.warning("已发送中断请求，下一次刷新将显示最终状态。")
            except Exception as exc:
                show_error(exc)

        if task.get("error"):
            st.error(task["error"])
        elif status == "failed":
            st.error("该任务由旧版本执行，未保存具体错误；请重新创建任务以获得详细诊断。")
        if task.get("result"):
            st.session_state.ai_result = task["result"]
            st.session_state.ai_task_id = task_id
            render_ai_problem_result(task_id, task["result"])

    live_panel()


def ai_page() -> None:
    if not require_login():
        return
    config_tab, author_tab, luogu_tab, iterate_tab, task_tab, history_tab = st.tabs(
        ["模型配置", "智能命题", "洛谷参考命题", "迭代改进", "任务控制台", "版本记录"]
    )
    with config_tab:
        st.info("模型密钥加密保存在后端，不会在查询、日志或页面中回显。")
        st.caption(
            "只填写域名时会自动使用标准 /v1/chat/completions；填写自定义路径时会保留该路径。"
            "复杂命题单次模型请求默认最多等待 300 秒。"
        )
        st.caption(
            "Token 用量由模型接口自动返回；OpenAI 兼容接口通常不提供模型单价，"
            "因此单价需要按供应商账单填写。"
            "费用 = 输入 Token ÷ 计价 Token 数 × 输入单价 + 输出 Token ÷ 计价 Token 数 × 输出单价。"
            "若只需统计 Token，可将两个单价都保留为 0。"
        )
        with st.form("ai-config"):
            provider_url = st.text_input(
                "提供商 URL",
                placeholder="例如：https://llmapi.paratera.com/v1",
                help=(
                    "填写兼容 API 的基础地址即可；若供应商给出完整 chat/completions 地址，"
                    "也可直接填写。"
                ),
            )
            model = st.text_input("模型名称")
            api_key = st.text_input("模型密钥", type="password")
            c1, c2, c3 = st.columns(3)
            input_price = c1.number_input(
                "输入单价（USD）",
                min_value=0.0,
                format="%.6f",
                help=(
                    "每个计价单位内输入 Token 的价格；若供应商按百万 Token 报价，"
                    "就填写每百万 Token 输入价。"
                ),
            )
            output_price = c2.number_input(
                "输出单价（USD）",
                min_value=0.0,
                format="%.6f",
                help=(
                    "每个计价单位内输出 Token 的价格；若供应商按百万 Token 报价，"
                    "就填写每百万 Token 输出价。"
                ),
            )
            price_unit = c3.number_input(
                "计价 Token 数",
                min_value=1,
                value=1_000_000,
                help="价格对应的 Token 数；多数供应商按 1,000,000 Token 报价。",
            )
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
            test_plan = test_plan_fields("author-plan")
            if st.form_submit_button("开始命题", type="primary"):
                if not test_plan["case_counts"]:
                    st.warning("请至少为一种测试点设置数量。")
                elif test_plan["target_count"] > 50:
                    st.warning("所有类型合计不能超过 50 个测试点。")
                else:
                    try:
                        data = client().post(
                            "/api/ai/problem-tasks/",
                            json={
                                "requirement": requirement,
                                "problem_id": reference or None,
                                "test_plan": test_plan,
                            },
                        )
                        st.session_state.ai_task_id = data["task_id"]
                        st.success(f"初始版本已创建：{data['task_id']}。请到“任务控制台”查看进度。")
                    except Exception as exc:
                        show_error(exc)
    with luogu_tab:
        st.markdown("### 根据洛谷题号创作新题")
        st.info(
            "输入公开题号（例如 P1001 或 1001），系统会提炼考点、难度、背景作用与边界，"
            "再生成原创相似题或进阶扩展题。"
        )
        st.caption("参考题只用于抽象分析；新题会更换标题、叙事和数据设计，不直接复刻原题。")
        st.link_button("打开洛谷题库 ↗", "https://www.luogu.com.cn/problem/list")
        with st.form("ai-luogu-author"):
            first, second = st.columns([1, 2])
            luogu_problem_id = first.text_input(
                "洛谷题号", placeholder="P1001", key="luogu-problem-id"
            )
            luogu_mode_label = second.radio(
                "命题方式",
                ["相似题", "扩展题"],
                horizontal=True,
                key="luogu-mode",
            )
            additional_requirement = st.text_area(
                "附加要求（可选）",
                placeholder=(
                    "例如：保留核心考点但改成校园场景；或增加多次查询，使题目成为进阶版本。"
                ),
                height=110,
            )
            luogu_test_plan = test_plan_fields("luogu-plan")
            if st.form_submit_button("读取参考题并开始命题", type="primary"):
                if not luogu_test_plan["case_counts"]:
                    st.warning("请至少为一种测试点设置数量。")
                elif luogu_test_plan["target_count"] > 50:
                    st.warning("所有类型合计不能超过 50 个测试点。")
                else:
                    try:
                        data = client().post(
                            "/api/ai/luogu-problem-tasks/",
                            json={
                                "problem_id": luogu_problem_id,
                                "mode": (
                                    "similar" if luogu_mode_label == "相似题" else "extension"
                                ),
                                "additional_requirement": additional_requirement,
                                "test_plan": luogu_test_plan,
                            },
                        )
                        st.session_state.ai_task_id = data["task_id"]
                        reference = data["reference"]
                        st.success(
                            f"已读取 {reference['problem_id']} · {reference['title']}"
                            f"（{reference['difficulty']}），命题任务：{data['task_id']}。"
                        )
                        st.caption("请前往“任务控制台”查看进度、Token、费用与最终题目。")
                    except Exception as exc:
                        show_error(exc)
    with iterate_tab:
        st.markdown("### 根据反馈继续迭代")
        st.info("上一版结果会由后端直接加入模型上下文；新版本作为子任务保存，不会覆盖旧版本。")
        with st.form("ai-iteration"):
            source_task = st.text_input(
                "作为基线的已完成任务 ID",
                value=st.session_state.get("ai_task_id", ""),
                key="iteration-source",
            )
            feedback = st.text_area(
                "改进意见",
                placeholder=(
                    "例如：题面过于抽象，请加入实际场景；保持输入格式不变，把难度提高到中等，"
                    "并增加能卡掉错误贪心的反例。"
                ),
                height=170,
            )
            test_plan = test_plan_fields("iteration-plan")
            if st.form_submit_button("生成改进版本", type="primary"):
                if not test_plan["case_counts"]:
                    st.warning("请至少为一种测试点设置数量。")
                elif test_plan["target_count"] > 50:
                    st.warning("所有类型合计不能超过 50 个测试点。")
                else:
                    try:
                        data = client().post(
                            f"/api/ai/problem-tasks/{source_task}/iterations",
                            json={"feedback": feedback, "test_plan": test_plan},
                        )
                        st.session_state.ai_task_id = data["task_id"]
                        st.success(
                            f"迭代任务已创建：{data['task_id']}，父版本：{data['parent_task_id']}。"
                        )
                    except Exception as exc:
                        show_error(exc)
        if st.session_state.get("ai_result"):
            with st.expander("当前已加载版本（供填写意见时参考）"):
                st.json(st.session_state.ai_result)
    with task_tab:
        st.markdown("### 当前任务与结果")
        task_id = st.text_input(
            "当前任务 ID", value=st.session_state.get("ai_task_id", ""), key="task-console-id"
        )
        refresh1, refresh2 = st.columns(2)
        auto_refresh = refresh1.toggle("自动刷新", value=True, key="ai-auto-refresh")
        refresh_seconds = refresh2.number_input(
            "刷新间隔（秒）",
            min_value=0.5,
            max_value=60.0,
            value=2.0,
            step=0.5,
            key="ai-refresh-seconds",
        )
        ai_task_live_panel(task_id, float(refresh_seconds), auto_refresh)
    with history_tab:
        try:
            tasks = client().get("/api/ai/problem-tasks/")
            rows = [
                {
                    "task_id": item["task_id"],
                    "类型": AI_TASK_NAMES.get(item["task_type"], item["task_type"]),
                    "版本": item["iteration_number"],
                    "父任务": item["parent_task_id"] or "-",
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
pages = ["首页", "账户", "个人信息", "题目与评测", "AI 智能命题"]
if current and current["role"] == "admin":
    pages.append("用户管理")
if st.session_state.get("nav_page") not in pages:
    st.session_state.nav_page = "首页"
page = st.session_state.nav_page
if page != "首页":
    subpage_shell(page)
{
    "首页": dashboard_page,
    "账户": auth_page,
    "个人信息": profile_page,
    "题目与评测": workspace_page,
    "AI 智能命题": ai_page,
    "用户管理": admin_page,
}[page]()
