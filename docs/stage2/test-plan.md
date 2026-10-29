# 第二阶段测试计划

主体为前轮未来计划；上一轮基线实测见baseline；切片1新增测试及本轮真实执行结果见文末和slice1/日志。统一规则见[design-rules D1–D7](design-rules.md)，待确认方案对应的测试只能在选择获批后确定产品预期。不可把下面测试ID当作已经存在或已经通过。继续使用同套mock/真实MongoDB fixture，纯逻辑不按后端重复计数。

## 基线保护与R3调整

先复现原455项、真实smoke、编译、依赖及JS语法并保存证据；当前阶段不改原测试。实现阶段保留原认证/校验/路径/去重/删除/统计覆盖。`test_published_edit_closed_readonly`、`test_published_delete_question_bumps_version`、`test_concurrent_published_edit_snapshots`及smoke的published编辑步骤需要按R3明确替换为冻结和修订验收；历史原文不改写，不以删除覆盖掩盖差异。

`test_next_api_and_historical_submission`的旧数据解释核心保留，可用legacy预置历史或修订的独立问卷组织场景，而不是再次开放published写。`test_snapshot_failure_keeps_current_and_recovers`继续覆盖快照协议，同时新增题目版本和分享准入故障，不把旧协议通过视为新协议已通过。

## 需求测试矩阵

| 测试组 | 输入/动作 | 预期与必须检查的持久化状态 |
|---|---|---|
| R1-01/R1-02 | 创建四题型v1，加入A/B；非法规则创建 | 同version来源、不同local ID；Validation一致；非法无可见半成品 |
| R2-01/ACL-01/ACL-02 | A分享v1给B；C访问；B枚举family和接收者 | B仅v1可读/可用；C404；不泄露未授权历史和问卷 |
| R2-04 | B从授权v1派生并编辑 | B有自己的family/v1；来源正确；A原内容hash不变 |
| R2-05/P-01 | revoke与选题/发布准入并发；授权部分成功后中断 | S3/Q2待确认：逐share准入与撤销CAS排序，survey封存另有线性化点；原确定票据例外按D3，不称全局原子准入 |
| R3-01/R3-02 | 发布后改题/删题/排序/规则/绑定 | 409且survey定义、快照、公开GET及旧答案解释不变 |
| R3-03/R3-04 | 创建修订草稿，换版本并发布；改型破坏规则 | S1/Q1-R待确认：新survey/token且原数据不变；草稿规则冲突统一409 rule_reference_conflict |
| R4-01/R4-02 | v1→v2→v3；从v1恢复两次同key | v4新实体、parent/restored_from正确；重试不产生v5；旧版hash不变 |
| R5-01/V-01 | A/v1 B/v2；并发创建版本，插入后切指针失败 | 各自内容独立；序号唯一、候选不可见；恢复不rebase |
| R6-01/R6-02 | 当前/历史/重复位置；删派生usage后重建 | 来源完整、范围正确；index_incomplete不伪装零；重建幂等 |
| R7-01至05 | 建库、加共享题、换默认、删成员/归档库 | 默认只影响后续选择；历史绑定仍有效；本人库隔离 |
| R8-01 | v1 A=20/30 B=40；v2 C=100 | v1 answered=3 avg=30；v2 answered=1 avg=100；不得合成47.5 |
| R8-02 | B属于另一owner；题目已共享给当前人 | 只统计本人问卷，不泄露B标题/答卷/人数；scope明确 |
| R8-03 | 0、null、跳过必答、未答、重复局部位置、各型 | 0有效，缺失不计，多选分母明确，位置单列，非自然人数 |
| R8-04 | bins端点值、单位/选项含义变化、无回答 | 频数和边界正确；不兼容版本不合计；空平均null |
| C-01至06 | 未登录、跨站、非法ID/未知字段、第三方、旧revision、DB故障 | 401/403/422/404/409/503稳定且不泄露凭据 |
| I-01/I-02/F-01/F-02 | 幂等重放、同key异body、查操作状态、并发resume | 同结果ID、冲突409；GET无恢复写副作用；无重复实体 |

