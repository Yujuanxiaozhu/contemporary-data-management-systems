# 第四轮交付：动态历史统计与管理 Web UI

项目 D:/Codex/survey-system，2026-10-16（Asia/Shanghai）。完整源码、测试、原始记录均在现有项目；未重建或修改前三轮测试掩盖回归。

## A. 总体设计

实施前只读核对 app/tests/templates/static/README/docs、MongoDB 集合索引与历史 schema/response 服务，实跑 371 基线。统计只读 responses 与版本快照，服务层共享计算；管理表单复用既有 API。无新增依赖、React/Vue、缓存、消息系统或微服务。

## B. 新增/修改文件

```text
修改原有源码：
app/main.py
app/core/database.py
app/routers/statistics.py
app/services/statistics.py
app/static/style.css
app/templates/index.html

新增源码/测试：
app/routers/management.py
app/static/management.js
app/templates/account.html
app/templates/base.html
app/templates/dashboard.html
app/templates/edit.html
app/templates/statistics.html
tests/smoke_statistics.py
tests/test_management.py
tests/test_statistics.py

更新文档：
README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md
docs/file-manifest.txt

新增报告与证据：
docs/project-report.md
docs/iteration-4/

```

原认证/提交/Validation/Jump/快照及公开填写源码哈希不变。旧测试与 fixture 全部字节一致。完整证据文件清单见 changed-files.txt/file-manifest。

## C. Statistics Service

compute_question_statistics、compute_version_statistics、compute_survey_statistics、compute_single_question_statistics 复用同一逻辑。先 owner 验证，再查目标答卷、按版本分组、加载 snapshot、核对历史答案/路径，最后计算。DataConsistencyError 映射 409 statistics_data_inconsistency，记录警告，不输出部分正常结果、不吞错修数据。

## D. 整份问卷统计

GET /api/surveys/{survey_id}/stats 返回 survey_id/total_responses/versions。每版包含 schema_version/response_count/questions，每题带原 question 与 statistics。所有有 response 的历史版全部纳入；当前 published/closed 已有 snapshot 的版本可零统计，其余无答卷旧版不展示。draft 无 response 为 versions=[]。

## E. 单题统计

GET /api/surveys/{survey_id}/questions/{question_id}/stats 返回所有统计范围内确有该 ID 的版本，不伪造缺题版本，均不存在则 404。同 ID 改题型、选项仍分别返回。response_count 是该版总答卷，不等于题目 answered_count；total_responses 仍是问卷总数。

## F. 四题型统计语义

| 类型 | 字段/语义 |
|---|---|
| single_choice | answered_count、snapshot option_id/label/count |
| multiple_choice | answered_count 为非空作答份数；total_selections 和各选项次数 |
| text | 非空合法 values 和 answered_count，无 NLP |
| number | values、answered_count、average/min/max；无回答均 null；0 计入 |

optional null/空串/空数组和 skipped 不计数；不根据总答卷推断每题人数。数字拒绝 bool/NaN/Infinity，Decimal 高精度累计避免求和溢出和严重消去，最终 JSON float 仍有表示精度边界。

## G. 历史 schema_version

题目定义来自对应 survey_versions，绝不使用当前 questions 解释旧 response。历史 option label 保留，同 ID single→number 等不合并，不存在题目不补零。统计前复用历史 Validation/Jump 并核对 visited，未知选项、坏类型、缺快照等整体 409。

## H. MongoDB 查询/索引

目标 responses 按 survey_id 查并以 submitted_at/_id 排序，Python 按 survey_schema_version 分组，用 survey_id/version 加载快照。新增 responses(survey_id,survey_schema_version) 复合索引；保留 survey_id、dedupe unique sparse 和快照唯一复合索引。没有新统计集合、物化视图或提交时 count +=1。环境 MongoDB 9.0.2 standalone。

## I. 统计权限

两个 API 和两个统计页面均 owner-only，其他账号 404，API 未登录 401，非法 ObjectId 422；public token 无公开统计接口。管理页面未登录重定向 303 到 /login；不能靠前端隐藏代替服务检查。

## J. 管理页面与路由

`/register`、`/login`、`/dashboard`、`/surveys/new`、`/surveys/{id}/edit`、`/surveys/{id}/stats`、`/surveys/{id}/questions/{qid}/stats`。首页说明演示步骤。dashboard 显示 title/status/schema_version/deadline、编辑/统计、published URL 复制与打开、publish/close、draft 删除。

## K. 编辑 UI

基本信息支持五类元信息与本地时间输入转换 UTC。题目支持四类、ID/order/required、每行 id|label 选项和分类数值 validation 输入；可新增/编辑/删除。规则支持 source/target/operator/value/priority/ID，可新增/改/删。表单仅做序列化，后端原规则为权威；closed 题目/规则只读。

## L. 统计 UI

Jinja2 明确按 Schema 版本分块显示版答卷数、题目题型和回答人数。选择题表格，多选另列总选择次数，文本列表，数字 average/min/max/values。单题链接保留历史版本区分；零数据提示明确。标题/答案默认转义，编辑内嵌数据用 tojson，无大型图表库。

## M. 公开填写回归

第三轮 survey.html/survey.js 未改动；原单选/多选/text/number、required/validation、Jump、匿名/登录、deadline、closed、成功提示回归全通过。dashboard 输出的 URL 实际获取公开页并完成 next/submit。没有新增公开统计接口。

## N. 实际命令

完整 commands.md；实际执行 compileall、全部 JS node --check、pip check、基线/扩展/最终 pytest、真实 MongoDB 和 Uvicorn smoke、统计值断言。没有安装新依赖。Git 128，其余验证 0。computer-use 仅查询现有窗口，无浏览器点击或操作其他应用。

## O. pytest 最终结果

**455 passed, 2262 warnings in 85.55s (0:01:25)；退出码 0。** 原基线 371 全通过；新增统计 62、管理页面 22。完整逐项输出见本文末和 pytest-final.txt。首轮 439 也通过，之后补四类型 optional/skipped 用例。

