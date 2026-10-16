# 测试记录

## 第四轮：统计与管理 UI

2026-10-16（Asia/Shanghai），Python 3.12.14，MongoDB 9.0.2 standalone，既有依赖组合。实施前真实基线 371 passed, 1706 warnings in 63.48s；退出码 0。原测试和 fixture、公开页和 JS、账户/快照/提交/Jump/Validation 核心哈希未改动。

最终 **455 passed, 2262 warnings in 85.55s (0:01:25)，退出码 0**。原 371 全通过；新增统计 62、管理页面 22。存储相关真实 MongoDB 160、mock 160；纯逻辑 135，不重复套后端。

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -v --log-file=docs/iteration-4/pytest-runtime-final.log --log-file-level=WARNING
.\.venv\Scripts\python.exe tests/smoke_statistics.py
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
node --check app/static/management.js
```

逐项结果：[pytest-final.txt](iteration-4/pytest-final.txt)。原始错误/预期故障日志：[errors-original.md](iteration-4/errors-original.md)。完整命令、哈希、计数、smoke、核对结果均在 iteration-4。

| 组别 | 输入与预期 | 实际 |
|---|---|---|
| 空统计 | draft 无数据版本空；published 空题零版/零答卷 | 通过 |
| 单份/多份 | total_responses 为 1/2，多选每项正确计数，数字 0 计入 | 通过 |
| single | 合法 a/a/b 得 2/1，空/null/optional missing/skipped 不计 | 通过 |
| multiple | [a,b]+[a] 得 answered=2、selections=3、counts=2/1 | 通过 |
| text | 非空原文 values，空/未答/skipped 不计 | 通过 |
| number | int/float、0、0.1/0.2 精度、大数溢出与消去、零回答 null | 通过 |
| 四类未答 | 分别经过 optional 未填、required 被跳过 | 全部 answered=0，无伪造选项/平均数 |
| 历史 | 同 ID 变 options/label/type，部分版本无题，当前版零答卷 | 按版本保留原义，不混合、不伪造不存在题 |
| 权限 | owner、其他账号、未登录、非法 ObjectId、public token 绕过 | 200/404/401/422/404，符合预期 |
| 异常历史 | unknown option、bool、NaN、缺快照/版本、重复答案、错误路径/类型 | 409 数据一致性错误，无部分正常计数 |
| UI 页面 | register/login/dashboard/new/edit/stats/单题，用户隔离 | 正常页 200，未登录管理页 303，其他 owner 404 |
| HTML/CSRF | 恶意标题和文本、同源写防护、closed 只读 | 转义、403、表单隐藏且服务端规则不变 |

真实 Uvicorn 数值 smoke 全通过，退出码 0。手算旧版三份：single=2/1，multiple 两人三次、x=2/y=1，text 两条，number=[10,20,30]、average=20/min=10/max=30。新版本一份 number=40，average=40，总答卷 4，统计保留两版及历史 label。直接核对 MongoDB 四条 response、两份 snapshot 和 response 复合索引。

核对文件：[statistics-check.json](iteration-4/statistics-check.json)。预期由固定示例手算，断言与实际比较由 Codex 执行，没有虚构人工操作或评分。HTML/next/submit/管理与统计路由均实际请求，非只检查 200。

首轮扩展 439 项也通过；补四类未答/跳过用例后最终 455 项通过。本轮无意外 pytest 或启动失败；只有 Git 非仓库原始输出 128。原故障注入与新异常数据测试的 ERROR/WARNING 是预期证据，保留完整日志。第三方弃用警告未屏蔽。

未进行真实浏览器点击：已有 computer-use 工具窗口检查未列出可接续浏览器，未安装额外浏览器包；按本轮允许方式采用 TestClient、HTTP smoke、JS 语法和转义测试。没有压力测试或大数据分页测试。统计动态读的并发新增数据可能下一次刷新才纳入，不承诺事务报表快照。


## 第三轮：快照 / 跳转 / 公开填写 / 正式提交

2026-10-16（Asia/Shanghai）。实际 Python 3.12.14、MongoDB 9.0.2 standalone、既有 FastAPI/PyMongo/pytest 依赖。修改前基线 220 passed, 541 warnings in 28.92s，退出码 0。原 test_system.py/test_questions.py/test_validation.py/conftest.py 哈希均未改变。

最终 **371 passed, 1706 warnings in 62.19s (0:01:02)；退出码 0**。分类：原基线 220；新公开/持久化 API 测试 112；新纯跳转测试 39。存储相关真实 MongoDB 126、mock 126，纯校验/跳转共 119，不为计数重复执行无存储逻辑。

实际命令：

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -v --log-file=docs/iteration-3/pytest-runtime-final.log --log-file-level=ERROR
.\.venv\Scripts\python.exe tests/smoke_responses.py
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
node --check app/static/survey.js
```

