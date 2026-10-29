# 切片4：题目分享、权限与撤销

## 范围和依据

本轮仅处理切片4，不进行全量迁移，也不实现usage索引或跨问卷统计。正式依据为[需求矩阵](../requirements-matrix.md)的R2、[设计规则](../design-rules.md)的U2/D3和[API契约](../api-contract.md)：共享针对确定的不可变版本，接收者可以使用和派生自己的题目，不能修改或转分享原题。用户明确选择D3在途票据：撤销前已经获准的确定操作允许完成。需求中的冻结发布语义保持原样。

## 权限与撤销

| 角色 | 可见性与操作 |
|---|---|
| owner | 管理自己的题目族和版本，对指定版本按用户ID或用户名分享、列出和撤销 |
| grantee | 可见活动共享的指定版本及owner用户名，可绑定到本人草稿或派生自己的题目族；不能浏览原题族历史、修改原题、创建原题新版本或转分享 |
| unrelated / anonymous | 无法通过ID读取私有版本或修改共享关系；匿名请求需登录 |

`question_shares`对版本和接收者建立唯一约束，并使用状态、revision和grant epoch处理重复分享、重复撤销及重授权。旧数据没有分享记录时仍为私有。共享版本响应裁剪未授权历史版本标识；派生题记录来源版本，所有权属于接收者。派生接口使用现有幂等key协议。

撤销阻止新的访问、绑定、派生和发布准入；不静默删除现有草稿绑定，编辑页显示授权失效并允许显式移除，普通草稿后续使用/发布须重新检查。已发布的冻结快照、历史查看和答题不因撤销而改写。在途绑定、派生和发布分别绑定确定payload及grant epoch，通过同一共享记录的原子准入与撤销竞争：已获准的原操作可恢复，新payload不能借用旧票据。多共享版本逐项准入；未获得全部所需票据不能发布。票据副本容量上限为128，异常中断后的原操作需要恢复以释放占用。

## 修改范围

既有源码：`app/routers/management.py`、`app/routers/question_bank.py`、`app/schemas/question_bank.py`、`app/services/draft_bindings.py`、`app/services/question_bank.py`、`app/services/surveys.py`、`app/services/versions.py`、`app/static/question-bank.js`、`app/templates/edit.html`、`app/templates/question_bank.html`。

新增源码：`app/services/question_shares.py`、`app/services/share_publish.py`。新增测试：`tests/test_slice4_sharing.py`、`tests/slice4_dom_contract.js`。此前已有测试文件与断言未修改。需求、接口、数据模型、决定、测试计划和AI日志六份stage2文档追加本轮说明；原有文档前缀按入轮哈希核对恢复。`source-and-tests.diff`仅包含上述源码和新增测试，前态从已有独立复审ZIP提取并逐项匹配入轮哈希。

## 验证结果

均在仓库根目录运行；`run_verification.py`配置loopback MongoDB和UUID测试库、保存原始日志/审计/清理结果。

| 顺序 | 命令或检查 | 结果 |
|---|---|---|
| A | `.venv\Scripts\python.exe -B docs/stage2/slice4/run_verification.py targeted-final5` | 退出0；43 passed，680 warnings，16.74秒 |
| B | `.venv\Scripts\python.exe -B docs/stage2/slice4/run_verification.py related-final4` | 退出0；205 passed，2106 warnings，47.62秒 |
| C | `js-final.json`中30条实际命令；Python AST及Jinja解析 | 全部退出0；40个Python文件和9个模板解析通过。这里包含既有JS契约检查，不等同真实浏览器E2E |
| D | `.venv\Scripts\python.exe -B docs/stage2/slice4/run_verification.py smoke-final3` | 退出0；REAL_UVICORN_SMOKE=PASS；独立HTTP客户端验证owner、grantee、共享列表、派生、绑定、撤销后权限与owner访问；服务已停止 |
| E | `.venv\Scripts\python.exe -B docs/stage2/slice4/run_verification.py full-final3` | 退出1；751 passed、36 failed、5145 warnings，124.13秒 |

完整回归逐节点与切片3的744节点比较：新增43节点全部通过，删除0，原节点状态变化0；失败集合精确相同，新增失败0，历史通过节点变失败0。`node-comparison.json`保留两轮全部节点状态，`failure-comparison.json`列出失败集合与新增节点。36项历史失败按既有独立复审分类：28项旧发布冻结断言与正式冻结要求冲突，8项旧固定绑定/存储模型断言冲突；未修改、删除、skip或xfail任何原断言，不将其报告为测试通过。

原始失败证据保留：最初`red-retry.txt`（共享端点实现前RED）；`targeted-fork-red.txt`（派生端点实现前4失败）；`targeted-final3.txt`（新增测试错误地将Response对象与整数比较，后修正为检查status_code）；`full-final.txt`（第一次完整回归发现额外失败，原因是新增代码绕过旧所有权服务接口，源码修复后`full-final2.txt`恢复36项）。原日志未覆盖。其余最终日志、结果和数据库审计位于本目录。

## 数据库、差异与保护

`database-isolation-summary.json`覆盖本轮22次生成审计的运行，所有业务库名符合UUID隔离命名、unexpected为空、清理后集合为空。Uvicorn子进程的实际启动参数在`smoke-final3-launch.json`，其使用`127.0.0.1`和独立UUID库；父进程命令监听不跟踪子进程命令，故同时保存启动、服务器日志和清理结果，不以父监听冒称覆盖子进程。没有连接默认业务数据库或执行全量迁移。

`diff-validation.json`记录差异可解析、当前状态逆向检查、临时副本正向检查/应用、逐字节比较、逆向检查/应用和原样还原；未用强制覆盖或忽略空白。Git对既有行尾报告少量空白警告，未影响上述逐字节检查。`preservation.json`核验入轮1143个文件：16个授权源码/文档变化，意外变化0、缺失0；所有既有测试文件保持原哈希。`git-before.txt`和`git-after.txt`保存现场：分支`stage2-question-bank`，HEAD `0b845575fef4863e49be1e22b20d1882c5c78f66`，`stage1-final^{commit}`为`96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9`，暂存区为空。原有未提交和未跟踪成果继续保留。

## 已知限制

本轮没有进行真实浏览器端到端、强杀、断网未知确认或压力测试；并发及中断恢复由确定性测试和实际MongoDB测试覆盖，不能替代这些验证。派生目前提供API，题库UI没有单独的派生按钮；共享题编辑提示创建自己的题目。授权票据达到容量上限时会拒绝新增准入；异常中断的原操作须恢复，未提供通用后台回收界面。切片4结果应交独立复审；不宣布整个第二阶段完成。
