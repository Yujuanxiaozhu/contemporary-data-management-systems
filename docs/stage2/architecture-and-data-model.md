# 架构与数据模型草案

本文按切片追加，前半部分是当时的设计草案，“未实现/待评审”属于历史记录。Slice 1–7 完成后，题目族、版本、绑定、修订、分享、题库、usage 和统计集合均已实现并在隔离库验证，最终结构见 [docs/database-design.md](../database-design.md) 与 [docs/architecture.md](../architecture.md)。统一细则见[design-rules](design-rules.md) D1–D7；U为已确认不变量，S系列为实现建议。继续使用现有FastAPI router→service→PyMongo分层、Validation/Jump、Jinja2/原生JS，不重建应用。

## 当前结构与兼容事实

现有users、sessions独立；surveys嵌入questions/jump_rules；survey_versions保存整份已发布结构；responses以survey_id+survey_schema_version关联快照。`app/services/questions.py`的published修改调用snapshot_commit，closed才拒绝；这满足旧答卷解释，但不满足R3旧公开问卷保持原内容。

实际索引在`app/core/database.py:ensure_indexes`：users.username unique；surveys.public_token unique、owner/created_at；responses.survey_id、survey_id/schema、dedupe_key unique sparse；survey_versions.survey/schema unique；sessions.token_hash unique、expires_at TTL。保留这些索引及其语义，不将新题库索引替换旧去重约束。

`QuestionDefinition(extra='forbid')`意味着新增来源字段必须明确扩展读写schema；不能把多余字段直接塞进现有嵌入定义。统计和Jump仍接受原四题型有效定义，引用元数据应隔离为binding或在解析时明确投影，不能关闭未知字段校验应付兼容。

## 四个身份空间

| 名称 | 物理含义 | 唯一性与用途 |
|---|---|---|
| question_id | 独立题目族/family的ObjectId | 跨问卷复用谱系；不是题干hash |
| question_version_id | 不可变版本文档ObjectId | 问卷固定内容的权威来源；绝不运行时跟随latest |
| schema_version | 原survey结构版本正整数 | 整份快照及response历史解释；draft修改仍可递增 |
| local_question_id | 问卷某个出现位置；现有物理字段questions[].id | answers[].question_id和jump source/target继续用该ID |

同题在A/B的局部ID可不同；若批准S6允许同题重复出现，则各位置必须有不同局部ID。原API字段answers[].question_id保持原含义，文档必须标明它是局部ID，不能在兼容阶段偷偷改成全局ObjectId。

## 建议集合与字段

所有ObjectId在库中保留BSON类型，API显式字符串化；时间UTC aware、BSON毫秒。以下集合均为拟议。

### questions

`_id, owner_id, created_at, status(active|archived), latest_version_id, committed_version_no, revision, _pending_version?`。owner来自当前身份，不接受客户端指定。latest用于题库提示，不解释任何已有问卷。归档阻止未来选用，不破坏历史。

建议索引：`(owner_id, created_at, _id)`；_id默认唯一。归档恢复不改变历史内容。

### question_versions

`_id, question_id, version_no, parent_version_id?, derived_from?, restored_from_version_id?, definition, created_by, created_at, content_hash, operation_id`。

definition含type/title/required/options/validation，不含问卷位置order和局部ID；选入时使用新位置ID/order重建并调用原Validation。U7：required为版本默认值，未来问卷位置允许独立覆盖，发布冻结最终值；本切片仅保存默认值。选项ID固定在该版本内，跨版本同option ID也不保证含义兼容。

parent属于同family，表达本次编辑基础；derived_from指向跨family派生来源；恢复在当前family新增版本，parent记录编辑基点，restored_from记录恢复内容的旧版本。content_hash检查规范化内容一致性，不用于全局合并或统计兼容判定。

版本只insert/read，不update/delete；撤销共享、归档和题库移除均不删除版本。唯一`(question_id, version_no)`、`operation_id`，辅助`(question_id, created_at, _id)`。全量不可变通过业务写入和受控数据库权限保证，不声称管理员无法直写。

### question_banks 与 bank_items

banks：`_id, owner_id, name, description, revision, created_at, updated_at, archived_at?`。

items：`_id, bank_id, question_id, selected_version_id, added_by, added_at, revision`。建议唯一`(bank_id, question_id)`；selected_version为显式默认，所有授权旧版本仍能在选择器中查看。换默认版本不批量修改草稿或published。归档题库/移除成员不删题目和版本；题库初版仅个人所有，不隐含题库整体分享。