## P. 真实 MongoDB

真实 MongoDB 160 项、mock 160 项、纯逻辑 135 项。共享 db fixture 切换后端，无复制测试文件凑数。实际核对 response/snapshot/index，测试只清理随机测试库，未删除正常项目文件或业务数据。

## Q. Uvicorn 完整业务 smoke

实际过程和输出（退出码 0）如下；首次即通过，startup-final 是该次真实输出的副本，并非虚构又执行一次：

```text
GET /: 200
GET /health: 200
GET /static/app.js: 200
GET /openapi.json: 200
POST /api/auth/register: 201
POST /api/auth/login: 200
POST /api/surveys: 201
GET /register: 200
GET /login: 200
GET /dashboard: 200
GET /surveys/new: 200
PUT /api/surveys/6ad11413514fbc2ac07fcff6: 200
POST /api/surveys/6ad11413514fbc2ac07fcff6/questions: 201
POST /api/surveys/6ad11413514fbc2ac07fcff6/questions: 201
POST /api/surveys/6ad11413514fbc2ac07fcff6/questions: 201
POST /api/surveys/6ad11413514fbc2ac07fcff6/questions: 201
POST /api/surveys/6ad11413514fbc2ac07fcff6/jump-rules: 201
POST /api/surveys/6ad11413514fbc2ac07fcff6/publish: 200
GET /surveys/6ad11413514fbc2ac07fcff6/edit: 200
GET /dashboard: 200
GET /survey/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk: 200
GET /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/responses: 201
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/responses: 201
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/responses: 201
GET /api/surveys/6ad11413514fbc2ac07fcff6/stats: 200
GET /surveys/6ad11413514fbc2ac07fcff6/stats: 200
GET /api/surveys/6ad11413514fbc2ac07fcff6/questions/score/stats: 200
PUT /api/surveys/6ad11413514fbc2ac07fcff6/questions/route: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/next: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/responses: 201
GET /api/surveys/6ad11413514fbc2ac07fcff6/stats: 200
GET /api/surveys/6ad11413514fbc2ac07fcff6/questions/route/stats: 200
MONGODB_RESPONSE_SNAPSHOT_AND_INDEX=PASS
HAND_CALCULATED_EXPECTATIONS_MATCH=PASS {"old_version_responses": 3, "old_single_counts": [2, 1], "old_multiple_answered": 2, "old_multiple_total_selections": 3, "old_multiple_counts": [2, 1], "old_text_count": 2, "old_number_values": [10, 20, 30], "old_number_average": 20, "new_version_responses": 1, "new_number_average": 40, "total_responses": 4}
POST /api/surveys/6ad11413514fbc2ac07fcff6/close: 200
POST /api/public/surveys/W3IUANW9cS7CpVn26J-ezz8Bwm1auEjgqPwIVrg4lkk/responses: 409
REAL_STATISTICS_AND_MANAGEMENT_SMOKE=PASS
POST /api/surveys: 201
POST /api/surveys/6ad11413514fbc2ac07fcffd/publish: 200
POST /api/surveys/6ad11413514fbc2ac07fcffd/close: 200
POST /api/auth/logout: 204
GET /api/surveys: 401
REAL_UVICORN_SMOKE=PASS
Temporary server stopped; disposable test database removed.

```

包含注册登录、metadata、四题型/validation、rule、发布分享、三次旧版填写、管理与整份/单题统计、新版本提交、双版本统计、关闭拒绝、logout。结束停止临时进程和删除随机库。仅 HTTP/页面路由检查，不声称真实浏览器点击。

## R. 统计数值及手算核对

| 核对项 | 固定示例手算预期 | 实际 |
|---|---|---|
| 旧版答卷 | 3 | 3 |
| 单选 | a=2、b=1 | 一致 |
| 多选 | 两份 [x,y]、[x]；人数2、选择3、x2/y1 | 一致 |
| 文本 | 第一条、第二条；跳转答卷不填该题 | 两条，一致 |
| 数字 | [10,20,30]，(10+20+30)/3=20，min10/max30 | 一致 |
| 新版 | 一份数字40，平均40 | 一致 |
| 总数/历史 | 共4份、旧3新1，旧 label 不被改名覆盖 | 一致 |

直接 MongoDB 核验四条 response、两份 snapshot、复合索引。详细 actual_statistics 与固定 expected_hand_calculation 在 statistics-check.json。手算预期与自动断言由 Codex 执行，不虚构人工参与。

## S. AI 日志

../ai-log.md 保留前三轮并追加第四轮完整 Prompt、文件/设计、统计/UI、实际测试/错误/自查和限制。Prompt 与用户原附件按字节相同。新增 project-report.md 汇总阶段成果，不伪称教师已评分或人工已修改。

## T. 真实错误与修正

唯一实际工具错误是 Git 非仓库（128），原文：

```text
fatal: not a git repository (or any of the parent directories): .git
```

本轮无意外 pytest/compile/smoke 失败，不编造失败修复。主动异常历史测试的 WARNING、旧故障注入 ERROR 以及第三方弃用警告完整保存在 errors-original.md 和 pytest-runtime-final.log。浏览器窗口检查未提供可接续窗口不是自动化崩溃；没有安装新浏览器包或虚构点击验收。实际自查处理平均值极端精度、空值、snapshot/答案一致性、模板 values 键访问和转义，均有相应验证。

## U. 已知限制

匿名/允许多次暂无通用幂等键；pending 由后续请求恢复；未发布的旧 draft 无法恢复但不能合法产生答卷；snapshot immutable 依赖业务和 DB 权限控制，MongoDB 不能给不可信远程用户直接写权限。统计为课程规模全量动态加载，无分页/压力测试/事务报表一致性，刷新可纳入并发新增。异常历史数据需修复后重试，不静默跳过。JSON 平均值仍受 float 精度约束。无真实浏览器点击 E2E，使用本轮允许的 TestClient/HTTP/JS/HTML 转义验收。

