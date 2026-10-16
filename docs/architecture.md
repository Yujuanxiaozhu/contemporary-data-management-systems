# 第一阶段架构

请求 → router → service/model/security → PyMongo → MongoDB；输出经 Pydantic schema 校验并转为 JSON。

| 层 | 职责 |
|---|---|
| app/main.py | 应用工厂、生命周期、路由注册、静态资源与 Jinja2、数据库错误映射 |
| core/config.py | .env 与有类型的配置 |
| core/database.py | MongoClient、ping、UTC 解码、索引、数据库依赖 |
| core/security.py | Argon2、会话摘要、当前用户依赖、同源检查、UTC 时钟 |
| models | MongoDB 文档构造与 response 文档类型 |
| schemas | HTTP 输入/输出、字段限制、ObjectId 显式序列化 |
| routers | HTTP 状态、Cookie、依赖注入与调用业务逻辑 |
| services/surveys.py | owner 查询约束、更新、token 冲突重试、原子状态变更 |
| templates/static | Jinja2 页面与原生 CSS/JS；DOM 文本使用 textContent |
| tests | 同一套 HTTP 回归用例覆盖 mock 与真实 MongoDB；独立进程启动检查 |

简单注册/登录的数据库操作保留在 auth router，不为单步操作额外建立空洞抽象。密码验证、身份查找与问卷规则独立，避免 main.py 成为业务中心。生产只走 PyMongo；测试向应用工厂注入 MongoDB 兼容数据库，未重写生产数据层。

## 认证与错误

随机 32 字节会话 token 写入 HttpOnly/SameSite=Strict Cookie，SHA-256 摘要和用户 ObjectId 写入 sessions；会话过期由依赖实时校验，TTL 索引用于清理。登出删除服务端记录，旧 Cookie 重放不能恢复身份。重复登录轮换当前浏览器会话。未知用户名也执行 dummy Argon2 验证，错误统一 401。

所有问卷接口通过 current_user 验证身份；数据库过滤同时包含 `_id`、`owner_id`。不存在及非本人问卷统一 404。非法 ObjectId 返回 422。数据库请求错误记录 traceback 并返回 503；连接或建索引失败直接让启动失败。

## 第二阶段继续迭代

- questions 和 jump_rules 继续嵌入，第三轮落实四题型与前向跳转规则。
- response 始终独立，survey_schema_version 保存提交对应版本；第三轮落实 answers/question_id/value/visited path，未来扩展统计时复用历史结构。
- validation.py 继续复用；jump_engine、responses router/service 已实现；statistics 已在第四轮落实动态历史版本统计。
- 已发布问卷允许编辑元信息及题目；题目结构通过 CAS 原子更新并递增版本，历史快照第三轮已保存到 survey_versions。
- 关闭后不可重新发布；对相同目标状态重复操作幂等；状态变更用状态条件匹配进行原子更新。
- 第三轮读取与提交执行 status/deadline/匿名策略，登录重复提交由唯一索引保护。
- 第三轮仅 draft 且无 responses 可物理删除；published/closed 不可物理删除，不级联。

## 第二轮增量设计

新增 `schemas/question.py` 提供字段类型（严格 bool/int、稳定 ID、四种 type），`services/validation.py` 是唯一跨字段规则与答案校验入口，`services/questions.py` 负责权限、顺序、重复 ID、题量及结构写入。现有 surveys router 只增加三条转发路由；main、数据库连接、认证、会话、状态机均未重建。现有 SurveyOut 的 questions 改用 QuestionDefinition 类型，API 字段名称保持兼容。旧的 questions=[] 无需迁移。

校验两步：Pydantic 验证文档基本类型与未知字段；统一 engine 验证选项数量、规则归属、范围/一致性与答案。API、纯函数测试、未来提交均复用同一 engine。ValidationResult 返回 valid 和可序列化的 code/field/message，不含可能无法 JSON 序列化的原始 NaN 输入。

题目 ID 默认 UUID hex，也允许创建时提供合法稳定字符串；修改不能改变 ID。order 从 1 开始，插入/移动/删除后连续重排，不改变其他题目 ID。上限每问卷 200 题，每选择题 2–100 个选项。

读取 owner 文档后，结构提交过滤 `_id + owner_id + schema_version + status`，使用 `$set` 仅更新题目（将来可复用为已校验 jump_rules），同一操作 `$inc schema_version:1`。竞争者返回 409，不能用旧数组覆盖新数据。无需进程内锁，跨进程仍使用 MongoDB 单文档条件更新；多线程测试分别验证真实 MongoDB 和 mock。元信息更新不覆盖 questions/jump_rules，结构更新不覆盖 title 等元信息。

closed 题目只读，目的为关闭时保留当前定义；GET 仍可读取。原有 survey 元信息 PUT 行为与 draft→published→closed 状态机不变。第二轮当时未保存历史结构；第三轮以下述 snapshot 协议落实版本解释。

第二轮的先查答卷再删存在跨集合竞态；第三轮改成下述状态互斥方案，不引入事务依赖。

## 第三轮：快照协议与提交链路

新增 versions service、jump_rules service/schema、responses service/schema；落实原 jump_engine 和 responses router 占位模块。main 只注册新 router，认证复用 optional_user/current_user，无复制登录实现。routers 继续只做 HTTP 映射。

### 先快照、后切换，可恢复的提交

