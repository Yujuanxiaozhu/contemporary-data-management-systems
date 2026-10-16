# MongoDB 数据设计

统一使用 UTC 有时区 datetime；MongoDB BSON Date 存 UTC 毫秒，PyMongo tz_aware 解码。API 输出 ISO 8601（UTC 使用 Z）。deadline 输入必须带时区并转 UTC，拒绝无时区时间。ObjectId 在数据库保留 BSON 类型，在 API 的 id/owner_id 输出 24 位十六进制字符串，永不直接 JSON 编码原始 ObjectId。

## users

| 字段 | 类型 | 含义 |
|---|---|---|
| _id | ObjectId | 用户主键，MongoDB 生成 |
| username | string | trim 后用户名，1–64 字符，大小写敏感唯一 |
| password_hash | string | Argon2id 含盐哈希，绝不保存或返回明文 |
| created_at | Date | UTC 注册时间 |

唯一索引 `username_1`。用户名重复由数据库唯一约束处理，避免先查再插的并发竞态。

## surveys

| 字段 | 类型/默认 | 含义 |
|---|---|---|
| _id | ObjectId | 主键 |
| owner_id | ObjectId | 引用 users._id，来自当前身份，禁止客户端指定 |
| title | string | trim 后 1–200 字符 |
| description | string / 空字符串 | 说明，最长 5000 字符 |
| status | string / draft | draft、published、closed；仅通过专用接口变更 |
| allow_anonymous | bool / false | 第二阶段匿名填写策略 |
| allow_multiple_submissions | bool / false | 第二阶段重复提交策略 |
| deadline | Date 或 null | UTC 截止时间；本轮不自动关闭或阻止发布 |
| public_token | string | secrets.token_urlsafe(32)，256 bit 随机公开标识 |
| questions | array / [] | 四类题目嵌入文档，见下文 |
| jump_rules | array / [] | 第二阶段可配置跳转规则 |
| schema_version | int / 1 | 服务端结构版本，每次有效题目结构修改原子 +1 |
| created_at | Date | UTC 创建时间 |
| updated_at | Date | UTC 最近更新或状态变化时间 |

索引：`public_token_1` unique；`owner_id_1_created_at_1` 复合索引，owner_id 为前缀满足 owner 查找并支持列表排序。MongoDB 自动建立 `_id_`。

token 唯一性由索引保证，碰撞时最多尝试三次，失败返回 503；不使用顺序 ID 或用户名衍生 token。public_token 仅用于未来公开填写，绝不代替管理端 owner 权限。

## responses

| 字段 | 类型 | 含义 |
|---|---|---|
| _id | ObjectId | 答卷主键 |
| survey_id | ObjectId | 所属问卷 |
| respondent_user_id | ObjectId 或 null | 填写用户；匿名政策下一阶段定义 |
| answers | array of document | 答案集合；本轮仅定义容器类型 |
| submitted_at | Date | UTC 提交时间 |
| survey_schema_version | int | 提交对应问卷结构版本 |

索引：`survey_id_1`。第三轮已落实下述正式写入结构、历史 schema 引用、路径与去重约束。

## sessions（认证辅助集合）

`_id: ObjectId`、`token_hash: string`、`user_id: ObjectId`、`created_at: Date`、`expires_at: Date`。
`token_hash_1` unique，`expires_at_1` TTL expireAfterSeconds=0。
只保存随机 Cookie 的 SHA-256 摘要；TTL 清理延迟不影响鉴权，因为每次请求显式过滤 expires_at > 当前 UTC。

## 嵌入与独立集合的理由

questions 与 jump_rules 是问卷定义的一部分，通常一起读取，嵌入让单文档读取和原子更新简单，也方便题型扩展，避免将题目、选项、题型约束拆成大量关系式表与多次 join。现限制每份 200 题、每选择题 100 个选项及文字长度；仍须遵守 BSON 16 MB 限制，pending 会暂存一份候选结构，大文档应进一步控制。

responses 随提交持续增长，与问卷定义生命周期、读取频率不同。独立集合避免单文档无限膨胀、热点写入及覆盖问卷元数据，适合按 survey_id 查找、分页和聚合统计。用户也具有独立生命周期，owner_id 引用即可，不复制用户名和密码到问卷。

关系数据库式拆表对固定结构及外键约束有优势，但本项目需要可扩展题型和规则文档，MongoDB 嵌入定义+独立提交的边界更自然。引用完整性由业务层负责；本轮只允许已登录用户创建，无提交功能。未加入关系数据库，也未将全部数据塞进单一集合。

当前依赖 Pydantic 与受控写入保证字段合法性，未启用 MongoDB $jsonSchema validator；直接数据库写入应受权限限制。下一阶段数据迁移须保留 schema_version 和旧答卷解释能力。