每个api-contract端点均必须覆盖对应专用测试和通用权限/输入/故障测试，不能只测页面按钮。分页、archived状态、无变化编辑与显式restore的差异另作边界断言。

## 统一规则验收场景

以下全部是未来验收设计，未运行。U标识测试验证已确认不变量；S/Q场景仅在用户选择该方案后成为产品预期，不通过列测试的方式反向批准建议。技术实现仍需代码审查及真实故障验证。

| 测试ID | 规则/批准状态 | 输入及动作 | 预期断言 |
|---|---|---|---|
| FRZ-01 | D1/U1 | 发布后逐一增删改题型、题干、required、选项、validation、order、局部ID、Jump各字段 | 409 published_frozen；结构/snapshot摘要不变 |
| FRZ-02 | D1/S2/Q1-M | 尝试改title/description | 若批准只读则409；如批准特例按特例验收。未确认不编写暗含可变/只读默认的实现 |
| FRZ-03 | D1/U1 | 更新binding/version指针、题库latest、恢复版本、归档或撤销共享 | 已发布固定绑定及结构解释不变 |
| FRZ-04 | D1/S2/Q1-M | 调整deadline、匿名/重复策略；截止和关闭边界 | 先决定字段是否可变；获批例外不得绕过原服务端准入/唯一去重 |
| FRZ-05 | D1/C1、Q5 | close、内部准入及draft发布pending恢复；预置旧published改题pending | close保留；合法恢复不替换冻结结构；旧published pending只列异常不自动执行 |
| FIX-01 | D2/U1/U2 | 同version入A/B，latest指向v2，A/B有各自局部ID | 仍按v1定义解释；Jump/answers用local ID；不同版本统计不混 |
| FIX-02 | D2/U5/S4 | 恢复同内容旧版；尝试required局部覆盖 | restore必新增并记录来源；required覆盖预期取决于Q4，不暗批 |
| REV-01 | D2/S1/Q1-R | 从指定snapshot创建修订草稿并发布 | 若获批：新survey/token/schema1，revision_of正确；不继承旧答卷/准入/去重，原URL结构不变 |
| REV-02 | D2/S1/S3 | 共享撤销后复制本人旧published为修订draft | 若获批：标needs_authorization，复制不继承票据，未重授/替换不得新发布 |
| AUTH-01 | D3/S3/Q2 | 普通draft；撤销在该share准入CAS之前；请求任意被撤销版本 | 已知操作依赖409 authorization_revoked；任意不可见version404；不写snapshot |
| AUTH-02 | D3/S3/Q2 | 两share分别准入；第一张已取后撤销；第二张取前撤销 | 原已取票只限原payload；第二张拒绝则无SEALED；若其余票均合法可完成，不假称全局原子授权 |
| AUTH-03 | D3/S3/Q2 | share已登记未复制receipt、封存后、快照插入后、指针后分别崩溃 | 恢复原票/原operation，撤销不删在途证据；最多一个snapshot/result；不自动取消 |
| AUTH-04 | D3/S3/Q2 | revoke→regrant新epoch；重放旧key和尝试修改payload | 新授权须新operation/key；旧receipt不能迁移或扩权；同key异请求409 |
| AUTH-05 | D3/S3技术参数 | 达到bounded_admissions上限，恢复后回收；并发撤销 | 409 authorization_capacity且无无界数组；只有receipt耐久可删副本，撤销不清待恢复票 |
| AUTH-06 | D3/S3/Q2 | 收票期间draft被改；两个operation同时封存；网络结果不确定 | CAS单胜；未封存且draft已变可ABORTED，SEALED只能恢复；503不盲取消 |
| LEG-01 | D4/U4/S7 | 同源键同摘要重复dry-run/apply/resume（隔离库） | 重用同映射目标，原snapshot/response摘要不变，无重复实体 |
| LEG-02 | D4/U4/S7/Q5 | 同名/同hash/同local跨问卷；同问卷删除重用或缺schema | 不自动合并；获批逐位置方案则独立family，否则needs_review |
| LEG-03 | D4/U4 | 同映射键源摘要变化、缺snapshot、损坏答案 | conflict/历史409；不覆盖映射、不补造当前题解释旧答卷 |
| LEG-04 | D4/S7/Q5 | 人工批准关联；业务旧published pending；迁移中断 | 只新增审计关系及review_reference；pending不自动改结构；恢复按原键补缺项 |
| USG-01 | D5/S9/Q9 | 一整份usage/manifest缺失；少行/多行/错误hash | 权威source_set能发现，409 index_incomplete，不返回零使用 |
| USG-02 | D5/S9/Q9 | BUILDING写半代崩溃，resume两次，并发重建 | 不暴露半代；新代count/hash验证后切READY；幂等且旧代清理不伤来源 |
| USG-03 | D5/S9/Q9 | 源变更发生在重建验证/READY切换或请求核验期间 | revision/hash比较识别陈旧；index_incomplete/source_changed，不误报完整 |
| USG-04 | D5/S9/Q9 | current/historical、零绑定、分页、并发新增问卷 | 完整性在分页前；零使用须整个观察source_set完整；coverage明确非事务时点 |
| USG-05 | D5/U3/S9 | usage混入其他owner行、legacy映射缺失 | owner过滤后核对权威行；不泄露他人；所需映射缺失409 legacy_mapping_required |
| STAT-REV-01 | D6/S11/Q8 | 撤销后查询本人published/closed v1跨问卷统计 | 若获批：由本人合法历史binding证明，仍正确汇总，不要求ACTIVE grant |
| STAT-REV-02 | D6/U2/S3/S11 | 撤销后新选入/fork/发布；只有draft无历史 | 不拿本人历史统计证明新使用权；任意不可见资源404，已知操作按409 |
| STAT-REV-03 | D6/U2/S11 | 有本人v1历史但GET原family/其他version/接收者列表 | 历史统计窄入口不开放目录；只返回本人可解释版本和答案 |
| STAT-REV-04 | D6/U3 | 分享题A问卷属他人；请求scope=all | 他人数据不进入聚合；显式越界403 unsupported_statistics_scope |
| ERR-01 | D7/S10 | 未登录/跨站写/对已可见资源执行无权动作 | 分别401/403，细化code稳定，不泄露凭据 |
| ERR-02 | D7/S10 | 未知/他人/任意已撤销版本ID | 404 resource_not_found；不先返回其发布/撤销状态 |
| ERR-03 | D7/S10 | 定义非法vs合法定义破坏既存Jump；published结构写 | 定义422；所有入口引用冲突409 rule_reference_conflict；冻结409 |
| ERR-04 | D7/S8/S10 | revision旧值、同key不同路径资源或payload、draft改变 | 409并发/幂等/draft_changed；同key同规范请求返回同result |
| ERR-05 | D7/S9/S10 | 缺映射、冲突映射、半代usage、源变更、历史损坏 | 相应409 code一一对应，不返回正常部分统计 |
| ERR-06 | D7/S10 | DB写结果不确定；operation尚未持久化或已持久化 | 503，只有真实持久化ID才回operation_id；GET状态不执行恢复写 |

