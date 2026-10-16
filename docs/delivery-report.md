# 第一阶段交付报告

项目位置：`D:/Codex/survey-system`。开始 2026-10-15，续作 2026-10-16，时区 Asia/Shanghai。

## A. 环境检查结果

原 D:/Codex 下有其他课程与桌宠等项目和资料；先只读列目录、搜索全项目文件清单及已有问卷相关文件，未发现已有 survey-system。两个 AGENTS.md 位于不相关子项目，不适用于本目录。未覆盖其他项目或修改原始作业附件。使用 documents 技能只读提取原 DOCX 内容；更广的附件要求与本轮用户指令区分，范围以用户指令为准。

- Windows；Python 3.12.14，项目虚拟环境 `.venv`。
- 原 `python` 命令不可用；`py` 默认指向 Anaconda 3.9。捆绑 Python 3.12 创建 venv 后直接用项目 Python。
- 真实 MongoDB ping `{'ok': 1.0}`；server_info 版本 9.0.2。
- 关键安装版本：FastAPI 0.143.1、PyMongo 4.19.0、Pydantic 2.14.1、pydantic-settings 2.16.0、pwdlib 0.3.1、argon2-cffi 25.1.0、Jinja2 3.1.6、Uvicorn 0.54.0、pytest 9.1.1、httpx 0.28.1、mongomock 4.3.0。
- requirements.txt 是实际环境 pip freeze 的精确锁定，含传递依赖；pip check 无冲突。选择使用已安装可兼容的稳定 API，没有实验性 API。
- 初始安装遇到沙箱网络限制，经过授权安装成功；可选 httpx2 后续安装因自动审核额度失败未执行。原文在 [errors-original.md](errors-original.md)。

## B. 实际创建/修改文件

全部位于新项目，不修改原始作业说明。完整文件清单如下；.venv 与缓存不列入源码清单：

```text
.env.example
.gitignore
README.md
app/__init__.py
app/core/__init__.py
app/core/config.py
app/core/database.py
app/core/security.py
app/main.py
app/models/__init__.py
app/models/response.py
app/models/survey.py
app/models/user.py
app/routers/__init__.py
app/routers/auth.py
app/routers/responses.py
app/routers/statistics.py
app/routers/surveys.py
app/schemas/__init__.py
app/schemas/auth.py
app/schemas/response.py
app/schemas/survey.py
app/services/__init__.py
app/services/jump_engine.py
app/services/statistics.py
app/services/surveys.py
app/services/validation.py
app/static/app.js
app/static/style.css
app/templates/index.html
docs/ai-log.md
docs/api.md
docs/architecture.md
docs/commands.md
docs/database-design.md
docs/delivery-report.md
docs/dependency-install.txt
docs/errors-original.md
docs/file-manifest.txt
docs/prompt-original.md
docs/pytest-final.txt
docs/startup-final.txt
docs/startup-server.txt
docs/testing.md
pytest.ini
requirements.txt
tests/conftest.py
tests/smoke_startup.py
tests/test_system.py

```

## C. MongoDB 最终数据模型

- users：`_id:ObjectId, username:string, password_hash:Argon2id string, created_at:UTC Date`。
- surveys：`_id:ObjectId, owner_id:ObjectId, title:string, description:string, status:draft|published|closed, allow_anonymous:bool, allow_multiple_submissions:bool, deadline:UTC Date|null, public_token:string, questions:[], jump_rules:[], schema_version:1, created_at:UTC Date, updated_at:UTC Date`。
- responses：`_id:ObjectId, survey_id:ObjectId, respondent_user_id:ObjectId|null, answers:array[document], submitted_at:UTC Date, survey_schema_version:int`；本轮只建模型/索引，无提交接口。
- sessions 辅助集合：`_id, token_hash, user_id, created_at, expires_at`，认证状态同样存在 MongoDB。

唯一索引 users.username、surveys.public_token、sessions.token_hash；surveys(owner_id,created_at) 复合索引以 owner_id 为前缀；responses.survey_id；sessions.expires_at TTL。各集合自带 _id 主键索引。

questions/jump_rules 嵌入问卷定义，responses 独立，避免无界答卷数组与热点。API 用字符串 id/owner_id，DB 保留 ObjectId；时间均转 UTC，拒绝无时区 deadline。详见 [database-design.md](database-design.md)。

## D. 已实现 API

| Method | URL |
|---|---|
| POST | /api/auth/register |
| POST | /api/auth/login |
| POST | /api/auth/logout |
| GET | /api/auth/me |
| GET、POST | /api/surveys |
| GET、PUT、DELETE | /api/surveys/{survey_id} |
| POST | /api/surveys/{survey_id}/publish |
| POST | /api/surveys/{survey_id}/close |
| GET | /health、/、/docs、/openapi.json |

除认证入口及健康/页面外均需登录；接口输入、输出及错误完整记录于 [api.md](api.md)。PUT 更新基础字段，受保护字段不可传入。增加 DELETE 实现完整基础 CRUD。