1. 结构变更先在内存完成题目与规则引用校验。
2. draft 结构继续单文档 CAS +1，不生成快照。
3. 首次 publish 或 published 结构写，以 `_id/owner_id/schema_version/status` 和不存在 pending 为条件原子预留 `_pending_schema`。这是单个有界待提交操作，不是历史列表。
4. pending 包含操作 ID、基础版本/状态、确定的新 snapshot 和允许修改的字段。预留时不改变对外版本、questions、jump_rules 或 status。
5. insert immutable snapshot，唯一 `(survey_id,schema_version)`；重复插入只能接受与同一 pending 快照完全一致的文档，不覆盖历史。
6. 确认快照存在后，以 pending ID、基础版本/状态为条件切换当前定义/版本并移除标记。未修改字段及并发元信息保留。
7. 数据库异常原样记录并返回 503；pending 留存，使网络结果不确定或进程退出后仍可恢复。后续 owner/public/version 读取可帮助完成同一已授权操作。多个恢复者通过相同操作 ID 和唯一索引幂等协作，不用时间租约，避免租约过期后的双写。

survey_versions 从不 update/delete；服务端不存在快照修改 API。未提交快照只有 pending 协议可见，历史读取先恢复 pending，且仅允许已发布到当前版本范围内的快照。操作故障采用恢复而非盲目回滚，避免删除已被其他请求引用的历史文档。503 后客户端须重读状态，不应认定操作已经永久取消。

旧项目已有 published/closed 但无 snapshot 时，仅按现有当前定义补当前版本；无法推测早先定义，不伪造旧历史。外部直接数据库改写不属于此协议，权限应限制。

### 跳转与引用

定义统一校验 source/target 存在、合法题型/操作符/值、前向 order、唯一 ID、同 source 唯一 priority。按 priority、规则 ID 做防御性稳定排序；第一匹配生效，否则顺序下一题。完整路径保留 visited set 与最大步数上限。题目修改后重新校验全体规则，破坏引用即 409，先于 pending 或版本变化；不自动删除规则。

### 提交准入与持久化

当前问卷 status/deadline/匿名策略 → 历史 snapshot → 原 Validation Engine → Jump Engine 重建路径 → 拒绝 skipped/unknown/duplicate 答案 → 当前状态/截止时间/策略原子准入 → response insert。

准入用同一 survey 文档条件更新 `_last_response_admitted_at` 作为线性化点；发生在校验后，重新检查 published、deadline 与匿名/重复策略。MongoDB Date 毫秒精度通过向上取整查询下界避免亚毫秒截止越界。关闭前已准入请求允许随后完成插入，关闭后不接受新准入。不是声称关闭与插入跨集合事务化。

响应仅保存历史版本引用和答案，不复制 schema。登录且禁止重复的 response 有唯一 dedupe_key；查历史记录用于策略切换，但并发保护来自唯一索引。匿名没有可靠身份，不作精确去重承诺。

### DELETE 与页面

DELETE 过滤 `status=draft` 且无 pending，仍防御性检查非法历史答卷。publish 使用同一 pending/CAS 边界，因此与物理删除互斥；合法 response 只准入 published，published/closed 永不物理删除。

Jinja2 页面配原生 JS，服务端 next API 执行跳转；前端 visited 防护只用于 UX，最终路径完全在服务端重算。DOM 用 textContent，公开数据采用白名单，pending/owner/session/准入标记均不外泄。第四轮已补统计和简单管理表单，不引入复杂编辑器。

公开分享的安全 GET/HEAD/OPTIONS 不执行同源写请求拦截；POST/PUT/DELETE 仍检查 Origin/Fetch-Site。这样外站可打开问卷，跨站伪造提交仍 403。

## 第四轮：动态统计与管理网页

statistics.py 落实原占位模块，提供 compute_question_statistics、compute_version_statistics、compute_survey_statistics、compute_single_question_statistics。router 只做身份/参数/转发。统计先检查 owner，再按 survey_id 查询 responses，按 survey_schema_version 分组，批量加载 survey_versions。不读当前 questions 来解释旧答案，不改 response 提交、不写计数器或物化统计。

有答卷的历史版本全部返回；若当前 published/closed 版已有快照，即使无答卷也返回零统计。其他无答卷旧快照省略。draft 无答卷返回 versions=[]。单题复用整份计算，只保留该 ID 实际存在的版本，缺失不伪造零题目；均不存在返回 404。

每份历史答卷检查结构、重复答案、历史校验、重新计算路径并核对 visited。异常版本、缺 snapshot、未知选项、bool/非有限数或错误路径抛 DataConsistencyError；API 映射为 409 statistics_data_inconsistency，记录不含答案内容的警告，整份停止，不返回部分正常结果。统计不修复/删除历史数据。

管理页面独立 management router，未登录重定向 /login，API 仍返回 401。dashboard 按 owner 查询，编辑和统计页面复用服务端 owner 检查。metadata/question/jump 表单调用既有 API，JS 只序列化类型，不复制 Validation/Jump Engine。表单里显示原 ID/order/options/validation/rule 字段，closed 隐藏写按钮只是交互提示，后端继续强制拒绝。

统计页面由 Jinja2 按版本渲染表格/列表，数值/文本和问卷标题默认转义；嵌入编辑数据用 tojson，避免 script 标签注入。单题页面与整份页面复用同一模板。公开 survey.html/survey.js 沿用第三轮，不重写。

统计为请求时动态读，不承诺跨请求或跨集合事务一致的报表快照；当前响应基于一次物化的 response 列表计算，下一次刷新可纳入并发新增答卷。课程规模不引入缓存或消息系统。
