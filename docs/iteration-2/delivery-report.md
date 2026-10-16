# 第二轮交付报告：题目、Validation、schema_version

日期：2026-10-16，Asia/Shanghai。项目仍为 D:/Codex/survey-system。

## A. 本轮设计说明

先完整只读检查源码/测试/docs 与 Git 状态，实际回归原 70 项，再增量开发。Git 非仓库（退出码 128）已记录；未创建新项目、远程仓库或替换既有架构。

复用原 FastAPI/PyMongo/Jinja2/.env/pytest 体系；不改 main、认证、安全、连接、模型及原状态机。类型在 schemas/question.py，唯一配置/答案规则在 services/validation.py；顺序、ID、权限、并发提交在 services/questions.py。router 仅转发，生产仍是 MongoDB，未新增依赖或 questions 集合。

## B. 修改/新增文件

```text
修改：
README.md
app/routers/surveys.py
app/schemas/survey.py
app/services/surveys.py
app/services/validation.py
tests/smoke_startup.py
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md
docs/file-manifest.txt

新增代码/测试：
app/schemas/question.py
app/services/questions.py
tests/test_questions.py
tests/test_validation.py
tests/smoke_questions.py

新增本轮证据/报告：
docs/iteration-2/baseline-hashes.json
docs/iteration-2/baseline-preservation.txt
docs/iteration-2/changed-files.txt
docs/iteration-2/commands.md
docs/iteration-2/compile.txt
docs/iteration-2/delivery-report.md
docs/iteration-2/errors-original.md
docs/iteration-2/git-status.txt
docs/iteration-2/pip-check.txt
docs/iteration-2/prompt-original.txt
docs/iteration-2/pytest-baseline.txt
docs/iteration-2/pytest-final.txt
docs/iteration-2/pytest-first.txt
docs/iteration-2/startup-first.txt
docs/iteration-2/startup-server.txt
docs/iteration-2/test-counts.json
docs/iteration-2/verification.json

```

原 test_system.py、conftest.py 哈希未变；原 auth/core/main/model 均未变。第一轮日志/Prompt/报告保留，本轮日志独立存 iteration-2。新 smoke 脚本通过旧启动脚本的可选 hook 复用连接与进程检查；旧脚本无参数行为仍保留。

## C. 最终 Question 数据结构

```json
{
  "id":"q_fruit",
  "type":"multiple_choice",
  "title":"喜欢的水果",
  "required":true,
  "order":1,
  "options":[{"id":"a","label":"苹果"},{"id":"b","label":"香蕉"}],
  "validation":{"min_selections":1,"max_selections":2,"exact_selections":1}
}
```

四类 type：single_choice、multiple_choice、text、number。默认 required=false，options=[]，validation={}；题目总数 ≤200，选择题 2–100 个选项。id 为 1–64 字符 `[A-Za-z0-9_-]` 字符串，创建可提供或自动 UUID hex，在 survey 内唯一；更新不可换 ID。options.id 在题内唯一。题目/选项标题 trim 且不为空，最多 500 字符。

order 从 1 连续计数；POST 省略追加、PUT 省略保留位置，传值可插入/移动，删除自动重排。重排不改变其他题目 ID。

## D. Validation Engine

两个纯业务入口：`validate_question_definition(definition)` 和 `validate_answer(definition, answer=MISSING)`。统一 ValidationResult 提供 valid、errors，每条错误 code/field/message；合法定义带规范化 question。定义不合法时不进行答案校验。HTTP 将定义错误转成 422，不在 router 重写规则。

- single_choice：存在的 option ID，required 时不能缺失。
- multiple_choice：字符串数组、不重复、选项存在；min/max/exact 非负严格整数且不超过选项数；min≤max，exact 满足 min/max，拒绝不可满足必答配置。
- text：字符串；按 Unicode code point 检查 min_length/max_length，范围一致；必答空字符串/纯空白失败。非必答 missing/null/空串跳过；其他非空字符串照常校验原始长度。
- number：有限 JSON number；拒绝 bool、数字字符串、NaN、±Infinity，整数须为 BSON int64 范围。integer_only 接受 2、2.0，拒绝 2.5；min/max 有限且 min≤max，整数范围须可满足。
- 非本题型规则、未知字段、错误类型和非法 ID 在创建/修改即拒绝。错误不回显原始非有限输入，避免 JSON 编码错误。

