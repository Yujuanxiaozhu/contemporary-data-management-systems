# 第二阶段API契约草案

状态：本文按切片追加，正文中“未实现/草案”是当时日期下的记录，不是最终交付状态。Slice 1–7 的接口均已实现，最终可用接口以 [docs/api.md](../api.md) 和实际 OpenAPI 为准；D1–D7详见[统一规则](design-rules.md)，Q8等未批准项仍不实现。T/U/S/Q来源见decision-log。保留现有账户、问卷、公开填写、答案局部ID和统计接口，不迁移到另一套框架。

## 通用输入、输出与权限

使用现有Cookie current_user；未登录401。所有写请求复用同源检查（跨站403）。ObjectId路径格式非法422，未知字段422；不存在/不可见实体404，避免泄露存在性。对已能读取的共享版本执行所有者操作可返回403 forbidden_action，但不能借错误展开隐藏来源。校验错误使用既有valid/errors结构；一致性错误409，MongoDB异常503，不吞错伪装空列表。

所有输出显式序列化ObjectId、UTC时间，不返回owner密码、Cookie/session token、内部pending、授权准入标记。新列表统一`{items, next_cursor}`，limit默认20、范围1–100，cursor格式非法422。未注明的写入body均拒绝额外字段。

新建题目/版本/恢复/派生/修订/题库使用 `Idempotency-Key`（建议必填，1–128字符）；同owner+action+key+规范请求摘要重复返回同一result ID，同key不同body为409 idempotency_conflict。缺key为422。测试ID I-01/I-02验证重放和冲突。更新body含expected_revision，问卷含expected_schema_version；不匹配409 concurrent_modification。503中返回可用operation_id，客户端查询结果，不能认定已撤销。

统一错误code、权限优先级及409/422界限按D7（S10技术审查稿）。新选入/换版等所有既存Jump引用冲突均409 rule_reference_conflict；独立定义非法才422。通用错误测试 C-01未登录、C-02跨站、C-03非法ID/未知字段、C-04第三方404、C-05条件更新409、C-06数据库故障503。这些适用于下表每个端点；表内列出额外错误及专用验收，不意味着省略通用测试。

## 资源输出形状

- Definition：`{type,title,required,options:[{id,label}],validation}`。复用原Validation；不接受owner/order/local ID作为独立版本内容。
- Family：`{question_id,owner_id,status,latest_version_id,revision,created_at}`，仅owner完整读取。
- Version：`{question_version_id,question_id,version_no,definition,parent_version_id,derived_from,restored_from_version_id,content_hash,created_at}`。来源不可见时只给opaque引用和允许的摘要，不展开内容；共享者只能读取被授予的版本。
- Bank：`{bank_id,name,description,revision,created_at,updated_at,archived}`。
- BankItem：`{item_id,bank_id,question_id,selected_version_id,revision}`。
- Share：`{share_id,question_version_id,grantee_user_id,state,grant_epoch,revision,created_at,revoked_at}`；state取ACTIVE/REVOKED，原始准入票据不输出；仅授权管理者看到接收者字段。
- Survey：延续SurveyOut，管理端增加bindings和revision_of；公开定义继续白名单，不直接暴露完整来源/权限。
- Operation：`{operation_id,action,state,published_result?,retryable,error_code?}`，仅调用者可读，无请求凭据和内部完整payload。发布action的state按D3，retryable由原因决定；GET只读，resume仅同一确定payload，不能通过修改字段扩大授权。

## 独立题目、版本、历史和恢复

