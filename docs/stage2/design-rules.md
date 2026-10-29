# 第二阶段统一规则审查稿 R2

日期：2026-10-24。状态：主体为R2审查稿；切片1已按U6–U9获批并实现，边界见文末增补，其他S/Q继续待审。本文件为跨文档规则的唯一详细定义；其余文档引用规则ID，发现差异时先修正文档，不能自行以一份覆盖另一份实施。来源以decision-log的T/U/C/S/Q分类为准。

U1–U5是用户确认的设计基线。下列算法、字段及错误码属于技术草案；S1–S11及其Q事项是待确认方案。验收ID均为未来测试计划，不是已执行结果。

## D1 发布冻结字段边界

| 字段或操作 | 已确认的边界 | 待确认部分 | 验收 |
|---|---|---|---|
| questions：题型、题干、required、options及选项ID/文字、validation、位置order和局部ID | U1：published后不可增删、替换或原位修改，closed亦不开放结构写 | U7允许草稿位置覆盖required（后续切片），不影响published已确认冻结 | FRZ-01、FRZ-03 |
| jump_rules：ID、source、target、operator、value、priority | U1：published后不可增删改 | 无已批准例外 | FRZ-01 |
| 固定来源绑定、question_version_id、解释用schema_version | 作为题目/跳转结构组成部分保持固定；版本只能由服务端在合法草稿操作/发布中管理 | 新字段布局为技术草案，不允许借修复指针替换已发布内容 | FRZ-03、FIX-01 |
| title、description | 本轮用户确认清单没有批准其可变或冻结 | S2/Q1-M：建议发布后也只读；未确认前不得实现任一发布后编辑策略 | FRZ-02 |
| allow_anonymous、allow_multiple_submissions、deadline | 不从“题目和跳转结构冻结”推导额外产品权限 | S2/Q1-M：建议只读；是否允许延期等例外需明确批准及准入兼容测试 | FRZ-02、FRZ-04 |
| public_token及revision_of | 不作为原位改题入口 | 新修订ID/token及原URL规则属于S1/Q1-R，见D2 | REV-01 |
| close、准入时间、去重、确定pending恢复、updated_at等内部标记 | 保留原状态/准入和历史解释保护；内部标记变化不等于允许改结构 | 仅恢复同一已授权payload；不能以恢复为名改题或改绑定 | FRZ-05、AUTH-03 |

published结构写返回409 published_frozen；closed结构写返回409 closed_readonly。草稿结构合法性/引用检查继续执行。题库latest、撤销分享、恢复旧题均不得追写已有published结构。元信息待决只阻塞对应产品入口，不否定U1已确认的结构冻结。

内部恢复例外只适用于不改既有published结构的确定操作，例如draft首次发布；旧系统遗留的published改题pending不能自动完成，须按migration文档的Q5异常处理另行批准。FRZ-05验证此边界。

## D2 修订问卷与固定引用

U1要求通过新草稿/修订问卷改结构，但没有批准ID/token细节。S1/Q1-R建议：每次修订生成新survey_id、新public_token，schema_version从1开始，记录revision_of={survey_id,source_schema_version}。复制有效定义和局部ID；原survey/token仍指向原结构，不重定向、不自动关闭，不继承responses、dedupe_key、准入记录、账号提交身份或授权票据。元信息复制只作为新draft初始值，实际准入在新问卷发布/提交时重新检查。

source_schema_version必须存在且可解释，expected_schema_version用于防并发。共享来源已撤销时允许为本人创建只读内容的修订草稿是S1附属建议：复制不生成新授权，显示needs_authorization；再次发布、选入新位置或fork必须按D3取得新的授权，不能借旧published票据复制授权。该建议未批准，不作为实现默认。测试REV-01/REV-02。

固定版本含义已明确：question_id是全局谱系；question_version_id是不可变内容；schema_version是问卷结构；local_question_id是该问卷出现位置，answers[].question_id和Jump继续引用它。绑定与有效定义一一对应，服务端生成并比对内容摘要，禁止读取时跟随latest。restore新增版本并记录restored_from，绝不覆盖历史。required默认值/位置覆盖已获U7批准，见slice1/protocol.md，不改变上述不变量。测试FIX-01、FIX-02、R4-02。

## D3 分享撤销与发布授权状态机

U2只批准分享指定版本及接收者派生自己的题。以下S3/Q2产品策略及恢复算法仍待批准：撤销阻止撤销后新的授权准入；已在撤销前通过单个share原子准入的确定operation可继续。它是有边界的在途例外，不等于所有旧草稿均有永久引用权。

