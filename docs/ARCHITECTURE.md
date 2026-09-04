# 系统架构与接口说明

## 组件与数据流

```text
Streamlit UI ──HTTP + Session Cookie──> FastAPI async routes
                                            │
                     ┌──────────────────────┼──────────────────────┐
                     ▼                      ▼                      ▼
              SQLAlchemy Async       Judge task registry     AI task registry
                     │                      │                      │
                  SQLite          isolated subprocesses    OpenAI-compatible API
```

FastAPI 路由只负责协议、认证和参数边界；评测器与 AI 任务通过独立服务模块运行。
SQLite 保存用户、服务端 Session、题目、语言、提交、测试点结果、访问审计、AI 配置和
任务状态。提交或 AI 请求先持久化为 `pending`，再创建后台任务，因此客户端无需保持
长连接，可通过轮询观察结果。

## API 分组

- `/api/problems/`：题目列表和新增；`/api/problems/{id}`：详情、编辑和删除。
- `/api/languages/`：支持语言列表与安全的动态语言注册。
- `/api/submissions/`：提交、按用户/题目/状态筛选；详情和 `/rejudge`。
- `/api/users/`、`/api/auth/*`：注册、用户、角色与 Session 生命周期。
- `/api/submissions/{id}/log`、`/api/logs/access/`：测试点结果与访问审计。
- `/api/ai/model-config`、`/api/ai/problem-tasks/*`：模型配置与命题任务。
- `/api/reset/`：自动测试恢复初始管理员、Python 和 C++ 配置。

异常按认证、封禁/权限、参数、频率、冲突、不存在和内部错误的顺序处理。FastAPI 的
请求校验异常转换为 HTTP 400，所有错误也保持统一响应信封。

## 评测状态模型

- Submission 状态：`pending`、`success`、`error`。
- Test case 结果：`AC`、`WA`、`TLE`、`MLE`、`RE`、`CE`、`UNK`。
- 编译失败属于正常完成的评测任务，因此 submission 为 `success`，测试点结果为 `CE`。
- 每个 AC 测试点计 10 分；`counts` 等于测试点数量乘 10。

输出比较会统一换行并移除各行末尾空白和最终多余换行，不忽略其他字符。

## 权限矩阵

| 资源 | 普通用户 | 管理员 |
| --- | --- | --- |
| 题目列表/详情/新增/编辑 | 登录后允许 | 允许 |
| 删除题目、日志公开策略 | 禁止 | 允许 |
| 提交与本人结果 | 允许 | 允许 |
| 他人提交结果、重新评测 | 禁止 | 允许 |
| 私有日志 | 仅本人 | 全部 |
| 公开日志 | 登录后允许 | 允许 |
| 用户列表与角色管理 | 禁止 | 允许 |
| AI 任务 | 仅本人 | 可查看全部 |

被封禁用户即使持有旧 Session 也返回 403；封禁操作同时清除该用户所有服务端 Session。

## AI 命题工作流

任务先分析知识点与难度，生成完整题目草稿，再以第二次模型调用复核题意、边界条件、
常见错误和复杂度区分度。最终结果必须通过与题目新增接口相同的 Pydantic 模型校验。
两次调用的输入/输出 Token 分别累加并按配置价格计费。取消会取消真实 asyncio 任务，
而不是只停止前端动画。

## 已知部署边界

课程执行器能限制常见错误和资源滥用，但不是通用恶意代码沙箱。公网部署需要把评测器
迁移到无网络、只读根文件系统、独立 UID 的容器或虚拟机工作节点。SQLite 适合单机验收；
多实例部署应迁移到 PostgreSQL，并把 Session 和任务队列迁移到 Redis/Celery 等共享服务。
