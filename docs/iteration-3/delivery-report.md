# 第三轮增量交付：历史快照、跳转、公开填写与正式提交

项目：D:/Codex/survey-system；日期：2026-10-16（Asia/Shanghai）。完整 Prompt、原始错误、逐项测试和真实访问日志全部保存在本目录。

## A. 本轮总体设计

完整只读核对原源码/tests/README/docs、survey/question/validation/version 设计、MongoDB hello 与索引，再实跑 220 项基线。项目非 Git 仓库，未重建或创建远程仓库。

保持 FastAPI/PyMongo/MongoDB/Jinja2/pytest/.env 分层；增加 versions、jump_rules、responses service 与对应 schema，落实原 jump_engine/responses 占位模块，router 无复杂业务复制。统计仍未实现。

## B. 新增/修改文件

```text
修改既有源码/启动脚本：
app/core/database.py
app/core/security.py
app/main.py
app/models/response.py
app/routers/responses.py
app/routers/surveys.py
app/schemas/response.py
app/schemas/survey.py
app/services/jump_engine.py
app/services/questions.py
app/services/surveys.py
app/static/style.css
tests/smoke_questions.py
tests/smoke_startup.py

新增源码/测试：
app/schemas/jump_rule.py
app/services/jump_rules.py
app/services/responses.py
app/services/versions.py
app/static/survey.js
app/templates/survey.html
tests/smoke_responses.py
tests/test_jumps.py
tests/test_public_responses.py

更新文档：
README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md
docs/file-manifest.txt

新增证据目录：docs/iteration-3/

```

原 220 项测试源码和 fixture 哈希未变；业务 DELETE 政策变化在新测试覆盖，旧 smoke 的播种对象改为先发布。认证 router/密码/session 主逻辑保留，security 仅增加复用 current_user 的 optional_user。依赖未变。

## C. survey_versions 最终模型

```text
_id: ObjectId
survey_id: ObjectId
schema_version: int
questions: 完整题目定义数组
jump_rules: 完整跳转定义数组
created_at: UTC Date
created_reason: publish | question_change | jump_rule_change
```

唯一 `(survey_id,schema_version)`；只 insert/read，不更新/删除历史。current survey 保存最新版，历史不无限嵌入主文档。`get_survey_version(db,survey_id,schema_version)` 按 pair 取历史，不存在 404，不使用当前题目替代旧版。

## D. Snapshot 创建与一致性

本机 MongoDB 9.0.2 standalone，不要求事务。draft 编辑只增当前版本；publish 当前版先保存快照；published 题目/规则有效改变 +1 并保存新 snapshot。

协议：内存校验 → survey CAS 预留 `_pending_schema`（含唯一操作 ID、base 版本/状态、确定的 snapshot 与字段更新）→ insert snapshot → 比对重复内容，仅同一操作可幂等 → CAS 切换当前版本/定义/状态并清 pending。

预留时当前版不推进，快照失败不能发布或推进；异常 503 并保留恢复记录。后续读取/写入可以完成同一已授权操作，多个帮助者通过唯一键/CAS 协作。持久化的快照从不改写，不盲目删快照补偿。503 后需重读确认操作结果，恢复可能已完成原操作。

并发新结构预留失败 409；如恢复推进了版本，旧数组不能重定基到新版，必须重新读取。current/pending/gate 内部字段不暴露。旧系统已发布但无快照时，只补当前定义，无法伪造更早结构。

## E. Jump Rule 最终模型

```json
{"id":"r1","source_question_id":"q1","operator":"equals","value":"a","target_question_id":"q3","priority":1}
```

稳定字符串 ID；创建没有有效 ID 由服务端 UUID hex；同 survey 唯一，更新不可换 ID。priority 为 1..1000000 严格整数、默认 1，source 内唯一。选择题规则值必须是实际 option ID；数值用与原 Validation Engine 一致的有限数字/BSON int64 策略。text 不作为 source；前向 target.order > source.order；禁止无效引用、自跳、后跳、未知 operator。

## F. Jump Engine 行为

single equals、multiple contains、number equals/greater_than/greater_than_or_equal/less_than/less_than_or_equal。按 priority 稳定排序，第一命中生效；不命中按 order 下一题；最后完成 null。

`resolve_next_question` 处理单步；`validate_response_path` 从首题计算完整路径，执行原答案校验，visited set/max_steps 保护。访问到的 required 必须答，optional 可缺失；skipped required 不要求答，skipped/unknown/重复答案直接拒绝。

## G. Question/Jump 引用完整性

question 变更后统一重验现有规则。删除 source/target、切换题型、删规则引用的 option 或移序导致后跳，均 409，提示先改/删相关规则。失败在预留/写快照之前，题目、版本、快照均不变；不自动级联清规则。删规则后可正常删题。

## H. Public Survey API

| Method | URL | 行为 |
|---|---|---|
| GET | /api/public/surveys/{public_token} | 当前可填定义，字段白名单 |
| GET | /survey/{public_token} | 最小 Jinja2 + 原生 JS 填写页 |
| POST | /api/public/surveys/{public_token}/next | 指定历史版本的单步校验/跳转 |
| POST | /api/public/surveys/{public_token}/responses | 正式提交 |

