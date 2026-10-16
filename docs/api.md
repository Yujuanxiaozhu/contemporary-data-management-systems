# 第一阶段 API

基础 URL：http://127.0.0.1:8000。请求/响应 JSON，除 204 无响应体。Cookie 身份由登录建立；浏览器同源 fetch 自动携带，命令行需 cookie jar。跨站写请求（Origin 或 Sec-Fetch-Site: cross-site）返回 403；安全 GET/HEAD 读取允许外站分享链接。没有启用跨域 CORS。

## 输入及输出

Credentials：`{"username":"alice","password":"password123"}`。username trim 后非空、最多 64 字符；密码 8–128 字符；未知字段返回 422。注册不自动登录。

SurveyInput：`{"title":"课程反馈","description":"说明","allow_anonymous":false,"allow_multiple_submissions":false,"deadline":"2030-01-01T00:00:00Z"}`。title 必填，其他字段可省略；deadline 可 null，非空必须带时区。PUT 是基础字段整体替换，省略的可选字段重置为默认值。不能传 owner_id、status、public_token、questions、jump_rules 或 schema_version。

UserOut：`id, username, created_at`；永不返回 password_hash。
SurveyOut：`id, owner_id, title, description, status, allow_anonymous, allow_multiple_submissions, deadline, public_token, questions, jump_rules, schema_version, created_at, updated_at`。id/owner_id 为字符串，所有时间输出 UTC。
错误形如 `{"detail":"请先登录"}`；422 输入校验错误可能是 detail 数组。

| Method | URL | 登录 | 输入 | 成功输出 | 常见错误 |
|---|---|---|---|---|---|
| POST | /api/auth/register | 否 | Credentials | 201 UserOut | 409 用户名已存在；422 输入错误 |
| POST | /api/auth/login | 否 | Credentials | 200 UserOut + Set-Cookie | 401 用户名或密码错误；422 |
| POST | /api/auth/logout | 否，可重复 | 无 | 204 + 清 Cookie | 403 跨站 |
| GET | /api/auth/me | 是 | 无 | 200 UserOut | 401 |
| GET | /api/surveys | 是 | 无 | 200 SurveyOut 数组，仅本人 | 401 |
| POST | /api/surveys | 是 | SurveyInput | 201 SurveyOut，draft | 401、422、503 |
| GET | /api/surveys/{survey_id} | 是 | 路径 ObjectId | 200 SurveyOut | 401、404、422 |
| PUT | /api/surveys/{survey_id} | 是 | SurveyInput | 200 SurveyOut | 401、404、422 |
| DELETE | /api/surveys/{survey_id} | 是 | 路径 ObjectId | 204 | 401、404、409 已有答卷、422 |
| POST | /api/surveys/{survey_id}/publish | 是 | 无 | 200 SurveyOut，published | 401、404、409、422 |
| POST | /api/surveys/{survey_id}/close | 是 | 无 | 200 SurveyOut，closed | 401、404、409、422 |
| GET | /health | 否 | 无 | 200 {"status":"ok"} | 503 数据库不可用 |
| GET | / | 否 | 无 | 200 管理页面 HTML | — |

所有数据库请求可能返回 503；服务器记录原始异常。不存在和他人问卷均返回 404，避免泄露存在性。非法 ObjectId 返回 422，不产生 500。

状态：draft→published→closed，重复发布 published、重复关闭 closed 返回 200；关闭 draft 或重新发布 closed 返回 409。空 questions 在本阶段允许发布。截止时间不自动切换状态，但公开加载、next 和提交均由服务端检查。

第三轮 DELETE 仅 draft 且无答卷可物理删除；published 提示关闭，closed 保留历史，均返回 409。不级联删除答卷。

题目管理与下述第三轮公开填写/提交均已实现；统计已在第四轮实现如下。`/docs` 和 `/openapi.json` 为 FastAPI 自动 API 说明。

## 第二轮题目 API