## E. 身份认证方案

Argon2id 带盐哈希密码。登录生成 32 随机字节会话，HttpOnly/SameSite=Strict Cookie 保存 token，MongoDB 仅保存 SHA-256 摘要。默认一天过期，每次请求核查 expires_at，TTL 负责清理；登出删除会话并清 Cookie，旧 Cookie 重放无效。重复登录轮换当前会话；未知用户名走 dummy hash，错误统一 401。统一 current_user dependency 注入所有受保护接口。HTTPS 部署必须配置 COOKIE_SECURE=true。本地 HTTP 默认 false。浏览器跨站 Origin/Fetch-Site 请求被拒绝。

## F. owner 权限隔离

创建 owner_id 仅来自 current_user。列表数据库过滤 owner_id；读、改、删、发布、关闭均以 `_id + owner_id` 过滤，不依赖前端。对他人和不存在的问卷统一 404；非法 ObjectId 为 422。状态转换以原状态为条件原子更新，同目标重复操作幂等。

## G. 实际执行命令

完整命令清单见 [commands.md](commands.md)。包括环境检查、实际建 venv 与 pip install、真实 MongoDB ping/version、两次 pytest、Uvicorn 独立进程检查、pip check、compileall、`node --check app/static/app.js`。最后三项退出码均为 0。文档与日志由本地 Python 写入，没有使用子代理。

## H. pytest 完整最终结果与退出码

最终退出码：**0**。同一套用例 mock 35 项 + 真实 MongoDB 35 项。以下为最终 pytest 输出全文：

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.7.0 -- D:\Codex\survey-system\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Codex\survey-system
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 70 items

