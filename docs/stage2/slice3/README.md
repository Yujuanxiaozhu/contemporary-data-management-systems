# 切片3交付与独立复审入口（2026-10-26）

当前增量实现题库管理页面与独立修订draft，停止等待审查。没有开始切片4、分享、usage、跨问卷统计或全量业务迁移。完整回归有真实旧冲突，不能称全绿。

## 最终实际结果

| 运行 | 原始结果 | exit |
|---|---|---|
| new-final | 62 passed, 665 warnings in 20.55s | 0 |
| full-final | 36 failed, 649 passed, 4026 warnings in 163.35s | 1 |
| smoke-final | SLICE3_BANK_PAGES_REVISION_EDIT_PUBLISH_SOURCE_PROTECTED=PASS、REAL_UVICORN_SMOKE=PASS | 0 |

685=切片2最终623+新增62。旧623节点逐一保持587通过36失败，新增62全部通过（Mongo30/Mock30/纯JS契约2）。完整Mongo267=249通过18冲突；mock相同；纯逻辑151通过。36旧失败仍28发布冻结+8旧questions集合不存在断言，原失败语句和位置逐项核对，详见failure-classification.md/json和failures/。KeyError没有单独HTTP码时不补造；提前失败后的断言未执行，不冒称通过。全部原断言保留、无skip/xfail或条件跳过。Mongo已包含在完整运行，extract不是独立重跑。

首批48项→补充并发/恢复54项→损坏来源保护62项均通过；full-attempt1为641通过/36失败，后续增加8实例后最终649通过/36失败。早期日志都保留，没有删除失败。Warnings原文主要为mongomock utcnow、Starlette/httpx弃用。单次耗时不能视为性能评测。

## 用户批准、模型和API

用户本轮批准新修订ID/token、revision_of、独立draft/发布、不继承答案/会话/去重/操作日志；批准仅显式修订的保守来源转换。sharing/usage/跨问卷统计以及全库legacy映射仍不实施。实际revision_of为来源ObjectId，revision_source_schema_version另存权威snapshot版本，schema从1开始；不改变原公开URL、状态、结构、snapshot或response。

唯一新集合revision_operations持久化候选新ID/token、source snapshot摘要/版本、逐位置计划和结果；unique(owner,source,key)、result_survey_id unique。PREPARED→确定绑定→resolved耐久→仅insert新draft→COMMITTED。同key同body重用结果，新key新修订；未知写503原operation恢复。已有结果重放返回当前完整文档，不覆盖后续编辑；已删结果410，状态未确认的结果draft先恢复再删除。

legacy只对明确来源snapshot的(owner,source survey,schema,local ID)调用现有bank.create的确定子key，不按相似内容合并。不同位置/问卷分family，同一来源位置不同修订意图复用确定转换；来源不可靠409，不改旧snapshot或填补不存在历史。没有新并行版本分配协议、事务或Redis。

新增POST /api/surveys/{sid}/revisions，必填I-Key及source_schema_version/expected_schema_version；新增GET /revision-operations/{opid}与POST /resume，owner范围。本人published/closed来源可修订，draft/缺快照/坏结构拒绝。SurveyOut新增可空revision_of与来源schema，旧记录兼容null。Family只读摘要增加题名/题型/最高已提交版本/计数/更新时间，COMMITTED可见性及写协议不变。细节见protocol.md和根api-contract增补。

## 页面与实际修改

新/修改页面：/question-bank、/question-bank/{qid}，dashboard及survey edit的修订来源/入口，草稿picker/同族换版/required三态/明示新family。模板与原生JS复用既有API；服务端owner、Validation、固定版本、CAS、冻结仍为边界。published/closed不再显示结构编辑表单，元信息保留既有语义。目录只本人已提交题目；没有命名banks/items集合及跨用户共享。

JS失败保留输入和意图key，成功新意图换key，按钮防重复；保存成功后刷新失败提示重新加载并禁止再次提交。局部ID/order/Jump语义保留，删除位置不删历史版本；修改题库latest不追写草稿。精确源码/测试diff在source-and-tests.diff，所有28条源码/测试/根设计文档变更及理由在changed-files-and-reasons.json，完整差异changes.diff；before/保存旧原文。

真实HTTP页面证据：pages-smoke-final/，包括题库、历史、原问卷、修订、dashboard。真实Edge截图browser-screenshots/question-history.jpg，完成注册/登录、数字题v1创建及v2编辑。旧版恢复原生确认框CDP超时，后续picker/修订浏览器点击未完成，不称全浏览器E2E；相应API、真库和HTTP smoke另有通过证据。浏览器临时服务/库已清理，关闭测试标签页的工具调用也超时，如仍显示确认框可由用户关闭。详见browser-check和browser-cleanup。

## Git、文件保护与数据库隔离

前后stage2-question-bank，HEAD=0b845575fef4863e49be1e22b20d1882c5c78f66，stage1-final peeled=96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9，暂存区空。保护697个既有app/tests/docs文件，18个授权既有文件变化；原12份测试/fixture/smoke与HEAD/tag及旧hash一致，所有此前测试原文、第一阶段报告、旧baseline/slice1证据及旧slice2原始证据未改。slice1服务仅Family摘要读扩展，切片2draft_bindings和versions服务不改。精确结果见preservation与protected-before/after。

7份worker审计611个不同UUID库，加独立浏览器1个共612。worker有drop started及当次cleanup空集合，unexpected为空；browser单独drop返回与空集合。parent监听不等于子Uvicorn所有命令审计，空集合不等于当前库名不存在。环境MongoDB9.0.2 standalone/Python3.12.14，显式loopback和fixture/子进程env隔离。不接触业务库、不迁移、不输出.env、会话或真实凭据。

## 未执行、风险与停止

未执行真实强杀/网络未知确认、完整浏览器E2E、压力/大BSON容量测试、业务备份或迁移恢复。无后台revision恢复；操作与大候选文档仍有BSON16MB/长期记录容量约束。个人题库列表摘要按历史求值和前端搜索适用课程规模，无大数据性能承诺。无key延迟重放限制不变。

Q1-R本人修订身份子项及显式旧位置转换已批准；共享撤销、全库映射、命名题库成员策略、使用索引及统计权限仍待后续独立批准，不阻塞本切片。下一步只审查源码、完整非零回归/36分类、恢复协议和页面证据，不自动开始下一切片。未commit/push/水杉，未移动标签、reset/clean或切换分支。