完整输出：[pytest-final.txt](iteration-3/pytest-final.txt)、[test-counts.json](iteration-3/test-counts.json)、[verification.json](iteration-3/verification.json)。各阶段输出、命令及原始错误均保留 iteration-3，未覆盖历史日志。

| 类别 | 输入/步骤 | 预期与实际 |
|---|---|---|
| snapshot | draft 编辑、publish、published 题目/规则编辑 | draft 不写快照，publish 当前版，编辑 +1 且先保存新快照；通过 |
| 不可变/唯一/读取 | 重复 pair 插入、修改返回对象、owner 读取旧版 | 唯一索引拒绝重复；旧快照内容不变；不存在版 404；无修改端点；通过 |
| snapshot/pointer 故障 | 主动注入 insert 或切换指针 OperationFailure | 503、当前题目/版本不变、保留恢复记录；下一次请求恢复且 snapshot 存在；通过 |
| publish 故障 | 主动注入首次 snapshot 失败 | draft 不变，未发布，snapshot 未写；通过 |
| published 并发 | 四线程同版本写结构 | 一成功、三 409，新版本和快照对应；通过 |
| 恢复后旧数组 | 模拟恢复已推进当前版 | 旧计算结果不得隐式 rebase；409、不覆盖新题；通过 |
| 跳转定义 | 各题型合法规则及不合法 type/operator/value/reference/priority/id | 正确接受/拒绝；bool/NaN/Infinity/int64 处理与原 engine 一致；通过 |
| priority | 不同物理顺序、同 source 重复优先级、默认值 | 按 priority 首匹配；重复拒绝；默认值明确保存；通过 |
| 执行器 | 顺序、单选、多选、数字五类比较、最后一题 | 命中跳转、未命中下一题、结束 null；通过 |
| runtime 防护 | 故意构造回路、max_steps=1 | visited/步数错误，无死循环；通过 |
| 引用完整性 | 删 source/target，改型、删 option、逆序 | 409、题目/版本/快照不变；先删规则后可删题；通过 |
| public | 外站分享 GET 可读、跨站 POST 拒绝；正确/错误 token、draft/published/closed、过期、匿名权限、HTML | 200/404/409/410/401；公开字段白名单无 owner/session/pending；通过 |
| response/path | 顺序、跳转、skipped required、extra/skipped/unknown/重复答案、四题型 | 按历史路径验证；不污染答卷；通过 |
| 旧版提交 | 发布后改范围，再按旧版提交 | 旧版成功，新版不合法答案失败；其他 survey 的缺失版本失败；通过 |
| 匿名 | allow_anonymous 两值 × 登录状态 | 未授权 401；允许时 null/真实 ID，匿名不伪造去重；通过 |
| 去重 | 登录允许多次/禁止多次、两线程同时 insert | 允许多次成功；禁止时单成功、另一 409；数据库仅一条；通过 |
| deadline | null、未来、过去、等于、前后 1μs、校验后突然过期 | 截止前/等于成功，超过拒绝；最终 gate 复查；通过 |
| close race | 校验后关闭，再提交准入 | 409、无 response；通过 |
| DELETE | draft/published/closed | draft 204，其余 409，历史数据保留；通过 |

