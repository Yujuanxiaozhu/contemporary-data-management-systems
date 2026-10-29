# 切片6：题目使用追踪 R6

## 权威来源和范围

usage按本人问卷的当前draft固定绑定与本人published/closed的不可变`survey_versions`快照生成，行携带全局question/version、survey、schema、local ID和位置；不以题名、内容相似性或跨问卷local ID识别题目。题库和bank_items不是usage来源。不同版本在结果中逐行明确标识，不自动合并；同一版本的不同位置和问卷分别保留。

历史legacy只使用U11中已COMMITTED的显式修订来源转换：逐位置核对源survey/schema/local、源快照摘要、确定子key、对应题目创建操作和版本。未建立可信映射返回`legacy_mapping_required`，不一致返回`legacy_mapping_conflict`；不改写旧快照和答卷，不自动创建或合并其他legacy关系。

## 派生索引和失败恢复

`usage_generations`按owner和scope记录BUILDING/READY/FAILED及来源集合摘要；`usage_manifests`逐来源记录source hash、预期行数及行摘要；`question_usages`以generation/source/local ID唯一；`usage_heads`按owner/scope CAS切换完整代次。重建先扫描权威来源、写新代次、校验每个来源，再重读来源并切换READY；失败或并发冲突不把半代作为查询结果，也不更改问卷和快照。旧代次保留；来源本身变化后旧代次虽然仍在，但查询必须拒绝陈旧结果。

`GET /api/questions/{qid}/usages`支持`scope=all|current|historical`、`version_id`、`cursor`、`limit`。查询枚举权威来源，逐项验证READY状态、manifest、实际索引行数与摘要，再按权限筛选并分页；缺索引、缺映射、来源变化或损坏返回409。分页cursor绑定代次和查询过滤条件。响应coverage标明来源数量、摘要、scope、历史来源盘点方式和非事务动态读取口径。查询期间再次核对来源、代次、head和授权；跨集合没有事务时点，验证到最终返回间的极短并发窗口不承诺事务快照。

重建是显式维护命令：`.venv\Scripts\python.exe -B scripts/rebuild_question_usages.py --uri <URI> --database <DB> --owner-id <OWNER_ID> --scope all --apply`。命令不会从应用默认配置选择数据库，也没有普通HTTP重建入口。业务库维护须另行授权；本轮仅对UUID测试库执行。

## 权限和撤销

题目owner及对指定版本有ACTIVE grant的接收者可以查询各自本人问卷中的usage，题目owner不能看到接收者问卷，接收者不能看到owner或其他用户问卷。共享撤销阻止新的绑定；已发布历史快照不删除。Q8/S11的撤销后本人历史窄入口尚未批准，因此不以历史绑定扩张读取权限，撤销后对该共享题的usage请求返回404；其他版本若仍获授权只可见其授权范围。

## 修改和测试

既有源码仅修改`app/routers/question_bank.py`；新增`app/services/usage.py`、`scripts/rebuild_question_usages.py`和`tests/test_slice6_usage.py`。七份设计、决策、迁移、测试及AI记录追加本轮说明；旧测试文件及断言未修改。

| 阶段 | 命令/证据 | 结果 |
|---|---|---|
| RED | `.venv\Scripts\python.exe -B docs/stage2/slice6/run_verification.py red` | 实现前18 failed，保留原日志 |
| targeted | `.venv\Scripts\python.exe -B docs/stage2/slice6/run_verification.py targeted-final4` | 退出0；36 passed, 391 warnings in 10.43s |
| related | `.venv\Scripts\python.exe -B docs/stage2/slice6/run_verification.py related-final3` | 退出1；2 failed, 309 passed, 3081 warnings in 79.29s (0:01:19) |
| Python | `static-final.json` | Python AST通过 |
| Uvicorn | `.venv\Scripts\python.exe -B docs/stage2/slice6/run_verification.py smoke-final` | 退出0；REAL_UVICORN_SMOKE=PASS，实际HTTP和显式CLI覆盖draft、publish、重建及bank独立性；服务已停止 |
| full | `.venv\Scripts\python.exe -B docs/stage2/slice6/run_verification.py full-final2` | 退出1；36 failed, 795 passed, 5679 warnings in 160.62s (0:02:40) |

related的2项失败均为基线中`test_historical_options_types_and_absent_question`的mock/mongo旧断言；275个相关旧节点逐项状态无变化，见`related-comparison.json`。完整回归对比原795节点：新增36项全部通过，原节点删除0、状态变化0，36项失败集合完全一致。历史分类仍是28项发布冻结旧断言冲突和8项固定绑定/旧存储模型断言冲突；不得把完整回归称作全绿。所有旧断言保留。

确定性测试覆盖半代/部分usage行写入中断、验证失败、验证前后来源变化、并发重建CAS、查询期间来源与代次变化、索引集合整体丢失重建、遗漏整份来源、分页前完整性、共享权限、revision及可信legacy转换。测试使用mock和UUID真实Mongo；不是强杀或压力测试。

## 隔离与保护

`database-isolation-summary.json`记录16次有审计的运行；所有测试库名为UUID隔离、unexpected为空且清理后集合为空。Uvicorn及CLI子进程的显式loopback启动参数、日志和清理单独记录，父进程Mongo监听不覆盖子进程所有命令。未访问默认业务库或执行业务迁移。

入轮1370个文件逐项哈希核对：授权源码/文档变化8项，意外变化0、缺失0。`source-and-tests.diff`经过正向/逆向及逐字节还原检查，不忽略空白、不强制覆盖；行尾告警见`diff-validation.json`。分支`stage2-question-bank`、HEAD `0b845575fef4863e49be1e22b20d1882c5c78f66`、`stage1-final^{commit}` `96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9`，暂存区为空。

## 限制

查询按当前可枚举的快照及答卷引用盘点历史；如果某历史快照及其全部引用都早已消失，现有数据没有外部历史目录，无法证明它曾存在，coverage不会声称能恢复不可观察的历史。旧代次尚无自动清理，扫描和逐来源核验面向课程规模。未进行真实进程强杀、断网或大规模压力测试。Q8、S7全库映射和跨问卷统计未在本轮批准或实现；交独立复审，不宣布第二阶段整体完成。