复用 current_user、owner 过滤与跨站防护；通过现有 GET /api/surveys/{survey_id} 读取题目。题目管理响应返回整份更新后的 SurveyOut，便于观察重排后的全部题目和 schema_version。

| Method | URL | 登录 | 输入 | 输出 |
|---|---|---|---|---|
| POST | /api/surveys/{survey_id}/questions | 是 | Question JSON | 201 SurveyOut |
| PUT | /api/surveys/{survey_id}/questions/{question_id} | 是 | Question JSON，全量题目替换 | 200 SurveyOut |
| DELETE | /api/surveys/{survey_id}/questions/{question_id} | 是 | 无 | 200 SurveyOut |

创建请求示例：

```json
{"type":"multiple_choice","title":"喜欢的水果","required":true,"options":[{"id":"a","label":"苹果"},{"id":"b","label":"香蕉"}],"validation":{"min_selections":1,"max_selections":2}}
```

- 必填 type/title，required 默认 false，options 默认 []，validation 默认 {}。
- 创建可省略 id（服务端 UUID hex）或显式提供合法唯一字符串；PUT 省略 id 保留原值，传不同 id 返回 422。
- POST 省略 order 则追加，显式 order 需在 1..N+1；PUT 省略 order 保留位置，显式 order 需在 1..N。插入、移动和删除后服务端重排 1..N，其他题目 ID 不变。
- PUT 是整题替换：type/title 仍必填；省略 required/options/validation 重置为默认，不提供 PATCH 语义。切换类型时按新题型重新校验。
- 不接受 schema_version 或其他未知字段；客户端不能更改 owner、版本等 survey 字段。
- draft/published 可增删改，closed 题目只读（409），仍可通过 survey GET 读取；closed 的题目写请求优先返回状态冲突。
- 结构真正改变才 +1，完全相同的 PUT 返回当前版本；一次重排/修改只增一次。并发版本/状态冲突 409，调用方重新读取再重试。

常见错误：401 未登录；403 跨站；404 不存在/非本人 survey 或不存在 question；422 非法 ObjectId、题目字段/规则/order；409 重复 question id、closed、并发修改/删除。校验错误形如：

```json
{"detail":{"valid":false,"errors":[{"code":"invalid_range","field":"validation","message":"min_length 不得大于 max_length"}]}}
```

错误 code 稳定，文案便于定位；结构类型错误 code 为 invalid_definition。不将 raw input（可能含 NaN）回显。部分 service 边界错误仍沿用第一轮 `{"detail":"..."}` 风格。

## 可复用答案校验（第三轮正式提交复用）

`validate_question_definition(dict)` 返回 ValidationResult，有 valid、errors、规范化 question；`validate_answer(question, answer=MISSING)` 返回同类结果，`as_dict()` 只输出 valid 与错误 code/field/message。定义不合法时直接返回定义错误，不继续校验答案。

- MISSING 与 null 视为未答；非必答可省略。
- 单选空字符串、多选空数组、文本空字符串也视为未答；必答返回 required，非必答跳过内容约束。
- 必答文本仅空白失败；非必答的非空字符串（包括纯空白字符串）都按原文本长度检查，不 trim 答案。长度按 Python Unicode code point 计数。
- 单选必须是存在的 option id；多选必须为字符串数组，不可重复，数量规则对非空答案检查。
- 数字必须为有限 JSON number；bool、数字字符串、NaN/±Infinity、超 BSON int64 的整数均拒绝。integer_only 接受具有整数值的有限 float（如 2.0）。

规则完整表见 database-design.md。无需为每个 API 再实现一份答案校验。

## 第三轮 Jump Rule 管理与版本读取

| Method | URL | 登录/权限 | 输入 | 输出/常见错误 |
|---|---|---|---|---|
| POST | /api/surveys/{survey_id}/jump-rules | owner | JumpRule JSON | 201 SurveyOut；422 定义/ID/priority 冲突 |
| PUT | /api/surveys/{survey_id}/jump-rules/{rule_id} | owner | 完整 JumpRule JSON，可省略原 id | 200 SurveyOut；404 不存在；422 定义错误 |
| DELETE | /api/surveys/{survey_id}/jump-rules/{rule_id} | owner | 无 | 200 SurveyOut；404 不存在 |
| GET | /api/surveys/{survey_id}/versions/{schema_version} | owner | 路径版本 | 200 snapshot（ObjectId 转字符串）；404 不存在；422 非法 ID |