建议索引banks(owner_id,created_at,_id)，items(bank_id,question_id) unique及(question_id,selected_version_id)。

### question_shares

`_id, owner_id, question_version_id, grantee_user_id, permission='use', state(ACTIVE|REVOKED), grant_epoch, revision, bounded_admissions, created_at, revoked_at?`。这些是S3的待确认技术字段，准入票据不得无限增长。

仅授权确定的单个版本。owner必须为原版本owner；接收者可读该版本、选入或派生自己的题，不能改原family、展开未授权版本、再次分享原题或看他人问卷/答卷。建议唯一`(question_version_id, grantee_user_id)`，重授更新同授权记录并记录审计事件；grantee/state/created_at索引支持收件箱。

### surveys 与新的 survey_versions

保留原questions/jump_rules和局部ID；建议新增`question_bindings:[{local_question_id, question_id, question_version_id, content_hash, provenance_type, use_authorization?}]`。绑定数量须与新模型问卷题目一一对应。旧问卷允许缺binding并走legacy兼容路径。

questions保留可直接填写的有效定义，bindings保存来源。服务端解析version生成定义，禁止客户端同时伪造source和任意内容。U7允许required位置覆盖；其他内容仍由固定版本生成。后续切片须记录required_override及有效定义摘要，不能把其他任意覆盖静默当作同版本。新snapshot同时写定义、规则、binding和schema格式标识；使用原pending协议先完整快照后发布。

S1/Q1-R待确认：修订草稿记录revision_of，生成新survey ID/token，schema_version从1起步；原token仍指向原survey结构，不重定向或自动关闭。不继承responses、dedupe、准入或授权票据。撤销来源可否复制为needs_authorization草稿及发布重验权见D2/D3，不暗中继承旧许可。测试REV-01/REV-02。元信息是否冻结另见D1/Q1-M。

### question_usages（派生索引）

S9/Q9待评审：usage行增加generation；source_key=(survey_id,schema_version,scope)，唯一(source_key,generation,local_question_id)。另设usage_manifests(source_key unique)，包含source_revision、active_generation、expected_count/hash及state。权威current源通过同文档CAS推进binding_revision；historical源由snapshot摘要及legacy映射代次确定。详细重建/核验见D5，测试USG-01至USG-05。

binding和legacy映射是权威，usage不是历史真相。查询先按owner枚举权威source_set，逐源核对manifest、代次、行count/hash和源revision；缺整份索引也能发现。新代验证后切换，旧代随后清理；未完整返回409 index_incomplete，不将漏建视为零。source_set是动态请求观察范围，不承诺跨集合事务时点。不得为draft补造未发布历史。

### legacy_question_bindings 与 stage2_operations

legacy映射见D4及migration文档，唯一survey/schema/local ID，保存源摘要、规则版本与审计来源；不能仅凭稳定local ID自动归同family。operations保存owner/action/idempotency key/request hash/result pointer/state、checkpoint和错误类别；不保存明文凭据或请求Cookie。唯一(owner,action,key)，同key不同内容409。已成功幂等记录不依靠短TTL避免延迟重试重复。

## 可恢复版本提交协议

建议每个family同时仅有一个pending。先验证内容/身份/parent；同owner读取revision，以CAS预留确定operation/version ID/序号/内容。插入不可变版本；确认完全一致后CAS推进latest/committed_version_no并清pending。读者只返回已完成提交的版本，不暴露pending插入的候选版本。重复键必须比较完整确定内容，不能覆盖历史。

初次创建family时先写带pending且尚不可选用的family，恢复完成首版本再公开。序号允许因失败预留而存在空洞，不重用；不并发max+1。并发恢复者用operation ID和唯一键协作。中断后继续既定操作，不自动把旧请求rebase到新内容；503表示需读取操作状态，不代表取消。

同内容不同来源不自动合并；无变化更新建议返回当前版，不额外创建，但显式restore即使内容相同也新增，记录恢复意图。此细节纳入API测试。

## 发布冻结与授权准入

U1只确定题目和跳转结构冻结，包括排序、局部ID、固定绑定及解释结构；title/description、准入策略、deadline的冻结是S2/Q1-M待确认。close及内部准入标记不等于结构编辑。字段表、FRZ-01至FRZ-05见统一规则D1。

