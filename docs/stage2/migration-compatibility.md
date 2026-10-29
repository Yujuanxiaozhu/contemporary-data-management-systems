# 旧数据兼容与迁移草案

状态：仅设计，未对业务库执行dry-run或迁移。判据以[统一规则D4](design-rules.md)为准；S7/Q5仍待用户选择。D5规定派生索引完整性，不能仅凭usage存在行就宣称迁移完整。U4已确认旧survey_versions和responses不改写、不按猜测合并题目。以下集合、命令名称和检查点为待审建议，不是已运行工具。

## 原数据与兼容读取

现有答卷以survey_id+survey_schema_version找snapshot；snapshot内questions[].id用于答案和Jump。保持这条解释链，不把旧答案question_id换成全局ID，不将旧答卷绑定latest。

建议新快照增加显式格式版本与bindings；旧快照缺bindings时由legacy侧表补来源，校验/跳转仍只用原嵌入定义。旧快照和答卷字节及逻辑摘要保持原样。新读取层先识别格式，绝不默认“缺来源就是最新版”。新API输出字段显式兼容extra=forbid的旧schema。

现有ensure_current_snapshot可给缺快照的非draft补当前快照。本阶段不调用；将来迁移盘点须绕过这些有写副作用的业务GET，直接只读查询。只有已知当前完整定义可用于另行授权的修复，不能补造未保存的历史，也不能为让统计通过而用当前题替换损坏历史。

## 盘点与备份设计

在获准接触业务库后，先确认明确库名、备份位置和恢复责任；读取surveys、各snapshot、responses的数量、版本引用、题目/选项/规则、pending、关闭/删除状态及异常。备份须能验证恢复，不能把源码ZIP当数据库备份。

每条快照按稳定序列规范化内容生成hash；答卷另存摘要。盘点只输出数量、匿名化标识和错误类别，不输出文本答卷、账号凭据或会话记录。所有异常须保留清单，不能静默跳过。

## 保守映射

建议`legacy_question_bindings`主键为(survey_id,survey_schema_version,local_question_id)，字段：question_id、question_version_id、source_content_hash、mapping_rule_version、migration_run_id、status、created_at、review_reference?。唯一复合索引保护重复；所有来源可审计。

D4明确：题名、local ID或内容hash单独及组合均不自动证明题目身份；同survey跨schema也不能仅凭稳定ID关联，删除重用或缺历史均不合并。S7/Q5待确认方案为无可信来源的每个(survey,schema,local)独立建legacy family/version，或停needs_review；不再沿用原survey+local自动谱系建议。已有同键同摘要的审计映射可幂等重用；源摘要变化409 legacy_mapping_conflict；人工批准关联必须保留review_reference及有版本的审计关系，不覆盖原来源。验收LEG-01至LEG-04。

对无快照的draft只能记录“当前草稿”，不能伪称历史版本已存在。首次新系统发布旧草稿时建议显式创建独立题目版本并绑定；该转换是获准的新发布动作，需原子/恢复设计，不是本阶段后台迁移。已经发布的legacy问卷保持旧snapshot，通过侧表解释来源，不能为了固定引用反向改旧快照。

## 拟议命令职责

未来维护工具建议分为 `inventory`、`dry-run`、`apply --run-id`、`resume --run-id`、`verify --run-id`、`rebuild-usages --run-id`。这些名称仅表达职责，当前没有实现或执行。

- dry-run只读业务库，输出计划、冲突、预期数量、确定映射键与摘要，不创建业务集合/索引或幂等记录；“dry-run也写检查点”不得作为默认。
- apply必须指定库、备份、计划hash及允许范围，另获授权；先核验计划对应的数据未漂移。
- checkpoint含batch、确定的源键、目标ID、摘要、状态与错误；不依赖任意大skip分页，使用稳定键范围。
- deterministic key或唯一source key保证重跑返回同一实体。内容hash变化时停止冲突，不覆盖已有映射。
- 每条操作先确定family/version/mapping ID，记录可恢复操作，再创建版本、侧表绑定及usage；最后标记完成。不依赖事务。
- 部分成功不删已可被引用的版本。恢复重读确认内容后补缺项；同run或并发resume必须幂等。

## 失败点与恢复验收

| 中断点 | 预期可见状态 | 恢复要求 |
|---|---|---|
| 计划后源数据变化 | 计划不再有效 | 停止，重新盘点并审阅，不能覆盖 |
| family已建、version未插入 | family pending不可选用 | 按同operation ID补version |
| version已插入、映射未写 | 孤立候选有审计记录 | 核对摘要后补映射，不建第二版 |
| 映射已写、usage缺失 | 权威链完整，索引不完整 | 409 index_incomplete；按D5新generation核验count/hash/revision后切READY |
| 检查点写入结果不确定 | 操作可能已完成 | 按唯一键读取确认，不能盲重建 |
| 同源键存在不同摘要 | 冲突显式报告 | 不覆盖、不合并；人工处理 |
| snapshot缺失或答案损坏 | 历史不可解释 | 保持409/异常报告，不补造数据 |

在隔离旧样本库注入以上中断，重复执行与并发恢复后实体、映射和usage数量相同，所有原snapshot/response摘要不变。未演练成功前不建议业务apply。

## 回退边界

回退应先停止新写、恢复兼容读，保留新系统已经产生的合法答卷；不以删除新数据当回滚。新模型可旁路但来源记录不能破坏。旧应用能否直接读取新binding字段、是否会因extra=forbid失败，应在兼容适配中测试，不能假设回退旧二进制总能读新数据。

旧published结构更新pending不得由新版本GET或通用恢复自动完成；应在只读盘点中列为待决，另行批准采用保留原结构/独立修订等处理，不能套用D3的draft发布票据例外。draft历史pending也要核对操作来源和授权，不能补造D3票据。该legacy pending策略属Q5待决，验收LEG-04/FRZ-05。

旧快照不改写、侧表可重建，降低迁移风险，但不代表“无需迁移/无需备份”。公开旧问卷稳定、历史统计一致、新问卷固定版本和异常透明是最终验收标准。真实业务库状态、备份恢复和执行范围仍未核查，需另行授权。


## 切片3显式修订兼容（2026-10-26）

用户本轮已批准的范围是“明确请求一次修订”，不是此文全库迁移工具获准执行。缺bindings的正式snapshot只读验证后，按(owner,source survey,source schema,local ID)逐位置确定create子key；不同schema/来源位置绝不按题干、local ID或hash猜测合并。转换只产生新题目族/版本及新修订draft，不反写source survey/snapshot/response。可靠固定绑定直接复制指定版本、覆盖值和有效定义；损坏字段、无正式快照或无权版本明确拒绝。

来源tuple/摘要/子key及结果在revision_operations和现有stage2_operations有审计依据。相同来源位置不同修订意图重用确定转换，新的独立修订仍有不同survey ID/token。来源摘要变化409，版本写中断按原bank协议续写。没有新增legacy全库侧表，没有扫描迁移，没有按现有缓存补旧快照，也没有迁移答卷。隔离样本测试/失败恢复/源保护见test_revisions.py和slice3/原始记录，不冒充业务库dry-run/apply或备份演练。


## 切片6只读legacy解释（2026-10-29）

不执行全库迁移。历史旧位置仅在U11显式修订operation已COMMITTED，来源survey/schema/local、快照摘要、确定子key和对应版本创建操作均一致时使用其审计关系；没有该证明返回409 legacy_mapping_required，冲突返回409 legacy_mapping_conflict。旧快照与答卷不改写；内容hash仅作一致性校验，不用于建立身份。
