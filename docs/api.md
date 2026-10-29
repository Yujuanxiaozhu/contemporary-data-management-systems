# API 说明

本地运行后 `/docs` 可查看实际 OpenAPI 参数。管理接口需要登录；写请求还检查同源。ObjectId 在 JSON 中以字符串返回；常见错误包括 401 未登录、404 不可见或不存在、409 冲突/索引不完整、422 输入非法。不同旧接口的错误形状可能不同。

## 账户、问卷和填写

| 方法与路径 | 用途 |
|---|---|
| `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me` | 账户与会话 |
| `GET/POST /api/surveys`，`GET/PUT/DELETE /api/surveys/{sid}` | 本人问卷和基本信息 |
| `POST /api/surveys/{sid}/publish`、`POST /api/surveys/{sid}/close` | 发布、关闭 |
| `POST /api/surveys/{sid}/questions`，`PUT/DELETE /api/surveys/{sid}/questions/{local_id}` | 草稿题目 |
| `POST /api/surveys/{sid}/jump-rules`，`PUT/DELETE /api/surveys/{sid}/jump-rules/{rule_id}` | 草稿跳转规则 |
| `GET /api/surveys/{sid}/versions/{schema}` | 本人问卷历史快照 |
| `GET /api/public/surveys/{token}`，`POST .../next`，`POST .../responses` | 公开读取、下一题和提交 |
| `GET /api/surveys/{sid}/stats`，`GET /api/surveys/{sid}/questions/{local_id}/stats` | 本人单问卷统计 |

published/closed 题目、绑定和跳转结构不可直接修改；应创建修订草稿。

## 题目族、版本与绑定

| 方法与路径 | 用途 |
|---|---|
| `POST /api/questions`；`GET /api/questions`、`GET /api/questions/{qid}` | 创建题目族、列出或查看本人题目 |
| `GET /api/questions/{qid}/versions`；`GET /api/question-versions/{vid}` | 版本历史或授权的确定版本 |
| `POST /api/questions/{qid}/versions`；`POST /api/questions/{qid}/restore` | 创建新版本、从旧版恢复为新版本 |
| `POST /api/question-versions/{vid}/fork` | 从授权版本派生本人题目族 |
| `POST /api/surveys/{sid}/question-references` | 向草稿添加固定版本 |
| `PUT /api/surveys/{sid}/questions/{local_id}/binding` | 更换草稿位置的固定版本 |
| `POST /api/surveys/{sid}/revisions` | 从指定已发布快照创建独立修订草稿 |

题目创建、版本、恢复、派生和修订需 `Idempotency-Key`；版本更新/恢复使用 `expected_revision`，选题与修订使用 `expected_schema_version`。相同 key 的不同请求返回冲突。操作查询/恢复路径见 OpenAPI；网络结果未知时应先读状态或按原意图恢复。

## 分享和题库

- `PUT /api/question-versions/{vid}/shares/{uid}` 按用户 ID 分享；`POST /api/question-versions/{vid}/shares` 按用户名分享；`GET` 同路径列出共享对象；`DELETE /api/question-versions/{vid}/shares/{uid}` 撤销。只有原题 owner 可以管理分享。
- `GET/POST /api/question-banks`；`GET/PUT/DELETE /api/question-banks/{bid}` 管理私人题库。创建使用 `Idempotency-Key`，更新和删除使用 `expected_revision`。
- `GET/POST /api/question-banks/{bid}/items`，`PUT/DELETE /api/question-banks/{bid}/items/{qid}` 管理成员。请求使用 `question_version_id`，更新/删除需成员 revision；同族只能有一个成员。失效共享项保留但不可选。

## usage 与跨问卷统计

`GET /api/questions/{qid}/usages` 可选 `scope=all|current|historical`、`version_id`、`cursor`、`limit`。它先核对本人来源和完整 READY 代次，再返回本人问卷位置与 coverage。重建只由显式维护命令执行，不提供普通 HTTP 重建接口。

`GET /api/questions/{qid}/stats` 可选 `version_id`，scope 固定为 `owned_surveys`。每个版本单独返回 `statistics`、`answered_count` 和 `by_occurrence`；单选包括 percentage，多选包括 total_selections，数字空集的 min/max/average 为 null。返回只代表有效回答次数，不代表独立人数。索引缺失、来源变化、legacy 映射或历史快照缺失时返回 409；分享不授予其他用户问卷或答卷查看权。