### 原需求测试ID的对应关系

R2-02对应ACL-01/C-04的原题写入拒绝；R2-03对应R8-02和STAT-REV-04的不泄露答卷；R6-03对应USG-05的owner过滤。R7-01至05表示建库/成员/选题/换默认/移除的五个验收点；具体输入和错误仍逐端点依api-contract验证。FRZ等新增ID只是细化验收，不替代原R1–R8需求追踪。

## 历史兼容与迁移样本

构造：空draft、published/closed、同local ID跨survey、同survey跨schema变型/改选项、题目删除后重用ID（不能自动归family）、缺snapshot、损坏答案、pending和重复映射。快照/答卷前后规范摘要一致；审计映射幂等及冲突按D4，旧published pending不得自动恢复改结构。dry-run零业务写；apply/resume仅隔离样本；中断点见migration文档。不能用当前业务库演练。

## 真实MongoDB与故障

验证BSON/ObjectId/UTC、unique/sparse索引、CAS、并发版本和grant准入、mapping/usage补建、幂等键。测试库使用随机survey_test_*且只清理自建库。失败保存traceback、操作状态和checkpoint；不清理用户数据、不修改断言隐藏失败。预期故障ERROR/WARNING标注为注入证据。

## Smoke与真实页面

未来新增stage2 smoke：A注册→建v1/题库→分享B→A/B固定版发布→提交→A建v2→新问卷采用→原问卷不变→恢复→查使用→本人跨问卷统计→撤销→新选用拒绝→关闭。核对DB内容、来源、数值和错误码，不只HTTP200。