草稿显式换版保留local ID并重校验Jump；合法候选破坏既存引用统一409 rule_reference_conflict。published/closed结构写分别409 published_frozen/closed_readonly。required覆盖已获U7批准但问卷绑定改造尚未实施；其他产品细节不得先实现后追认。

S3/Q2撤销及发布状态机见D3：普通DRAFT无永久票据；PREPARED→PARTIALLY_ADMITTED→READY→SEALED→COMMITTED，另有BLOCKED/ABORTED。每个share的准入与撤销分别在同文档CAS排序，没有多个share的全局原子准入点；全部确定票据齐备后，survey封存CAS决定同草稿发布竞争。撤销前已准入的确定operation可继续，是待确认的在途例外，而不是所有未发布草稿都能继续。崩溃恢复、重授epoch、票据清理、容量和禁止超时盲取消均遵循D3。测试AUTH-01至AUTH-06。

U2：接收者修改必须派生自己的题。分享不授予其他问卷、答卷或原题目录权限。S11/Q8建议撤销后允许本人合法published/closed历史binding提供窄范围统计证明；原版本目录仍要求owner或ACTIVE grant。此建议尚未批准，见D6。初版跨owner统计授权入口不在本次设计实施范围。

## 统计与页面

查询链：当前用户owner过滤→指定question/version→本人survey bindings及legacy映射→response的survey/schema→snapshot内local ID→答案。撤销后的本人历史证明使用S11/Q8待确认路径，不能以ACTIVE grant一刀切阻断本人历史，也不能未经批准自动开放；D6定义候选谓词，D5定义完整性门槛。即使usage有他人记录也不得返回他人标题/答卷。旧损坏历史沿用409 fail-closed，权限过滤必须先于读取他人内容。

默认按question_version_id分组，同时保留survey/schema/local位置分组。有效回答次数不等于去重自然人数；是否允许重复位置及默认聚合是S6/Q4待确认；若允许则不静默去重。多选answered_count与total_selections分开；数字0有效，空平均null，未答/skipped不计；数值频数/分箱边界明确。跨版本合并默认拒绝，未来必须显式兼容映射和授权。

沿用现有管理页面，增加题库、共享版本收件箱、选题、历史/恢复、使用追踪和跨问卷统计页；published编辑页改为只读及“创建修订草稿”。按钮不是权限边界，后端逐端点检查；继续模板转义、tojson、textContent、同源写防护。公开API不外泄owner、share、pending或内部来源权限信息。

## 查询与规模边界

新列表按各资源实际时间字段+_id稳定游标分页（bank_items为added_at），limit 1–100。使用/统计按必要复合索引验证explain，不预先承诺大数据性能。大问卷和pending副本受BSON16MB约束；保持200题及既有选项长度上限。统计为动态结果，不承诺跨集合事务快照。重建、分页和索引优化不能改变统计分母。

## 切片1实际模型修订

本节替代上文版本提交协议的建议细节：questions增加next_version_no，初始revision=0、首次成功=1；_pending_version={operation_id,version_no}；最新版为缓存。question_versions使用restored_from（输出兼容restored_from_version_id），created_by来自owner；definition.required为默认值。stage2_operations的COMMITTED是版本可见性的权威，非latest。持久化状态与恢复顺序、索引、规范摘要、并发及指针修复见[slice1/protocol.md](slice1/protocol.md)。不创建其余拟议集合、不迁移或绑定问卷。

## 切片2已实施模型（2026-10-25）

本节为U1/U6–U9的切片2落地，替代主体中相同字段仍属草案的描述；其余分享/usage/legacy/修订策略仍未批准。实现详见[slice2/protocol.md](slice2/protocol.md)。surveys.question_bindings[]保存local_question_id、BSON question_id/question_version_id、required_override、版本content_hash、有效definition的effective_hash；管理输出转ID字符串。questions仍是可直接执行Validation/Jump的内嵌有效定义，来源元数据不混入QuestionDefinition。required在固定版本中是默认，在位置通过null/bool覆盖；旧PUT的required为位置实际值，已有版本默认不被覆盖，只有内容变化创建新版，order/required覆盖变化不改版本。

draft_operations保存确定计划/子key/结果和状态，unique(owner_id,survey_id,key)。survey._pending_binding用draft+schema CAS预留，_binding_commits永久提交收据随同结构CAS写入，解决结构已切换而操作状态落后的恢复窗口。子版本统一调用切片1协议，不重新分配序号。只在用户明确编辑该草稿时逐位置适配legacy，不扫描其他问卷。publish重新校验绑定/有效定义/权限/Jump，快照保存bindings及最终required。旧published/closed快照无bindings仍可解释。