| 方法与路径 | 输入 | 成功输出 | 权限检查 | 额外错误 | 专用测试 |
|---|---|---|---|---|---|
| POST /api/questions | `{definition}`+I-Key | 201 `{family,version,operation_id}` | current_user为新owner；Validation | 422非法定义；409幂等冲突 | R1-01保存后复用，I-01故障恢复 |
| GET /api/questions | cursor/limit/status | 200 Family分页 | 仅本人family，不把共享混入本人所有权 | 422游标 | QL-01多owner隔离/稳定分页 |
| GET /api/questions/{qid} | 无body | 200 Family | 仅owner | 404归属不可见 | QL-02不能通过family读未共享版本 |
| GET /api/questions/{qid}/versions | cursor/limit | 200 Version分页 | 仅owner，排除pending候选 | 409版本一致性异常 | R4-01历史序及来源 |
| GET /api/question-versions/{vid} | 无body | 200 Version | owner或当前有效的该版本grant；不因持有family ID放开 | 404已撤销/无权；409绑定异常 | R2-01指定版可读，未来版拒绝 |
| POST /api/questions/{qid}/versions | `{parent_version_id,definition,expected_revision}`+I-Key | 201 `{version,family_revision,operation_id}`；同内容新key也新建版本（显式版本意图） | owner；parent同family且已提交 | 409父版本/并发冲突；422内容 | R5-01并存；V-01并发及半成功恢复 |
| POST /api/questions/{qid}/restore | `{source_version_id,expected_revision}`+I-Key | 201 `{version,operation_id}` | owner；source同family；即使内容相同也新增 | 409错误family；404来源不存在 | R4-02 restored_from正确，旧版hash不变 |
| POST /api/question-versions/{vid}/fork | `{definition?}`+I-Key | 201 `{family,version,operation_id}` | 当前owner或该版有效grant；新owner恒为调用者 | 404撤销/无权；422新定义 | R2-04新family归B、source归A且不变 |
| POST /api/questions/{qid}/archive | `{expected_revision}` | 200 Family(status=archived) | owner；只阻止未来选用 | 409并发 | V-02历史仍能解释，不能新绑定 |

版本序号由服务端分配，客户端不可提供owner、version_no、content_hash。归档后的既有published不变；恢复归档family及未来重新开放选用不在初版接口内，另行评审。

## 分享确定版本

| 方法与路径 | 输入 | 成功输出 | 权限检查 | 额外错误 | 专用测试 |
|---|---|---|---|---|---|
| PUT /api/question-versions/{vid}/shares/{uid} | `{expected_revision?}`；无已有share时省略revision | 201新Share；200重授/已active | 原version owner；接收者存在；不授未来版 | 404用户/版本；409revision；422分享给自己 | R2-01 A/B/C及仅v1 |
| GET /api/question-versions/{vid}/shares | cursor/limit | 200 Share分页 | 原owner | 404非owner | ACL-01接收者不能枚举其他接收者 |
| DELETE /api/question-versions/{vid}/shares/{uid} | query expected_revision | 204（已撤销幂等） | 原owner；记录撤销审计 | 409并发；404实体不可见 | R2-05撤销与新选用/发布竞态 |
| GET /api/shared-question-versions | cursor/limit | 200 Version分页 | 仅授予当前用户且active的确定版本；来源裁剪 | 422cursor | ACL-02不枚举原family其他版本 |

接收者不获得原题写权、原题再分享权、题库所有权、问卷读取或统计权。fork后自己的新family可按自己的所有权管理，但来源信息显示服从Q3。S3/Q2待确认：普通draft需本次发布票据，已取得票据的在途operation例外、多个share和崩溃恢复严格按D3。重授有新epoch，不使旧key/payload变成新许可。不得把撤销当作删旧published定义。测试AUTH-01至AUTH-06。

## 题库和成员

| 方法与路径 | 输入 | 成功输出 | 权限检查 | 额外错误 | 专用测试 |
|---|---|---|---|---|---|
| POST /api/question-banks | `{name,description?}`+I-Key | 201 Bank | 创建者owner | 422空名/超长 | R7-01建库 |
| GET /api/question-banks | cursor/limit | 200 Bank分页 | 仅本人 | 422cursor | B-01他人库不可见 |
| GET /api/question-banks/{bid} | 无body | 200 Bank | owner | 404归档/不存在 | B-02读取边界 |
| PUT /api/question-banks/{bid} | `{name,description,expected_revision}` | 200 Bank | owner；active | 409revision；422字段 | B-03修改元信息 |
| DELETE /api/question-banks/{bid} | query expected_revision | 204软归档 | owner | 409revision | B-04不删除题/版本/引用 |
| GET /api/question-banks/{bid}/items | cursor/limit | 200 BankItem分页及可用/不可用状态 | bank owner；已撤销条目不展开题目内容 | 422cursor | R7-02撤销成员显示不可新选 |
| POST /api/question-banks/{bid}/items | `{question_version_id}` | 201 BankItem；完全相同重放200 | bank owner且对版本有use权限 | 409同family其他默认已存在；404无权 | R7-03共享版可加，本人库隔离 |
| PUT /api/question-banks/{bid}/items/{iid} | `{question_version_id,expected_revision}` | 200 BankItem | owner；同family；目标版可用 | 409异family/并发；404版本无权 | R7-04默认换v2不改旧问卷 |
| DELETE /api/question-banks/{bid}/items/{iid} | query expected_revision | 204 | owner | 409revision | R7-05仅移成员不删实体 |