真实 Uvicorn 实跑注册→登录→建题→建规则→发布→公开页面/API→next 路径→提交→MongoDB 核验→published 改题/新快照→旧版再提交→close→拒绝再提交→logout。最终 REAL_RESPONSE_API_SMOKE=PASS、REAL_UVICORN_SMOKE=PASS，退出码 0；临时服务和测试库清理。日志：[startup-final.txt](iteration-3/startup-final.txt)、[startup-server.txt](iteration-3/startup-server.txt)。

实际失败：第一次客户端启动探测 ConnectTimeout，退出码 1，服务已启动；修正本地 HTTP 探测不读取环境代理，并将 ConnectTimeout 纳入有限 readiness 重试，后续两次通过。完整 traceback 在 [errors-original.md](iteration-3/errors-original.md) 和 startup-first.txt，未用 catch-all 伪装成功。

故障注入中的 ERROR 是主动测试，不是意外 pytest 失败，原 traceback 保存在 pytest-runtime-final.log。第三方弃用警告未屏蔽。compileall、pip check、JS 语法检查均退出码 0。

局限：无浏览器自动化端到端或压力测试；API smoke 已实际取 HTML、执行 next 和提交，但不声称做过真实浏览器点击。匿名及允许多次请求暂无通用幂等键，网络重试可能重复。当前提交以准入点为线性化语义，关闭前已准入可在关闭后完成插入。standalone 恢复协议故障响应需重读确认结果，不等于事务回滚。


## 第二轮：题目系统 / Validation / 版本

本轮日期 2026-10-16（Asia/Shanghai）。Windows、Python 3.12.14、MongoDB 9.0.2，继续使用既有 .venv 和 requirements.txt，无新增依赖。

修改前实际基线为 70 passed, 183 warnings in 6.94s；保留原测试文件与 fixture 不变。增加独立纯 engine 测试及依赖同一 db fixture 的 API 测试，未复制 mock/mongo 测试文件。

```powershell
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe tests/smoke_questions.py
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
```

最终 **220 passed, 541 warnings in 16.60s，退出码 0**。原用例 70 + 新题目 API 70 + 纯 engine 80。按后端：真实 MongoDB 70、mock 70；纯 engine 80 不依赖存储所以不重复按后端执行。首轮扩展 208 项也全部通过。完整逐项最终输出：[iteration-2/pytest-final.txt](iteration-2/pytest-final.txt)，计数核对：[test-counts.json](iteration-2/test-counts.json)。