本轮不开放答案提交 API；后续 response service 直接复用 validate_answer，无需重写规则。

## E. schema_version 实际行为

新问卷 1。新增、删除及实际更改题目 title/type/required/order/options/validation，一次请求只 +1。插入/删除导致多个 order 改变也只 +1；完全相同 PUT 不增加。survey 普通元信息和发布/关闭不增加版本；客户端传 schema_version 被拒绝。

`commit_structure` 以 `_id+owner_id+schema_version+status` 作为更新条件，`$set` 仅改指定结构字段和 updated_at，同一 MongoDB 原子操作 `$inc:1`。并发冲突 409，重新读取再提交；不覆盖并发元信息修改。4 线程同版本写入测试在两个数据后端均验证：1 成功、3 冲突，最终仅 +1。

为未来已校验 jump_rules 保留同一结构提交边界；未提供跳转修改接口或执行器。published 可编辑；closed 题目只读（409）、可读取，以保留关闭时定义。原状态机不变。

## F. 题目 API

| Method | URL | 成功 |
|---|---|---|
| POST | /api/surveys/{survey_id}/questions | 201 SurveyOut |
| PUT | /api/surveys/{survey_id}/questions/{question_id} | 200 SurveyOut |
| DELETE | /api/surveys/{survey_id}/questions/{question_id} | 200 SurveyOut |

统一返回整份问卷，包含更新后顺序与版本。读取复用 GET survey。PUT 为整题替换而非 PATCH，type/title 必填，省略可选字段回默认；id/order 省略保留。401 未登录；403 跨站；404 他人/不存在 survey/question；422 非法 ID/定义/order；409 重复 ID/closed/并发冲突。完整输入输出在 ../api.md。

## G. survey 删除保护

先校验 owner 后查 responses.survey_id：有任何答卷即 409，建议关闭，问卷和答卷均保留；无答卷继续物理删除 204。禁止级联删除。用测试库直接播种 response 检查，没有假装已实现正式提交接口。

当前没有生产 response 写入，故未引入事务设施；未来提交上线前必须解决检查与删除之间的跨集合竞态。

## H. 实际执行命令

详见 [commands.md](commands.md)。核心实际命令：

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.venv/Scripts/python.exe -m pytest tests/test_system.py -v
.venv/Scripts/python.exe -m compileall -q app tests
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe tests/smoke_questions.py
.venv/Scripts/python.exe -m pip check
```

基线后补充题目代码并跑 208 项，再增加非有限 HTTP JSON、options/validation 等边界用例并最终跑 220 项。compileall/pip check 全部退出码 0。无安装新依赖命令。

## I. pytest 完整最终结果与退出码

最终 220 passed, 541 warnings in 16.60s；退出码 **0**。原 70 用例仍全部通过，测试源文件和 fixture 哈希未变。

分类：原用例 70、新题目 API 70、纯 engine 80；mock 70、MongoDB 70，engine 80 不依赖数据库。完整逐项输出附后，也独立保存在 pytest-final.txt。

## J. 真实 MongoDB 测试

本次真实 ping 成功，MongoDB 9.0.2；Python 3.12.14。70 项真实数据库用例全部通过，包括原功能、新题型、ObjectId/UTC 序列化、版本递增、权限、删除保护、非有限 JSON 和并发条件写。通过同一个 db fixture 切换后端，没有复制业务测试文件。使用 UUID 随机测试库，仅清理测试自建数据库。

## K. 启动/API 实际验证

真实 Uvicorn 子进程使用生产连接/settings/lifespan，启动及接口检查退出码 **0**；输出如下：

```text
GET /: 200
GET /health: 200
GET /static/app.js: 200
GET /openapi.json: 200
POST /api/auth/register: 201
POST /api/auth/login: 200
POST /api/surveys: 201
POST /api/surveys/6ad106bd9be20203efff70fc/questions: 201
PUT /api/surveys/6ad106bd9be20203efff70fc: 200
GET /api/surveys/6ad106bd9be20203efff70fc: 200
POST /api/surveys/6ad106bd9be20203efff70fc/publish: 200
PUT /api/surveys/6ad106bd9be20203efff70fc/questions/stable: 200
DELETE /api/surveys/6ad106bd9be20203efff70fc/questions/stable: 200
POST /api/surveys/6ad106bd9be20203efff70fc/questions: 201
POST /api/surveys/6ad106bd9be20203efff70fc/close: 200
POST /api/surveys/6ad106bd9be20203efff70fc/questions: 409
GET /api/surveys/6ad106bd9be20203efff70fc: 200
POST /api/surveys: 201
DELETE /api/surveys/6ad106bd9be20203efff70fd: 409
POST /api/surveys: 201
DELETE /api/surveys/6ad106bd9be20203efff70fe: 204
REAL_QUESTION_API_SMOKE=PASS
POST /api/surveys: 201
POST /api/surveys/6ad106be9be20203efff70ff/publish: 200
POST /api/surveys/6ad106be9be20203efff70ff/close: 200
POST /api/auth/logout: 204
GET /api/surveys: 401
REAL_UVICORN_SMOKE=PASS
Temporary server stopped; disposable test database removed.