owner 另有 POST/PUT/DELETE jump-rules 和 GET versions 端点，全部保留权限隔离。公开输出仅 id/title/description/schema_version/questions/jump_rules/填写政策/deadline，无 owner/password/session/pending 等内部字段。404 token 缺失；409 draft/closed；410 过期；401 需登录。页面显示四题型、逐题 next、错误提示、最终提交，不使用 React/Vue。

## I. Response 最终模型

```text
_id: ObjectId
survey_id: ObjectId
respondent_user_id: ObjectId|null
survey_schema_version: int
answers: [{question_id,value}]
visited_question_ids: [question_id]
submitted_at: UTC Date
dedupe_key: 可选字符串
```

保留 survey_id 索引，增加 dedupe_key unique sparse。答卷独立集合，不复制整份 schema，通过 survey_id+survey_schema_version 找到不可变历史定义。

## J. Response 提交流程

当前 survey 与状态/时间/身份政策 → 解析严格输入 → 读取该 survey 的提交版本 snapshot → 拒绝重复 question_id → 原 Validation Engine 校验 → Jump Engine 推导完整实际路径 → 拒绝额外答案 → 当前状态/deadline/政策原子准入 → 写答卷。

当前 13 可提交已发布 12，只要当前仍开放且政策允许；旧版规则/选项/范围按 12 解释，绝不套 13。请求不接受伪造 respondent_user_id、survey_id、visited path 或 dedupe_key。

## K. 匿名/登录策略

allow_anonymous=false：未登录 GET/页面/next/submit 均 401；已登录允许。true：未登录允许并存 null，已登录记录 ID。匿名没有可靠的自然人身份，不用 IP/Cookie 假称能精确限制重复。

## L. 重复提交并发保护

登录且禁止多次时生成 survey:<survey_id>:user:<user_id>，unique sparse 索引让并发只一条成功，另一 409；限制跨版本。历史查询兼容从允许多次切回禁止的政策，不能取代唯一约束。允许多次或匿名不写 key。两个同步 insert 线程在真实 MongoDB/mock 均验证一成功一冲突。

## M. deadline 行为

UTC aware；null 不限；now>deadline 拒绝，等于允许。加载/next/submit 都查，提交校验后在 survey 原子准入点复查。BSON 毫秒下界向上取整，测试等于及前后 1μs。校验期间突然过期返回 410，无答卷。

准入点是 `_last_response_admitted_at` 条件更新：关闭之后不能新准入；关闭前已准入的请求可以随后落库。不宣称关闭与答卷插入具备跨集合事务语义。

## N. DELETE 新策略

仅 draft 且无 pending 可物理删除，保留异常历史答卷防御检查；published 提示关闭、closed 保留历史，均 409。publish 与 DELETE 使用同一 survey 原子条件互斥。合法 response 只能准入 published，因此与可物理删除状态互斥；不级联删除 response/snapshot，不要求 replica set 或分布式锁。

## O. 实际执行命令

完整 [commands.md](commands.md)。实际执行基线、原 220 回归、扩展、最终 pytest；compileall；pip check；node --check；真实 Uvicorn smoke；MongoDB hello/version/index 检查。无依赖安装。Git 128、首次 smoke 1，修正后 smoke 0，全部 pytest/编译/依赖/JS 检查 0。

## P. pytest 最终结果、数量与退出码

**371 passed, 1706 warnings in 62.19s (0:01:02)；退出码 0。**

原 220 全通过；新公开/存储 API 112、新纯 Jump 39。真实 MongoDB 126、mock 126，纯 Validation/Jump 119，不重复套后端。完整输出见本文末及 pytest-final.txt。

## Q. 真实 MongoDB 测试

MongoDB 9.0.2 standalone，126 项真实库测试通过。覆盖 snapshot 唯一性/不变/失败恢复、published 并发、去重并发、历史版本解释、路径/权限、deadline、DELETE。随机测试库自动清理，未写用户业务数据。实际索引输出也在 smoke 原文。

## R. Uvicorn/真实 API smoke

当前最终代码实际输出如下（退出码 0，临时服务与随机库清理）：

