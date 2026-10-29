# 测试与验证

## 最终功能回归

最后一次完整 pytest 在 Slice 7 最终功能代码上运行，使用 mock 和本机真实 MongoDB 的 UUID 临时库：

```text
846 collected
810 passed, 36 failed, 5932 warnings in 182.93s
exit code 1
```

原 831 个节点逐项状态不变，新增 15 个节点全部通过，没有新增失败。36 项失败集合与进入 Slice 7 前相同：28 项要求继续修改已发布结构，与第二阶段冻结要求冲突；8 项依赖旧题目存储/固定绑定断言。原断言仍运行，没有删除、修改、skip 或 xfail。不能将这次完整回归描述为全绿；分类和每个节点比较见 [Slice 7 记录](stage2/slice7/README.md)、[失败集合](stage2/slice7/failure-comparison.json) 和 [逐节点比较](stage2/slice7/node-comparison.json)。

Slice 7 专项为 15 passed，相关统计回归为 75 passed / 2 failed；两个失败均属于上述既有集合。最终集成只改文档与隔离验证脚本，未修改正式运行代码，因此没有重复完整 pytest。

## 代表性测试用例

| 输入/步骤 | 预期与实际 |
|---|---|
| 本人两个问卷使用同一题目 v1，答案为 20、30、40；另一问卷用 v2 答 100 | v1 有效回答 3、平均 30；v2 单独为 100；Slice 7 专项通过。 |
| 单选答案 a、a、b；多选为 [a,b]、[a] 和空 | 单选 2/1、比例 66.67%/33.33%；多选有效回答 2、总选择 3；专项通过。 |
| 同一版本同问卷不同位置，或不同问卷恰好有相同 local ID | 分位置计数，不把局部 ID 当全局身份；专项通过。 |
| 删除 usage 行或 manifest、来源变化、legacy 未映射 | 返回 409，不返回部分结果；Slice 6 专项通过。 |
| 分享题被他人使用后查询 owner 统计 | 只包含本人问卷，不能读取接收者问卷；Slice 7 专项及最终 smoke 通过。 |
| 数字题无有效答案 | count=0，min/max/average 为 null；专项通过。 |

完整测试还覆盖注册、问卷 CRUD、四题型校验、跳转路径、提交、快照、修订、授权和恢复；具体输入和断言在 `tests/`。

## 最终集成实测

使用 `127.0.0.1`、真实 MongoDB 和随机 `survey_test_smoke_<UUID>` 库启动 Uvicorn。链路覆盖题目 v1/v2、草稿固定绑定、发布快照、分享、接收者私人题库选题、答卷、usage 重建、本人统计的版本分组、撤销和 owner 隔离；页面及健康路由返回正常。结果 `REAL_UVICORN_SMOKE=PASS`，服务停止、测试库清理后集合为空，日志见 [集成记录](stage2/final-integration-20261029/README.md)。

旧数据隔离演练的只读盘点没有写入：两个未映射位置返回 409；故障注入后保留可恢复 PREPARED 操作及一个已提交题目版本，重试后两个位置完成映射且原旧快照不变。中间状态存在，不应描述成多集合原子事务。

## 如何复现

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -v
```

设置该变量后，数据库 fixture 使用随机 `survey_test_<UUID>` 库并在结束时删除；未设置时采用 mock。确认连接的是可供测试的本地 MongoDB，不要将测试 URI 指向生产服务。上面的命令会重新运行完整套件及已知 36 项失败；最终收尾未再次执行它。

Slice 3 的桌面 Edge BFCache 结果来自独立复审提供的证据；本轮没有重复该专项。真实强杀、断网未知确认与大规模压力尚未测试。警告主要来自第三方弃用提示，未屏蔽。