tests/test_system.py::test_register[mock] PASSED                         [  1%]
tests/test_system.py::test_register[mongo] PASSED                        [  2%]
tests/test_system.py::test_duplicate[mock] PASSED                        [  4%]
tests/test_system.py::test_duplicate[mongo] PASSED                       [  5%]
tests/test_system.py::test_bad_registration[mock-data0] PASSED           [  7%]
tests/test_system.py::test_bad_registration[mock-data1] PASSED           [  8%]
tests/test_system.py::test_bad_registration[mongo-data0] PASSED          [ 10%]
tests/test_system.py::test_bad_registration[mongo-data1] PASSED          [ 11%]
tests/test_system.py::test_login_and_me[mock] PASSED                     [ 12%]
tests/test_system.py::test_login_and_me[mongo] PASSED                    [ 14%]
tests/test_system.py::test_wrong_login[mock-alice] PASSED                [ 15%]
tests/test_system.py::test_wrong_login[mock-missing] PASSED              [ 17%]
tests/test_system.py::test_wrong_login[mongo-alice] PASSED               [ 18%]
tests/test_system.py::test_wrong_login[mongo-missing] PASSED             [ 20%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/auth/me-None] PASSED [ 21%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys-None] PASSED [ 22%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys-data2] PASSED [ 24%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys/012345678901234567890123-None] PASSED [ 25%]
tests/test_system.py::test_unauthenticated[mock-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 27%]
tests/test_system.py::test_unauthenticated[mock-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 28%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 30%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 31%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/auth/me-None] PASSED [ 32%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys-None] PASSED [ 34%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys-data2] PASSED [ 35%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys/012345678901234567890123-None] PASSED [ 37%]
tests/test_system.py::test_unauthenticated[mongo-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 38%]
tests/test_system.py::test_unauthenticated[mongo-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 40%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 41%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 42%]
tests/test_system.py::test_create_serialization[mock] PASSED             [ 44%]
tests/test_system.py::test_create_serialization[mongo] PASSED            [ 45%]
tests/test_system.py::test_update_delete[mock] PASSED                    [ 47%]
tests/test_system.py::test_update_delete[mongo] PASSED                   [ 48%]
tests/test_system.py::test_owner_isolation[mock] PASSED                  [ 50%]
tests/test_system.py::test_owner_isolation[mongo] PASSED                 [ 51%]
tests/test_system.py::test_publish_close[mock] PASSED                    [ 52%]
tests/test_system.py::test_publish_close[mongo] PASSED                   [ 54%]
tests/test_system.py::test_invalid_id[mock-invalid] PASSED               [ 55%]
tests/test_system.py::test_invalid_id[mock-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 57%]
tests/test_system.py::test_invalid_id[mock-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 58%]
tests/test_system.py::test_invalid_id[mongo-invalid] PASSED              [ 60%]
tests/test_system.py::test_invalid_id[mongo-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 61%]
tests/test_system.py::test_invalid_id[mongo-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 62%]
tests/test_system.py::test_missing_id[mock] PASSED                       [ 64%]
tests/test_system.py::test_missing_id[mongo] PASSED                      [ 65%]
tests/test_system.py::test_logout_revokes[mock] PASSED                   [ 67%]
tests/test_system.py::test_logout_revokes[mongo] PASSED                  [ 68%]
tests/test_system.py::test_expired_session[mock] PASSED                  [ 70%]
tests/test_system.py::test_expired_session[mongo] PASSED                 [ 71%]
tests/test_system.py::test_cookie_and_rotation[mock] PASSED              [ 72%]
tests/test_system.py::test_cookie_and_rotation[mongo] PASSED             [ 74%]
tests/test_system.py::test_cross_origin[mock] PASSED                     [ 75%]
tests/test_system.py::test_cross_origin[mongo] PASSED                    [ 77%]
tests/test_system.py::test_invalid_survey_input[mock-data0] PASSED       [ 78%]
tests/test_system.py::test_invalid_survey_input[mock-data1] PASSED       [ 80%]
tests/test_system.py::test_invalid_survey_input[mock-data2] PASSED       [ 81%]
tests/test_system.py::test_invalid_survey_input[mock-data3] PASSED       [ 82%]
tests/test_system.py::test_invalid_survey_input[mock-data4] PASSED       [ 84%]
tests/test_system.py::test_invalid_survey_input[mongo-data0] PASSED      [ 85%]
tests/test_system.py::test_invalid_survey_input[mongo-data1] PASSED      [ 87%]
tests/test_system.py::test_invalid_survey_input[mongo-data2] PASSED      [ 88%]
tests/test_system.py::test_invalid_survey_input[mongo-data3] PASSED      [ 90%]
tests/test_system.py::test_invalid_survey_input[mongo-data4] PASSED      [ 91%]
tests/test_system.py::test_indexes[mock] PASSED                          [ 92%]
tests/test_system.py::test_indexes[mongo] PASSED                         [ 94%]
tests/test_system.py::test_token_collision_retry[mock] PASSED            [ 95%]
tests/test_system.py::test_token_collision_retry[mongo] PASSED           [ 97%]
tests/test_system.py::test_home_and_health[mock] PASSED                  [ 98%]
tests/test_system.py::test_home_and_health[mongo] PASSED                 [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== 70 passed, 183 warnings in 7.04s =======================

```

## I. 启动验证结果

实际运行 Uvicorn 生产启动路径，真实 MongoDB 连接与建索引成功。启动脚本退出码 **0**；HTTP 检查原文如下：

```text
GET /: 200
GET /health: 200
GET /static/app.js: 200
GET /openapi.json: 200
POST /api/auth/register: 201
POST /api/auth/login: 200
POST /api/surveys: 201
POST /api/surveys/6ad102466c68b27ca3e96b8c/publish: 200
POST /api/surveys/6ad102466c68b27ca3e96b8c/close: 200
POST /api/auth/logout: 204
GET /api/surveys: 401
REAL_UVICORN_SMOKE=PASS
Temporary server stopped; disposable test database removed.

```

服务器输出保留 [startup-server.txt](startup-server.txt)。临时服务已停止；不在后台留常驻进程。测试只清理自建随机测试库。

## J. AI 日志

[ai-log.md](ai-log.md) 包含工具 Codex、完整实际 Prompt、续作指令、生成文件清单、设计、真实环境问题和修正、验证结果及未解决事项。[prompt-original.md](prompt-original.md) 为用户原消息逐字副本。从本聊天记录提取，不杜撰 Prompt 或人工修改。原始报错完整按工具返回保存 [errors-original.md](errors-original.md)；没有重构被工具截断的数据。

## K. 尚未实现

完整题目编辑器、高级题目/答案校验、条件跳转、公开填写页 /survey/{public_token}、填写提交、统计、复杂前端及 React/Vue。预留模块仅简短说明；不提供伪成功接口。未引入 Docker、Redis、Celery、消息队列、微服务或关系数据库。

## L. 风险、问题与下一阶段

1. 第三方 Starlette/httpx 与 mongomock 弃用警告仍在；测试通过但需后续协调依赖升级。可选 httpx2 自动审核未完成，原因为账户额度，未绕过审核。
2. answers 只定容器类型；下一阶段需定义 question_id、答案类型、validation、jump_rules 的结构及版本兼容；继续修改本代码并保留当前回归用例。
3. 截止时间、匿名、重复提交目前只存储，提交接口实现时必须在服务端执行规则。当前允许空题发布，deadline 不自动关闭。
4. 发布后只修改基本元数据，schema_version 本轮固定 1；下一阶段需设计题目改版、历史快照及并发编辑冲突规则。
5. 本轮 DELETE 物理删除；引入 responses 前需落实答卷保留、归档、级联或禁止删除政策。
6. 当前问卷列表未分页；无压力测试、登录限流或完整浏览器端到端测试。对本轮课程基础架构不额外引入大型设施。
7. MongoDB 无关系式外键，受控业务写入维护引用完整性；未配置数据库 JSON Schema validator。数据库直写权限应限定。
8. 原课程 DOCX 对阶段一总体功能要求比本轮范围更大；此交付遵守用户限定的基础设施子范围，不能声称已完成附件全部功能。
