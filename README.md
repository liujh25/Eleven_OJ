# Async OJ

清华大学“程序设计训练（Python）”实验二的完整在线评测系统。项目覆盖题目管理、
Python/C++ 异步评测、提交管理、用户权限、测试点日志、Streamlit 前端以及 AI 智能命题。

## 功能与评分项

| 模块 | 实现 |
| --- | --- |
| Step 1 | 题目字段校验、关键词/标签筛选、列表、详情、新增、编辑和管理员删除 |
| Step 2 | Python/C++14、GCC/C 动态注册、异步评测、分层时间/内存限制 |
| Step 3 | 提交筛选、分页、详情、限流和管理员重新评测 |
| Step 4 | 注册、服务端 Session、登录/退出、角色与封禁管理 |
| Step 5 | 分层测试点日志、题目级公开策略、成功/拒绝访问审计 |
| Step 6 | 用户、题目与评测同屏工作区、提交记录和结果页面 |
| Advance | OpenAI 兼容模型、洛谷参考命题、版本迭代、精细测试点、进度/取消、Token/费用、题目导入 |

首页采用角色化控制台布局：左侧展示用户等级和角色背景，右侧提供习题评测、账户、
管理员用户管理和 AI 命题入口。满分通过的新题目按难度升级，简单、中等、困难题
分别提升 1、2、3 级；同一题目的重复通过不会重复计算。
所有功能页面均从首页进入，不使用侧边导航；每个子页面左上角提供返回首页按钮，
并统一采用深色斜切背景、蓝橙强调色和控制台卡片样式。
所有登录用户都可通过题库主页新增、编辑题目；只有管理员会看到并可调用删除入口。
进入“习题与评测”后会先打开独立题库页，题目卡片置于固定高度的滚动区域。关键词
可匹配题号、标题、题面、标签、难度、来源和作者，并可与标签筛选组合；点击卡片即可
进入题目与代码评测同屏工作区，工作区顶部可返回题库。

首次启动会一次性安装 16 道经重新表述的洛谷入门题（`P1001`、`P5703–P5706`、
`P5710–P5716`、`P5720–P5723`），共 85 个自建测试点，覆盖输入输出、字符串、条件、
日期、排序、循环、格式化与质数枚举。每题保留原题链接和“洛谷”标签，可以直接在题库中
搜索或筛选。安装状态记录在数据库中，因此用户删除题目后不会在下次启动时被强制恢复。

