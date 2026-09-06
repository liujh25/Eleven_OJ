from __future__ import annotations

import os
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "output" / "screenshots"
API = os.getenv("OJ_API_URL", "http://127.0.0.1:8000")
FRONTEND = os.getenv("OJ_FRONTEND_URL", "http://127.0.0.1:8501")
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def seed() -> None:
    with httpx.Client(base_url=API) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admintestpassword"},
        )
        response.raise_for_status()
        sample = __import__("json").loads((ROOT / "examples" / "sum_2.json").read_text("utf-8"))
        if client.get("/api/problems/sum_2").status_code == 404:
            client.post("/api/problems/", json=sample).raise_for_status()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    seed()
    with sync_playwright() as playwright:
        kwargs = {"headless": True}
        if EDGE.exists():
            kwargs["executable_path"] = str(EDGE)
        browser = playwright.chromium.launch(**kwargs)
        page = browser.new_page(viewport={"width": 1440, "height": 950}, device_scale_factor=1)
        page.goto(FRONTEND, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(1200)
        assert not page.get_by_test_id("stSidebar").is_visible()
        assert not page.get_by_test_id("stSidebarCollapsedControl").is_visible()
        page.screenshot(path=OUTPUT / "00-dashboard-guest.png", full_page=True)
        page.locator("div.stButton button").nth(1).click()
        page.wait_for_timeout(1000)
        page.screenshot(path=OUTPUT / "01-login.png", full_page=True)
        page.get_by_label("用户名", exact=True).fill("admin")
        page.get_by_label("密码", exact=True).fill("admintestpassword")
        page.get_by_role("button", name="登录", exact=True).click()
        page.wait_for_timeout(1800)
        page.screenshot(path=OUTPUT / "02-account.png", full_page=True)
        page.get_by_role("button", name="← 返回首页", exact=True).click()
        page.wait_for_timeout(1400)
        dashboard = page.locator("body").inner_text()
        assert "ADMIN // CODER" in dashboard
        assert not page.locator("div.stButton button").nth(2).is_disabled()
        page.screenshot(path=OUTPUT / "00-dashboard-admin.png", full_page=True)
        page.locator("div.stButton button").nth(2).click()
        page.wait_for_timeout(900)
        assert "用户管理" in page.locator("body").inner_text()
        page.get_by_role("button", name="← 返回首页", exact=True).click()
        page.wait_for_timeout(900)
        page.locator("div.stButton button").nth(3).click()
        page.wait_for_timeout(900)
        assert "模型配置" in page.locator("body").inner_text()
        page.get_by_role("tab", name="智能命题", exact=True).click()
        page.wait_for_timeout(500)
        authoring = page.locator("body").inner_text()
        assert "普通测试点" in authoring
        assert "时间限制测试点" in authoring
        page.screenshot(path=OUTPUT / "04-ai-authoring.png", full_page=True)
        page.get_by_role("tab", name="迭代改进", exact=True).click()
        page.wait_for_timeout(500)
        iteration = page.locator("body").inner_text()
        assert "根据反馈继续迭代" in iteration
        assert "普通测试点" in iteration
        page.screenshot(path=OUTPUT / "06-ai-iteration.png", full_page=True)
        page.get_by_role("button", name="← 返回首页", exact=True).click()
        page.wait_for_timeout(900)
        page.locator("div.stButton button").nth(0).click()
        page.wait_for_timeout(1500)
        library = page.locator("body").inner_text()
        assert "习题列表" in library
        assert "关键词查找" in library
        assert "两数之和" in library
        page.screenshot(path=OUTPUT / "03-problem-library.png", full_page=True)
        page.get_by_label("关键词查找", exact=True).fill("图论")
        page.get_by_label("关键词查找", exact=True).press("Enter")
        page.wait_for_timeout(700)
        assert "没有找到相关题目" in page.locator("body").inner_text()
        page.get_by_label("关键词查找", exact=True).fill("两数")
        page.get_by_label("关键词查找", exact=True).press("Enter")
        page.wait_for_timeout(700)
        assert "两数之和" in page.locator("body").inner_text()
        page.get_by_role("button", name="开始作答 ›", exact=True).first.click()
        page.wait_for_timeout(1200)
        workspace = page.locator("body").inner_text()
        assert "按标签查找" in workspace
        assert "提交代码" in workspace
        assert "返回题目列表" in workspace
        page.screenshot(path=OUTPUT / "03-problems.png", full_page=True)
        docs = browser.new_page(viewport={"width": 1440, "height": 950})
        schema = httpx.get(f"{API}/openapi.json").json()
        cards = []
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                cards.append(
                    f'<div class="route"><b class="{method}">{method.upper()}</b>'
                    f"<code>{path}</code><span>{operation.get('summary', '')}</span></div>"
                )
        docs.set_content(
            "<style>body{font-family:Segoe UI;margin:42px;background:#f8fafc;color:#172033}"
            "h1{color:#1d4ed8}.route{display:grid;grid-template-columns:80px 430px 1fr;"
            "align-items:center;background:white;margin:8px 0;padding:12px 16px;border-radius:10px;"
            "box-shadow:0 1px 3px #dbe3ef}.route b{color:white;padding:5px 8px;"
            "border-radius:6px;text-align:center}.get{background:#16a34a}.post{background:#2563eb}"
            ".put{background:#d97706}.delete{background:#dc2626}code{font-size:15px}"
            "span{color:#64748b}</style><h1>Async OJ · OpenAPI 路由总览</h1>"
            f"<p>共 {len(cards)} 个 HTTP 操作，全部由 FastAPI 异步接口提供。</p>" + "".join(cards)
        )
        docs.screenshot(path=OUTPUT / "05-openapi.png", full_page=True)
        browser.close()
    print(f"Screenshots written to {OUTPUT}")


if __name__ == "__main__":
    main()