## 第二轮 question 嵌入结构

```json
{
  "id": "q_fruit",
  "type": "multiple_choice",
  "title": "喜欢的水果",
  "required": true,
  "order": 1,
  "options": [{"id":"apple","label":"苹果"},{"id":"banana","label":"香蕉"}],
  "validation": {"min_selections":1,"max_selections":2,"exact_selections":1}
}
```

| 字段 | 类型/规则 |
|---|---|
| id | 1–64 位 `[A-Za-z0-9_-]` 字符串；默认 UUID hex；在该 survey 内唯一且修改时不变 |
| type | single_choice / multiple_choice / text / number |
| title | trim 后非空，最多 500 字符 |
| required | 严格 bool，默认 false |
| order | 严格整数 ≥1；服务端维护连续 1..N；bool 不作为整数 |
| options | `{id,label}` 数组；选择题 2–100 项，其他类型必须空；id 在题内唯一；label trim 非空，最多 500 字符 |
| validation | 仅允许该题型规则；默认 {}，未知字段直接拒绝 |

每问卷最多 200 题。未创建独立 questions 集合。选择题的 option ID 在修改 label 时可保留；替换 option ID 属于结构变更，递增 schema_version。

| type | validation | 配置一致性 |
|---|---|---|
| single_choice | {} | 不支持其他规则；答案为一个存在的 option id |
| multiple_choice | min_selections、max_selections、exact_selections | 非负严格整数，不超过选项数；min≤max，exact 同时满足 min/max；必答题不允许上限/exact=0 |
| text | min_length、max_length | 非负严格整数，≤1000000，min≤max；必答题 max_length 不能为 0 |
| number | min、max、integer_only | 边界为有限 JSON 数字，min≤max；integer_only 严格 bool；整数限制范围须至少有一个整数 |

数值整数采用 BSON int64 范围，浮点必须有限；bool、NaN、Infinity、数字字符串不作为合法数字。integer_only 接受 2、2.0，拒绝 2.5。所有字段通过 engine 后才写入数据库。

## schema_version 与后续兼容

新 survey 仍为 1。新增/删除题目、修改 type/title/required/options/validation/order 的有效操作一次 +1；同一操作造成其他题目 order 重排也只 +1；完全相同 PUT 不增加版本。普通 title/description/allow_anonymous/allow_multiple_submissions/deadline 以及发布/关闭均不增加版本。客户端不能指定版本。

`commit_structure` 仅允许 questions/jump_rules 结构字段；未来 jump_rules 在独立校验后复用同一原子更新边界。第三轮已新增跳转管理和执行，复用该边界。

单文档版本条件匹配加 `$inc` 避免丢失更新。旧空数组文档无需迁移。response 继续独立，`survey_schema_version` 将绑定提交时的结构版本。第三轮已保存已发布版本的完整 questions/jump_rules 历史快照；draft 中间版本未发布过则不保证存在快照。

questions 与问卷一起读取及更新，继续嵌入能保持题目数组和版本同一次原子修改；答卷独立可持续增长、按 survey_id 聚合，不受单份问卷文档大小和高频提交热点约束。

## 第二轮删除保护（第三轮最终策略见后文）

业务层先确认 owner，再以真实 ObjectId 查询 responses.survey_id。查到任何答卷即 409，建议关闭，问卷/答卷均保留；没有答卷才物理删除。不级联删除。本轮没有 response 正式写入接口；未来需要补齐并发提交与删除的跨集合一致性协议。

## 第三轮新增 survey_versions

| 字段 | 类型 | 含义 |
|---|---|---|
| _id | ObjectId | 在 pending 预留时确定的快照主键 |
| survey_id | ObjectId | 所属 survey，不用 token 或其他 survey 的版本解释 |
| schema_version | int | 该份问卷的结构版本 |
| questions | array[QuestionDefinition] | 当时完整题目定义 |
| jump_rules | array[JumpRuleDefinition] | 当时完整跳转规则 |
| created_at | UTC Date | 快照准备时间 |
| created_reason | string | publish / question_change / jump_rule_change |

唯一复合索引 `survey_id_1_schema_version_1`。快照只 insert/read，不 update/delete，没有客户端修改入口。相同版本若出现不同内容则报冲突，不覆盖。当前最新版仍在 surveys；所有历史独立放 survey_versions，避免当前文档无限增长。

draft 编辑只增加当前版本；publish 前创建当前 snapshot。published 每次有效题目/规则变更先写新 snapshot，再切换当前版本，closed 不编辑。普通元信息、无变化 PUT、发布/关闭本身不额外增加版本。`get_survey_version(db,survey_id,schema_version)` 用 pair 查询，不存在返回 404。