```json
{"id":"r1","source_question_id":"q1","operator":"equals","value":"a","target_question_id":"q3","priority":1}
```

POST 没有有效 id 时生成 UUID hex，PUT 不可换 id。priority 默认 1，严格正整数，同 source 唯一；不依赖物理顺序。单选 equals、多选 contains、数字 equals/>/>=/</<= 对应具名 operator；text 不能作为 source。值必须匹配源题型，目标 order 必须更大。未知字段/操作符、bool 数字、NaN/Infinity、无效引用均拒绝。draft/published 可编辑，closed 409；401/403/404 owner 规则沿用。

published 编辑产生新版本及不可变 snapshot；draft 编辑仅增版本，首次 publish 才保存该版本。完全相同 PUT 不增版本。快照无 POST/PUT/DELETE 客户端管理接口。

题目增删改会重新验证现有规则；删除 source/target 或改变题型/options/order 破坏规则，409 并要求先修规则，题目/版本/snapshot 均不变。

结构写入遇到 DB 异常返回 503，保留旧当前版本和可恢复 pending。后续请求会恢复已授权操作；503 是结果待确认，不代表操作永久取消。并发预留冲突 409，读取最新状态后重试，不能盲目重发新增请求。

## 第三轮 Public API

| Method | URL | 登录条件 | 输入 | 成功输出 |
|---|---|---|---|---|
| GET | /api/public/surveys/{public_token} | allow_anonymous=false 时需登录 | 无 | 200 当前公开定义 |
| GET | /survey/{public_token} | 同上 | 无 | 200 Jinja2 填写页面 |
| POST | /api/public/surveys/{public_token}/next | 同上 | schema_version/current_question_id/answer | 200 next_question_id + completed |
| POST | /api/public/surveys/{public_token}/responses | 同上 | schema_version/answers | 201 提交结果 |

公开定义白名单：`id, title, description, allow_anonymous, allow_multiple_submissions, deadline, schema_version, questions, jump_rules`，不含 owner/session/password、pending、准入字段或其他内部元信息。

不存在 token 为 404；draft/closed 为 409；now>deadline 为 410；不允许匿名且未登录为 401。页面、next、submit 都检查当前状态；默认 token 不可预测沿用第一轮生成机制。跨站写请求 403，安全读取允许外站链接；未启用任意 CORS。

next 示例：

```json
{"schema_version":6,"current_question_id":"q1","answer":"a"}
```

```json
{"next_question_id":"q3","completed":false}
```

最后一题返回 next_question_id=null、completed=true。optional 可省略 answer/null。无效答案 422；未知当前题目 422。next 使用请求版本快照；它只计算一步，不作为最终提交可信证明。

正式提交示例：

```json
{"schema_version":6,"answers":[{"question_id":"q1","value":"a"},{"question_id":"q3","value":20}]}
```

成功输出字段：`id, survey_id, survey_schema_version, visited_question_ids, submitted_at`，ObjectId 为字符串、时间为 UTC。不会回传密码、会话或多余身份信息。

规则：