```

服务器日志 startup-server.txt 保存 Application startup complete 和真实 HTTP 访问。临时进程已终止，临时测试库已清理，不留下后台服务。

## L. ai-log 更新说明

`../ai-log.md` 真实追加第二轮记录，保留第一轮内容；完整 Prompt 从用户粘贴附件复制，按字节核对一致并全文嵌入日志。包含实际改动、设计、验证、问题与未解决事项，未编造人工修改。

## M. 实际错误与修正

仅 Git 非仓库是本轮实际工具错误，退出码 128。完整原文：

```text
fatal: not a git repository (or any of the parent directories): .git
```

处理是记录现状、继续现有目录开发；没有擅自初始化或创建远程仓库。基线、扩展、最终 pytest 和真实 API 检查均无失败，不虚构错误修复。

自查补强了可选文本非空时长度校验、BSON int64 边界、HTTP NaN 错误安全序列化与并发/字段变化测试；这些不是失败后编造的修复记录。第三方弃用警告仍在，原文完整保留 errors-original.md 与 pytest-final.txt，未隐藏。

## N. 尚未实现与下一阶段风险

- 不实现条件跳转执行、公开填写页面、response 正式提交、统计、复杂前端编辑器。
- schema_version 不等于历史快照，旧题目被替换后不能仅靠数字恢复；正式提交前需落实结构快照/旧版本解释策略。
- 提交上线前必须让答卷写入和 survey 删除遵守共同的跨集合一致性协议，当前先查后删不能保证与未来并发提交串行化。
- deadline、匿名、重复提交目前仍为元信息，未来提交需服务端约束；跳转定义与题目删除引用完整性仍需下一轮实现。
- 第三方弃用警告尚存；没有压力测试、长时间并发负载测试或浏览器编辑器端到端测试。

## 附：pytest 最终原文

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.7.0 -- D:\Codex\survey-system\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Codex\survey-system
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 220 items

tests/test_questions.py::test_create_each_type[mock-single_choice-rules0] PASSED [  0%]
tests/test_questions.py::test_create_each_type[mock-multiple_choice-rules1] PASSED [  0%]
tests/test_questions.py::test_create_each_type[mock-text-rules2] PASSED  [  1%]
tests/test_questions.py::test_create_each_type[mock-number-rules3] PASSED [  1%]
tests/test_questions.py::test_create_each_type[mongo-single_choice-rules0] PASSED [  2%]
tests/test_questions.py::test_create_each_type[mongo-multiple_choice-rules1] PASSED [  2%]
tests/test_questions.py::test_create_each_type[mongo-text-rules2] PASSED [  3%]
tests/test_questions.py::test_create_each_type[mongo-number-rules3] PASSED [  3%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data0] PASSED [  4%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data1] PASSED [  4%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data2] PASSED [  5%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data3] PASSED [  5%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data4] PASSED [  5%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data5] PASSED [  6%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data6] PASSED [  6%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data7] PASSED [  7%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data8] PASSED [  7%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data9] PASSED [  8%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data0] PASSED [  8%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data1] PASSED [  9%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data2] PASSED [  9%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data3] PASSED [ 10%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data4] PASSED [ 10%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data5] PASSED [ 10%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data6] PASSED [ 11%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data7] PASSED [ 11%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data8] PASSED [ 12%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data9] PASSED [ 12%]
tests/test_questions.py::test_question_lifecycle_and_metadata_version[mock] PASSED [ 13%]
tests/test_questions.py::test_question_lifecycle_and_metadata_version[mongo] PASSED [ 13%]
tests/test_questions.py::test_order_and_stable_ids[mock] PASSED          [ 14%]
tests/test_questions.py::test_order_and_stable_ids[mongo] PASSED         [ 14%]
tests/test_questions.py::test_id_conflicts_and_invalid_order[mock] PASSED [ 15%]
tests/test_questions.py::test_id_conflicts_and_invalid_order[mongo] PASSED [ 15%]
tests/test_questions.py::test_auth_required[mock-POST-] PASSED           [ 15%]
tests/test_questions.py::test_auth_required[mock-PUT-/missing] PASSED    [ 16%]
tests/test_questions.py::test_auth_required[mock-DELETE-/missing] PASSED [ 16%]
tests/test_questions.py::test_auth_required[mongo-POST-] PASSED          [ 17%]
tests/test_questions.py::test_auth_required[mongo-PUT-/missing] PASSED   [ 17%]
tests/test_questions.py::test_auth_required[mongo-DELETE-/missing] PASSED [ 18%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-POST-] PASSED [ 18%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-PUT-/q1] PASSED [ 19%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-DELETE-/q1] PASSED [ 19%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-POST-] PASSED [ 20%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-PUT-/q1] PASSED [ 20%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-DELETE-/q1] PASSED [ 20%]
tests/test_questions.py::test_missing_question[mock] PASSED              [ 21%]
tests/test_questions.py::test_missing_question[mongo] PASSED             [ 21%]
tests/test_questions.py::test_published_edit_closed_readonly[mock] PASSED [ 22%]
tests/test_questions.py::test_published_edit_closed_readonly[mongo] PASSED [ 22%]
tests/test_questions.py::test_delete_survey_protects_responses[mock] PASSED [ 23%]
tests/test_questions.py::test_delete_survey_protects_responses[mongo] PASSED [ 23%]
tests/test_questions.py::test_response_does_not_leak_survey_existence[mock] PASSED [ 24%]
tests/test_questions.py::test_response_does_not_leak_survey_existence[mongo] PASSED [ 24%]
tests/test_questions.py::test_concurrent_question_edits_use_cas[mock] PASSED [ 25%]
tests/test_questions.py::test_concurrent_question_edits_use_cas[mongo] PASSED [ 25%]
tests/test_questions.py::test_commit_preserves_unrelated_fields_and_checks_status[mock] PASSED [ 25%]
tests/test_questions.py::test_commit_preserves_unrelated_fields_and_checks_status[mongo] PASSED [ 26%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock-NaN] PASSED [ 26%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock-Infinity] PASSED [ 27%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock--Infinity] PASSED [ 27%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo-NaN] PASSED [ 28%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo-Infinity] PASSED [ 28%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo--Infinity] PASSED [ 29%]
tests/test_questions.py::test_edit_options_validation_required_each_bumps_once[mock] PASSED [ 29%]
tests/test_questions.py::test_edit_options_validation_required_each_bumps_once[mongo] PASSED [ 30%]
tests/test_questions.py::test_published_delete_question_bumps_version[mock] PASSED [ 30%]
tests/test_questions.py::test_published_delete_question_bumps_version[mongo] PASSED [ 30%]
tests/test_questions.py::test_structure_change_ignores_simultaneous_metadata_edit[mock] PASSED [ 31%]
tests/test_questions.py::test_structure_change_ignores_simultaneous_metadata_edit[mongo] PASSED [ 31%]
tests/test_system.py::test_register[mock] PASSED                         [ 32%]
tests/test_system.py::test_register[mongo] PASSED                        [ 32%]
tests/test_system.py::test_duplicate[mock] PASSED                        [ 33%]
tests/test_system.py::test_duplicate[mongo] PASSED                       [ 33%]
tests/test_system.py::test_bad_registration[mock-data0] PASSED           [ 34%]
tests/test_system.py::test_bad_registration[mock-data1] PASSED           [ 34%]
tests/test_system.py::test_bad_registration[mongo-data0] PASSED          [ 35%]
tests/test_system.py::test_bad_registration[mongo-data1] PASSED          [ 35%]
tests/test_system.py::test_login_and_me[mock] PASSED                     [ 35%]
tests/test_system.py::test_login_and_me[mongo] PASSED                    [ 36%]
tests/test_system.py::test_wrong_login[mock-alice] PASSED                [ 36%]
tests/test_system.py::test_wrong_login[mock-missing] PASSED              [ 37%]
tests/test_system.py::test_wrong_login[mongo-alice] PASSED               [ 37%]
tests/test_system.py::test_wrong_login[mongo-missing] PASSED             [ 38%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/auth/me-None] PASSED [ 38%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys-None] PASSED [ 39%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys-data2] PASSED [ 39%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys/012345678901234567890123-None] PASSED [ 40%]
tests/test_system.py::test_unauthenticated[mock-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 40%]
tests/test_system.py::test_unauthenticated[mock-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 40%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 41%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 41%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/auth/me-None] PASSED [ 42%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys-None] PASSED [ 42%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys-data2] PASSED [ 43%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys/012345678901234567890123-None] PASSED [ 43%]
tests/test_system.py::test_unauthenticated[mongo-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 44%]
tests/test_system.py::test_unauthenticated[mongo-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 44%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 45%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 45%]
tests/test_system.py::test_create_serialization[mock] PASSED             [ 45%]
tests/test_system.py::test_create_serialization[mongo] PASSED            [ 46%]
tests/test_system.py::test_update_delete[mock] PASSED                    [ 46%]
tests/test_system.py::test_update_delete[mongo] PASSED                   [ 47%]
tests/test_system.py::test_owner_isolation[mock] PASSED                  [ 47%]
tests/test_system.py::test_owner_isolation[mongo] PASSED                 [ 48%]
tests/test_system.py::test_publish_close[mock] PASSED                    [ 48%]
tests/test_system.py::test_publish_close[mongo] PASSED                   [ 49%]
tests/test_system.py::test_invalid_id[mock-invalid] PASSED               [ 49%]
tests/test_system.py::test_invalid_id[mock-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 50%]
tests/test_system.py::test_invalid_id[mock-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 50%]
tests/test_system.py::test_invalid_id[mongo-invalid] PASSED              [ 50%]
tests/test_system.py::test_invalid_id[mongo-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 51%]
tests/test_system.py::test_invalid_id[mongo-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 51%]
tests/test_system.py::test_missing_id[mock] PASSED                       [ 52%]
tests/test_system.py::test_missing_id[mongo] PASSED                      [ 52%]
tests/test_system.py::test_logout_revokes[mock] PASSED                   [ 53%]
tests/test_system.py::test_logout_revokes[mongo] PASSED                  [ 53%]
tests/test_system.py::test_expired_session[mock] PASSED                  [ 54%]
tests/test_system.py::test_expired_session[mongo] PASSED                 [ 54%]
tests/test_system.py::test_cookie_and_rotation[mock] PASSED              [ 55%]
tests/test_system.py::test_cookie_and_rotation[mongo] PASSED             [ 55%]
tests/test_system.py::test_cross_origin[mock] PASSED                     [ 55%]
tests/test_system.py::test_cross_origin[mongo] PASSED                    [ 56%]
tests/test_system.py::test_invalid_survey_input[mock-data0] PASSED       [ 56%]
tests/test_system.py::test_invalid_survey_input[mock-data1] PASSED       [ 57%]
tests/test_system.py::test_invalid_survey_input[mock-data2] PASSED       [ 57%]
tests/test_system.py::test_invalid_survey_input[mock-data3] PASSED       [ 58%]
tests/test_system.py::test_invalid_survey_input[mock-data4] PASSED       [ 58%]
tests/test_system.py::test_invalid_survey_input[mongo-data0] PASSED      [ 59%]
tests/test_system.py::test_invalid_survey_input[mongo-data1] PASSED      [ 59%]
tests/test_system.py::test_invalid_survey_input[mongo-data2] PASSED      [ 60%]
tests/test_system.py::test_invalid_survey_input[mongo-data3] PASSED      [ 60%]
tests/test_system.py::test_invalid_survey_input[mongo-data4] PASSED      [ 60%]
tests/test_system.py::test_indexes[mock] PASSED                          [ 61%]
tests/test_system.py::test_indexes[mongo] PASSED                         [ 61%]
tests/test_system.py::test_token_collision_retry[mock] PASSED            [ 62%]
tests/test_system.py::test_token_collision_retry[mongo] PASSED           [ 62%]
tests/test_system.py::test_home_and_health[mock] PASSED                  [ 63%]
tests/test_system.py::test_home_and_health[mongo] PASSED                 [ 63%]
tests/test_validation.py::test_valid_definitions[single_choice-rules0] PASSED [ 64%]
tests/test_validation.py::test_valid_definitions[multiple_choice-rules1] PASSED [ 64%]
tests/test_validation.py::test_valid_definitions[text-rules2] PASSED     [ 65%]
tests/test_validation.py::test_valid_definitions[number-rules3] PASSED   [ 65%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch0-invalid_definition] PASSED [ 65%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch1-empty_title] PASSED [ 66%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch2-too_few_options] PASSED [ 66%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch3-too_few_options] PASSED [ 67%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch4-duplicate_option_id] PASSED [ 67%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch5-empty_option_label] PASSED [ 68%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch6-unsupported_rule] PASSED [ 68%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch7-invalid_range] PASSED [ 69%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch8-conflicting_exact] PASSED [ 69%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch9-conflicting_exact] PASSED [ 70%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch10-impossible_selection_count] PASSED [ 70%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch11-unsatisfiable_required] PASSED [ 70%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch12-invalid_rule_value] PASSED [ 71%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch13-invalid_rule_value] PASSED [ 71%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch14-invalid_rule_value] PASSED [ 72%]
tests/test_validation.py::test_invalid_definitions[text-patch15-invalid_range] PASSED [ 72%]
tests/test_validation.py::test_invalid_definitions[text-patch16-unsatisfiable_required] PASSED [ 73%]
tests/test_validation.py::test_invalid_definitions[text-patch17-invalid_rule_value] PASSED [ 73%]
tests/test_validation.py::test_invalid_definitions[text-patch18-invalid_rule_value] PASSED [ 74%]
tests/test_validation.py::test_invalid_definitions[text-patch19-unexpected_options] PASSED [ 74%]
tests/test_validation.py::test_invalid_definitions[number-patch20-invalid_range] PASSED [ 75%]
tests/test_validation.py::test_invalid_definitions[number-patch21-invalid_rule_value] PASSED [ 75%]
tests/test_validation.py::test_invalid_definitions[number-patch22-invalid_rule_value] PASSED [ 75%]
tests/test_validation.py::test_invalid_definitions[number-patch23-invalid_rule_value] PASSED [ 76%]
tests/test_validation.py::test_invalid_definitions[number-patch24-invalid_rule_value] PASSED [ 76%]
tests/test_validation.py::test_invalid_definitions[number-patch25-invalid_rule_value] PASSED [ 77%]
tests/test_validation.py::test_invalid_definitions[number-patch26-unsatisfiable_integer] PASSED [ 77%]
tests/test_validation.py::test_invalid_definitions[number-patch27-unsupported_rule] PASSED [ 78%]
tests/test_validation.py::test_invalid_definitions[number-patch28-invalid_definition] PASSED [ 78%]
tests/test_validation.py::test_invalid_definitions[number-patch29-invalid_definition] PASSED [ 79%]
tests/test_validation.py::test_invalid_definitions[number-patch30-invalid_definition] PASSED [ 79%]
tests/test_validation.py::test_invalid_definitions[number-patch31-invalid_definition] PASSED [ 80%]
tests/test_validation.py::test_invalid_definitions[number-patch32-invalid_definition] PASSED [ 80%]
tests/test_validation.py::test_required_missing[answer0-single_choice] PASSED [ 80%]
tests/test_validation.py::test_required_missing[answer0-multiple_choice] PASSED [ 81%]
tests/test_validation.py::test_required_missing[answer0-text] PASSED     [ 81%]
tests/test_validation.py::test_required_missing[answer0-number] PASSED   [ 82%]
tests/test_validation.py::test_required_missing[None-single_choice] PASSED [ 82%]
tests/test_validation.py::test_required_missing[None-multiple_choice] PASSED [ 83%]
tests/test_validation.py::test_required_missing[None-text] PASSED        [ 83%]
tests/test_validation.py::test_required_missing[None-number] PASSED      [ 84%]
tests/test_validation.py::test_answers[single_choice-rules0-a-None] PASSED [ 84%]
tests/test_validation.py::test_answers[single_choice-rules1-missing-invalid_option] PASSED [ 85%]
tests/test_validation.py::test_answers[single_choice-rules2-answer2-invalid_option] PASSED [ 85%]
tests/test_validation.py::test_answers[single_choice-rules3-True-invalid_option] PASSED [ 85%]
tests/test_validation.py::test_answers[multiple_choice-rules4-answer4-None] PASSED [ 86%]
tests/test_validation.py::test_answers[multiple_choice-rules5-answer5-min_selections] PASSED [ 86%]
tests/test_validation.py::test_answers[multiple_choice-rules6-answer6-max_selections] PASSED [ 87%]
tests/test_validation.py::test_answers[multiple_choice-rules7-answer7-exact_selections] PASSED [ 87%]
tests/test_validation.py::test_answers[multiple_choice-rules8-answer8-duplicate_selection] PASSED [ 88%]
tests/test_validation.py::test_answers[multiple_choice-rules9-answer9-invalid_option] PASSED [ 88%]
tests/test_validation.py::test_answers[multiple_choice-rules10-a-invalid_answer_type] PASSED [ 89%]
tests/test_validation.py::test_answers[multiple_choice-rules11-answer11-invalid_answer_type] PASSED [ 89%]
tests/test_validation.py::test_answers[multiple_choice-rules12-answer12-invalid_answer_type] PASSED [ 90%]
tests/test_validation.py::test_answers[text-rules13-\u4e2d\u6587-None] PASSED [ 90%]
tests/test_validation.py::test_answers[text-rules14-a-min_length] PASSED [ 90%]
tests/test_validation.py::test_answers[text-rules15-abc-max_length] PASSED [ 91%]
tests/test_validation.py::test_answers[text-rules16-12-invalid_answer_type] PASSED [ 91%]
tests/test_validation.py::test_answers[text-rules17-  -required] PASSED  [ 92%]
tests/test_validation.py::test_answers[number-rules18-5-None] PASSED     [ 92%]
tests/test_validation.py::test_answers[number-rules19--1-min] PASSED     [ 93%]
tests/test_validation.py::test_answers[number-rules20-11-max] PASSED     [ 93%]
tests/test_validation.py::test_answers[number-rules21-1.5-integer_only] PASSED [ 94%]
tests/test_validation.py::test_answers[number-rules22-2.0-None] PASSED   [ 94%]
tests/test_validation.py::test_answers[number-rules23-True-invalid_number] PASSED [ 95%]
tests/test_validation.py::test_answers[number-rules24-False-invalid_number] PASSED [ 95%]
tests/test_validation.py::test_answers[number-rules25-1.5-invalid_number] PASSED [ 95%]
tests/test_validation.py::test_answers[number-rules26-nan-invalid_number] PASSED [ 96%]
tests/test_validation.py::test_answers[number-rules27-inf-invalid_number] PASSED [ 96%]
tests/test_validation.py::test_answers[number-rules28--inf-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules29-9223372036854775808-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_empty_answers[single_choice-] PASSED      [ 98%]
tests/test_validation.py::test_empty_answers[multiple_choice-empty1] PASSED [ 98%]
tests/test_validation.py::test_empty_answers[text-] PASSED               [ 99%]
tests/test_validation.py::test_optional_nonempty_answer_still_validates PASSED [ 99%]
tests/test_validation.py::test_engine_does_not_mutate_input_and_refuses_invalid_definition PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_questions.py: 358 warnings
tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
===================== 220 passed, 541 warnings in 16.60s ======================

```