题库成员默认版本更新必须显式；初版不实现自动跟随latest或题库整体共享。

## 问卷固定引用、修订与旧接口变化

| 方法与路径 | 输入 | 成功输出 | 权限检查 | 额外错误 | 专用测试 |
|---|---|---|---|---|---|
| POST /api/surveys/{sid}/question-references | `{question_version_id,order?,expected_schema_version}`+I-Key | 201 Survey，含新局部ID和binding | survey owner；draft；可用version；服务端构造定义 | 409published_frozen/closed_readonly/concurrent_modification/rule_reference_conflict；422非法order | R1-01/R5-01固定版、不同局部ID |
| PUT /api/surveys/{sid}/questions/{local_id}/binding | `{question_version_id,expected_schema_version}` | 200 Survey | owner；draft；目标版use权限；保持local ID | 409published_frozen/closed_readonly/rule_reference_conflict/concurrent_modification；404局部题 | R3-04草稿换版重校验Jump |
| POST /api/surveys/{sid}/revisions | `{source_schema_version,expected_schema_version}`+I-Key | 201新Survey、revision_of、新token | owner；原published/closed；确定来源快照可解释 | 409来源不一致；404snapshot | R3-03、REV-01/02；S1/Q1-R待确认 |
| POST /api/surveys/{sid}/publish（现有） | 保留旧调用形态，内部记录确定发布operation | 200 Survey（保持旧成功码） | owner；draft；固定引用完整；S3/Q2确定operation逐share票据齐备后封存；见D3 | 409缺映射/撤销/并发/快照冲突；503恢复中 | P-01授权撤销并发；P-02跨集合恢复 |

旧题目POST/PUT/DELETE及跳转写接口：draft保留编辑能力；published/closed返回409 published_frozen或closed_readonly。分享来源的draft不允许通过旧PUT改写原版本，返回409 requires_fork；可先fork再显式绑定自己的新版本。U8已批准旧PUT格式兼容，草稿创建新版并更新绑定；本切片不实现该适配，不得要求旧调用新增header。旧legacy草稿编辑暂走兼容路径，发布前需生成可审计来源或显式legacy绑定，详见迁移文档。

元信息PUT冻结范围见S2；close保持原接口与准入线性化语义。公开GET/next/responses输入输出保持；答案question_id仍是local ID，旧版本不回退到latest。新公开定义不暴露授权和内部operation。

## 使用追踪、跨问卷统计和恢复状态

| 方法与路径 | 输入 | 成功输出 | 权限检查 | 额外错误 | 专用测试 |
|---|---|---|---|---|---|
| GET /api/questions/{qid}/usages | version_id?/scope=current或historical/cursor/limit | 200 `{items:[{survey_id,schema_version,local_question_id,question_version_id,status}],next_cursor,index_state}` | S11/Q8待确认：题owner/ACTIVE grant/本人published或closed历史binding窄证明；仅本人survey详情，见D6 | 409index_incomplete/source_changed/legacy_mapping_required；422filter；D5逐源完整性核验 | R6-01/R6-02重建一致及不泄露他人 |
| GET /api/questions/{qid}/stats | version_id?/limit/cursor（明细）/bins? | 200 `{question_id,scope:'owned_surveys',versions:[{version_id,response_count,answered_count,by_occurrence,statistics}],coverage}` | 先survey.owner=current_user过滤；S11/Q8候选历史证明不要求仍ACTIVE；不开放原题目录；不得scope=all，见D6 | 403unsupported_statistics_scope；422invalid_bins；409statistics_data_inconsistency/legacy_mapping_required/index_incomplete/source_changed | R8-01手算；R8-02权限；R8-03分组/分母 |
| GET /api/stage2/operations/{opid} | 无body | 200 Operation | 原操作owner；只读，不自动恢复 | 404他人/不存在 | F-01 503后读状态不产生新写 |
| POST /api/stage2/operations/{opid}/resume | 无body | 200 Operation及已有结果；未完成可202 | owner；只恢复原确定payload与已准入权限 | 409原状态冲突；503依赖暂不可用 | F-02重复/并发恢复无双写 |