浏览器实际点击登录、建题、入库、共享、选版本、修订、历史恢复、usage和统计；记录浏览器/步骤/结果。继续Jinja2转义、tojson及textContent防注入。不把TestClient/HTTP等同真实浏览器E2E；本阶段未执行点击。

## 验收闸门

1. R1–R8逐项有真实证据和未解决项；设计覆盖不算实现完成。
2. 旧行为要么保持，要么有需求依据和替代流程；不移动stage1-final。
3. 完整pytest包含真实后端时不为凑数量再跑相同integration；需报告实际后端实例数。
4. 真库、smoke、手算、隔离迁移恢复、页面均明确执行状态；无未解释失败。
5. 报告/API/模型/AI日志一致；未压测/未分页等限制如实说明。仅为文档改动不重复重跑业务套件。

## 切片1实际测试范围与计划ID

本轮授权实现并验证独立版本，不调整旧published可编辑的原测试；其R3替代在后续切片执行。S1-01初始/四题型/required，S1-02连续版本/排序分页，S1-03规范化摘要/非法定义，S1-04恢复/旧内容ID摘要不变，S1-05登录/同源/owner404，S1-06幂等重放及冲突，S1-07并发不同key及同key，S1-08各持久化断点恢复，S1-09latest损坏核验修复，S1-10索引与约束，S1-11旧回归和真实Mongo standalone，S1-12真实Uvicorn扩展smoke。具体测试函数见新tests/test_question_bank.py及tests/test_question_bank_logic.py；计划与真实执行结果分开，结果只以slice1日志为准。新并发测试同时在mock和真实Mongo上执行；mock结果不证明standalone并发。

### 切片1最终实测（2026-10-24）

`slice1/full-final.txt`：516 passed、2552 warnings、58.28s，退出0；185真实Mongo+185mock+146纯逻辑。原455项保持，新增25真实+25mock+11纯逻辑=61。R1/R4/R5基础API部分验收完成，其他需求未完成。

| 验收ID | 实际测试名/证据 | 当前结果 |
|---|---|---|
| S1-01 | test_initial_family_and_default_required，4题型×2后端 | 8通过 |
| S1-02/S1-04 | test_versions_history_detail_restore_immutable | 2通过；顺序/分页/详情/恢复/旧ID内容hash不变 |
| S1-03 | test_question_bank_logic.py全11项，test_invalid_api_and_pagination | 11纯逻辑+2API通过 |
| S1-05 | test_owner_auth_same_origin_and_no_leaks | 2通过；401/403/404 |
| S1-06 | test_idempotency_body_resource_conflicts_and_same_content | 2通过；重复/冲突/跨资源key/同内容新key |
| S1-07 | test_concurrent_creation_unique_versions | 4通过；6线程不同key仅一胜，相同key同结果，后续版本唯一 |
| S1-08 | test_interruption_resume_exactly_once | 24通过；3操作×4断点×2后端 |
| S1-08 | test_concurrent_resume_after_inserted_interruption，test_pending_blocks_pointer_repair_and_stale_resume | 4通过；6线程恢复/阻塞与过时失败 |
| S1-09/S1-10 | test_pointer_repair_and_indexes | 2通过；损坏缓存核验修复、唯一约束 |
| S1-11 | full-final.txt全部516项 | 退出0；真实standalone185项，不重复跑相同integration子集凑数 |
| S1-12 | smoke.txt及uvicorn-server.log | 新版本与原统计smoke PASS，退出0 |