所有结构写及直接服务入口受draft约束：questions._editable/commit_structure、底层draft CAS、snapshot_commit/finish_pending、surveys.update_survey结构字段白名单/transition目标白名单。旧published pending不自动完成；未知状态保留失败现场。没有实现修订ID/token、分享、usage或跨问卷统计。课程规模全量候选及长期收据仍受BSON16MB/保留容量约束；未声称后台自动修复。


## 切片3实际模型（2026-10-26）

沿用surveys内嵌有效questions/Jump与固定question_bindings、独立questions/question_versions和切片1恢复协议。SurveyOut新增可空revision_of字符串及revision_source_schema_version整数；旧记录输出null。物理revision_of是来源ObjectId，新draft schema=1，新的_id/token/timestamps，没有来源内部pending、准入、收据或response/session/dedupe/旧操作字段。

唯一新集合revision_operations：owner_id、source_survey_id、key、request_hash、source_schema_version、source_hash、candidate（确定新ID/token/元信息和源结构）、plans（legacy来源tuple/hash/确定子key）、legacy、result_survey_id、state、resolved_document。唯一(owner_id,source_survey_id,key)和result_survey_id。只在合法显式修订写时建索引，原启动和旧接口不初始化新集合。来源正式snapshot直接只读查询，不调用有补写副作用的ensure_current_snapshot。先校验owner/状态/期望schema/权威快照/结构/绑定，再持久化计划。

legacy来源转换复用bank.write(create)：子key按owner/source/schema/local确定，同源位置跨修订意图复用已耐久结果；不同位置即使内容相同也新family。计划保存源摘要，重试源快照变化409，不覆盖。插入新survey是结果存在的收据；幂等重放返回该survey当前完整文档，绝不以原candidate覆盖编辑后的结构。状态落后时显式resume补记；COMMITTED结果已删除410，插入后状态未确认时拒绝删除，避免结果复活。不使用事务、Redis或内存幂等表。

family_out增补题名/题型/最高已提交version ID及序号/版本数/更新时间，用COMMITTED操作关联的实际版本计算；latest仍只是可核验缓存。课程规模读取历史求摘要，不承诺大规模查询性能或全局事务快照。未实现命名banks/items、分享、usage、统计新集合。


## 切片4 ACL与操作票据（2026-10-29）

`question_shares`按(version, grantee)唯一，记录owner、活动状态、revision及grant epoch；原旧数据没有共享记录时默认私有。新增索引按需创建，无全库迁移。`share_publish_operations`持久保存与问卷结构和元数据绑定的授权票据；草稿绑定及派生操作复用相同准入机制；派生题版本记录derived_from_version_id。单份share文档原子记录准入，与撤销竞争，以确保已获准的原payload可恢复而新payload和新epoch不可借用。操作收据有上限，异常中断需原操作恢复以释放。发布快照继续独立冻结。


## 切片5题库落地（2026-10-29）

`question_banks`存owner、名称、说明、revision、创建/更新及归档时间，创建幂等键在owner内唯一。`bank_items`存bank_id、question_id、selected_version_id、added_by、时间及revision，唯一(bank_id,question_id)。默认版必须committed、同族且用户当前可用；读取重新核权，失效时仅返回不可用状态。题库及成员不作为问卷绑定或快照的权威来源。


## 切片6派生usage索引（2026-10-29）

权威来源为本人当前draft的question_bindings、本人published/closed的survey_versions，以及U11已提交修订操作中逐位置的可核验旧来源转换。`usage_generations`记录owner/scope及BUILDING/READY/FAILED，`usage_manifests`按来源记录摘要、计数和行摘要，`question_usages`唯一键为(generation, source_key, local_question_id)，`usage_heads`按(owner,scope)原子切换代次。查询扫描来源并逐来源核验后分页，期间重读来源、授权、代次和head；这是动态非跨集合事务视图。缺映射、缺快照、行数或摘要不一致均fail-closed。


## 切片7统计（2026-10-29）

先完整核验Slice 6 usage并分页收集本人历史位置，按survey/schema定位不可变snapshot与答卷；复用既有历史路径/答案校验。固定question_version_id分别聚合，同版本不同local位置分别计数，不使用题名或跨问卷local ID识别。处理前后复核usage、授权、版本、快照及答卷集合；为动态非事务视图。统计不写usage、snapshot或response。