## V. 第一阶段尚未完成要求

本轮及前三轮要求的主要功能已实现，含网页从创建到统计的可用入口和实际 HTTP 闭环。未实现复杂编辑器/图表/NLP/导出/实时缓存，这些不在本轮要求。课程人工演示与教师最终验收、材料打包上传和评分未执行；不能声称已完成这些人为环节。可依据 README 从零启动并演示。

## 附：pytest 完整最终原文

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.7.0 -- D:\Codex\survey-system\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Codex\survey-system
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 455 items

tests/test_jumps.py::test_valid_rules[single_choice-equals-a] PASSED     [  0%]
tests/test_jumps.py::test_valid_rules[multiple_choice-contains-a] PASSED [  0%]
tests/test_jumps.py::test_valid_rules[number-equals-2] PASSED            [  0%]
tests/test_jumps.py::test_valid_rules[number-greater_than-2] PASSED      [  0%]
tests/test_jumps.py::test_valid_rules[number-greater_than_or_equal-2] PASSED [  1%]
tests/test_jumps.py::test_valid_rules[number-less_than-2] PASSED         [  1%]
tests/test_jumps.py::test_valid_rules[number-less_than_or_equal-2] PASSED [  1%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch0-invalid_operator] PASSED [  1%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch1-invalid_operator] PASSED [  1%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch2-invalid_rule_value] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[multiple_choice-patch3-invalid_rule_value] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[number-patch4-invalid_rule_value] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[number-patch5-invalid_rule_value] PASSED [  2%]
tests/test_jumps.py::test_invalid_rules[number-patch6-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[number-patch7-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[number-patch8-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[number-patch9-invalid_rule_value] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[text-patch10-invalid_operator] PASSED [  3%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch11-missing_question] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch12-missing_question] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch13-not_forward] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch14-not_forward] PASSED [  4%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch15-invalid_rule] PASSED [  5%]
tests/test_jumps.py::test_invalid_rules[single_choice-patch16-invalid_rule] PASSED [  5%]
tests/test_jumps.py::test_duplicate_rules_and_priority[second0-duplicate_rule_id] PASSED [  5%]
tests/test_jumps.py::test_duplicate_rules_and_priority[second1-duplicate_priority] PASSED [  5%]
tests/test_jumps.py::test_resolve[single_choice-equals-a-a-q3] PASSED    [  5%]
tests/test_jumps.py::test_resolve[single_choice-equals-a-b-q2] PASSED    [  6%]
tests/test_jumps.py::test_resolve[multiple_choice-contains-a-answer2-q3] PASSED [  6%]
tests/test_jumps.py::test_resolve[multiple_choice-contains-a-answer3-q2] PASSED [  6%]
tests/test_jumps.py::test_resolve[number-greater_than-2-3-q3] PASSED     [  6%]
tests/test_jumps.py::test_resolve[number-greater_than-2-2-q2] PASSED     [  7%]
tests/test_jumps.py::test_resolve[number-greater_than_or_equal-2-2-q3] PASSED [  7%]
tests/test_jumps.py::test_resolve[number-less_than-2-1-q3] PASSED        [  7%]
tests/test_jumps.py::test_resolve[number-less_than_or_equal-2-2-q3] PASSED [  7%]
tests/test_jumps.py::test_resolve[number-equals-2-2-q3] PASSED           [  7%]
tests/test_jumps.py::test_sequential_last_and_priority PASSED            [  8%]
tests/test_jumps.py::test_path_required_skipped_extra_and_optional PASSED [  8%]
tests/test_jumps.py::test_runtime_cycle_and_max_steps PASSED             [  8%]
tests/test_management.py::test_public_account_pages[mock-/] PASSED       [  8%]
tests/test_management.py::test_public_account_pages[mock-/login] PASSED  [  9%]
tests/test_management.py::test_public_account_pages[mock-/register] PASSED [  9%]
tests/test_management.py::test_public_account_pages[mongo-/] PASSED      [  9%]
tests/test_management.py::test_public_account_pages[mongo-/login] PASSED [  9%]
tests/test_management.py::test_public_account_pages[mongo-/register] PASSED [  9%]
tests/test_management.py::test_management_requires_login[mock-/dashboard] PASSED [ 10%]
tests/test_management.py::test_management_requires_login[mock-/surveys/new] PASSED [ 10%]
tests/test_management.py::test_management_requires_login[mock-/surveys/012345678901234567890123/edit] PASSED [ 10%]
tests/test_management.py::test_management_requires_login[mock-/surveys/012345678901234567890123/stats] PASSED [ 10%]
tests/test_management.py::test_management_requires_login[mongo-/dashboard] PASSED [ 10%]
tests/test_management.py::test_management_requires_login[mongo-/surveys/new] PASSED [ 11%]
tests/test_management.py::test_management_requires_login[mongo-/surveys/012345678901234567890123/edit] PASSED [ 11%]
tests/test_management.py::test_management_requires_login[mongo-/surveys/012345678901234567890123/stats] PASSED [ 11%]
tests/test_management.py::test_dashboard_isolation_and_owner_pages[mock] PASSED [ 11%]
tests/test_management.py::test_dashboard_isolation_and_owner_pages[mongo] PASSED [ 12%]
tests/test_management.py::test_statistics_page_escapes_response_text[mock] PASSED [ 12%]
tests/test_management.py::test_statistics_page_escapes_response_text[mongo] PASSED [ 12%]
tests/test_management.py::test_edit_data_and_dashboard_escape_html[mock] PASSED [ 12%]
tests/test_management.py::test_edit_data_and_dashboard_escape_html[mongo] PASSED [ 12%]
tests/test_management.py::test_closed_ui_readonly_and_same_origin[mock] PASSED [ 13%]
tests/test_management.py::test_closed_ui_readonly_and_same_origin[mongo] PASSED [ 13%]
tests/test_public_responses.py::test_publish_snapshot_immutable_unique_and_owner_history[mock] PASSED [ 13%]
tests/test_public_responses.py::test_publish_snapshot_immutable_unique_and_owner_history[mongo] PASSED [ 13%]
tests/test_public_responses.py::test_jump_crud_snapshot_and_reference_integrity[mock] PASSED [ 14%]
tests/test_public_responses.py::test_jump_crud_snapshot_and_reference_integrity[mongo] PASSED [ 14%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mock-POST-] PASSED [ 14%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mock-PUT-/r1] PASSED [ 14%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mock-DELETE-/r1] PASSED [ 14%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mongo-POST-] PASSED [ 15%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mongo-PUT-/r1] PASSED [ 15%]
tests/test_public_responses.py::test_jump_owner_auth_status_ids[mongo-DELETE-/r1] PASSED [ 15%]
tests/test_public_responses.py::test_rule_id_and_priority_validation[mock] PASSED [ 15%]
tests/test_public_responses.py::test_rule_id_and_priority_validation[mongo] PASSED [ 16%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-published-200] PASSED [ 16%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-draft-409] PASSED [ 16%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-closed-409] PASSED [ 16%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-missing-404] PASSED [ 16%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mock-expired-410] PASSED [ 17%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-published-200] PASSED [ 17%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-draft-409] PASSED [ 17%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-closed-409] PASSED [ 17%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-missing-404] PASSED [ 18%]
tests/test_public_responses.py::test_public_status_deadline_page_and_privacy[mongo-expired-410] PASSED [ 18%]
tests/test_public_responses.py::test_anonymous_policy[mock-False-False-401] PASSED [ 18%]
tests/test_public_responses.py::test_anonymous_policy[mock-False-True-201] PASSED [ 18%]
tests/test_public_responses.py::test_anonymous_policy[mock-True-False-201] PASSED [ 18%]
tests/test_public_responses.py::test_anonymous_policy[mock-True-True-201] PASSED [ 19%]
tests/test_public_responses.py::test_anonymous_policy[mongo-False-False-401] PASSED [ 19%]
tests/test_public_responses.py::test_anonymous_policy[mongo-False-True-201] PASSED [ 19%]
tests/test_public_responses.py::test_anonymous_policy[mongo-True-False-201] PASSED [ 19%]
tests/test_public_responses.py::test_anonymous_policy[mongo-True-True-201] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra0-201] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra1-422] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra2-422] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra3-422] PASSED [ 20%]
tests/test_public_responses.py::test_response_path_validation[mock-extra4-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra5-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra6-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra7-201] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra8-422] PASSED [ 21%]
tests/test_public_responses.py::test_response_path_validation[mock-extra9-201] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mock-extra10-422] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mock-extra11-422] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra0-201] PASSED [ 22%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra1-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra2-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra3-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra4-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra5-422] PASSED [ 23%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra6-422] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra7-201] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra8-422] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra9-201] PASSED [ 24%]
tests/test_public_responses.py::test_response_path_validation[mongo-extra10-422] PASSED [ 25%]
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
tests/test_public_responses.py::test_submit_deadline[mock-none] PASSED   [ 27%]
tests/test_public_responses.py::test_submit_deadline[mock-future] PASSED [ 27%]
tests/test_public_responses.py::test_submit_deadline[mock-past] PASSED   [ 28%]
tests/test_public_responses.py::test_submit_deadline[mongo-none] PASSED  [ 28%]
tests/test_public_responses.py::test_submit_deadline[mongo-future] PASSED [ 28%]
tests/test_public_responses.py::test_submit_deadline[mongo-past] PASSED  [ 28%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mock-closed] PASSED [ 29%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mock-expired] PASSED [ 29%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mongo-closed] PASSED [ 29%]
tests/test_public_responses.py::test_final_gate_rechecks_after_validation[mongo-expired] PASSED [ 29%]
tests/test_public_responses.py::test_delete_state_policy[mock-draft-204] PASSED [ 29%]
tests/test_public_responses.py::test_delete_state_policy[mock-published-409] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mock-closed-409] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mongo-draft-204] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mongo-published-409] PASSED [ 30%]
tests/test_public_responses.py::test_delete_state_policy[mongo-closed-409] PASSED [ 30%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mock-snapshot] PASSED [ 31%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mock-pointer] PASSED [ 31%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mongo-snapshot] PASSED [ 31%]
tests/test_public_responses.py::test_snapshot_failure_keeps_current_and_recovers[mongo-pointer] PASSED [ 31%]
tests/test_public_responses.py::test_publish_snapshot_failure_does_not_publish[mock] PASSED [ 32%]
tests/test_public_responses.py::test_publish_snapshot_failure_does_not_publish[mongo] PASSED [ 32%]
tests/test_public_responses.py::test_concurrent_published_edit_snapshots[mock] PASSED [ 32%]
tests/test_public_responses.py::test_concurrent_published_edit_snapshots[mongo] PASSED [ 32%]
tests/test_public_responses.py::test_rule_default_priority_is_saved[mock] PASSED [ 32%]
tests/test_public_responses.py::test_rule_default_priority_is_saved[mongo] PASSED [ 33%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mock-NaN] PASSED [ 33%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mock-Infinity] PASSED [ 33%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mock--Infinity] PASSED [ 33%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mongo-NaN] PASSED [ 34%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mongo-Infinity] PASSED [ 34%]
tests/test_public_responses.py::test_nonfinite_rule_json_and_response_json[mongo--Infinity] PASSED [ 34%]
tests/test_public_responses.py::test_duplicate_answer_and_cross_survey_version[mock] PASSED [ 34%]
tests/test_public_responses.py::test_duplicate_answer_and_cross_survey_version[mongo] PASSED [ 34%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mock--1-201] PASSED [ 35%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mock-0-201] PASSED [ 35%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mock-1-410] PASSED [ 35%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mongo--1-201] PASSED [ 35%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mongo-0-201] PASSED [ 36%]
tests/test_public_responses.py::test_deadline_millisecond_boundary[mongo-1-410] PASSED [ 36%]
tests/test_public_responses.py::test_metadata_change_does_not_snapshot[mock] PASSED [ 36%]
tests/test_public_responses.py::test_metadata_change_does_not_snapshot[mongo] PASSED [ 36%]
tests/test_public_responses.py::test_get_version_returns_detached_document[mock] PASSED [ 36%]
tests/test_public_responses.py::test_get_version_returns_detached_document[mongo] PASSED [ 37%]
tests/test_public_responses.py::test_recovery_cannot_rebase_stale_question_array[mock] PASSED [ 37%]
tests/test_public_responses.py::test_recovery_cannot_rebase_stale_question_array[mongo] PASSED [ 37%]
tests/test_public_responses.py::test_external_shared_link_read_but_cross_site_write_blocked[mock] PASSED [ 37%]
tests/test_public_responses.py::test_external_shared_link_read_but_cross_site_write_blocked[mongo] PASSED [ 38%]
tests/test_questions.py::test_create_each_type[mock-single_choice-rules0] PASSED [ 38%]
tests/test_questions.py::test_create_each_type[mock-multiple_choice-rules1] PASSED [ 38%]
tests/test_questions.py::test_create_each_type[mock-text-rules2] PASSED  [ 38%]
tests/test_questions.py::test_create_each_type[mock-number-rules3] PASSED [ 38%]
tests/test_questions.py::test_create_each_type[mongo-single_choice-rules0] PASSED [ 39%]
tests/test_questions.py::test_create_each_type[mongo-multiple_choice-rules1] PASSED [ 39%]
tests/test_questions.py::test_create_each_type[mongo-text-rules2] PASSED [ 39%]
tests/test_questions.py::test_create_each_type[mongo-number-rules3] PASSED [ 39%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data0] PASSED [ 40%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data1] PASSED [ 40%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data2] PASSED [ 40%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data3] PASSED [ 40%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data4] PASSED [ 40%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data5] PASSED [ 41%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data6] PASSED [ 41%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data7] PASSED [ 41%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data8] PASSED [ 41%]
tests/test_questions.py::test_invalid_create_is_atomic[mock-data9] PASSED [ 41%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data0] PASSED [ 42%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data1] PASSED [ 42%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data2] PASSED [ 42%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data3] PASSED [ 42%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data4] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data5] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data6] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data7] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data8] PASSED [ 43%]
tests/test_questions.py::test_invalid_create_is_atomic[mongo-data9] PASSED [ 44%]
tests/test_questions.py::test_question_lifecycle_and_metadata_version[mock] PASSED [ 44%]
tests/test_questions.py::test_question_lifecycle_and_metadata_version[mongo] PASSED [ 44%]
tests/test_questions.py::test_order_and_stable_ids[mock] PASSED          [ 44%]
tests/test_questions.py::test_order_and_stable_ids[mongo] PASSED         [ 45%]
tests/test_questions.py::test_id_conflicts_and_invalid_order[mock] PASSED [ 45%]
tests/test_questions.py::test_id_conflicts_and_invalid_order[mongo] PASSED [ 45%]
tests/test_questions.py::test_auth_required[mock-POST-] PASSED           [ 45%]
tests/test_questions.py::test_auth_required[mock-PUT-/missing] PASSED    [ 45%]
tests/test_questions.py::test_auth_required[mock-DELETE-/missing] PASSED [ 46%]
tests/test_questions.py::test_auth_required[mongo-POST-] PASSED          [ 46%]
tests/test_questions.py::test_auth_required[mongo-PUT-/missing] PASSED   [ 46%]
tests/test_questions.py::test_auth_required[mongo-DELETE-/missing] PASSED [ 46%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-POST-] PASSED [ 47%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-PUT-/q1] PASSED [ 47%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mock-DELETE-/q1] PASSED [ 47%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-POST-] PASSED [ 47%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-PUT-/q1] PASSED [ 47%]
tests/test_questions.py::test_other_owner_and_invalid_ids[mongo-DELETE-/q1] PASSED [ 48%]
tests/test_questions.py::test_missing_question[mock] PASSED              [ 48%]
tests/test_questions.py::test_missing_question[mongo] PASSED             [ 48%]
tests/test_questions.py::test_published_edit_closed_readonly[mock] PASSED [ 48%]
tests/test_questions.py::test_published_edit_closed_readonly[mongo] PASSED [ 49%]
tests/test_questions.py::test_delete_survey_protects_responses[mock] PASSED [ 49%]
tests/test_questions.py::test_delete_survey_protects_responses[mongo] PASSED [ 49%]
tests/test_questions.py::test_response_does_not_leak_survey_existence[mock] PASSED [ 49%]
tests/test_questions.py::test_response_does_not_leak_survey_existence[mongo] PASSED [ 49%]
tests/test_questions.py::test_concurrent_question_edits_use_cas[mock] PASSED [ 50%]
tests/test_questions.py::test_concurrent_question_edits_use_cas[mongo] PASSED [ 50%]
tests/test_questions.py::test_commit_preserves_unrelated_fields_and_checks_status[mock] PASSED [ 50%]
tests/test_questions.py::test_commit_preserves_unrelated_fields_and_checks_status[mongo] PASSED [ 50%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock-NaN] PASSED [ 50%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock-Infinity] PASSED [ 51%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mock--Infinity] PASSED [ 51%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo-NaN] PASSED [ 51%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo-Infinity] PASSED [ 51%]
tests/test_questions.py::test_nonfinite_json_definition_returns_safe_error[mongo--Infinity] PASSED [ 52%]
tests/test_questions.py::test_edit_options_validation_required_each_bumps_once[mock] PASSED [ 52%]
tests/test_questions.py::test_edit_options_validation_required_each_bumps_once[mongo] PASSED [ 52%]
tests/test_questions.py::test_published_delete_question_bumps_version[mock] PASSED [ 52%]
tests/test_questions.py::test_published_delete_question_bumps_version[mongo] PASSED [ 52%]
tests/test_questions.py::test_structure_change_ignores_simultaneous_metadata_edit[mock] PASSED [ 53%]
tests/test_questions.py::test_structure_change_ignores_simultaneous_metadata_edit[mongo] PASSED [ 53%]
tests/test_statistics.py::test_question_statistics[single_choice-values0-expected0] PASSED [ 53%]
tests/test_statistics.py::test_question_statistics[multiple_choice-values1-expected1] PASSED [ 53%]
tests/test_statistics.py::test_question_statistics[text-values2-expected2] PASSED [ 54%]
tests/test_statistics.py::test_question_statistics[number-values3-expected3] PASSED [ 54%]
tests/test_statistics.py::test_question_statistics[number-values4-expected4] PASSED [ 54%]
tests/test_statistics.py::test_question_statistics[number-values5-expected5] PASSED [ 54%]
tests/test_statistics.py::test_question_statistics[number-values6-expected6] PASSED [ 54%]
tests/test_statistics.py::test_question_statistics[number-values7-expected7] PASSED [ 55%]
tests/test_statistics.py::test_bad_values_fail_closed[single_choice-unknown] PASSED [ 55%]
tests/test_statistics.py::test_bad_values_fail_closed[multiple_choice-bad1] PASSED [ 55%]
tests/test_statistics.py::test_bad_values_fail_closed[multiple_choice-bad2] PASSED [ 55%]
tests/test_statistics.py::test_bad_values_fail_closed[text-5] PASSED     [ 56%]
tests/test_statistics.py::test_bad_values_fail_closed[number-True] PASSED [ 56%]
tests/test_statistics.py::test_bad_values_fail_closed[number-nan] PASSED [ 56%]
tests/test_statistics.py::test_bad_values_fail_closed[number-inf] PASSED [ 56%]
tests/test_statistics.py::test_bad_values_fail_closed[number-9223372036854775808] PASSED [ 56%]
tests/test_statistics.py::test_empty_statistics[mock-False] PASSED       [ 57%]
tests/test_statistics.py::test_empty_statistics[mock-True] PASSED        [ 57%]
tests/test_statistics.py::test_empty_statistics[mongo-False] PASSED      [ 57%]
tests/test_statistics.py::test_empty_statistics[mongo-True] PASSED       [ 57%]
tests/test_statistics.py::test_multiple_responses_counts_and_skips[mock] PASSED [ 58%]
tests/test_statistics.py::test_multiple_responses_counts_and_skips[mongo] PASSED [ 58%]
tests/test_statistics.py::test_one_response_optional_missing_number_zero_answered[mock] PASSED [ 58%]
tests/test_statistics.py::test_one_response_optional_missing_number_zero_answered[mongo] PASSED [ 58%]
tests/test_statistics.py::test_historical_options_types_and_absent_question[mock] PASSED [ 58%]
tests/test_statistics.py::test_historical_options_types_and_absent_question[mongo] PASSED [ 59%]
tests/test_statistics.py::test_statistics_permissions_and_bad_ids[mock-/stats] PASSED [ 59%]
tests/test_statistics.py::test_statistics_permissions_and_bad_ids[mock-/questions/q1/stats] PASSED [ 59%]
tests/test_statistics.py::test_statistics_permissions_and_bad_ids[mongo-/stats] PASSED [ 59%]
tests/test_statistics.py::test_statistics_permissions_and_bad_ids[mongo-/questions/q1/stats] PASSED [ 60%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-unknown_option] PASSED [ 60%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-bool] PASSED [ 60%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-nan] PASSED [ 60%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-missing_snapshot] PASSED [ 60%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-duplicate_answer] PASSED [ 61%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-bad_path] PASSED [ 61%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-missing_version] PASSED [ 61%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mock-bad_type] PASSED [ 61%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-unknown_option] PASSED [ 61%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-bool] PASSED [ 62%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-nan] PASSED [ 62%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-missing_snapshot] PASSED [ 62%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-duplicate_answer] PASSED [ 62%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-bad_path] PASSED [ 63%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-missing_version] PASSED [ 63%]
tests/test_statistics.py::test_corrupt_history_api_returns_conflict[mongo-bad_type] PASSED [ 63%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-False-single_choice] PASSED [ 63%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-False-multiple_choice] PASSED [ 63%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-False-text] PASSED [ 64%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-False-number] PASSED [ 64%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-True-single_choice] PASSED [ 64%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-True-multiple_choice] PASSED [ 64%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-True-text] PASSED [ 65%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mock-True-number] PASSED [ 65%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-False-single_choice] PASSED [ 65%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-False-multiple_choice] PASSED [ 65%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-False-text] PASSED [ 65%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-False-number] PASSED [ 66%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-True-single_choice] PASSED [ 66%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-True-multiple_choice] PASSED [ 66%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-True-text] PASSED [ 66%]
tests/test_statistics.py::test_every_type_optional_missing_or_skipped_not_counted[mongo-True-number] PASSED [ 67%]
tests/test_system.py::test_register[mock] PASSED                         [ 67%]
tests/test_system.py::test_register[mongo] PASSED                        [ 67%]
tests/test_system.py::test_duplicate[mock] PASSED                        [ 67%]
tests/test_system.py::test_duplicate[mongo] PASSED                       [ 67%]
tests/test_system.py::test_bad_registration[mock-data0] PASSED           [ 68%]
tests/test_system.py::test_bad_registration[mock-data1] PASSED           [ 68%]
tests/test_system.py::test_bad_registration[mongo-data0] PASSED          [ 68%]
tests/test_system.py::test_bad_registration[mongo-data1] PASSED          [ 68%]
tests/test_system.py::test_login_and_me[mock] PASSED                     [ 69%]
tests/test_system.py::test_login_and_me[mongo] PASSED                    [ 69%]
tests/test_system.py::test_wrong_login[mock-alice] PASSED                [ 69%]
tests/test_system.py::test_wrong_login[mock-missing] PASSED              [ 69%]
tests/test_system.py::test_wrong_login[mongo-alice] PASSED               [ 69%]
tests/test_system.py::test_wrong_login[mongo-missing] PASSED             [ 70%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/auth/me-None] PASSED [ 70%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys-None] PASSED [ 70%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys-data2] PASSED [ 70%]
tests/test_system.py::test_unauthenticated[mock-GET-/api/surveys/012345678901234567890123-None] PASSED [ 70%]
tests/test_system.py::test_unauthenticated[mock-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 71%]
tests/test_system.py::test_unauthenticated[mock-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 71%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 71%]
tests/test_system.py::test_unauthenticated[mock-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 71%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/auth/me-None] PASSED [ 72%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys-None] PASSED [ 72%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys-data2] PASSED [ 72%]
tests/test_system.py::test_unauthenticated[mongo-GET-/api/surveys/012345678901234567890123-None] PASSED [ 72%]
tests/test_system.py::test_unauthenticated[mongo-PUT-/api/surveys/012345678901234567890123-data4] PASSED [ 72%]
tests/test_system.py::test_unauthenticated[mongo-DELETE-/api/surveys/012345678901234567890123-None] PASSED [ 73%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/publish-None] PASSED [ 73%]
tests/test_system.py::test_unauthenticated[mongo-POST-/api/surveys/012345678901234567890123/close-None] PASSED [ 73%]
tests/test_system.py::test_create_serialization[mock] PASSED             [ 73%]
tests/test_system.py::test_create_serialization[mongo] PASSED            [ 74%]
tests/test_system.py::test_update_delete[mock] PASSED                    [ 74%]
tests/test_system.py::test_update_delete[mongo] PASSED                   [ 74%]
tests/test_system.py::test_owner_isolation[mock] PASSED                  [ 74%]
tests/test_system.py::test_owner_isolation[mongo] PASSED                 [ 74%]
tests/test_system.py::test_publish_close[mock] PASSED                    [ 75%]
tests/test_system.py::test_publish_close[mongo] PASSED                   [ 75%]
tests/test_system.py::test_invalid_id[mock-invalid] PASSED               [ 75%]
tests/test_system.py::test_invalid_id[mock-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 75%]
tests/test_system.py::test_invalid_id[mock-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 76%]
tests/test_system.py::test_invalid_id[mongo-invalid] PASSED              [ 76%]
tests/test_system.py::test_invalid_id[mongo-aaaaaaaaaaaaaaaaaaaaaaa] PASSED [ 76%]
tests/test_system.py::test_invalid_id[mongo-zzzzzzzzzzzzzzzzzzzzzzzz] PASSED [ 76%]
tests/test_system.py::test_missing_id[mock] PASSED                       [ 76%]
tests/test_system.py::test_missing_id[mongo] PASSED                      [ 77%]
tests/test_system.py::test_logout_revokes[mock] PASSED                   [ 77%]
tests/test_system.py::test_logout_revokes[mongo] PASSED                  [ 77%]
tests/test_system.py::test_expired_session[mock] PASSED                  [ 77%]
tests/test_system.py::test_expired_session[mongo] PASSED                 [ 78%]
tests/test_system.py::test_cookie_and_rotation[mock] PASSED              [ 78%]
tests/test_system.py::test_cookie_and_rotation[mongo] PASSED             [ 78%]
tests/test_system.py::test_cross_origin[mock] PASSED                     [ 78%]
tests/test_system.py::test_cross_origin[mongo] PASSED                    [ 78%]
tests/test_system.py::test_invalid_survey_input[mock-data0] PASSED       [ 79%]
tests/test_system.py::test_invalid_survey_input[mock-data1] PASSED       [ 79%]
tests/test_system.py::test_invalid_survey_input[mock-data2] PASSED       [ 79%]
tests/test_system.py::test_invalid_survey_input[mock-data3] PASSED       [ 79%]
tests/test_system.py::test_invalid_survey_input[mock-data4] PASSED       [ 80%]
tests/test_system.py::test_invalid_survey_input[mongo-data0] PASSED      [ 80%]
tests/test_system.py::test_invalid_survey_input[mongo-data1] PASSED      [ 80%]
tests/test_system.py::test_invalid_survey_input[mongo-data2] PASSED      [ 80%]
tests/test_system.py::test_invalid_survey_input[mongo-data3] PASSED      [ 80%]
tests/test_system.py::test_invalid_survey_input[mongo-data4] PASSED      [ 81%]
tests/test_system.py::test_indexes[mock] PASSED                          [ 81%]
tests/test_system.py::test_indexes[mongo] PASSED                         [ 81%]
tests/test_system.py::test_token_collision_retry[mock] PASSED            [ 81%]
tests/test_system.py::test_token_collision_retry[mongo] PASSED           [ 81%]
tests/test_system.py::test_home_and_health[mock] PASSED                  [ 82%]
tests/test_system.py::test_home_and_health[mongo] PASSED                 [ 82%]
tests/test_validation.py::test_valid_definitions[single_choice-rules0] PASSED [ 82%]
tests/test_validation.py::test_valid_definitions[multiple_choice-rules1] PASSED [ 82%]
tests/test_validation.py::test_valid_definitions[text-rules2] PASSED     [ 83%]
tests/test_validation.py::test_valid_definitions[number-rules3] PASSED   [ 83%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch0-invalid_definition] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch1-empty_title] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch2-too_few_options] PASSED [ 83%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch3-too_few_options] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch4-duplicate_option_id] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch5-empty_option_label] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[single_choice-patch6-unsupported_rule] PASSED [ 84%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch7-invalid_range] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch8-conflicting_exact] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch9-conflicting_exact] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch10-impossible_selection_count] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch11-unsatisfiable_required] PASSED [ 85%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch12-invalid_rule_value] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch13-invalid_rule_value] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[multiple_choice-patch14-invalid_rule_value] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[text-patch15-invalid_range] PASSED [ 86%]
tests/test_validation.py::test_invalid_definitions[text-patch16-unsatisfiable_required] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[text-patch17-invalid_rule_value] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[text-patch18-invalid_rule_value] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[text-patch19-unexpected_options] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[number-patch20-invalid_range] PASSED [ 87%]
tests/test_validation.py::test_invalid_definitions[number-patch21-invalid_rule_value] PASSED [ 88%]
tests/test_validation.py::test_invalid_definitions[number-patch22-invalid_rule_value] PASSED [ 88%]
tests/test_validation.py::test_invalid_definitions[number-patch23-invalid_rule_value] PASSED [ 88%]
tests/test_validation.py::test_invalid_definitions[number-patch24-invalid_rule_value] PASSED [ 88%]
tests/test_validation.py::test_invalid_definitions[number-patch25-invalid_rule_value] PASSED [ 89%]
tests/test_validation.py::test_invalid_definitions[number-patch26-unsatisfiable_integer] PASSED [ 89%]
tests/test_validation.py::test_invalid_definitions[number-patch27-unsupported_rule] PASSED [ 89%]
tests/test_validation.py::test_invalid_definitions[number-patch28-invalid_definition] PASSED [ 89%]
tests/test_validation.py::test_invalid_definitions[number-patch29-invalid_definition] PASSED [ 89%]
tests/test_validation.py::test_invalid_definitions[number-patch30-invalid_definition] PASSED [ 90%]
tests/test_validation.py::test_invalid_definitions[number-patch31-invalid_definition] PASSED [ 90%]
tests/test_validation.py::test_invalid_definitions[number-patch32-invalid_definition] PASSED [ 90%]
tests/test_validation.py::test_required_missing[answer0-single_choice] PASSED [ 90%]
tests/test_validation.py::test_required_missing[answer0-multiple_choice] PASSED [ 90%]
tests/test_validation.py::test_required_missing[answer0-text] PASSED     [ 91%]
tests/test_validation.py::test_required_missing[answer0-number] PASSED   [ 91%]
tests/test_validation.py::test_required_missing[None-single_choice] PASSED [ 91%]
tests/test_validation.py::test_required_missing[None-multiple_choice] PASSED [ 91%]
tests/test_validation.py::test_required_missing[None-text] PASSED        [ 92%]
tests/test_validation.py::test_required_missing[None-number] PASSED      [ 92%]
tests/test_validation.py::test_answers[single_choice-rules0-a-None] PASSED [ 92%]
tests/test_validation.py::test_answers[single_choice-rules1-missing-invalid_option] PASSED [ 92%]
tests/test_validation.py::test_answers[single_choice-rules2-answer2-invalid_option] PASSED [ 92%]
tests/test_validation.py::test_answers[single_choice-rules3-True-invalid_option] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules4-answer4-None] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules5-answer5-min_selections] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules6-answer6-max_selections] PASSED [ 93%]
tests/test_validation.py::test_answers[multiple_choice-rules7-answer7-exact_selections] PASSED [ 94%]
tests/test_validation.py::test_answers[multiple_choice-rules8-answer8-duplicate_selection] PASSED [ 94%]
tests/test_validation.py::test_answers[multiple_choice-rules9-answer9-invalid_option] PASSED [ 94%]
tests/test_validation.py::test_answers[multiple_choice-rules10-a-invalid_answer_type] PASSED [ 94%]
tests/test_validation.py::test_answers[multiple_choice-rules11-answer11-invalid_answer_type] PASSED [ 94%]
tests/test_validation.py::test_answers[multiple_choice-rules12-answer12-invalid_answer_type] PASSED [ 95%]
tests/test_validation.py::test_answers[text-rules13-\u4e2d\u6587-None] PASSED [ 95%]
tests/test_validation.py::test_answers[text-rules14-a-min_length] PASSED [ 95%]
tests/test_validation.py::test_answers[text-rules15-abc-max_length] PASSED [ 95%]
tests/test_validation.py::test_answers[text-rules16-12-invalid_answer_type] PASSED [ 96%]
tests/test_validation.py::test_answers[text-rules17-  -required] PASSED  [ 96%]
tests/test_validation.py::test_answers[number-rules18-5-None] PASSED     [ 96%]
tests/test_validation.py::test_answers[number-rules19--1-min] PASSED     [ 96%]
tests/test_validation.py::test_answers[number-rules20-11-max] PASSED     [ 96%]
tests/test_validation.py::test_answers[number-rules21-1.5-integer_only] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules22-2.0-None] PASSED   [ 97%]
tests/test_validation.py::test_answers[number-rules23-True-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules24-False-invalid_number] PASSED [ 97%]
tests/test_validation.py::test_answers[number-rules25-1.5-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_answers[number-rules26-nan-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_answers[number-rules27-inf-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_answers[number-rules28--inf-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_answers[number-rules29-9223372036854775808-invalid_number] PASSED [ 98%]
tests/test_validation.py::test_empty_answers[single_choice-] PASSED      [ 99%]
tests/test_validation.py::test_empty_answers[multiple_choice-empty1] PASSED [ 99%]
tests/test_validation.py::test_empty_answers[text-] PASSED               [ 99%]
tests/test_validation.py::test_optional_nonempty_answer_still_validates PASSED [ 99%]
tests/test_validation.py::test_engine_does_not_mutate_input_and_refuses_invalid_definition PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_management.py: 91 warnings
tests/test_public_responses.py: 1165 warnings
tests/test_questions.py: 358 warnings
tests/test_statistics.py: 465 warnings
tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================ 455 passed, 2262 warnings in 85.55s (0:01:25) ================

```