| 测试组 | 输入/步骤 | 预期及实际 |
|---|---|---|
| 四题型定义 | 单选、多选、text、number 的合法配置 | engine valid；API 201，嵌入 MongoDB、无 questions 集合，全部通过 |
| 非法定义 | 未知 type、空白标题、缺 options、重复 option、非法 ID、未知规则、错误类型、bool order/计数、范围倒置、exact 冲突、不可满足 required | 定义阶段失败；API 422 且数组/版本不变，全部通过 |
| 答案缺失 | MISSING/null、空文本/多选数组、必答空白文本 | 必答失败，非必答允许缺失；填写后仍校验内容，全部通过 |
| single/multiple 答案 | 合法/非法 option，重复 option，数量少/多/exact，错误容器及元素类型 | 合法通过，其余稳定错误 code，全部通过 |
| text 答案 | 中文、过短、过长、非字符串、空白 | 按 Unicode 字符长度/required 规则处理，全部通过 |
| number 答案 | 范围内外、整数/小数、bool、字符串、NaN/±Infinity、超 int64 | 拒绝非正常数值与 bool；2.0 可作为整数值，全部通过 |
| 非有限 HTTP JSON | 手工发送 NaN/Infinity/-Infinity 规则参数 | 安全 422，可 JSON 编码错误，不出现 500，全部通过 |
| owner/认证 | 未登录、他人 survey、非法 ObjectId、不存在 survey/question | 401/404/422，三个写接口均覆盖，全部通过 |
| 顺序与 ID | 前插、移动、删除、重复 question ID、修改 ID、越界 order | 连续 1..N；稳定 ID；冲突/无效写拒绝，全部通过 |
| 版本 | 新建、增题、改题、改题型/options/validation/required、移动、删题、普通元信息、无变化 PUT | 1 起步，每次有效结构操作 +1；元信息/无变化不增，全部通过 |
| 状态 | published 增改删；closed 写与读 | published 正常 +1；closed 409、可读，原状态机不变，全部通过 |
| 删除保护 | 测试库直接插入 response，删除 survey；无 response 删除 | 有答卷 409 并保留两者；无答卷 204；他人 404，全部通过 |
| 并发结构 | 4 线程同步读同版本并修改，同一个真实/mocked MongoDB | 一次成功 +1，三个 409，未丢失或覆盖成功更新，全部通过 |
| 非覆盖与状态竞争 | 同时改元信息；旧快照提交时状态已 closed | 元信息/jump_rules 保留；状态变化导致 409，全部通过 |

真实 Uvicorn 检查：基础流程与题目增改删、published 编辑、closed 拒绝、版本与元信息、删除保护全部通过，`REAL_QUESTION_API_SMOKE=PASS` 和 `REAL_UVICORN_SMOKE=PASS`，退出码 0。生产连接/lifespan 经真实进程实际验证，测试后临时服务与随机测试库清理。原文：[startup-first.txt](iteration-2/startup-first.txt)、[startup-server.txt](iteration-2/startup-server.txt)。

compileall 退出码 0；pip check 输出 `No broken requirements found.`，退出码 0。Git 非仓库退出码 128 为已记录事实，不创建远程仓库。原始错误与警告见 [iteration-2/errors-original.md](iteration-2/errors-original.md)。541 条警告为原有第三方 Starlette/httpx 与 mongomock 弃用警告，本轮未升级/替换稳定依赖、未隐藏警告。

局限：没有压力测试或真实浏览器编辑器测试；response 正式写入不存在，删除保护测试通过在临时库播种答卷实现，未假装调用提交接口。当前删除检查不是跨集合事务；未来提交与删除竞态必须补齐一致性协议。历史版本快照、跳转执行和提交/统计仍未实现。

## 第一轮历史记录（原测试及结果保留）

实施开始 2026-10-15，续作日期 2026-10-16（Asia/Shanghai）。

实际环境：Windows、Python 3.12.14、MongoDB 9.0.2、FastAPI 0.143.1、PyMongo 4.19.0、pytest 9.1.1、mongomock 4.3.0、httpx 0.28.1、Starlette 1.8.0。完整依赖锁定在 requirements.txt，安装原文在 dependency-install.txt。

## 实际命令与结果

```powershell
cd D:\Codex\survey-system
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe tests/smoke_startup.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app tests
```

最终 pytest：**70 passed, 183 warnings in 7.04s；退出码 0**。35 个参数化测试实例分别跑 mock 与真实 MongoDB，各 35 项，无 skip、无 failed。首次为 70 passed, 183 warnings in 6.68s；修改前端错误展示和 integration 标记后重新运行得到最终结果。

完整最终逐项输出：[pytest-final.txt](pytest-final.txt)。启动原文：[startup-final.txt](startup-final.txt)、[startup-server.txt](startup-server.txt)。所有执行命令：[commands.md](commands.md)。

pip check：`No broken requirements found.`，退出码 0；compileall 无输出，退出码 0。

## 测试输入、预期与实际

每行均在 mock 与真实 MongoDB 上通过；带多输入的行会产生多个参数实例。