stats对数字必须至少提供有效次数、values或受限明细、average/min/max及数值频数；bins可明确left/right边界。四题型沿用既有统计定义，多选区分作答和选择次数。version_id省略返回分版本结果，不能默认合并。coverage按D5标记本次source_set；所需legacy映射缺失返回409 legacy_mapping_required，usage未完整409 index_incomplete，不返回部分结果冒充全量。默认范围缩小/权威计算回退未批准，不暗中排除不完整历史。损坏答案409 statistics_data_inconsistency。S6重复位置与S11撤销后权限仍待确认；测试USG-01至05、STAT-REV-01至04、ERR-01至06。

usage重建与legacy迁移为维护命令草案，不开放普通HTTP执行接口。只读dry-run与apply明确分开；业务库apply须另行授权，不作为当前或普通用户操作。

## 页面与API对应

题目列表/历史/恢复调用题目接口；共享收件箱调用shared-question-versions；个人题库调用banks/items；草稿选择器调用question-references/binding；published页只读并提供revisions入口；使用页展示授权范围和index_state；统计页展示version及位置、coverage和回答次数口径。所有写按钮状态由后端复查，不把按钮隐藏当作权限措施。

## 切片1实际契约补充（优先于上文同端点草案）

本切片只实现questions创建/本人列表/详情/版本历史、question-versions详情、versions创建、restore及operations查询/恢复。fork/archive/share/banks/survey绑定/usage/stats均未实现。新接口使用必填Idempotency-Key，旧接口保持原状。具体请求、响应、错误、游标和恢复见[slice1/protocol.md](slice1/protocol.md)。新增POST /api/questions/{qid}/repair-latest仅owner、body={expected_revision}，无新版本产生，成功200 Family；pending或revision变化409；不存在/非owner404。GET只读检查latest_pointer_valid，不自动写修复。

Family新增latest_pointer_valid；Version新增default_required（等于definition.required）及restored_from，保留restored_from_version_id别名。版本列表按version_no降序、cursor为正整数上页末序号；family列表按_id升序，cursor为上页末ObjectId，不再承诺时间+ID双字段游标。create/version/restore成功均201，重放同码、同实体ID；共同响应{family,version,family_revision,operation_id}，family_revision为该操作提交修订，family是读取时当前信息。Operation COMMITTED表示版本已可见，family缓存可能仍需resume完成；resume返回200 Operation加result。

## 切片2已实施API补充（2026-10-25）

以下优先于此前同端点草案。旧题目POST/PUT/DELETE格式和原字段保持，新增可选Idempotency-Key；PUT可选new_family=true表示明确新身份，可选required_override=null/bool指定位置覆盖。无key PUT一致有效结构为no-op，不重复版本；显式key同payload重放原结构，不同请求409。无key任意延迟重放无法区分新意图，限制见slice2/protocol；不强迫旧客户端新增header。

| 端点 | body/成功 | 权限与错误 | 验收 |
|---|---|---|---|
| POST /api/surveys/{sid}/question-references | ReferenceInput={question_version_id,required_override:null默认,order?:正整数,expected_schema_version}，必填I-Key，201 Survey | survey owner draft；version owner且COMMITTED；缺失/他人404；schema/Jump409；非法输入422 | S2-01/02/04 |
| PUT /api/surveys/{sid}/questions/{local_id}/binding | BindingInput同上无order；必填I-Key，200 Survey | 同family固定换版/位置覆盖，保持局部ID；异family409 version_family_conflict；新身份用旧PUT new_family=true | S2-02/04 |
| GET /api/surveys/{sid}/binding-operations/{opid} | 200 {operation_id,state,result_schema_version?}；未COMMITTED的结果版本为null | owner；只读不触发恢复；404他人/不存在；非法ID422 | S2-05 |
| POST 同路径/resume | 无body，200 Survey（确定原操作结构） | owner；只恢复原payload，409终结冲突，503未知结果 | S2-05/06 |

SurveyOut新增question_bindings，已有无bindings问卷输出空列表；公开定义接口不暴露bindings和内部操作/收据。版本快照owner GET新增bindings白名单序列化ID，原answers.question_id仍是局部ID。快照结构新增元数据不改变历史统计读取原questions的语义。