其余FRZ/REV/AUTH/LEG/USG/STAT等仍为后续计划。没有执行页面交互、迁移/恢复演练或跨用户授权新模块验收。原失败与环境阻塞见slice1/README.md；不能将最终成功覆盖首轮失败。

## 切片2实际验收与冲突口径（2026-10-25）

用户正式批准：原始测试文件/断言只读保留，完整pytest包含冲突实例；不skip/xfail、不降低断言。与新冻结及绑定模型相反的旧断言逐项记录真实失败，其他既有测试必须通过。此批准取代前文“按R3替换原断言”的未来建议，前文保留为历史设计，不据此修改原测试。

新增tests/test_draft_bindings.py与smoke_draft_bindings.py；全部使用原mock/真实Mongo夹具，不更改conftest。S2-01两个draft固定同版、历史指定版、单draft新版不外溢、删位置留版本；S2-02 required继承/true/false、同版不同覆盖、发布冻结、默认改版不回写；S2-03已发布/关闭所有题目/规则/绑定入口及直接服务保护；S2-04旧PUT可选key/new_family/required_override、局部ID/Jump/顺序/幂等及非法引用；S2-05 reserved/version_ready/resolved/survey_committed中断及显式resume；S2-06切片1子操作中断/四线程恢复/家族CAS冲突释放；S2-07发布绑定校验及legacy draft只在明确写操作适配、旧published pending隔离；S2-08合法分开草稿发布和旧快照解释的统计/答卷不变。

真实Uvicorn只启动survey_test_smoke_UUID，验证固定绑定、required快照、409冻结、两个合法问卷独立统计和旧快照/答卷不变。父进程命令审计与子进程启动env验证分开，不声称监听子Uvicorn每条Mongo命令。所有新测试结果、完整回归非零码和每项冲突分析在slice2/，不以本计划代替通过证据。

不重复第一阶段基线，完整回归已包含真实Mongo integration不另跑相同子集凑数。没有页面E2E、真实进程强杀/未知写确认、业务迁移/压测；原冲突用例提前失败的后续断言未执行，新增核心覆盖不是声称旧函数全部断言已通过。


## 切片2最小复审修正验收（2026-10-25）

新增独立tests/test_slice2_review_fix.py，不改第一阶段及切片1/2原有测试断言：

| ID | 实际新增场景 | 参数实例 |
|---|---|---|
| FIX2-A | A提交→B推进schema→恢复A，draft/published、COMMITTED/落后PREPARED收据，GET区分当前/结果版本，重复恢复409且全部存储不变；同schema发布恢复返回完整当前文档 | 10（mock5+mongo5） |
| FIX2-B | 数字min=1→1.0，显式/无key×required继承/true/false，生成新ID/hash，重试不重复版本，发布快照精确浮点；tamper定义/有效hash/内容hash拒绝；normalize/planner/发布纯逻辑 | 21（mock9+mongo9+纯逻辑3） |
| FIX2-C | 不先修改published结构，直接提交NaN/Infinity/-Infinity答案，422安全错误且survey/snapshot/answer/version/operation均不变 | 6（mock3+mongo3） |

合计37实例。适用smoke新增smoke_slice2_review_fix.py，在原适用HTTP扩展后验证数值新版本、发布后过期resume409、三类非有限答案422和持久化不变。完整pytest仍包含原36项冲突，不skip/xfail；真实执行结果、失败尝试、隔离与保护另存slice2/review-fix-20261025，不把本表当通过证据。


## 切片2最终状态投影验收（2026-10-25）

