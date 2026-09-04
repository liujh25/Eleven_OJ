# Async OJ

清华大学“程序设计训练（Python）”实验二的完整在线评测系统。项目覆盖题目管理、
Python/C++ 异步评测、提交管理、用户权限、测试点日志、Streamlit 前端以及 AI 智能命题。

## 功能与评分项

| 模块 | 实现 |
| --- | --- |
| Step 1 | 题目字段校验、列表、详情、新增、编辑和管理员删除 |
| Step 2 | Python/C++14、动态语言注册、异步评测、时间/内存限制 |
| Step 3 | 提交筛选、分页、详情、限流和管理员重新评测 |
| Step 4 | 注册、服务端 Session、登录/退出、角色与封禁管理 |
| Step 5 | 测试点日志、题目级公开策略、成功/拒绝访问审计 |
| Step 6 | 用户、题目、提交/结果三组 Streamlit 页面 |
| Advance | 可配置 OpenAI 兼容模型、进度、取消、Token/费用、题目导入 |

所有 API 路由均使用 `async def`，响应统一为 `{"code", "msg", "data"}`，HTTP
状态码与 `code` 相同。详细设计见 [架构文档](docs/ARCHITECTURE.md)，课程要求见
[实验二文档](https://dbg-course.github.io/python-docs/oj/)。

## 快速开始

建议使用 Python 3.10–3.12 和 GCC 9+。Windows 可以开发和演示，最终资源限制以
Linux 为准。

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -e ".[dev,report]"
uvicorn oj.app:app --reload
```

另开终端启动前端：

```bash
streamlit run frontend/app.py
```

- API：<http://127.0.0.1:8000>
- Swagger：<http://127.0.0.1:8000/docs>
- 前端：<http://127.0.0.1:8501>
- 初始管理员：`admin / admintestpassword`（仅课程验收默认值，部署时应立即修改）

也可使用 `docker compose up --build` 在 Linux 容器中启动前后端。

## 配置

复制 `.env.example` 为 `.env`。常用配置如下：

- `OJ_DATABASE_URL`：异步 SQLAlchemy 数据库 URL。
- `OJ_SESSION_COOKIE`、`OJ_SESSION_TTL_HOURS`：Session Cookie 名称和有效期。
- `OJ_COOKIE_SECURE`：HTTPS 部署时设为 `true`。
- `OJ_EXECUTOR_ENABLED`：是否自动运行提交代码。
- `OJ_AI_TIMEOUT_SECONDS`：外部模型请求超时。
- `OJ_API_URL`：Streamlit 使用的后端地址。

运行时数据库、加密密钥、临时代码和 `.env` 都被 Git 忽略。AI 模型配置在页面中
按用户填写；API Key 使用本地 Fernet 密钥加密，接口和日志不会回显密钥。

## API 示例

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admintestpassword"}'

curl -b cookies.txt http://127.0.0.1:8000/api/problems/
```

题目示例位于 [examples/sum_2.json](examples/sum_2.json)。AI 假服务可用于无密钥演示：

```bash
uvicorn tests.fake_provider:app --port 9000
# 页面配置 provider URL=http://127.0.0.1:9000/v1, model=fake, api_key=anything
```

## 质量检查

```bash
ruff check oj frontend tests
ruff format --check oj frontend tests
mypy oj
pytest --cov=oj --cov-report=term-missing --cov-fail-under=80 -q
```

当前测试覆盖认证和权限优先级、全部基础 CRUD、语言命令安全、Python/C++ 判题状态、
提交限流与重评、日志公开和审计、AI 进度/取消/费用，以及 Streamlit 冒烟。GitHub
Actions 在 Python 3.10/3.12 的 Ubuntu 环境重复以上检查。

## 安全边界

- 语言命令不会交给 shell，拒绝管道、重定向和命令连接符，只替换 `{src}`/`{exe}`。
- 每次评测使用独立临时目录、进程组和最小环境；Linux 设置 CPU、地址空间、文件大小
  和进程数限制，同时监控整个进程树的 RSS。
- 这仍是课程级执行器，不应直接暴露到不受信任的公网。生产 OJ 应进一步使用容器、
  seccomp、只读文件系统、网络隔离和独立低权限工作节点。
- 后端执行所有权限判断；隐藏前端按钮不被视为安全措施。

## 实验报告

最终报告输出为 `output/pdf/async_oj_experiment_report.pdf`。若需重新生成截图和报告：

```bash
python scripts/capture_screenshots.py
python scripts/build_report.py
```