published/closed结构POST/PUT/DELETE（题目、规则、引用、绑定）分别409 published_frozen/closed_readonly，提示新建草稿；并不擅自冻结title/description/准入等待审元信息。元信息服务拒收结构字段，非法transition目标422；snapshot底层拒绝非draft更新，legacy published pending进入409人工审查，不写新快照。publish无绑定legacy草稿409 legacy_binding_required，破损/定义不匹配409 binding_mismatch，无权/缺失版本404，非法有效required规则422。没有新增修订问卷接口或分享能力。

切片2幂等作用域的明确精化：这些问卷位置写端点使用(owner_id,survey_id,key)，同survey跨action或body重用key冲突409，不同survey允许复用文本key；这取代D7草案对这些端点的通用owner/action作用域描述。切片1题目版本端点仍用原(owner_id,action,key)，未变更。具体request_hash均包含action/局部资源/输入，不能在同survey把一个key用于其他位置。该实现差异已在slice2/protocol和模型索引中记录，不暗称与先前通用草案完全相同。


## 切片2最小复审修正：操作结果与精确定义（2026-10-25）

本段精化切片2实际端点，不批准任何分享/usage/迁移新策略。

- GET /api/surveys/{sid}/binding-operations/{opid}：owner只读200 {operation_id,state,result_schema_version,current_schema_version,superseded}。result_schema_version由原COMMITTED或survey提交收据证实；尚无提交事实为null。superseded仅表示已提交结果版本小于当前schema；不自动改变state、不执行恢复。
- POST 同路径/resume：owner，只恢复原payload。当前schema>base_schema+1时409 detail={code:operation_superseded,message,operation_id,next_action:read_current_survey}，客户端重新GET当前survey；过期恢复不补写操作状态或返回SurveyOut。相同schema必须核验原结果结构/绑定一致，然后返回当前完整SurveyOut（允许当前已published/closed）；未超过版本却结构不一致或版本倒退409 operation_inconsistent。未完成操作沿用draft CAS/503规则；GET与resume错误不生成新版本、不删除历史。
- 同key显式草稿结构请求的过期结果同样409 operation_superseded；published/closed普通结构接口依旧先409冻结。相同结构仅发布不推进schema，不构成superseded。
- 数值精确表示沿用切片1：1和1.0的canonical JSON/SHA-256不同，草稿编辑须新版本；required覆盖独立，版本默认值不变。发布要求指定版本定义摘要、binding.content_hash、按override重建的有效定义及effective_hash全链匹配，不能凭Python字典数值相等放行。

验收FIX2-A/B/C见test-plan；原36项冲突仍须完整实际执行和逐项分类。无key任意延迟重放、真实进程强杀、页面E2E与压测仍未解决/未执行。


## 切片2最终状态查询投影修正（2026-10-25）

GET /api/surveys/{sid}/binding-operations/{opid} 的state现在是逻辑投影：若op.state==COMMITTED或该opID存在于survey._binding_commits，输出COMMITTED；否则输出原state。result_schema_version、current_schema_version、superseded与前轮契约相同，使用相同提交判据。GET仅read，无数据库补写；不能从响应COMMITTED推断原操作状态字段已经补写。本条替代前轮“原state”响应措辞，保留原文作历史。未改变resume：结果过期409 operation_superseded且无补写；同版发布后验证结构并返回当前完整SurveyOut。验收PROJ-01/02见test-plan。


## 切片3实际端点与页面（2026-10-26）

以下替代同端点旧修订草案的未批准状态；仅本人来源，未实现共享授权。

| 端点 | 输入/成功输出 | 权限、错误及验收 |
|---|---|---|
| POST /api/surveys/{sid}/revisions | 严格body={source_schema_version,expected_schema_version}正整数；必填1–128可见ASCII I-Key；201完整SurveyOut | source owner，published/closed；未登录401/跨站403/不可见404，非法输入422；schema冲突409；无正式快照409 revision_snapshot_required；坏结构/绑定409；同key异body409 idempotency_conflict；已删除结果410 revision_result_deleted；不确定写503 operation_recovery_required带operation_id |
| GET /api/surveys/{sid}/revision-operations/{opid} | 200 {operation_id,state,result_survey_id?}，已有插入收据则逻辑COMMITTED | owner；只读，无恢复副作用；404其他人/缺失，422非法ID |
| POST 同路径/resume | 无body，200原结果survey当前完整文档 | owner，只恢复已持久化原意图；源快照变化409 revision_source_changed；不改后续编辑，已删除结果410；不确定写503 |

