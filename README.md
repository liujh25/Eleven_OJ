# Async OJ

清华大学“程序设计训练（Python）”实验二的完整在线评测系统。项目覆盖题目管理、
Python/C++ 异步评测、提交管理、用户权限、测试点日志、Streamlit 前端以及 AI 智能命题。

## 功能与评分项

| 模块 | 实现 |
| --- | --- |
| Step 1 | 题目字段校验、标签筛选、列表、详情、新增、编辑和管理员删除 |
| Step 2 | Python/C++14、GCC/C 动态注册、异步评测、分层时间/内存限制 |
| Step 3 | 提交筛选、分页、详情、限流和管理员重新评测 |
| Step 4 | 注册、服务端 Session、登录/退出、角色与封禁管理 |
| Step 5 | 测试点日志、题目级公开策略、成功/拒绝访问审计 |
| Step 6 | 用户、题目与评测同屏工作区、提交记录和结果页面 |
| Advance | OpenAI 兼容模型、版本迭代、精细测试点、进度/取消、Token/费用、题目导入 |

首页采用角色化控制台布局：左侧展示用户等级和角色背景，右侧提供习题评测、账户、
管理员用户管理和 AI 命题入口。满分通过的新题目按难度升级，简单、中等、困难题
分别提升 1、2、3 级；同一题目的重复通过不会重复计算。
所有功能页面均从首页进入，不使用侧边导航；每个子页面左上角提供返回首页按钮，
并统一采用深色斜切背景、蓝橙强调色和控制台卡片样式。

所有 API 路由均使用 `async def`，响应统一为 `{"code", "msg", "data"}`，HTTP
状态码与 `code` 相同。详细设计见 [架构文档](docs/ARCHITECTURE.md)，课程要求见
[实验二文档](https://dbg-course.github.io/python-docs/oj/)。

## 快速开始

建议使用 Python 3.10–3.12 和 GCC 9+。Windows 可以开发和演示，最终资源限制以
Linux 为准。

Windows 用户可以直接双击项目根目录的 `run.bat`。脚本会检查虚拟环境和依赖，分别
启动后端与前端，并在服务就绪后打开浏览器。关闭两个服务窗口即可停止平台。仅检查
环境而不启动服务时可运行 `run.bat --check`。

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
- `OJ_DEFAULT_TIME_LIMIT_SECONDS`、`OJ_DEFAULT_MEMORY_LIMIT_MB`：系统默认评测限制，
  默认分别为 3 秒和 128 MB。
- `OJ_AI_TIMEOUT_SECONDS`：外部模型请求超时。
- `OJ_API_URL`：Streamlit 使用的后端地址。

运行时数据库、加密密钥、临时代码和 `.env` 都被 Git 忽略。AI 模型配置在页面中
按用户填写；API Key 使用本地 Fernet 密钥加密，接口和日志不会回显密钥。

“智能命题”和“迭代改进”表单均内置测试点配额列表，可分别设置简单、普通、边界、
时间限制、特殊情形、溢出、易错对抗和多样数据测试点的数量，填 0 即不生成该类型。
迭代时可以填写自然语言反馈，以任一已完成任务为基线生成新版本；每个新版本保留父任务 ID
和迭代轮次，旧版本不会被覆盖。时间限制测试点要求生成可执行的确定输入输出，并说明测试点
要区分的算法复杂度。

## API 示例

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admintestpassword"}'

curl -b cookies.txt http://127.0.0.1:8000/api/problems/

# 服务器安装 GCC 后可动态注册 C11；省略限制表示继续向系统默认值回退
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/languages/ \
  -H "Content-Type: application/json" \
  -d '{"name":"c","file_ext":".c","compile_cmd":"gcc {src} -std=c11 -O2 -o {exe}","run_cmd":"{exe}"}'
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

当前测试覆盖认证和权限优先级、全部基础 CRUD、限制继承、级联删除、题目测试点可见性、
单题按角色提交范围、独立用户统计、动态 C 注册、语言命令安全、Python/C++ 判题状态、
提交限流与重评、日志公开和审计、AI 进度/取消/费用，以及 Streamlit 冒烟。GitHub
Actions 在 Python 3.10/3.12 的 Ubuntu 环境重复以上检查。

评测的时间和内存限制分别独立按照“题目配置 → 语言配置 → 系统默认值”确定。普通用户
查看题目详情时也会得到 `testcases`。题目详情页请求提交记录时不传 `user_id`：管理员
因此看到该题全部用户的记录，普通用户由后端自动收窄到本人。删除题目会在同一事务中
清理关联提交、逐测试点结果、访问审计及关联 AI 任务。

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