surveys 增加内部可选 `_pending_schema`（单操作恢复记录）与 `_last_response_admitted_at`（提交准入时间），均不在管理/公开 API 白名单。完整一致性协议见 architecture.md。pending 并非历史集合，也不依赖 replica set。旧系统缺历史快照时只补当前 published/closed 定义，不伪造更早版本。

## JumpRuleDefinition

```json
{"id":"r1","source_question_id":"q1","operator":"equals","value":"a","target_question_id":"q3","priority":1}
```

rule/source/target ID 是稳定字符串；创建未提供有效 rule ID 则服务端 UUID hex，更新不能换 ID。priority 为 1..1000000 严格整数，默认 1 且规范化保存，同 source 不得重复；不依赖数组物理顺序。

- single_choice：equals，value 必须是存在的 option ID。
- multiple_choice：contains，同样为单个合法 option ID。
- number：equals、greater_than、greater_than_or_equal、less_than、less_than_or_equal；value 与 Validation Engine 使用相同有限数字/BSON int64 策略，拒绝 bool/NaN/Infinity。
- text 不作为 source。target.order 必须更大，禁止自跳和回跳。上限 1000 条。

题目仍嵌入 survey，规则也随同一版本原子修改。删除 source/target 或改变题型、选项、顺序使规则失效，服务层直接 409，不创建 snapshot、不改版本、不静默清规则。

## 正式 responses

```text
_id: ObjectId
survey_id: ObjectId
respondent_user_id: ObjectId | null
survey_schema_version: int
answers: [{question_id: stable string, value: typed JSON value}]
visited_question_ids: [stable string]
submitted_at: UTC Date
dedupe_key: optional string
```

保留 `survey_id_1`，新增 `dedupe_key_1` unique sparse。只有登录且不允许多次时写 `survey:<survey_id>:user:<user_id>`；匿名和允许多次不写该字段（不是写 null）。同账号的限制跨 schema_version，数据库唯一约束解决并发双提交。政策从允许多次切回禁止时还会查已有账号答卷，唯一索引继续负责并发保护。

按访问路径保存答案，只存实际提供的 visited 答案；skipped 的 required 不检查，任何 skipped/unknown 答案拒绝，不让统计污染。重复 question_id 拒绝。`survey_id + survey_schema_version` 直接关联历史结构，当前版本更新不会改变已提交 response 的含义。

response 独立集合避免提交数增长撑大 survey；每条不复制完整 schema，避免重复存储与同一版本定义分歧。历史 schema 按版本共享即可恢复解释。

## 匿名、时间与删除

匿名允许时未登录 respondent_user_id=null，登录仍记录真实 ID。匿名无可靠身份，Cookie/IP 都不能精确表示一个自然人，因此匿名不使用身份 dedupe_key，不承诺同一人仅一次。

时间沿用 UTC aware datetime 与 BSON 毫秒。deadline=null 无限制；now>deadline 拒绝；等于截止点允许，准入查询按数据库精度处理。加载和提交分别检查，不能依赖页面先前判断。

第三轮最终 DELETE 策略取代上轮先查后删的主要方案：仅 draft 无 pending 且无异常历史答卷可删；published/closed 不能物理删除。提交只能准入 published，publish/DELETE 通过同一 survey 原子条件互斥；不级联删除 response 或历史快照，不引入事务要求。

## 第四轮：统计查询与语义

新增 responses `(survey_id, survey_schema_version)` 普通复合索引，保留 survey_id、dedupe_key unique sparse；survey_versions 的 survey_id/version 唯一索引继续用于历史结构查找。无新统计集合、无写入时 count +=1、无永久缓存。

统计先只查目标问卷答卷，按 submitted_at/_id 稳定排序；按版本分组，以 pair 查 immutable snapshot；同 ID 的选项/题型改变各自解释，旧 label 永不被当前定义替换。values 列表顺序随答卷排序，不代表匿名身份信息。

单选：answered_count 和 snapshot 选项次数。多选：answered_count 为非空作答份数，total_selections 为选择总次数，一份 [a,b,c] 是 1 人、3 次。文本：非空有效 values 与人数。数字：有效 int/float values、人数、average/min/max，零回答三者均 null，数字 0 是有效回答。optional null/空串/空数组不计人数；合法非空白/空白文本按原 engine 语义处理。skipped 没有 answer，绝不从总答卷数推定该题回答人数。

平均值使用 Decimal(str(value)) 作高精度求和/除法，再输出 JSON float。800 位覆盖有限 double 的指数跨度，避免浮点求和溢出与严重消去误差；JSON 最终仍受 double 表达精度约束，不声称无限精度。

历史数据异常采取整体 fail-closed：409 与明确 code，不将未知选项当合法项、不将 bool 当数字、不漏掉损坏版本后继续返回正常总数。数据库直接写权限应受控；本服务不会静默修复数据。