### 对象与持久化字段

- share：version_id、grantee、state=ACTIVE/REVOKED、grant_epoch、revision、bounded_admissions。撤销在同一share文档CAS改变state/revision，不清空在途票据；重授增加grant_epoch。旧票据只能完成原operation，不能用于新operation或新payload。
- operation：owner、kind、idempotency key/request_hash、draft_id、base_schema/revision、payload_hash、精确version及share/epoch清单、逐项admission_receipts、state、确定snapshot_id、result_id、错误。凭据不入日志。
- receipt：operation_id、share_id、epoch、version_id、payload_hash、准入序号；owner/grantee必须匹配。share文档中的原子准入记录是尚未复制到operation时的恢复依据。

### 状态与转换（待确认方案）

| 状态 | 进入条件和权威位置 | 撤销影响及恢复 | 测试 |
|---|---|---|---|
| 普通DRAFT | 只有已选题定义，没有本次发布operation票据 | 撤销后不能凭旧选题直接发布；移除/换成自己的派生版本/重新获授权 | AUTH-01 |
| PREPARED | 持久化确定payload和版本清单，尚未收齐票据 | 每个share分别以ACTIVE+epoch+revision条件CAS准入；失败不伪造票据 | AUTH-01、AUTH-02 |
| PARTIALLY_ADMITTED | 至少一个确定share票据已原子登记，其他票据未齐 | 已登记的原operation票据在随后撤销后仍有效；其余share仍需在各自准入时ACTIVE。若未获票据的share已撤销，BLOCKED，不得发布 | AUTH-02、AUTH-04 |
| READY | 所有确定依赖票据已持久化/可从share恢复 | 不是“现在所有share同时ACTIVE”的承诺；按逐share已授票据授权，不存在跨集合全局原子时刻 | AUTH-02 |
| SEALED | survey以draft+base_schema/revision+无pending条件CAS写入带operation_id的确定_pending_schema | 这是同一draft竞争发布的线性化点，不重新消费或扩大票据；其后撤销不撤销该在途发布 | AUTH-03 |
| COMMITTED | 完整snapshot存在且survey指针切换成功 | operation结果可能滞后；恢复以survey/snapshot确定结果补记，不重复发布/建快照 | AUTH-03 |
| BLOCKED | 未取得的新票据被撤销、资料需处理，或容量不足 | 容量等暂时原因可重试同operation；授权epoch已变/重授时必须新key和新operation，旧票据不搬迁。不得替换已封存payload | AUTH-04、AUTH-05 |
| ABORTED | 封存前确认draft已变或原operation不再适用 | 原票据仅属于旧operation，不允许移给新草稿。新内容需新key/operation | AUTH-06 |

每个share的准入CAS与其撤销CAS在同一文档排序。多个share没有单一全局准入点；只有全部票据满足条件后才可SEALED。选择“撤销立即阻断所有尚未发布操作”是另一种产品策略，不得混入本方案；若用户选择它，必须重新设计相应协议和测试。

崩溃处理：share准入成功而operation未记票据时，从share按operation_id/payload_hash恢复；撤销不得删该记录。operation票据耐久后才可移除share中的副本。容量上限、满时409 authorization_capacity及显式维护回收为技术草案，不能无限增长或用短TTL静默失效。结果不确定返回503并保留现场，不自动标ABORTED。SEALED后不支持取消；仅确认未封存且draft已变化时可终结旧operation。多恢复者由唯一operation key、share CAS及survey CAS幂等协作。

新选入、入库、fork使用同样的确定payload准入原则，但各自operation不得转成发布许可。普通草稿选用成功不代表以后发布免验权。测试AUTH-01至AUTH-06、I-01、F-02。以上为协议草案，尚未证明实现正确或通过并发测试。

## D4 legacy映射判据

U4已确认：不改旧survey_versions/responses，不按猜测自动合并。映射键固定为(survey_id,survey_schema_version,local_question_id)，内容摘要只能校验一致性，不能证明题目身份。

