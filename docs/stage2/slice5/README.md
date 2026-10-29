# 切片5：正式私有题库管理（R7）

## 范围与设计

本轮实现正式R7的题库实体和成员关系。`question_banks`保存owner、名称、说明、revision和归档时间；创建使用owner作用域幂等key。`bank_items`按(bank_id, question_id)唯一，存固定的`selected_version_id`、成员revision和时间；API同时提供等值的`default_version_id`别名。历史问卷绑定及发布快照仍是各自的权威数据，题库不是权限或历史来源。

题库只允许owner管理。本人committed版本和当前获授权的共享版本可以加入；成员更新必须同族、committed且调用者当前有权使用。更换默认版本只影响之后从题库选题，既有草稿绑定和已发布快照不改变。共享撤销后成员保留但标记`authorization_lost`，不展开题目内容，不能用于新绑定；owner可以显式移除。删除题库为软归档，删除成员只移除组织关系，不删除题目、版本或历史。题库不支持跨用户分享。

实现`GET/POST /api/question-banks`、`GET/PUT/DELETE /api/question-banks/{bank_id}`和对应`/items`接口；成员更新/删除路径使用本轮要求的question_id。创建使用Idempotency-Key；元信息和成员修改、删除使用expected_revision。重复加入同一族同一版本是确定性no-op，加入同族其他版本返回冲突。界面新增题库列表、创建、改名、删除、成员添加/移除/更换默认版本及survey picker题库筛选，选择题库成员时默认选中推荐版本，也可显式选择同族的其他已授权版本；最终绑定仍发送明确version ID。

## 代码及测试

既有文件：`app/main.py`、`app/static/question-bank.js`、`app/templates/question_bank.html`、`app/templates/edit.html`。新增：`app/routers/banks.py`、`app/services/banks.py`。新增测试：`tests/test_slice5_banks.py`、`tests/slice5_dom_contract.js`、`tests/slice5_organizer_contract.js`。追加六份stage2设计/验收文档；入轮原有测试文件及断言未改。

新测试覆盖题库私有权限和匿名、创建幂等/CAS、同族唯一、同族及committed版本、修改默认不改草稿/快照、新旧选择、删除题库/成员不删除题、共享撤销及公开快照、选择器固定version ID和失效成员切换。数据库关键场景分别运行mock和真实Mongo；DOM契约是Node测试替身，不是浏览器E2E。

## 测试结果

| 阶段 | 命令/证据 | 结果 |
|---|---|---|
| RED | `.venv\Scripts\python.exe -B docs/stage2/slice5/run_verification.py red` | 新测试实现前6 failed；显式选择其他版本先有Node RED，日志均保留 |
| targeted | `.venv\Scripts\python.exe -B docs/stage2/slice5/run_verification.py targeted-final5` | 退出0；8 passed, 145 warnings in 2.82s |
| related | `.venv\Scripts\python.exe -B docs/stage2/slice5/run_verification.py related-final5` | 退出0；213 passed, 2250 warnings in 55.40s |
| JS/模板 | `static-final.json` | 5条JS命令、Python AST及模板解析通过 |
| Uvicorn | `.venv\Scripts\python.exe -B docs/stage2/slice5/run_verification.py smoke-final4` | 退出0，REAL_UVICORN_SMOKE=PASS；创建题库、添加、绑定、更新默认、确认旧绑定不变、移除且原题保留；服务停止 |
| full | `.venv\Scripts\python.exe -B docs/stage2/slice5/run_verification.py full-final4` | 退出1；36 failed, 759 passed, 5289 warnings in 135.55s (0:02:15) |

`node-comparison.json`逐项保存新旧节点状态：基线787节点、新增8个全部通过、删除0、旧节点状态变化0；36项失败集合完全一致，无新增失败。既有分类为28项发布冻结旧断言冲突、8项固定绑定/存储模型旧断言冲突；本轮未修改、删除、skip或xfail这些断言。此前`full-final.txt`和`full-final2.txt`也保留，不覆盖历史。

## 隔离和保护

采用loopback MongoDB和UUID测试库。`database-isolation-summary.json`记录20次有审计的运行，各测试库名符合隔离规则、unexpected为空，清理检查无剩余集合。Uvicorn子进程使用独立库的启动参数、服务器日志和清理记录单独保存；父进程Mongo监听不能证明覆盖子进程命令。未访问默认业务数据库或执行全量迁移。

入轮1221个文件逐项哈希核对：10个授权源码/文档变化，意外变化0、缺失0。差异文件从入轮快照生成，通过严格正向应用、逆向检查和逐字节还原；Git的行尾空白警告保存在`diff-validation.json`，未忽略空白或强制覆盖。分支`stage2-question-bank`，HEAD `0b845575fef4863e49be1e22b20d1882c5c78f66`，`stage1-final^{commit}`为`96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9`，暂存区为空；原有未提交成果保留。

## 限制

未进行真实浏览器E2E、压力、强杀或断网竞态测试；Node DOM契约和Uvicorn HTTP冒烟不替代这些验证。题库归档不物理清除其成员记录；不支持题库恢复、跨用户题库分享、usage索引或跨问卷统计。切片5交独立复审，不宣布第二阶段整体完成。