新增独立tests/test_binding_operation_projection.py，原始及此前新增测试不修改。PROJ-01：正常COMMITTED和收据已提交/状态仍PREPARED，×当前/过期，×draft/published；共16个Mock/真实Mongo实例，逐次状态查询核对state=COMMITTED、结果版本和superseded且七个集合均不变；过期resume重复409、记录不变；同schema已发布正常恢复仍200。published场景创建正式答案和快照，使保护断言覆盖实际历史数据。PROJ-02：reserved中断、尚无收据的PREPARED，2个后端实例；结果版本null、superseded=false，查询不帮助恢复。

新smoke_binding_operation_projection.py沿用此前适用smoke后，在唯一隔离库模拟PREPARED标记滞后，真实HTTP核验只读COMMITTED投影、历史数据不变、过期resume409。完整回归仍运行所有原测试和已知冲突，不skip/xfail；真实结果在slice2/state-projection-20261025，计划本身不是通过记录。


## 切片3验收映射（2026-10-26）

详见slice3/test-plan.md及实际test_revisions.py、test_question_bank_pages.py、test_slice3_javascript.py。S3-REV：新ID/token/来源/schema1、快照权威、子draft独立编辑发布、状态冻结、幂等/不同意图、插入后编辑不覆盖、删除不复活、owner/输入/缺快照拒绝；S3-LEG：逐来源位置转换，不同位置相似内容不合并，同源跨意图复用，并发/子版本及父操作中断恢复、损坏快照明确409；S3-UI：四题型/版本摘要/历史恢复/required和固定历史版、owner及pending可见性、模板只读结构；S3-JS：失败保留幂等key，成功新意图换key，原生JS语法。

真实Uvicorn smoke沿用原隔离库生命周期，新增修订创建→幂等→编辑→发布→冻结→源/快照/答案不变，并保存真实页面HTTP输出。浏览器本轮实际完成注册/登录/题目族创建/改版；恢复旧版原生确认框的控制通道超时，后续页面点击未完成，不能称完整浏览器E2E通过。截图和部分验收边界另列。所有原始测试断言保留，无skip/xfail；完整回归对照切片2最终623节点，报告所有新/旧失败与退出码。


## 切片4验证（2026-10-29）

新增`tests/test_slice4_sharing.py`及`tests/slice4_dom_contract.js`覆盖owner/grantee/unrelated/anonymous、版本范围、历史信息、绑定、撤销、重授权、快照、派生和在途恢复；复跑题库、绑定、修订相关回归、JS/模板、真实Uvicorn冒烟及完整pytest。实际结果、历史节点逐项比较、UUID数据库审计与清理记录见[slice4/README.md](slice4/README.md)。不改写或跳过历史36项断言。


## 切片5验证（2026-10-29）

新增`tests/test_slice5_banks.py`及`tests/slice5_dom_contract.js`，覆盖题库私有权限、幂等、CAS、固定默认版本与草稿/快照、共享撤销、移除、选择器提交版本。mock和UUID Mongo运行专项、相关回归及完整pytest；实际命令、节点比较、隔离清理与Uvicorn结果见[slice5/README.md](slice5/README.md)。

切片5另以`tests/slice5_organizer_contract.js`核对授权失效成员切换到其他可用版本时的页面操作。

题库picker还验证默认选中推荐版本，并可显式选本人或已授权共享的同族其他版本，不请求未授权的族历史。


## 切片6验证（2026-10-29）

`tests/test_slice6_usage.py`覆盖当前/历史、revision、版本与位置、权限撤销、bank独立、索引缺失/损坏、分页、并发重建、故障注入、来源变化和U11旧位置映射；mock与UUID Mongo执行。真实Uvicorn及维护命令、逐节点基线和清理记录见[slice6/README.md](slice6/README.md)。


## 切片7验证（2026-10-29）

`tests/test_slice7_statistics.py`覆盖各题型、按版本分组、不同问卷同local ID、同问卷重复位置、跳题和空值、历史schema、共享隔离、索引损坏及legacy缺失；mock和UUID Mongo执行。最小页面交互由`tests/slice7_stats_dom.js`验证。最终验证与逐节点对照见[slice7/README.md](slice7/README.md)。