幂等scope=(owner_id,source_survey_id,key)；不同key可创建多个修订，同key同body不重复创建。source_schema可选存在的正式历史版本但不超过当前；expected_schema校验来源当前版本。无快照不补造，不采用当前缓存拼结构。状态/快照/绑定不可靠时明确拒绝，不改来源。SurveyOut新增revision_of和revision_source_schema_version；现有旧问卷为null。删除尚有未确认revision创建标记的draft为409 revision_recovery_required，先恢复原创建。

GET /api/questions和详情Family增加title/type/latest_version_no/latest_committed_version_id/version_count/updated_at，所有数据仍限owner且有已提交版本；latest_version_id缓存字段不改变。已有create/version/history/restore契约不变。页面/选题调用现有明确版本端点，保留required_override三态和局部ID/Jump。

新页面GET /question-bank、/question-bank/{qid}：未登录303登录，本人目录/详情，未完成family和他人404；API仍401/404。dashboard/edit增加修订来源和入口；draft才显示结构表单和picker，published/closed只读结构并显示修订入口，元信息沿用原接口。原生JS用Idempotency-Key持久化一次payload意图，成功后新意图换key，失败保留表单/key。保存成功后刷新失败需重新加载，禁再次提交；无key旧请求的固有限制未消除。

测试对应S3-REV/LEG/UI/JS，真实记录slice3/，不从HTTP渲染推断浏览器E2E通过。


## 切片4共享接口（2026-10-29）

- `GET /api/shared-question-versions`：当前用户的活动共享版本，带owner用户名，分页；只返回授权版本，历史来源ID对接收者隐藏。
- `PUT /api/question-versions/{vid}/shares/{uid}`：owner按用户ID授权，可携带expected_revision；重复有效授权确定返回已有关系。
- `POST /api/question-versions/{vid}/shares`：owner按用户名授权。
- `GET /api/question-versions/{vid}/shares`、`DELETE /api/question-versions/{vid}/shares/{uid}`：仅owner列出和撤销，可用revision约束；重授权递增grant epoch。
- 共享版本只开放具体版本读取和绑定，题目族、版本历史、修改及转分享仍需owner；服务端核验。撤销后草稿保留但后续发布/编辑校验失败，可移除失效引用；原发布快照不变。
- `POST /api/question-versions/{vid}/fork`：owner或有效接收者以幂等key派生新题族，保留源版本标识，授权准入后原操作可恢复。


## 切片5实际题库接口（2026-10-29）

`GET/POST /api/question-banks`，`GET/PUT/DELETE /api/question-banks/{bid}`，`GET/POST /api/question-banks/{bid}/items`，`PUT/DELETE /api/question-banks/{bid}/items/{question_id}`。创建题库使用Idempotency-Key；元信息及成员更新和删除使用expected_revision，题库删除软归档。新增同族同版本是确定性no-op，同族其他版本409；更新须同族且当前可用。列表分页，授权失效成员不展开题目内容，不能绕过共享授权。路径成员标识按本轮指令采用question_id，替代上文提议的iid。

切片5实际成员响应包含正式`bank_id`、`selected_version_id`，同时提供`default_version_id`等值别名；活动题库响应包含`archived=false`。


## 切片6实际usage契约（2026-10-29）

`GET /api/questions/{qid}/usages`支持`scope=all|current|historical`、`version_id`、`cursor`、`limit`。返回本人来源的固定版本与位置、状态和coverage；先验证整个范围的READY索引，缺失/损坏或需legacy映射返回409。题目owner或当前ACTIVE授权版本可访问，分享不开放他人问卷；Q8未获批准，撤销后本人历史窄入口暂不开放。维护命令`scripts/rebuild_question_usages.py`要求显式`--uri --database --owner-id --scope --apply`，不开放普通HTTP重建接口。


## 切片7实际统计接口（2026-10-29）

`GET /api/questions/{qid}/stats`支持可选`version_id`，范围固定为`owned_surveys`，其他scope返回403。复用Slice 6全范围READY完整性检查和现有授权，按版本返回`statistics`、`answered_count`、`by_occurrence`及coverage；单选比例为该选项次数除以有效回答次数，多选另给total_selections，数字无有效值时min/max/average为null。历史快照或答卷不一致返回409。Q8撤销后历史窄入口仍未批准。