所有 API 路由均使用 `async def`，响应统一为 `{"code", "msg", "data"}`，HTTP
状态码与 `code` 相同。详细设计见 [架构文档](docs/ARCHITECTURE.md)，课程要求见
[实验二文档](https://dbg-course.github.io/python-docs/oj/)。

## 快速开始

建议使用 Python 3.10–3.12 和 GCC 9+。Windows 可以开发和演示，最终资源限制以
Linux 为准。

Windows 用户可以直接双击项目根目录的 `run.bat`。脚本会检查虚拟环境和依赖，分别
启动后端与前端，并在服务就绪后打开浏览器。关闭两个服务窗口即可停止平台。仅检查
环境而不启动服务时可运行 `run.bat --check`。
如果端口 8000 上运行的是本项目的旧版本后端，脚本会核对 OpenAPI 版本并自动重启；
如果端口属于其他程序，脚本不会终止该程序，而会显示明确错误。

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
- `OJ_AI_TIMEOUT_SECONDS`：单次外部模型请求超时，默认 300 秒。
- `OJ_AI_MAX_OUTPUT_TOKENS`：单次结构化命题输出上限，默认 24000 Token。
- `OJ_LUOGU_TIMEOUT_SECONDS`：读取洛谷公开题目页面的超时，默认 15 秒。
- `OJ_SEED_CURATED_PROBLEMS`：是否在全新或未安装过题单的数据库中安装预置题，默认开启。
- `OJ_API_URL`：Streamlit 使用的后端地址。

运行时数据库、加密密钥、临时代码和 `.env` 都被 Git 忽略。AI 模型配置在页面中
按用户填写；API Key 使用本地 Fernet 密钥加密，接口和日志不会回显密钥。
使用 DeepSeek 官方地址 `https://api.deepseek.com` 时，系统会关闭其默认高强度思考模式，
并对无效 JSON 自动重试一次。题目草稿会先独立完成严格结构校验；复核响应若截断或结构退化，
系统保留已验证草稿并在生成备注中记录降级原因。常见的毫秒时间限制和字节/KB 内存限制会在
严格校验前安全换算为秒和 MB。
任务控制台会直接渲染题面、样例、测试点与覆盖说明。复核通过的结果可由登录用户一键写入题库；
复核回退结果必须先载入管理表单审阅。题目列表首页提供显眼的新增与管理入口，保存成功后会
刷新题库并自动打开新题。

“智能命题”和“迭代改进”表单均内置测试点配额列表，可分别设置简单、普通、边界、
时间限制、特殊情形、溢出、易错对抗和多样数据测试点的数量，填 0 即不生成该类型。
迭代时可以填写自然语言反馈，以任一已完成任务为基线生成新版本；每个新版本保留父任务 ID
和迭代轮次，旧版本不会被覆盖。时间限制测试点要求生成可执行的确定输入输出，并说明测试点
要区分的算法复杂度。

“洛谷参考命题”允许输入 `P1001` 或 `1001` 形式的题号，并选择“相似题”或“扩展题”。
系统只访问固定的 `luogu.com.cn/problem/{题号}` 页面，提炼考点、难度、背景作用、限制和
样例结构后生成原创题目；不会把参考题直接导入题库。洛谷页面内容按不可信外部数据处理，
其中出现的任何指令都不会被执行。参考来源会随 AI 版本链保留，但 API 只返回题号、标题、
难度和链接等摘要，不回显整份参考题面。

模型提供商只填写域名时，后端按 OpenAI 兼容约定自动补为 `/v1/chat/completions`；已经填写
`/v1` 或其他自定义路径时不会重复添加。任务控制台默认每 2 秒获取一次状态、输入/输出/总
Token 和费用，刷新间隔可在 0.5-60 秒间调整，也可以关闭自动刷新、立即刷新或随时中断任务。
Token 数来自模型服务的 usage 字段，因此一次请求尚未返回时会暂时保持上一已确认值。
超时、HTTP 状态错误、连接失败和无效 JSON 都会保存为可读错误，不再出现空白失败原因。

## API 示例

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admintestpassword"}'

curl -b cookies.txt http://127.0.0.1:8000/api/problems/

# 按多个关键词联合搜索（空格分隔，所有关键词均需匹配）
curl -b cookies.txt "http://127.0.0.1:8000/api/problems/?keyword=动态规划&tag=算法"

# 服务器安装 GCC 后可动态注册 C11；省略限制表示继续向系统默认值回退
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/languages/ \
  -H "Content-Type: application/json" \
  -d '{"name":"c","file_ext":".c","compile_cmd":"gcc {src} -std=c11 -O2 -o {exe}","run_cmd":"{exe}"}'

# 需先在 AI 页面保存 OpenAI 兼容模型配置
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/ai/luogu-problem-tasks/ \
  -H "Content-Type: application/json" \
  -d '{"problem_id":"P1001","mode":"extension","additional_requirement":"增加多次查询","test_plan":{"case_counts":{"normal":3}}}'
```

题目示例位于 [examples/sum_2.json](examples/sum_2.json)。AI 假服务可用于无密钥演示：

```bash
uvicorn tests.fake_provider:app --port 9000
# 页面配置 provider URL=http://127.0.0.1:9000/v1, model=fake, api_key=anything
```

需要手动确认或补装预置题单时，可以执行：

```bash
python -m oj.starter_catalog
```

## 质量检查

```bash
ruff check oj frontend tests
ruff format --check oj frontend tests
mypy oj
pytest --cov=oj --cov-report=term-missing --cov-fail-under=80 -q
```

当前测试覆盖认证和权限优先级、全部基础 CRUD、限制继承、级联删除、分层题目测试点可见性、
单题按角色提交范围、独立用户统计、动态 C 注册、语言命令安全、Python/C++ 判题状态、
提交限流与重评、日志公开和审计、16 道预置题的参考答案复算、洛谷页面安全解析、
AI 进度/取消/费用，以及 Streamlit
真实浏览器冒烟。GitHub
Actions 在 Python 3.10/3.12 的 Ubuntu 环境重复以上检查。

评测的时间和内存限制分别独立按照“题目配置 → 语言配置 → 系统默认值”确定。普通用户
查看题目详情时也会得到 `testcases`。题目详情页请求提交记录时不传 `user_id`：管理员
因此看到该题全部用户的记录，普通用户由后端自动收窄到本人。删除题目会在同一事务中
清理关联提交、逐测试点结果、访问审计及关联 AI 任务。
当 `public_cases=false` 时，提交者访问自己的日志只能得到 `score`、`counts` 和空的
`details`；其他普通用户返回 403。当 `public_cases=true` 时，所有登录用户均可查看逐测试点
状态、耗时和内存。管理员始终可查看完整明细，公开日志不会开放提交代码和编译信息。

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