1. schema_version 为正严格整数；answers 数组最多 200 项，question_id/value 明确提供；不能额外传 survey_id、用户 ID、dedupe_key 或 visited path。
2. snapshot 必须属于该 token 的 survey；缺失版本返回 404，绝不回退当前最新版。
3. 使用该历史快照执行原 Validation Engine 和 Jump Engine；从首题推导路径，visited required 缺失失败，optional 可缺失，skipped required 不要求填写。
4. skipped/unknown 答案和重复 question_id 都 422；原值按实际路径顺序保存，不静默剔除统计污染数据。
5. 当前 survey 仍 published、未过截止且策略允许时，可以提交较旧的已发布版本；公开 GET 返回当前版本，next/submit 按客户端实际版本解释。
6. 当前匿名、截止、重复策略以提交准入时为准，不按旧快照锁定元信息。状态/时间/策略在最终准入点复查；若策略改变需重新读取，可能返回 409。
7. 匿名允许时未登录记录 null，已登录记录账号 ID；匿名不可靠去重。登录且禁止多次时第二次/并发失败返回 409；允许多次时返回多条独立答卷。
8. 提交准入发生在验证后。准入早于 close 的请求可随后保存；close 之后不能新准入。deadline 空值不限，等于截止点允许，超过拒绝。

路径错误示例：

```json
{"detail":{"valid":false,"visited_question_ids":["q1","q3"],"errors":[{"code":"extraneous_answer","field":"answers","message":"包含被跳过或不存在题目的答案: q2"}]}}
```

数据库错误保持 503 并记录 traceback。提交响应网络不确定时，禁止多次的登录用户由唯一键防重复；允许多次及匿名请求暂未提供通用幂等键，网络重试可能产生多条，应在下一轮按需求补充。

## 第四轮统计 API

| Method | URL | 登录/权限 | 成功 | 错误 |
|---|---|---|---|---|
| GET | /api/surveys/{survey_id}/stats | owner | 200 整份版本统计 | 401、404、422 非法 ObjectId、409 数据异常 |
| GET | /api/surveys/{survey_id}/questions/{question_id}/stats | owner | 200 单题版本统计 | 同上；404 统计版本不存在该题 |

整份输出：`{survey_id,total_responses,versions:[{schema_version,response_count,questions:[{question,statistics}]}]}`。
单题输出：`{survey_id,question_id,total_responses,versions:[{schema_version,response_count,question,statistics}]}`。

版本升序，题目按 snapshot.order。返回全部有答卷的历史版，加当前 published/closed 且已有 snapshot 的零答卷版；其他零答卷旧版省略。draft 无答卷 versions=[]。total_responses 为所有合法已保存答卷数；单题的 total_responses 仍为问卷总数，response_count 是该版总数，不等于该题 answered_count。

statistics：
- single_choice：type、answered_count、options[{option_id,label,count}]。
- multiple_choice：另加 total_selections；选择次数不等于作答人数。
- text：type、answered_count、values。
- number：type、answered_count、values、average、min、max；无数值时 average/min/max=null。

题目定义与 option label 来自对应 snapshot，不跨不兼容版本合并；单题只返回该 ID 存在的所选版本。空/null/未答/skipped 不计 answered_count，数字 0 计入。公开 token 不能调用统计，没有公开统计 API。

异常历史结构/版本/答案/路径/快照缺失：409 `{detail:{code:"statistics_data_inconsistency",message:"..."}}`，不返回部分计数，服务记录警告但不回显原始答案。其他数据库错误仍 503。

## 第四轮管理 Web 路由

| GET 路径 | 行为 |
|---|---|
| / | 演示说明与注册/登录入口 |
| /register、/login | 账号表单，调用原 auth API |
| /dashboard | 本人问卷列表、版本/状态/UTC 截止、分享/发布/关闭/删除草稿 |
| /surveys/new | 创建基础信息表单 |
| /surveys/{survey_id}/edit | owner 基本信息、题目、校验、跳转表单 |
| /surveys/{survey_id}/stats | owner 整份版本统计页面 |
| /surveys/{survey_id}/questions/{question_id}/stats | owner 单题跨版本页面 |

受保护页面未登录 303 到 /login，API 未登录仍 401；非 owner 页面也 404。编辑表单只调用已有 API，不绕过其规则；JS 数值转换用于提交格式，不重复完整校验逻辑。复制分享 URL 仅在 published dashboard 展示。页面使用 Jinja2 转义与 tojson，统计原始文本不当 HTML 渲染。跨站写入保护继续执行。
