# 第二阶段切片1交付与审查入口

最新增补（2026-10-25）：未提交题目族可见性与操作结果表述已作最小修正。本文件下方原516项/554临时库等数字保留为前轮历史，当前结果独立记录于[visibility-fix-20261025/README.md](visibility-fix-20261025/README.md)，不得混作同一次执行。

2026-10-24。完成题目族、不可变版本、历史、恢复、owner隔离、幂等与持久化恢复API；本切片停止，不进入问卷绑定或分享。U6–U9见decision-log。

## Git与文件范围
分支始终stage2-question-bank；HEAD仍0b845575fef4863e49be1e22b20d1882c5c78f66，阶段二起点未变；stage1-final peeled仍96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9。没有commit、add、push、切换分支、重置或水杉上传；暂存区为空。

既有源码只改app/main.py注册路由、app/core/database.py增加懒索引函数。新增app/schemas/question_bank.py、app/services/question_bank.py、app/routers/question_bank.py；新增tests/test_question_bank.py、test_question_bank_logic.py、smoke_question_bank.py。没有改任何原测试、原业务服务、配置或第一阶段报告/历史日志。现有七份stage2文档按本切片更新：decision-log、design-rules、architecture-and-data-model、api-contract、requirements-matrix、test-plan、ai-log。

全部226个既有文件在开始前hash保护，原文档7份在before-designs留副本；baseline全部74个文件（31份证据+43 ignored pyc）原字节不变。逐文件变更见preservation.json、新文件见new-files.json、源码diff见source.diff、文档逐文件diff见design-diffs/。这些是当前未提交工作区成果。

## 模型、API和恢复
[protocol.md](protocol.md)是实际契约：question_id/family与question_version_id分离；definition.required为默认；SHA-256采用显式规范JSON；版本只插入。唯一索引约束family+序号和operation_id；owner/action/key唯一。首次独立题目写入前才初始化新索引，不改变纯旧流程的集合布局。

PREPARED操作持久化确定ID/payload→单family CAS预留并增序号→不可变插入→COMMITTED可见→CAS切latest并清pending。无事务；错误后重放/显式resume确定操作，不rebase。候选不可读；latest为可核验缓存，owner+revision+无pending时显式修复。无后台自动恢复。

实现POST questions、versions、restore，GET本人family列表/详情/历史/版本详情，GET operations和POST resume，POST repair-latest。Cookie与同源沿用旧401/403，不可见资源404；新一致性409、非法定义422、可恢复Mongo故障503附耐久operation_id。同key同请求同实体、不同请求409；不同key相同内容明确生成新版本。

## 实际验证与失败记录
| 运行 | 实测 | 退出码 |
|---|---|---|
| 首轮全套 | 8 failed、506 passed、2544 warnings、63.94s | 1 |
| 懒索引调整后 | 514 passed、2552 warnings、57.84s | 0 |
| 最终（补并发恢复/未登录写检查） | 516 passed、2552 warnings、58.28s | 0 |
| 真实Uvicorn原统计+新增版本扩展 | 两个smoke PASS | 0 |
| compileall、pip check、三份JS语法 | 均通过 | 各0 |

最终185真实Mongo+185mock+146纯逻辑；原455全部保留通过，新增61=25真实+25mock+11纯逻辑。真实MongoDB9.0.2 standalone，并发创建/重放与六线程故障恢复真实运行。完整全套已含integration，不为凑数重复运行相同子集。2552 warnings比历史2262多290，来自新增mock操作的datetime.utcnow弃用；另有沿用的Starlette/httpx弃用提示，未隐藏。历史85.55s与本次58.28s来自不同运行，不作性能结论。

首轮8失败来自旧测试要求纯旧流程无独立questions集合：改为懒初始化保留旧断言，未删除/改写失败测试。沙箱两次socketpair挂起、中断及独立11项纯逻辑运行在sandbox-attempts.md；没有把中断当作通过。原始完整pytest为full-attempt1.txt、full-attempt2.txt、full-final.txt，smoke为smoke.txt和uvicorn-server.log；环境、命令和退出码在environment.json、commands.md、results.json。测试ID与具体函数/结果在test-plan及test-results.json。

三轮pytest各使用184/184/185个独立真库，smoke1个，合计554个不同临时库，全部清理核验无剩余集合；每轮命名空间unexpected为空。pytest夹具自动清理，包括失败运行；保留故障原始日志而非保留测试数据库。未对默认业务库创建集合/索引、问卷、快照或答卷作任何操作；子Uvicorn强制env隔离，父进程审计边界已声明。

汇总脚本并行写results曾覆盖6条元数据，按工具真实命令/退出码恢复，耗时未知null；stdout及审计一直保留，见commands.md和AI日志。不把恢复元数据冒称原子生成。

## R1–R8与未完成项
R1完成独立保存基础，尚无选题绑定/管理页面；R4完成本人历史/来源/恢复API，尚无历史页面；R5完成不可变多版本及并发恢复基础，尚无问卷固定版本。R2分享、R3冻结/修订完整改造、R6usage、R7题库成员、R8跨问卷统计均未实现。旧published编辑行为此切片仍保留，不能称已完成教师R3。

版本默认required已实现；问卷位置覆盖、旧PUT兼容创建版本+绑定在下一切片。无legacy业务迁移/迁移演练、页面交互验收、压力测试、后台恢复或完整分享协议验证。S1修订ID/token、S2元信息冻结、S3撤销在途票据、S7legacy拆分/人工确认、S9usage完整性和S11撤销后本人统计等仍待审；不自动升级为批准。

## 下一切片建议（等待审查确认）
先评审本切片source.diff/新文件、protocol及原始验证证据，再确认问卷绑定数据布局、required_override有效定义摘要、旧PUT无新增header的内部操作标识方案和修订ID/token策略。批准后增量实施draft固定版本绑定及兼容适配；发布冻结/修订需相应R3替代验收，保护旧快照/答卷。分享、usage、统计仍单独切片。当前停止，不自动执行。

## 2026-10-25最小修正范围

只调整公开family读取的已提交可见性、operation_out待完成/已提交结果区分，新增三阶段×两后端回归，不进入新功能。具体规则见protocol增补，新增局部test-plan.md，当前源码/测试与历史相比的精确差异见visibility-fix-20261025/changes.diff。此前切片1证据、失败日志与审查ZIP均不重签或覆盖。