| 情况 | 规则与来源层次 | 验收 |
|---|---|---|
| 已存在审计映射，键、源摘要及规则版本相同 | 技术建议：重用已有目标，幂等；不是新合并 | LEG-01 |
| 同映射键但源摘要不同 | 停止，409 legacy_mapping_conflict；禁止覆盖旧映射或旧快照 | LEG-03 |
| 有可靠、已审计的明确来源关系 | 只按该来源/人工批准关系关联，记录review_reference、来源键、目标及理由；审批格式待确认 | LEG-04 |
| 没有可信来源，仅题名/local ID/hash相同 | 不自动关联；跨survey尤其禁止 | LEG-02 |
| 同survey跨schema稳定local ID，但有删除重用、缺失中间历史或语义变化 | 不能证明连续身份；不自动归同family | LEG-02 |
| 缺snapshot或答案损坏 | 不补造；原历史解释409，并输出异常清单 | LEG-03 |

S7/Q5推荐的可执行保守方案是“每个无来源的快照位置分别建立legacy family/version”，唯一源键分配确定目标ID，跨schema也不自动合并；替代方案是停在needs_review等待人工关联。这两者均待用户选择，未获批准前不得对业务库apply。原先“survey+local ID足以建同谱系”的模糊建议已撤回，不再作为自动规则。

人工确认合并只新增有版本的审计关联，不覆盖旧来源映射；再次运行以计划hash和源摘要核对。旧draft仅能声明当前结构，无历史快照不伪造。测试LEG-01至LEG-04以及migration文档中断点。

## D5 usage索引完整性机制

S9/Q9为待评审技术方案。binding及legacy审计映射是权威来源，usage只做派生加速。不得从usage候选行反推“所有问卷”，否则漏建整份问卷无法检测。

1. 先按调用者owner和请求scope枚举权威来源，物化本次source_set：每个source_key=(survey_id,schema_version,scope)，附source_revision及规范化绑定摘要。current使用新survey的binding_revision（与结构同文档CAS推进）；historical使用不可变snapshot摘要及legacy映射代次。缺必需legacy映射返回409 legacy_mapping_required，不假定该题不存在。
2. 每个source维护usage_manifest：source_key、source_revision、active_generation、expected_count、expected_hash、state(BUILDING/READY/FAILED)。每个usage行带generation，唯一(source_key,generation,local_question_id)。READY必须证明该代行的数量及排序后完整tuple摘要与权威来源相同，而不仅是“存在manifest”。
3. 重建先创建新generation并幂等写行；全部写完核对摘要，重读权威来源，只有revision/hash一致才CAS标READY并切active_generation。崩溃留下BUILDING或旧代，不直接当完整；清理旧代在切换后，不删权威来源。
4. 查询对本次每个source逐项核对manifest、实际行count/hash和权威revision；缺manifest、少行、多行、摘要错误、旧代或BUILDING均409 index_incomplete。重建验证与标READY之间发生源变更，也会被查询时的revision对比识别，不误报完整。
5. 只有枚举的整个source_set均完整才能返回“零使用”。响应coverage标出source_set_digest、来源数量、scope及动态读取口径；请求期间来源变化返回409 source_changed后重读，不以新代覆盖本次已观察的来源。并发新建问卷可能下一次刷新才纳入，不承诺跨集合事务时点。
6. 为课程规模先做权威扫描和全量核验，不能提前承诺性能；未来增量水位若替代扫描，必须另证完整性。列表分页只能在完整性判定后做，不得把一页行数当总量。

统计同样不得在缺索引/缺映射时静默略过来源。默认统计范围的历史映射未就绪时明确409；若未来允许显式缩小survey范围或回退直接权威计算，需另行定义coverage和授权，当前不默许部分结果。测试USG-01至USG-05。

## D6 撤销后的本人历史统计权限

U3确认默认仅本人问卷；U2不授予他人问卷/答卷。S11/Q8待确认的建议是把“新使用权”与“本人已发布历史解释权”分开：撤销后，用户仍可基于本人published/closed的合法固定binding或legacy审计映射汇总自己的答案；不要求原share仍ACTIVE。

候选权限谓词：先current_user认证和owner过滤；以本人历史binding证明指定qid/version曾合法使用，再从这些snapshot解释答案。不据此开放原family目录、未共享版本、原作者新题、他人usage/答卷。GET原question-version仍要求owner或ACTIVE grant；stats/usages可有“本人历史binding证明”这一窄入口，两者权限不同但不矛盾。

没有本人历史binding且grant已撤销的任意qid/version按404处理；已拥有历史绑定也只能返回该绑定可见的版本与本人数据。草稿不能拿来证明已发布历史权，新选题、fork和修订发布仍按D3重验。跨用户统计初版不实现授权入口，scope=all/他人owner请求403 unsupported_statistics_scope。