```text
GET /: 200
GET /health: 200
GET /static/app.js: 200
GET /openapi.json: 200
POST /api/auth/register: 201
POST /api/auth/login: 200
POST /api/surveys: 201
PUT /api/surveys/6ad11087bc4706f9d2b3a518: 200
POST /api/surveys/6ad11087bc4706f9d2b3a518/questions: 201
POST /api/surveys/6ad11087bc4706f9d2b3a518/questions: 201
POST /api/surveys/6ad11087bc4706f9d2b3a518/questions: 201
POST /api/surveys/6ad11087bc4706f9d2b3a518/questions: 201
POST /api/surveys/6ad11087bc4706f9d2b3a518/jump-rules: 201
POST /api/surveys/6ad11087bc4706f9d2b3a518/publish: 200
GET /survey/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA: 200
GET /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA: 200
POST /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA/next: 200
POST /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA/next: 200
POST /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA/next: 200
POST /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA/responses: 201
MONGODB_RESPONSE_AND_ORIGINAL_SNAPSHOT=PASS
PUT /api/surveys/6ad11087bc4706f9d2b3a518/questions/q3: 200
POST /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA/responses: 201
STALE_VERSION_SUBMISSION_WITH_IMMUTABLE_SCHEMA=PASS
INDEXES {'_id_': {'v': 2, 'key': [('_id', 1)], 'collation': SON([('locale', 'simple')])}, 'survey_id_1_schema_version_1': {'v': 2, 'key': [('survey_id', 1), ('schema_version', 1)], 'unique': True, 'collation': SON([('locale', 'simple')])}} {'_id_': {'v': 2, 'key': [('_id', 1)], 'collation': SON([('locale', 'simple')])}, 'survey_id_1': {'v': 2, 'key': [('survey_id', 1)], 'collation': SON([('locale', 'simple')])}, 'dedupe_key_1': {'v': 2, 'key': [('dedupe_key', 1)], 'unique': True, 'sparse': True, 'collation': SON([('locale', 'simple')])}}
POST /api/surveys/6ad11087bc4706f9d2b3a518/close: 200
POST /api/public/surveys/g4kus_5ZrDNXazP7Qtmh39QaLrQxdLYyYBzoaZHbIXA/responses: 409
DELETE /api/surveys/6ad11087bc4706f9d2b3a518: 409
REAL_RESPONSE_API_SMOKE=PASS
POST /api/surveys: 201
POST /api/surveys/6ad11088bc4706f9d2b3a51d/publish: 200
POST /api/surveys/6ad11088bc4706f9d2b3a51d/close: 200
POST /api/auth/logout: 204
GET /api/surveys: 401
REAL_UVICORN_SMOKE=PASS
Temporary server stopped; disposable test database removed.

```

真实检查了 HTML/公开 API/next/submit；没有声称做过浏览器自动点击测试。

## S. AI 日志更新

../ai-log.md 追加本轮完整 Prompt、实际文件/设计/问题/修正/验证与未解决风险；Prompt 独立副本与用户附件按字节一致。保留前两轮记录，不虚构人工参与或测试失败。

## T. 本轮所有真实错误与修正

- Git 原文：`fatal: not a git repository (or any of the parent directories): .git`，128。仅记录事实，不创建远程仓库。
- 首次 smoke `httpx.ConnectTimeout: timed out`，1。完整 traceback 在 startup-first.txt/errors-original.md；当时服务已 startup complete。修正 loopback 不使用环境代理、有限 ConnectError/ConnectTimeout readiness 重试；后续真实全流程通过，不能断言首次根因一定是代理。
- 快照 insert/指针/publish 的 OperationFailure 是主动故障注入，503/旧版本/恢复均按预期；原始 traceback 在 pytest-runtime-final.log，不伪称为意外生产失败。
- 自查实际修正：保存默认 priority、hidden CSS、deadline 毫秒精度及恢复后旧数组 rebase 防护，均有对应测试或静态/流程检查。pytest 各次均通过，没有编造失败修复。
- 第三方 Starlette/httpx 与 mongomock 弃用警告仍保留，未隐藏。

完整原始报错与警告集中在 [errors-original.md](errors-original.md)，未改写或仅存摘要。

## U. 未实现与下一阶段风险

统计仍未实现；无复杂问卷编辑器、压力测试或真实浏览器点击 E2E。匿名不能精确去重，允许多次/匿名提交暂未有通用幂等键，网络重试可能多条。pending 故障后需要后续请求恢复，503 后需重读确认；外部数据库写入不遵守 API 的不可变约束，应限制权限。旧阶段未保存过的更早 schema 无法重建。pending 暂存一份候选定义仍需考虑 BSON 16 MB 上限。关闭前已准入请求可在关闭后落库，这是明确准入语义而非事务。


交付前公开链接检查：安全 GET/HEAD/OPTIONS 允许外站导航，POST/PUT/DELETE 仍拒绝跨站 Origin/Fetch-Site。补充回归在两个后端通过；没有破坏已有 220 项。修正后的最终结果以上述 371 项为准。

## 附：pytest 完整最终输出

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.7.0 -- D:\Codex\survey-system\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Codex\survey-system
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 371 items