| 用例 | 输入/步骤 | 预期 | 实际 |
|---|---|---|---|
| 注册 | alice/password123 | 201；ObjectId 字符串；数据库 Argon2id；响应无哈希 | 通过 |
| 重复注册 | 相同 username 两次 | 201 后 409 | 通过 |
| 非法注册（2） | 空白用户名、短密码 | 422 | 通过 |
| 正常登录与当前身份 | alice/password123；GET me | 200；当前 alice；随机 Cookie | 通过 |
| 登录错误（2） | alice 或 missing + wrongpass | 均 401，同样错误文本 | 通过 |
| 未认证（8） | me、列表、创建、读取、修改、删除、发布、关闭 | 均 401 | 通过 |
| 创建与序列化 | 中文标题；2030-01-01T08:00:00+08:00 | 201 draft；数组空；token≥43 字符；UTC Z；DB ObjectId | 通过 |
| 修改删除 | 修改 title 后 DELETE 再 GET | 新标题；204；404 | 通过 |
| owner 隔离 | alice 建问卷，bob 登录并建立自己的问卷 | 列表仅 bob；读、改、删、发布、关闭 alice 问卷全部 404 | 通过 |
| 发布关闭 | draft 关闭；发布两次；关闭两次；closed 发布 | 409；200 published 两次；200 closed 两次；409 | 通过 |
| 非法 ID（3） | invalid、23 位、24 位非十六进制；读改删发布关闭 | 均 422，无 500 | 通过 |
| 不存在 ID | 合法随机 ObjectId | 404 | 通过 |
| 登出与旧 Cookie 重放 | 登录、登出、重放 Cookie | 204；随后 401；服务端会话删除 | 通过 |
| 会话过期 | DB 设置 expires_at 为过去 | 401，不依赖 TTL 删除速度 | 通过 |
| Cookie 与轮换 | 同一浏览器再次登录 | HttpOnly、SameSite=strict；仅保留当前会话；不保存明文 token 字段 | 通过 |
| 跨站防护 | evil Origin 请求登录和创建 | 403 | 通过 |
| 无效问卷输入（5） | 空白标题、伪造 owner、伪造 status、questions、无时区 deadline | 均 422 | 通过 |
| 索引 | 重复 token 插入；读取索引定义 | DuplicateKeyError；unique、owner、response、TTL 索引存在 | 通过 |
| token 冲突重试 | 首次 token 强制重复，第二次不同 | 自动重试并创建成功 | 通过 |
| 页面、健康检查 | GET /、JS、health | 200；health ok | 通过 |

## 真实启动

独立 Uvicorn 子进程使用真实生产 connect/settings/lifespan 路径连接 MongoDB，非 TestClient。自动选择本地空闲端口，临时库名 `survey_test_smoke_<uuid>`。检查首页、health、JS、OpenAPI、注册、登录、创建、发布、关闭、登出、登出后访问的状态码全部符合预期。`REAL_UVICORN_SMOKE=PASS`，退出码 0。检查后终止临时进程并删除自建临时库；未常驻启动服务。

## 警告与局限

- Starlette 提示 httpx TestClient 用法弃用，建议安装 httpx2；可选安装被自动审批额度问题阻止。现有组合 pip check 通过、全部测试通过，未压制警告。尚未消除该第三方兼容性警告。
- mongomock 使用 datetime.utcnow() 产生 182 条弃用警告，来自第三方内部；应用时间采用有时区 UTC。
- mock 不能替代服务端索引、BSON、真实连接与生命周期验证，因此本轮同时实际跑真实 MongoDB。
- 未实施压力测试、浏览器端到端测试、恶意登录限流测试；静态 JS 另做语法检查，基础 HTTP 页面和资产实际请求通过。
- 未实现的填写、题目、跳转、统计没有伪造测试结果，第二阶段应新增用例。
- 所有初始工具错误保留在 errors-original.md；测试从首次执行起没有失败案例，不虚构修复测试失败的记录。
