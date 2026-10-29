# 切片7：本人跨问卷单题统计 R8

## 实现语义

`GET /api/questions/{qid}/stats`按可选`version_id`返回当前用户本人有权查看的问卷统计；默认按不可变`question_version_id`分别成组。其他scope返回403。题目所有者不能据分享权看到接收者问卷或答案，接收者也不能看到他人问卷；未获授权用户返回404。Slice 6的授权规则保持不变，Q8撤销后的本人历史窄入口仍未批准。

统计只使用通过Slice 6 READY generation和逐来源完整性检查的usage，以survey ID、response的survey_schema_version、历史snapshot和local question ID/位置定位答案，不按题名、跨问卷local ID或内容相似性匹配。每个snapshot的答卷使用既有路径、题目定义和答案验证；缺snapshot、legacy映射或不完整索引不返回伪完整结果。处理前后复核usage、版本、快照和答卷集合；这仍是动态非事务视图，不能承诺跨集合事务快照。

每个版本返回`answered_count`及逐位置计数。单选返回选项频数与占有效回答次数的百分比；多选分别返回有效回答次数和total_selections；数字返回count/min/max/average，空集后三项为null；文本返回本人问卷允许查看的有效文本。跳题、缺失和空答案不计有效回答。统计单位始终是**有效回答次数**，不推断独立自然人数。题目详情及共享版本列表提供最小查看入口，不添加图表或跨owner授权。

## 文件范围

既有源码：`app/routers/question_bank.py`增加API，`app/static/question-bank.js`与`app/templates/question_bank.html`增加最小展示。新增`app/services/cross_question_statistics.py`、`tests/test_slice7_statistics.py`、`tests/slice7_stats_dom.js`。六份stage2需求、API、模型、决策、测试和AI日志追加说明；原测试文件及断言均保留。

## 验证

| 阶段 | 命令 | 结果 |
|---|---|---|
| targeted | `.venv\Scripts\python.exe -B docs/stage2/slice7/run_verification.py targeted-final3` | 退出0；15 passed, 254 warnings in 6.66s |
| related | `.venv\Scripts\python.exe -B docs/stage2/slice7/run_verification.py related-final` | 退出1；2 failed, 75 passed, 699 warnings in 17.63s |
| full | `.venv\Scripts\python.exe -B docs/stage2/slice7/run_verification.py full-final` | 退出1；36 failed, 810 passed, 5932 warnings in 182.93s (0:03:02) |

本轮只执行一次完整回归。related的两项失败均是原统计历史断言的mock/mongo节点，62个相关旧节点状态无变化。完整逐节点对照：原831节点删除0、状态变化0；新增15节点全部通过；36项失败集合完全相同，无新增失败。旧失败仍为28项发布冻结与8项旧绑定/存储模型断言冲突，没有修改、删除、skip或xfail。

新测试覆盖v1/v2分组、数字手算及空集、单选比例、多选总选择数、文本权限、跳题/空答案、同survey重复位置、不同survey相同local ID、按旧schema解释历史答卷、分享隔离、索引/快照缺失及legacy缺失。页面DOM使用Node测试替身，不冒称真实浏览器E2E。

## 隔离、差异与保护

UUID隔离MongoDB、loopback连接：`database-isolation-summary.json`包含6次测试运行审计，unexpected为空、清理后无剩余集合；未访问默认业务库。依用户要求仅运行专项、相关和一次完整回归，未另行运行Uvicorn冒烟、浏览器E2E、压力、强杀或断网验证。

入轮1490个文件哈希检查：9个授权源码/文档变化，意外变化0、缺失0。差异经正向、逆向和逐字节还原检查；Git行尾告警见`diff-validation.json`，未忽略空白或强制覆盖。分支`stage2-question-bank`，HEAD `0b845575fef4863e49be1e22b20d1882c5c78f66`，`stage1-final^{commit}` `96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9`，暂存区为空。未提交、推送或开始其他切片。

## 已知限制

统计需要本人`scope=all`的完整READY usage代次，索引陈旧须使用Slice 6既有维护命令重建。旧快照及其全部引用若早已消失，现有数据没有外部历史目录，无法证明其曾存在，沿用Slice 6已记录的coverage边界。聚合及逐位置明细面向课程规模，未做大规模性能验证。完整回归仍有36项已知历史失败，切片7交独立复审，不自行宣布整个第二阶段完成。