tests/test_jumps.py::test_valid_rules[single_choice-equals-a] PASSED     [  0%]
tests/test_jumps.py::test_valid_rules[multiple_choice-contains-a] PASSED [  0%]
tests/test_jumps.py::test_valid_rules[number-equals-2] PASSED            [  0%]
tests/test_jumps.py::test_valid_rules[number-greater_than-2] PASSED      [  1%]
tests/test_jumps.py::test_valid_rules[number-greater_than_or_equal-2] PASSED [  1%]
tests/test_jumps.py::test_valid_rules[number-less_than-2] PASSED         [  1%]
tests/test_jumps.py::test_valid_rules[number-less_than_or_equal-2] PASSED [  1%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch0-invalid_operator] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch1-invalid_operator] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch2-invalid_rule_value] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[multiple_choice-patch3-invalid_rule_value] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[number-patch4-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[number-patch5-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[number-patch6-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[number-patch7-invalid_rule_value] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[number-patch8-invalid_rule_value] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[number-patch9-invalid_rule_value] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[text-patch10-invalid_operator] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch11-missing_question] PASSED [  5%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch12-missing_question] PASSED [  5%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch13-not_forward] PASSED [  5%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch14-not_forward] PASSED [  5%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch15-invalid_rule] PASSED [  6%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch16-invalid_rule] PASSED [  6%]
tests/test_jumps.py::test_duplicate_rules_and_priority[second0-duplicate_rule_id] PASSED [  6%]
tests/test_jumps.py::test_duplicate_rules_and_priority[second1-duplicate_priority] PASSED [  7%]
tests/test_jumps.py::test_resolve[single_choice-equals-a-a-q3] PASSED    [  7%]
tests/test_jumps.py::test_resolve[single_choice-equals-a-b-q2] PASSED    [  7%]
tests/test_jumps.py::test_resolve[multiple_choice-contains-a-answer2-q3] PASSED [  7%]
tests/test_jumps.py::test_resolve[multiple_choice-contains-a-answer3-q2] PASSED [  8%]
tests/test_jumps.py::test_resolve[number-greater_than-2-3-q3] PASSED     [  8%]
tests/test_jumps.py::test_resolve[number-greater_than-2-2-q2] PASSED     [  8%]
tests/test_jumps.py::test_resolve[number-greater_than_or_equal-2-2-q3] PASSED [  8%]
tests/test_jumps.py::test_resolve[number-less_than-2-1-q3] PASSED        [  9%]
tests/test_jumps.py::test_resolve[number-less_than_or_equal-2-2-q3] PASSED [  9%]
tests/test_jumps.py::test_resolve[number-equals-2-2-q3] PASSED           [  9%]
tests/test_jumps.py::test_sequential_last_and_priority PASSED            [  9%]
tests/test_jumps.py::test_path_required_skipped_extra_and_optional PASSED [ 10%]
tests/test_jumps.py::test_runtime_cycle_and_max_steps PASSED             [ 10%]
tests/test_public_responses.py::test_publish_snapshot_immutable_unique_and_owner_history[mock] PASSED [ 10%]
tests/test_public_responses.py::test_publish_snapshot_immutable_unique_and_owner_history[mongo] PASSED [ 11%]
tests/test_public_responses.py::test_jump_crud_snapshot_and_reference_integrity[mock] PASSED [ 11%]
tests/test_public_responses.py::test_jump_crud_snapshot_and_reference_integrity[mongo] PASSED [ 11%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mock-POST-] PASSED [ 11%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mock-PUT-/r1] PASSED [ 12%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mock-DELETE-/r1] PASSED [ 12%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mongo-POST-] PASSED [ 12%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mongo-PUT-/r1] PASSED [ 12%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mongo-DELETE-/r1] PASSED [ 13%]
tests/test_public_responses.py::test_rule_id_and_priority_validation[mock] PASSED [ 13%]
tests/test_public_responses.py::test_rule_id_and_priority_validation[mongo] PASSED [ 13%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-published-200] PASSED [ 14%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-draft-409] PASSED [ 14%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-closed-409] PASSED [ 14%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-missing-404] PASSED [ 14%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-expired-410] PASSED [ 15%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-published-200] PASSED [ 15%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-draft-409] PASSED [ 15%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-closed-409] PASSED [ 15%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-missing-404] PASSED [ 16%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-expired-410] PASSED [ 16%]
tests/test_public_responses.py::test_anonymous_policy[mock-False-False-401] PASSED [ 16%]
tests/test_public_responses.py::test_anonymous_policy[mock-False-True-201] PASSED [ 16%]
tests/test_public_responses.py::test_anonymous_policy[mock-True-False-201] PASSED [ 17%]
tests/test_public_responses.py::test_anonymous_policy[mock-True-True-201] PASSED [ 17%]
tests/test_public_responses.py::test_anonymous_policy[mongo-False-False-401] PASSED [ 17%]
tests/test_public_responses.py::test_anonymous_policy[mongo-False-True-201] PASSED [ 18%]
tests/test_public_responses.py::test_anonymous_policy[mongo-True-False-201] PASSED [ 18%]
tests/test_public_responses.py::test_anonymous_policy[mongo-True-True-201] PASSED [ 18%]
tests/test_public_responses.py::test_response_path_validation[mock-extra0-201] PASSED [ 18%]
tests/test_public_responses.py::test_response_path_validation[mock-extra1-422] PASSED [ 19%]
tests/test_public_responses.py::test_response_path_validation[mock-extra2-422] PASSED [ 19%]
tests/test_public_responses.py::test_response_path_validation[mock-extra3-422] PASSED [ 19%]
tests/test_public_responses.py::test_response_path_validation[mock-extra4-422] PASSED [ 19%]
tests/test_public_responses.py::test_response_path_validation[mock-extra5-422] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra6-422] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra7-201] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra8-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra9-201] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra10-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra11-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra0-201] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra1-422] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra2-422] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra3-422] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra4-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra5-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra6-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra7-201] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra8-422] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra9-201] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra10-422] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra11-422] PASSED [ 25%]
tests/test_public_responses.py::test_next_api_and_historical_submission[mock] PASSED [ 25%]
tests/test_public_responses.py::test_next_api_and_historical_submission[mongo] PASSED [ 25%]
tests/test_public_responses.py::test_duplicate_submission[mock-False-False-409] PASSED [ 25%]
tests/test_public_responses.py::test_duplicate_submission[mock-True-False-201] PASSED [ 26%]
tests/test_public_responses.py::test_duplicate_submission[mock-False-True-201] PASSED [ 26%]
tests/test_public_responses.py::test_duplicate_submission[mongo-False-False-409] PASSED [ 26%]
tests/test_public_responses.py::test_duplicate_submission[mongo-True-False-201] PASSED [ 26%]
tests/test_public_responses.py::test_duplicate_submission[mongo-False-True-201] PASSED [ 27%]
tests/test_public_responses.py::test_concurrent_dedupe_unique_index[mock] PASSED [ 27%]
tests/test_public_responses.py::test_concurrent_dedupe_unique_index[mongo] PASSED [ 27%]
tests/test_public_responses.py::test_submit_deadline[mock-none] PASSED   [ 28%]
tests/test_public_responses.py::test_submit_deadline[mock-future] PASSED [ 28%]
tests/test_public_responses.py::test_submit_deadline[mock-past] PASSED   [ 28%]
tests/test_public_responses.py::test_submit_deadline[mongo-none] PASSED  [ 28%]
tests/test_public_responses.py::test_submit_deadline[mongo-future] PASSED [ 29%]
tests/test_public_responses.py::test_submit_deadline[mongo-past] PASSED  [ 29%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mock-closed] PASSED [ 29%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mock-expired] PASSED [ 29%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mongo-closed] PASSED [ 30%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mongo-expired] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mock-draft-204] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mock-published-409] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mock-closed-409] PASSED [ 31%]
tests/test_public_responses.py::test_delete_state_policy[mongo-draft-204] PASSED [ 31%]
tests/test_public_responses.py::test_delete_state_policy[mongo-published-409] PASSED [ 31%]
tests/test_public_responses.py::test_delete_state_policy[mongo-closed-409] PASSED [ 32%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mock-snapshot] PASSED [ 32%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mock-pointer] PASSED [ 32%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mongo-snapshot] PASSED [ 32%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mongo-pointer] PASSED [ 33%]
tests/test_public_responses.py::test_publish_snapshot_failure_does_not_publish[mock] PASSED [ 33%]
tests/test_public_responses.py::test_publish_snapshot_failure_does_not_publish[mongo] PASSED [ 33%]
tests/test_public_responses.py::test_concurrent_published_edit_snapshots[mock] PASSED [ 33%]
tests/test_public_responses.py::test_concurrent_published_edit_snapshots[mongo] PASSED [ 34%]
tests/test_public_responses.py::test_rule_default_priority_is_saved[mock] PASSED [ 34%]
tests/test_public_responses.py::test_rule_default_priority_is_saved[mongo] PASSED [ 34%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mock-NaN] PASSED [ 35%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mock-Infinity] PASSED [ 35%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mock--Infinity] PASSED [ 35%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mongo-NaN] PASSED [ 35%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mongo-Infinity] PASSED [ 36%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mongo--Infinity] PASSED [ 36%]
tests/test_public_responses.py::test_duplicate_answer_and_cross_survey_version[mock] PASSED [ 36%]
tests/test_public_responses.py::test_duplicate_answer_and_cross_survey_version[mongo] PASSED [ 36%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mock--1-201] PASSED [ 37%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mock-0-201] PASSED [ 37%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mock-1-410] PASSED [ 37%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mongo--1-201] PASSED [ 38%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mongo-0-201] PASSED [ 38%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mongo-1-410] PASSED [ 38%]
tests/test_public_responses.py::test_metadata_change_does_not_snapshot[mock] PASSED [ 38%]
tests/test_public_responses.py::test_metadata_change_does_not_snapshot[mongo] PASSED [ 39%]
tests/test_public_responses.py::test_get_version_returns_detached_document[mock] PASSED [ 39%]
tests/test_public_responses.py::test_get_version_returns_detached_document[mongo] PASSED [ 39%]
tests/test_public_responses.py::test_recovery_cannot_rebase_stale_question_array[mock] PASSED [ 39%]
tests/test_public_responses.py::test_recovery_cannot_rebase_stale_question_array[mongo] PASSED [ 40%]
tests/test_public_responses.py::test_external_shared_link_read_but_cross_site_write_blocked[mock] PASSED [ 40%]
tests/test_public_responses.py::test_external_shared_link_read_but_cross_site_write_blocked[mongo] PASSED [ 40%]
tests/test_questions.py::test_create_each_type[mock-single_choice-rules0] PASSED [ 40%]
tests/test_questions.py::test_create_each_type[mock-multiple_choice-rules1] PASSED [ 41%]
tests/test_questions.py::test_create_each_type[mock-text-rules2] PASSED  [ 41%]
tests/test_questions.py::test_create_each_type[mock-number-rules3] PASSED [ 41%]
tests/test_questions.py::test_create_each_type[mongo-single_choice-rules0] PASSED [ 42%]
tests/test_questions.py::test_create_each_type[mongo-multiple_choice-rules1] PASSED [ 42%]
tests/test_questions.py::test_create_each_type[mongo-text-rules2] PASSED [ 42%]
tests/test_questions.py::test_create_each_type[mongo-number-rules3] PASSED [ 42%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data0] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data1] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data2] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data3] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data4] PASSED [ 44%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data5] PASSED [ 44%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data6] PASSED [ 44%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data7] PASSED [ 45%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data8] PASSED [ 45%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data9] PASSED [ 45%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data0] PASSED [ 45%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data1] PASSED [ 46%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data2] PASSED [ 46%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data3] PASSED [ 46%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data4] PASSED [ 46%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data5] PASSED [ 47%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data6] PASSED [ 47%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data7] PASSED [ 47%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data8] PASSED [ 47%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data9] PASSED [ 48%]
tests/test_questions.py::test_question_lifecycle_and_metadata_version[mock] PASSED [ 48%]
tests/test_questions.py::test_question_lifecycle_and_metadata_version[mongo] PASSED [ 48%]
tests/test_questions.py::test_order_and_stable_ids[mock] PASSED          [ 49%]
tests/test_questions.py::test_order_and_stable_ids[mongo] PASSED         [ 49%]
tests/test_questions.py::test_id_conflicts_and_invalid_order[mock] PASSED [ 49%]
tests/test_questions.py::test_id_conflicts_and_invalid_order[mongo] PASSED [ 49%]
tests/test_questions.py::test_auth_required[mock-POST-] PASSED           [ 50%]
tests/test_questions.py::test_auth_required[mock-PUT-/missing] PASSED    [ 50%]
tests/test_questions.py::test_auth_required[mock-DELETE-/missing] PASSED [ 50%]
tests/test_questions.py::test_auth_required[mongo-POST-] PASSED          [ 50%]
tests/test_questions.py::test_auth_required[mongo-PUT-/missing] PASSED   [ 51%]
tests/test_questions.py::test_auth_required[mongo-DELETE-/missing] PASSED [ 51%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-POST-] PASSED [ 51%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-PUT-/q1] PASSED [ 52%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-DELETE-/q1] PASSED [ 52%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-POST-] PASSED [ 52%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-PUT-/q1] PASSED [ 52%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-DELETE-/q1] PASSED [ 53%]
tests/test_questions.py::test_missing_question[mock] PASSED              [ 53%]
tests/test_questions.py::test_missing_question[mongo] PASSED             [ 53%]
tests/test_questions.py::test_published_edit_closed_readonly[mock] PASSED [ 53%]
tests/test_questions.py::test_published_edit_closed_readonly[mongo] PASSED [ 54%]
tests/test_questions.py::test_delete_survey_protects_responses[mock] PASSED [ 54%]
tests/test_questions.py::test_delete_survey_protects_responses[mongo] PASSED [ 54%]
tests/test_questions.py::test_response_does_not_leak_survey_existence[mock] PASSED [ 54%]
tests/test_questions.py::test_response_does_not_leak_survey_existence[mongo] PASSED [ 55%]
tests/test_questions.py::test_concurrent_question_edits_use_cas[mock] PASSED [ 55%]
tests/test_questions.py::test_concurrent_question_edits_use_cas[mongo] PASSED [ 55%]
tests/test_questions.py::test_commit_preserves_unrelated_fields_and_checks_status[mock] PASSED [ 56%]
tests/test_questions.py::test_commit_preserves_unrelated_fields_and_checks_status[mongo] PASSED [ 56%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock-NaN] PASSED [ 56%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock-Infinity] PASSED [ 56%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock--Infinity] PASSED [ 57%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo-NaN] PASSED [ 57%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo-Infinity] PASSED [ 57%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo--Infinity] PASSED [ 57%]
tests/test_questions.py::test_edit_options_validation_required_each_bumps_once[mock] PASSED [ 58%]
tests/test_questions.py::test_edit_options_validation_required_each_bumps_once[mongo] PASSED [ 58%]
tests/test_questions.py::test_published_delete_question_bumps_version[mock] PASSED [ 58%]
tests/test_questions.py::test_published_delete_question_bumps_version[mongo] PASSED [ 59%]
tests/test_questions.py::test_structure_change_ignores_simultaneous_metadata_edit[mock] PASSED [ 59%]
tests/test_questions.py::test_structure_change_ignores_simultaneous_metadata_edit[mongo] PASSED [ 59%]
tests/test_system.py::test_register[mock] PASSED                         [ 59%]
tests/test_system.py::test_register[mongo] PASSED                        [ 60%]
tests/test_system.py::test_duplicate[mock] PASSED                        [ 60%]
tests/test_system.py::test_duplicate[mongo] PASSED                       [ 60%]
tests/test_system.py::test_bad_registration[mock-data0] PASSED           [ 60%]
tests/test_system.py::test_bad_registration[mock-data1] PASSED           [ 61%]
tests/test_system.py::test_bad_registration[mongo-data0] PASSED          [ 61%]
tests/test_system.py::test_bad_registration[mongo-data1] PASSED          [ 61%]
tests/test_system.py::test_login_and_me[mock] PASSED                     [ 61%]
tests/test_system.py::test_login_and_me[mongo] PASSED                    [ 62%]
tests/test_system.py::test_wrong_login[mock-alice] PASSED                [ 62%]
tests/test_system.py::test_wrong_login[mock-missing] PASSED              [ 62%]
tests/test_system.py::test_wrong_login[mongo-alice] PASSED               [ 63%]
tests/test_system.py::test_wrong_login[mongo-missing] PASSED             [ 63%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/auth/me-None] PASSED [ 63%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys-None] PASSED [ 63%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys-data2] PASSED [ 64%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys/012345678901234567890123-None] PASSED [ 64%]
tests/test_system.py::test_unauthenticated[mock-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 64%]
tests/test_system.py::test_unauthenticated[mock-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 64%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 65%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 65%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/auth/me-None] PASSED [ 65%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys-None] PASSED [ 66%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys-data2] PASSED [ 66%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys/012345678901234567890123-None] PASSED [ 66%]
tests/test_system.py::test_unauthenticated[mongo-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 66%]
tests/test_system.py::test_unauthenticated[mongo-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 67%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 67%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 67%]
tests/test_system.py::test_create_serialization[mock] PASSED             [ 67%]
tests/test_system.py::test_create_serialization[mongo] PASSED            [ 68%]
tests/test_system.py::test_update_delete[mock] PASSED                    [ 68%]
tests/test_system.py::test_update_delete[mongo] PASSED                   [ 68%]
tests/test_system.py::test_owner_isolation[mock] PASSED                  [ 69%]
tests/test_system.py::test_owner_isolation[mongo] PASSED                 [ 69%]
tests/test_system.py::test_publish_close[mock] PASSED                    [ 69%]
tests/test_system.py::test_publish_close[mongo] PASSED                   [ 69%]
tests/test_system.py::test_invalid_id[mock-invalid] PASSED               [ 70%]
tests/test_system.py::test_invalid_id[mock-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 70%]
tests/test_system.py::test_invalid_id[mock-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 70%]
tests/test_system.py::test_invalid_id[mongo-invalid] PASSED              [ 70%]
tests/test_system.py::test_invalid_id[mongo-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 71%]
tests/test_system.py::test_invalid_id[mongo-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 71%]
tests/test_system.py::test_missing_id[mock] PASSED                       [ 71%]
tests/test_system.py::test_missing_id[mongo] PASSED                      [ 71%]
tests/test_system.py::test_logout_revokes[mock] PASSED                   [ 72%]
tests/test_system.py::test_logout_revokes[mongo] PASSED                  [ 72%]
tests/test_system.py::test_expired_session[mock] PASSED                  [ 72%]
tests/test_system.py::test_expired_session[mongo] PASSED                 [ 73%]
tests/test_system.py::test_cookie_and_rotation[mock] PASSED              [ 73%]
tests/test_system.py::test_cookie_and_rotation[mongo] PASSED             [ 73%]
tests/test_system.py::test_cross_origin[mock] PASSED                     [ 73%]
tests/test_system.py::test_cross_origin[mongo] PASSED                    [ 74%]
tests/test_system.py::test_invalid_survey_input[mock-data0] PASSED       [ 74%]
tests/test_system.py::test_invalid_survey_input[mock-data1] PASSED       [ 74%]
tests/test_system.py::test_invalid_survey_input[mock-data2] PASSED       [ 74%]
tests/test_system.py::test_invalid_survey_input[mock-data3] PASSED       [ 75%]
tests/test_system.py::test_invalid_survey_input[mock-data4] PASSED       [ 75%]
tests/test_system.py::test_invalid_survey_input[mongo-data0] PASSED      [ 75%]
tests/test_system.py::test_invalid_survey_input[mongo-data1] PASSED      [ 76%]
tests/test_system.py::test_invalid_survey_input[mongo-data2] PASSED      [ 76%]
tests/test_system.py::test_invalid_survey_input[mongo-data3] PASSED      [ 76%]
tests/test_system.py::test_invalid_survey_input[mongo-data4] PASSED      [ 76%]
tests/test_system.py::test_indexes[mock] PASSED                          [ 77%]
tests/test_system.py::test_indexes[mongo] PASSED                         [ 77%]
tests/test_system.py::test_token_collision_retry[mock] PASSED            [ 77%]
tests/test_system.py::test_token_collision_retry[mongo] PASSED           [ 77%]
tests/test_system.py::test_home_and_health[mock] PASSED                  [ 78%]
tests/test_system.py::test_home_and_health[mongo] PASSED                 [ 78%]
tests/test_validation.py::test_valid_definitions[single_choice-rules0] PASSED [ 78%]
tests/test_validation.py::test_valid_definitions[multiple_choice-rules1] PASSED [ 78%]
tests/test_validation.py::test_valid_definitions[text-rules2] PASSED     [ 79%]
tests/test_validation.py::test_valid_definitions[number-rules3] PASSED   [ 79%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch0-invalid_definition] PASSED [ 79%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch1-empty_title] PASSED [ 80%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch2-too_few_options] PASSED [ 80%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch3-too_few_options] PASSED [ 80%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch4-duplicate_option_id] PASSED [ 80%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch5-empty_option_label] PASSED [ 81%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch6-unsupported_rule] PASSED [ 81%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch7-invalid_range] PASSED [ 81%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch8-conflicting_exact] PASSED [ 81%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch9-conflicting_exact] PASSED [ 82%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch10-impossible_selection_count] PASSED [ 82%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch11-unsatisfiable_required] PASSED [ 82%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch12-invalid_rule_value] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch13-invalid_rule_value] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch14-invalid_rule_value] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[text-patch15-invalid_range] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[text-patch16-unsatisfiable_required] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[text-patch17-invalid_rule_value] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[text-patch18-invalid_rule_value] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[text-patch19-unexpected_options] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[number-patch20-invalid_range] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[number-patch21-invalid_rule_value] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[number-patch22-invalid_rule_value] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[number-patch23-invalid_rule_value] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[number-patch24-invalid_rule_value] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[number-patch25-invalid_rule_value] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[number-patch26-unsatisfiable_integer] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[number-patch27-unsupported_rule] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[number-patch28-invalid_definition] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[number-patch29-invalid_definition] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[number-patch30-invalid_definition] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[number-patch31-invalid_definition] PASSED [ 88%]
tests/test_validation.py::test_invalid_definitions[number-patch32-invalid_definition] PASSED [ 88%]
tests/test_validation.py::test_required_missing[answer0-single_choice] PASSED [ 88%]
tests/test_validation.py::test_required_missing[answer0-multiple_choice] PASSED [ 88%]
tests/test_validation.py::test_required_missing[answer0-text] PASSED     [ 89%]
tests/test_validation.py::test_required_missing[answer0-number] PASSED   [ 89%]
tests/test_validation.py::test_required_missing[None-single_choice] PASSED [ 89%]
tests/test_validation.py::test_required_missing[None-multiple_choice] PASSED [ 90%]
tests/test_validation.py::test_required_missing[None-text] PASSED        [ 90%]
tests/test_validation.py::test_required_missing[None-number] PASSED      [ 90%]
tests/test_validation.py::test_answers[single_choice-rules0-a-None] PASSED [ 90%]
tests/test_validation.py::test_answers[single_choice-rules1-missing-invalid_option] PASSED [ 91%]
tests/test_validation.py::test_answers[single_choice-rules2-answer2-invalid_option] PASSED [ 91%]
tests/test_validation.py::test_answers[single_choice-rules3-True-invalid_option] PASSED [ 91%]
tests/test_validation.py::test_answers[multiple_choice-rules4-answer4-None] PASSED [ 91%]
tests/test_validation.py::test_answers[multiple_choice-rules5-answer5-min_selections] PASSED [ 92%]
tests/test_validation.py::test_answers[multiple_choice-rules6-answer6-max_selections] PASSED [ 92%]
tests/test_validation.py::test_answers[multiple_choice-rules7-answer7-exact_selections] PASSED [ 92%]
tests/test_validation.py::test_answers[multiple_choice-rules8-answer8-duplicate_selection] PASSED [ 92%]
tests/test_validation.py::test_answers[multiple_choice-rules9-answer9-invalid_option] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules10-a-invalid_answer_type] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules11-answer11-invalid_answer_type] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules12-answer12-invalid_answer_type] PASSED [ 94%]
tests/test_validation.py::test_answers[text-rules13-\u4e2d\u6587-None] PASSED [ 94%]
tests/test_validation.py::test_answers[text-rules14-a-min_length] PASSED [ 94%]
tests/test_validation.py::test_answers[text-rules15-abc-max_length] PASSED [ 94%]
tests/test_validation.py::test_answers[text-rules16-12-invalid_answer_type] PASSED [ 95%]
tests/test_validation.py::test_answers[text-rules17-  -required] PASSED  [ 95%]
tests/test_validation.py::test_answers[number-rules18-5-None] PASSED     [ 95%]
tests/test_validation.py::test_answers[number-rules19--1-min] PASSED     [ 95%]
tests/test_validation.py::test_answers[number-rules20-11-max] PASSED     [ 96%]
tests/test_validation.py::test_answers[number-rules21-1.5-integer_only] PASSED [ 96%]
tests/test_validation.py::test_answers[number-rules22-2.0-None] PASSED   [ 96%]
tests/test_validation.py::test_answers[number-rules23-True-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules24-False-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules25-1.5-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules26-nan-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules27-inf-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_answers[number-rules28--inf-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_answers[number-rules29-9223372036854775808-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_empty_answers[single_choice-] PASSED      [ 98%]
tests/test_validation.py::test_empty_answers[multiple_choice-empty1] PASSED [ 99%]
tests/test_validation.py::test_empty_answers[text-] PASSED               [ 99%]
tests/test_validation.py::test_optional_nonempty_answer_still_validates PASSED [ 99%]
tests/test_validation.py::test_engine_does_not_mutate_input_and_refuses_invalid_definition PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_public_responses.py: 1165 warnings
tests/test_questions.py: 358 warnings
tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================ 371 passed, 1706 warnings in 62.19s (0:01:02) ================

```