测试STAT-REV-01撤销后本人历史统计继续、STAT-REV-02新使用拒绝、STAT-REV-03不可枚举原题历史、STAT-REV-04他人数据不进入聚合。若用户不批准S11，需明确替代的本人统计入口及对R8的影响，不能在实现时默认为彻底禁止或无限开放。

## D7 统一错误码与验证顺序

S10为待评审的新接口技术契约，不声称已改变旧API。采用现有detail外壳，细化`detail:{code,message,operation_id?}`；Validation errors保留valid/errors。不得暴露原始凭据或不可见资源。API表中的简写错误统一按本表解释。 幂等request_hash包含HTTP方法、规范路径/资源ID和规范body，不包含Cookie/凭据；同key换资源也属于不同请求，返回409而不是复用另一资源结果。

| HTTP | code/条件 | 验收 |
|---|---|---|
| 401 | auth_required，未登录 | ERR-01 |
| 403 | cross_site_request；对已可见实体越权forbidden_action；显式跨owner统计unsupported_statistics_scope | ERR-01、STAT-REV-04 |
| 404 | resource_not_found，不存在或不可见；任意已撤销版本新选用不能泄露存在性 | ERR-02 |
| 409 | published_frozen、closed_readonly、rule_reference_conflict、concurrent_modification、requires_fork | ERR-03、FRZ-01 |
| 409 | idempotency_conflict、draft_changed、authorization_revoked（仅本人已知草稿/operation中可见授权依赖）、authorization_capacity | ERR-04、AUTH-01/05/06 |
| 409 | legacy_mapping_required、legacy_mapping_conflict、index_incomplete、source_changed、statistics_data_inconsistency | ERR-05、LEG/USG场景 |
| 422 | invalid_input/invalid_id/invalid_definition/invalid_cursor/invalid_bins，输入类型/范围/未知字段等 | ERR-03 |
| 503 | database_unavailable或operation_recovery_required；只有已持久化operation才附operation_id | ERR-06、AUTH-03 |

明确统一：合法输入造成既存Jump引用失效，在选入/换版/排序/删除等所有结构入口均409 rule_reference_conflict；独立题目定义本身非法为422 invalid_definition，不再把相同引用冲突在新选题写成422。

业务检查顺序建议：身份/同源检查→传输与ID基本类型→owner/可见性→published/closed写冻结→expected revision→字段规则及外部版本授权→候选结构与Jump引用→预留/提交。不可见实体先404，不先暴露它已发布或已撤销。框架级非法JSON可先422；不要求在无法解析请求时执行业务状态判断。503不能自动转换成已取消，202只表示已知operation尚未完成，不作为错误码。

旧API需要改变的状态/结构错误按R3显式记录；其余错误形态兼容，不能为了新catalog一次性改所有第一阶段响应。测试ERR-01至ERR-06对应test-plan，尚未执行。

## 切片1状态增补

U6–U9已批准，覆盖本文件开头“未获实施批准”的旧轮次状态，但仅授权题目族/不可变版本闭环。D1冻结、D2问卷固定绑定及旧PUT完整适配尚未实施。D3–D6有关分享、legacy、usage、统计的S/Q继续待审，不将其标记为已批准。切片1状态机、规范化、所有权、幂等和失败行为以[slice1/protocol.md](slice1/protocol.md)为实际落地契约；测试ID S1-01至S1-12，实测结果另列，计划本身不是通过证据。


## 切片3批准与落地增补（2026-10-26）

本节替代旧状态中D2“新ID/token未批准”的对应子项：用户已批准每次修订新survey ID/公开token、新draft独立生命周期、不变来源及不继承答卷/session/dedupe/操作历史。实际revision_of为来源survey ID，revision_source_schema_version另存来源快照版本（明确字段适配原嵌套草案）。D1题目/Jump冻结已在切片2落实；本轮页面也只在draft显示结构编辑表单，published/closed显示修订入口，元信息保留原语义，S2仍待决。

D4的本轮批准仅限用户明确修订：旧snapshot缺bindings时按owner/source survey/source schema/local ID建立确定转换，不改源snapshot/response，不跨位置/问卷/schema模糊合并。用现有stage2_operations的确定create key保证跨重试与不同修订意图不重复转换；revision_operations内计划保留来源tuple和摘要。全库映射/人工合并/分享来源复制依旧待审。D3/D5/D6不实施。技术恢复及验收ID S3-REV/LEG/UI/JS见slice3/protocol和test-plan，不把未来计划当已通过。
