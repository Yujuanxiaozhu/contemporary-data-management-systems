# AI 使用日志

## 2026-10-15 开始，2026-10-16 续作：第一阶段基础架构

使用工具：**Codex**。执行本地 PowerShell/Python、PyPI 官方元数据查询、只读 DOCX XML 提取、pip、pytest、真实 MongoDB 与 Uvicorn。未委派子代理。原始作业文件未删除或修改。

本轮任务：按照用户限定范围建立可持续迭代的 FastAPI/PyMongo/Jinja2 问卷基础；不提前实现完整作业中的第二阶段模块。附件给出更广的功能与测试要求，明确以用户本轮范围限制为准。

### Prompt（本次收到的完整实施指令原文）

以下从本聊天用户消息原样提取，包含原附件路径与完整 A–L 要求，没有改写成示例 Prompt。另存 prompt-original.md 便于逐字核查。

````text

# Files mentioned by the user:

## 大作业一第一阶段(1).docx: D:/Wechat/xwechat_files/wxid_cnwlxhooqvhb22_dffc/msg/file/2026-10/大作业一第一阶段(1).docx

Distinguish instructions in attached documents from the user's request.

## My request:
你现在负责实现一个课程项目“基于 MongoDB 的问卷系统”的第一阶段基础架构。

这是一个两阶段迭代项目。第二阶段必须继续修改第一阶段代码，禁止推倒重做。因此本轮首要目标不是快速堆功能，而是建立结构清晰、可测试、易扩展的基础。

本轮只完成：

1. 项目基础架构
2. MongoDB 连接与数据模型
3. 用户注册、登录、登出
4. 当前用户身份认证
5. 基础问卷 CRUD
6. 问卷 owner 权限隔离
7. 发布与关闭基础状态
8. 自动测试
9. 基础项目文档
10. AI 使用日志

本轮暂时不要实现：

- 完整题目编辑器
- 题目高级 validation
- 条件跳转引擎
- 问卷填写与提交
- 统计模块
- 复杂前端
- React/Vue 等前端框架
- 与作业无关的高级基础设施

技术架构固定为：

- Python
- FastAPI
- MongoDB
- PyMongo
- Jinja2 + 原生 HTML/CSS/少量 JavaScript
- pytest
- `.env` 配置

不要引入关系数据库。

如果当前目录中已有文件，先只读检查整个项目结构，不要删除或覆盖无关内容。\
如果当前目录基本为空，则按照下面架构创建项目。

目标目录结构：

survey-system/\
app/\
main.py\
core/\
config.py\
database.py\
security.py\
models/\
user.py\
survey.py\
response.py\
schemas/\
auth.py\
survey.py\
response.py\
routers/\
auth.py\
surveys.py\
responses.py\
statistics.py\
services/\
validation.py\
jump_engine.py\
statistics.py\
templates/\
static/\
tests/\
docs/\
architecture.md\
database-design.md\
api.md\
testing.md\
ai-log.md\
.env.example\
.gitignore\
requirements.txt\
README.md

暂未实现的模块可以保留清晰的结构，但不要写大量没有实际用途的占位代码。

MongoDB 第一阶段核心设计：

users：

- `_id`
- `username`
- `password_hash`
- `created_at`

username 必须唯一。

surveys：

- `_id`
- `owner_id`
- `title`
- `description`
- `status`：draft / published / closed
- `allow_anonymous`
- `allow_multiple_submissions`
- `deadline`
- `public_token`
- `questions`
- `jump_rules`
- `schema_version`
- `created_at`
- `updated_at`

questions 与 jump_rules 本轮允许初始化为空数组，为下一轮实现预留。

responses：

- `_id`
- `survey_id`
- `respondent_user_id`
- `answers`
- `submitted_at`
- `survey_schema_version`

responses 模型本轮建立即可，不需要实现正式填写接口。

设计原则：

- survey 的问题未来采用嵌入式文档。
- response 必须独立集合，禁止把大量 response 嵌入 survey。
- MongoDB ObjectId 的 API 序列化必须正确处理。
- 时间统一使用明确、一致的时间策略。
- public_token 应不可预测并保证唯一性。
- 密码禁止明文保存。
- 密码校验与身份认证逻辑放在独立 security 层。
- 配置、数据库连接、业务逻辑和 HTTP router 分离。
- 不允许把所有实现塞进 main.py。

身份认证：

实现：\
POST /api/auth/register\
POST /api/auth/login\
POST /api/auth/logout

提供统一的 current user dependency / middleware 机制。

注册要求：

- username 非空
- username 唯一
- 密码不得明文入库
- 重复用户名返回合理 HTTP 状态和错误信息

登录要求：

- 用户不存在或密码错误时不能泄露不必要的信息
- 登录成功后建立可靠的身份状态
- 后续 `/api/surveys` 能取得当前用户身份

问卷 API：

GET /api/surveys\
POST /api/surveys\
GET /api/surveys/{survey_id}\
PUT /api/surveys/{survey_id}\
POST /api/surveys/{survey_id}/publish\
POST /api/surveys/{survey_id}/close

权限要求：

- 用户只能看到自己创建的问卷。
- 用户只能读取、修改、发布、关闭自己的问卷。
- 用户 A 使用用户 B 的 survey_id 时必须被拒绝。
- 不要仅依靠前端隐藏实现权限控制。

创建问卷至少支持：

- title
- description
- allow_anonymous
- allow_multiple_submissions
- deadline

创建后：\
status = draft

发布后：\
status = published

关闭后：\
status = closed

为问卷生成公开 `public_token`。

本轮不用实现公开填写页面，但数据模型和 token 必须为后续 `/survey/{public_token}` 做好准备。

请同时实现必要的索引，包括至少：

- users.username unique
- surveys.public_token unique
- surveys.owner_id
- responses.survey_id

测试要求：

使用 pytest。

至少编写并实际运行以下测试：

- 注册成功
- 重复用户名注册失败
- 正确密码登录成功
- 错误密码登录失败
- 未登录不能访问需要认证的 API
- 创建问卷成功
- 当前用户只能看到自己的问卷
- 用户 A 无法读取用户 B 的问卷
- 用户 A 无法修改用户 B 的问卷
- 发布问卷
- 关闭问卷
- 非法 survey_id 不导致服务器 500
- MongoDB/API ObjectId 序列化正常

如果测试环境不适合直接连接真实 MongoDB，请采用合理的测试策略，但不要为了测试而把生产数据层完全改写成与 MongoDB 无关的假实现。\
如果某些测试必须依赖真实 MongoDB，请在报告中明确说明。

文档要求：

README.md：

- 项目用途
- 环境要求
- 安装步骤
- MongoDB 配置方法
- `.env` 方法
- 启动方法
- 测试方法
- 当前已实现功能
- 尚未实现功能

docs/architecture.md：

- 总体架构
- 每层职责
- 为什么这样拆分
- 为第二阶段保留了哪些扩展点

docs/database-design.md：\
详细说明：

- users
- surveys
- responses
- 每个字段含义
- 索引
- 为什么 questions 嵌入 surveys
- 为什么 responses 独立集合
- 为什么这种结构适合 MongoDB
- 与关系数据库式拆表设计相比的考虑

docs/api.md：\
记录本轮真实实现的 API，包括：

- Method
- URL
- 是否需要登录
- 输入
- 输出
- 常见错误

docs/testing.md：\
记录：

- 实际测试环境
- 测试命令
- 测试用例
- 输入
- 预期输出
- 实际结果

docs/ai-log.md：

这是课程明确要求的材料，必须从现在开始真实维护。

新增本轮记录，至少包含：

- 使用工具：Codex
- 本轮任务
- Prompt：保存本次收到的完整实施指令，不能杜撰别的 Prompt
- AI 生成/修改了哪些文件
- AI 做了哪些设计
- 测试过程中出现了哪些问题
- 是否进行了修正
- 实际修正内容
- 尚未解决的问题

不要虚构人工修改，也不要为了让报告好看而编造 AI 出错记录。\
只记录实际发生的事情。

代码质量要求：

- 类型和命名清晰。
- 适量注释，只解释必要的设计逻辑。
- 不要加入大量模板化、AI 风格的废话注释。
- 处理异常输入。
- 不要吞掉异常。
- 不要用 catch-all 来伪装成功。
- 不要为“未来可能使用”提前实现复杂抽象。
- 不要增加当前课程要求之外的大型依赖。
- 不追求复杂 UI。
- 不实施 Docker、Redis、Celery、消息队列、微服务等当前无必要内容。

依赖版本选择时，以当前环境中相互兼容、维护正常的稳定组合为准，并写入 requirements.txt。不要为了追求最新版本而使用实验性 API。

执行过程中：

- 先检查环境。
- 再实施。
- 实际安装必要依赖。
- 实际运行项目或最小启动检查。
- 实际运行 pytest。
- 遇到失败必须修复后重新运行。
- 不要只声称“理论上可以运行”。

不要删除原始作业说明或用户已有材料。

完成后不要只回复一句“完成”。

请完整返回：

A. 环境检查结果

B. 实际创建/修改的文件清单

C. MongoDB 最终数据模型

D. 已实现 API

E. 身份认证方案

F. 权限隔离实现方式

G. 实际执行的命令

H. pytest 完整最终结果与退出码

I. 启动验证结果

J. AI 日志位置与本轮记录说明

K. 当前尚未实现的功能

L. 发现的风险、问题或需要下一阶段解决的事项

如果出现任何报错，把原始错误信息完整保留在结果中，不要只给摘要。

````

续作用户指令原文：`继续`。

### AI 生成/修改的文件

本项目此前不存在；本轮在 D:/Codex/survey-system 下新建。完整清单：

```text
.env.example
.gitignore
README.md
app/__init__.py
app/core/__init__.py
app/core/config.py
app/core/database.py
app/core/security.py
app/main.py
app/models/__init__.py
app/models/response.py
app/models/survey.py
app/models/user.py
app/routers/__init__.py
app/routers/auth.py
app/routers/responses.py
app/routers/statistics.py
app/routers/surveys.py
app/schemas/__init__.py
app/schemas/auth.py
app/schemas/response.py
app/schemas/survey.py
app/services/__init__.py
app/services/jump_engine.py
app/services/statistics.py
app/services/surveys.py
app/services/validation.py
app/static/app.js
app/static/style.css
app/templates/index.html
docs/ai-log.md
docs/api.md
docs/architecture.md
docs/commands.md
docs/database-design.md
docs/delivery-report.md
docs/dependency-install.txt
docs/errors-original.md
docs/file-manifest.txt
docs/prompt-original.md
docs/pytest-final.txt
docs/startup-final.txt
docs/startup-server.txt
docs/testing.md
pytest.ini
requirements.txt
tests/conftest.py
tests/smoke_startup.py
tests/test_system.py
```

另外实际创建 `.venv` 并安装依赖；未提交本地环境。只删除了本轮自建的 bootstrap.py 和 add_tests.py 生成脚本，不删除任何用户原材料。测试运行生成的缓存由 .gitignore 忽略。

### AI 设计

分离 config/database/security/model/schema/router/service；应用工厂支持数据库注入。生产始终是 PyMongo；mock 仅用于同一套 API 测试。问题与跳转嵌入 survey，responses 独立，schema_version 预留兼容扩展。UTC Date 与 ObjectId 显式序列化。数据库唯一索引保证 username/token，公开 token 为随机 256 bit。

采用 Argon2id 与可撤销 MongoDB 会话，Cookie HttpOnly/SameSite=Strict，服务端存摘要而非 token；统一 current_user，查询同时匹配 owner 与 ID。状态变化用原子条件更新。增加 DELETE 满足 CRUD。暂不实现的模块只保留一行说明。

### 实际问题与修正

1. `python` 不在 PATH，`py` 默认 Anaconda 3.9；改用已存在的捆绑 Python 3.12.14 建立项目 venv。
2. WMI 查询 MongoDB 服务详细信息被拒绝；没有绕过系统权限，改用真实 PyMongo ping 和 server_info 验证，MongoDB 9.0.2 可用。
3. 首次 pip 网络被沙箱拒绝，WinError 10013；相同依赖安装通过 require_escalated 审核后成功，安装原文在 dependency-install.txt。
4. apply_patch 无法创建 Windows 绝对路径父目录；该批次没有写入成功。显式建立项目目录后使用项目内 Python 文件生成完成，没有覆盖其他目录。
5. 初次 DOCX 提取终端出现乱码；设置 PYTHONIOENCODING=utf-8 后重新提取，原文可读；未修改原 DOCX。
6. 首轮测试全部 70 项通过，但发现 Starlette/httpx 与 mongomock 弃用警告；尝试申请安装可选 httpx2 时自动审批额度失败，命令未执行。未规避审批，也未将其写入 requirements。该警告仍在，记录为未解决兼容性事项。
7. 自查发现页面初始化 catch 空函数会隐藏网络错误；已改为仅把未登录 401 作为正常初态，其他错误展示在页面。补充真实 MongoDB integration 标记后复跑 pytest。

所有已返回的原始错误逐块保存 errors-original.md（包括沙箱、工具与终端原文；若工具原返回包含截断标记，也原样保留，未声称恢复了被工具截断的数据）。没有测试失败，因此没有虚构失败修复记录；没有人工修改证据，因此所有实现和修正均记为 AI 操作。

### 实际验证与当前结果

首次 pytest 70 passed, 183 warnings in 6.68s；最终 pytest 70 passed, 183 warnings in 7.04s，退出码 0，其中真实 MongoDB 35 项、mongomock 35 项。真实 Uvicorn 独立进程完整基础流程通过，退出码 0；临时服务已停止、测试库已清理。pip check 与 compileall 通过。

尚未解决：第三方弃用警告；下一阶段题目/答案结构、问卷版本兼容、发布后定义修改、截止时间和匿名/重复提交约束、答卷保留与删除政策。未实现的模块没有虚构实现或测试。用户仍需理解代码与设计，并根据课程最终提交范围补充未实现部分。


## 2026-10-16：第二轮，题目系统 + Validation Engine + 问卷版本

工具：Codex。目标是在第一轮已验收项目上增量实现，不重建、不改写认证及基础功能。先只读检查源码、测试、配置、静态页面和 docs；项目没有 Git 仓库，未 init 或创建远程仓库。先运行原 70 项回归，全部通过。未使用子代理、未新增依赖。证据目录 `docs/iteration-2/`，第一轮测试、报错及启动日志原样保留。

### 本次完整 Prompt（粘贴附件原文）

独立副本 `iteration-2/prompt-original.txt` 与用户提供文件按字节核对一致。以下完整保存收到的实施指令，没有改写为示例：

````text
继续开发现有项目：

D:\Codex\survey-system

第一轮已经完成并通过验收。

严禁重建项目、推倒现有架构或重新实现第一轮已有功能。

先完整只读检查当前源码、测试和 docs，理解现有实现后，在现有代码基础上继续。

本轮目标：

实现“题目系统 + Validation Engine + 问卷版本机制”。

本轮不要实现：
- 条件跳转执行
- 公开填写页面
- response 正式提交
- 统计功能
- 复杂前端编辑器

====================
一、保留第一轮行为
====================

现有以下功能必须继续可用：

- 注册
- 登录
- 登出
- /api/auth/me
- 问卷 CRUD
- 发布
- 关闭
- owner 权限隔离
- MongoDB 真实连接
- sessions
- 所有第一轮测试

禁止为了本轮开发破坏第一轮已经通过的 70 个测试。

====================
二、题目模型
====================

系统内部统一支持四种 question type：

single_choice
multiple_choice
text
number

虽然课程说明将 text 和 number 都称为“填空题”，内部模型应区分二者。

Question 至少包含：

- id
- type
- title
- required
- order
- options
- validation

问题 ID 必须在所属 survey 内唯一并稳定。

不要使用 MongoDB ObjectId 作为嵌套 question 的唯一必需方案，如果当前实现采用稳定字符串 ID 更适合，请保持简单。

题目嵌入 surveys.questions。

不要创建独立 questions collection。

====================
三、各题型字段
====================

1. single_choice

options：

[
  {
    "id": "...",
    "label": "..."
  }
]

要求：

- 至少提供合理数量的选项。
- option id 在该 question 内唯一。
- answer 必须对应一个合法 option id。
- required=true 时不能缺失答案。

2. multiple_choice

options 与 single_choice 相同。

validation 支持：

- min_selections
- max_selections
- exact_selections

要求：

- answer 为 option id 数组。
- 禁止重复选择同一 option。
- 所有 option id 必须存在。
- exact_selections 与 min/max 的组合必须做一致性检查。
- validation 配置自身非法时，在题目创建/修改阶段直接拒绝，不要等用户填写时才发现。

3. text

validation 支持：

- min_length
- max_length

要求：

- answer 必须为字符串。
- 校验长度。
- min_length 不得大于 max_length。
- 必须合理处理 required 与空字符串之间的关系。

4. number

validation 支持：

- min
- max
- integer_only

要求：

- answer 必须是数字语义的数据。
- integer_only=true 时禁止小数。
- min 不得大于 max。
- 注意 Python 中 bool 是 int 子类，不要把 true/false 当合法数字答案。
- 对 NaN / Infinity 等非正常数值采取明确安全策略。

====================
四、Validation Engine
====================

核心业务逻辑放在：

app/services/validation.py

不要把大量校验写进 router。

至少提供两类校验：

1. question definition validation

负责检查题目本身配置是否合法。

例如：

- 未知 type
- title 为空
- 重复 option id
- single/multiple 没有合法 options
- min > max
- exact 与 min/max 冲突
- number min > max
- 不属于该题型的 validation 字段

2. answer validation

输入：

question definition
answer / missing answer

输出必须能够明确表示：

- valid / invalid
- 错误原因

设计应便于下一轮 response 提交时复用。

不要为每个 API 再写一套校验规则。

错误信息应适合 API 返回和测试断言。

====================
五、题目 API
====================

在现有 survey owner 权限模型基础上实现合理的题目管理 API。

建议至少：

POST /api/surveys/{survey_id}/questions

PUT /api/surveys/{survey_id}/questions/{question_id}

DELETE /api/surveys/{survey_id}/questions/{question_id}

如果现有项目 API 风格有更一致的设计，可以保持现有风格，但必须在 docs/api.md 说明。

必须保证：

- 未登录不能操作。
- 只能操作自己的 survey。
- 非法 survey id 不产生 500。
- 不存在 question 返回合理错误。
- question id 不重复。
- order 行为明确。

当删除题目后，题目顺序必须保持可解释、一致。

不要依赖前端保证数据合法。

====================
六、schema_version
====================

正式落实 surveys.schema_version。

新建 survey：

schema_version = 1

仅修改以下普通元信息不升级版本：

- title
- description
- allow_anonymous
- allow_multiple_submissions
- deadline

当发生会影响 response 含义的问题结构修改时：

- 新增题目
- 删除题目
- 修改题目内容
- 修改题型
- 修改 options
- 修改 validation

执行：

schema_version += 1

一次 API 操作只递增一次。

版本必须由服务端维护，禁止客户端自行指定新版本。

为下一阶段 jump_rules 修改版本预留清晰机制，但本轮不要实现跳转执行。

====================
七、状态与编辑
====================

采用以下规则：

draft：
允许编辑题目。

published：
仍允许编辑题目；
涉及问题结构修改时正常 schema_version +1。

closed：
默认不再接受未来填写，但题目历史数据仍应保持可读取。
本轮如果允许 closed 后继续编辑，请明确记录实际行为及理由；
如果限制编辑，也要通过明确业务规则实现。

不要凭感觉偷偷改变第一轮状态机。

====================
八、删除策略
====================

检查第一轮已经实现的 survey DELETE。

落实以下保护规则：

如果 survey 尚无 response：
允许物理删除。

如果 survey 已经存在 response：
禁止直接物理删除；
返回合理冲突状态，例如 HTTP 409；
提示应采用关闭问卷而不是删除历史数据。

不要在删除 survey 时自动级联删除 response。

即使 response 正式提交接口尚未实现，也需要把该规则加入数据层/服务层并测试。

====================
九、测试
====================

继续使用当前测试体系。

第一轮现有测试必须全部继续通过。

为本轮至少增加以下测试：

题目定义：

- 创建合法单选题
- 单选没有 options 被拒绝
- 重复 option id 被拒绝
- 创建合法多选题
- min_selections > max_selections 被拒绝
- exact_selections 冲突被拒绝
- 创建合法 text
- min_length > max_length 被拒绝
- 创建合法 number
- min > max 被拒绝

answer validation：

- required 缺失失败
- 非 required 缺失成功
- single 合法选项成功
- single 非法选项失败
- multiple 合法成功
- multiple 数量过少失败
- multiple 数量过多失败
- multiple exact 数量失败
- multiple 重复 option 失败
- text 长度合法
- text 太短
- text 太长
- number 合法
- number 越界
- integer_only 拒绝小数
- bool 不得作为合法数字
- NaN / Infinity 按设计被拒绝

API：

- owner 添加题目
- 非 owner 添加题目被拒绝
- 修改题目
- 删除题目
- 不存在 question
- 非法 survey id
- schema_version 初始为 1
- 新增题目版本 +1
- 修改题目版本 +1
- 删除题目版本 +1
- 仅修改 survey 普通元信息不升级 schema_version
- published 状态下题目编辑按设计工作
- 已有 response 时 survey DELETE 被禁止
- 无 response 时 DELETE 行为保持正常

同时尽可能继续覆盖：

- mongomock
- 真实 MongoDB

不要简单复制同一测试文件来制造测试数量，确保不同数据后端执行的是同一业务语义。

====================
十、文档更新
====================

更新：

README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md

database-design.md 新增：

- question 嵌入结构
- 四类题型
- options
- validation
- schema_version 设计
- 为什么 question 嵌入 survey
- 为什么 response 仍独立
- 版本机制如何为第二阶段保留兼容空间

testing.md：

记录本轮真实测试环境、命令、测试数量和结果。

ai-log.md：

继续真实追加本轮记录。

必须保存：
- 本次收到的完整 Prompt
- AI 实际修改内容
- 实际出现的问题
- 实际修复
- 测试结果
- 未解决问题

禁止虚构人工修改或 AI 错误。

====================
十一、质量要求
====================

继续遵守第一轮原则：

- Router 不承担复杂业务逻辑。
- Validation 统一实现。
- 不复制业务规则。
- 不吞异常。
- 不用 catch-all 掩盖问题。
- 不通过硬编码针对测试。
- 不引入当前无必要的大型依赖。
- 不重构已经稳定的模块，除非本轮确有必要。
- 如果必须修改第一轮架构，说明原因及影响。

特别检查：

- Pydantic / PyMongo 类型转换
- bool 与 number 的关系
- ObjectId
- UTC 时间
- option/question id 冲突
- schema_version 原子更新或并发安全
- MongoDB 更新操作不要意外覆盖其他 survey 字段

====================
十二、执行与交付
====================

实施前先检查 Git 状态和当前项目。

如果项目当前不是 Git 仓库，记录事实，不要擅自创建远程仓库。

执行：

- 代码修改
- 静态/编译检查
- pytest
- 真实 MongoDB 测试
- 必要的实际 API 启动验证

所有失败必须真实记录并修复后重新执行。

完成后返回：

A. 本轮设计说明

B. 修改/新增文件

C. 最终 Question 数据结构

D. Validation Engine 实现方式

E. schema_version 实际行为

F. 题目 API

G. survey 删除保护策略

H. 实际执行命令

I. pytest 完整最终结果与退出码

J. 真实 MongoDB 测试结果

K. 启动/API 实际验证结果

L. ai-log 更新说明

M. 本轮遇到的实际错误与修正

N. 尚未实现内容和下一阶段风险

不要只提供摘要。

如果执行过程中出现报错，请保存原始错误信息，不要只返回改写后的描述。
````

### AI 实际修改/新增

```text
修改：
README.md
app/routers/surveys.py
app/schemas/survey.py
app/services/surveys.py
app/services/validation.py
tests/smoke_startup.py
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md
docs/file-manifest.txt

新增代码/测试：
app/schemas/question.py
app/services/questions.py
tests/test_questions.py
tests/test_validation.py
tests/smoke_questions.py

新增本轮证据/报告：
docs/iteration-2/baseline-hashes.json
docs/iteration-2/baseline-preservation.txt
docs/iteration-2/changed-files.txt
docs/iteration-2/commands.md
docs/iteration-2/compile.txt
docs/iteration-2/delivery-report.md
docs/iteration-2/errors-original.md
docs/iteration-2/git-status.txt
docs/iteration-2/pip-check.txt
docs/iteration-2/prompt-original.txt
docs/iteration-2/pytest-baseline.txt
docs/iteration-2/pytest-final.txt
docs/iteration-2/pytest-first.txt
docs/iteration-2/startup-first.txt
docs/iteration-2/startup-server.txt
docs/iteration-2/test-counts.json
docs/iteration-2/verification.json

```

AI 实际设计：QuestionDefinition 严格字段类型，跨字段配置规则和答案规则统一在 validation.py；Question/Option 稳定字符串 ID；题目嵌入 surveys.questions；order 连续重排；service 调用 owner 权限并以版本/状态 CAS 原子提交，单次有效结构变更版本 +1。published 允许编辑，closed 题目只读，原状态机不变。已有答卷阻止 survey 物理删除，不级联。未来已校验 jump_rules 可复用 commit_structure，没有提前实现跳转引擎。

架构影响限于必要扩展：现有 survey router 加 3 个转发接口；SurveyOut 使用 QuestionDefinition；survey 删除 service 加 response 检查；validation 占位模块落实为 engine；新增 questions service。smoke_startup.py 只增加可选 extension/log_name，以复用既有真实启动框架而不复制整段启动逻辑，原无参数入口与基础流程保留。main/core/auth/model、原 test_system.py 与 conftest.py 均未改动，SHA256 核对在 baseline-preservation.txt。

### 实际问题、处理与修正

- Git 返回原文 `fatal: not a git repository (or any of the parent directories): .git`，退出码 128。这是现有环境事实，不是测试失败；保存 git-status.txt/errors-original.md 后继续本地修改，无创建远程仓库。
- 本轮编译、基线测试、首轮扩展测试、最终测试和真实 API 检查均首次执行即通过，没有失败 traceback，没有编造 AI 出错或人工修改。
- 实现时对 bool/int、NaN/Infinity、超 BSON int64 整数显式拒绝；通过边界检查补充非必答非空白/空白文本仍应按长度校验、HTTP 非有限数值错误安全序列化、题型/options/validation 变化以及并发更新测试。这些是本轮设计/自查补强，不伪称为已发生的测试报错。
- 仍有既有第三方 Starlette/httpx 与 mongomock 弃用警告；原样保存，不屏蔽、不为本轮额外升级依赖。

### 实际验证

- 修改前：70 passed, 183 warnings in 6.94s，退出码 0。
- 第一轮扩展：208 passed, 479 warnings in 15.06s，退出码 0。
- 最终：220 passed, 541 warnings in 16.60s，退出码 0。原有 70 + 新 API 70 + engine 80；存储相关真实 MongoDB 70、mongomock 70，纯 engine 不重复计后端。
- Python 3.12.14、MongoDB 9.0.2 真实连接；pip check 输出 No broken requirements found.；compileall 退出码 0。
- 真实 Uvicorn 进程：REAL_QUESTION_API_SMOKE=PASS、REAL_UVICORN_SMOKE=PASS，退出码 0；包括增改删、published 编辑、closed 拒绝、元信息不增版本、历史答卷删除保护及第一轮基础流程；验证后临时进程和随机测试库已清理。

### 未解决与未实现

本轮不实现公开填写、正式 response 提交、统计、跳转执行或复杂编辑器。版本数字已递增但未保存历史结构快照，正式提交前需实现旧版本解释策略。当前删除检查是先查后删，未来并发 response 提交必须协调跨集合原子性。匿名、重复提交及 deadline 在正式提交时执行。第三方弃用警告尚存。未发生人工修改，不对用户个人设计/操作作推测。


## 2026-10-16：第三轮，历史 Schema / Jump / 公开填写与 Response

工具：Codex。本轮按完整粘贴要求继续修改既有 D:/Codex/survey-system；未重建、未更换已有技术栈、未使用子代理、未新增依赖或远程仓库。

### 完整 Prompt 原文

本轮用户粘贴附件原样保存 iteration-3/prompt-original.txt，按字节核对一致；下文全文保存，不虚构 Prompt：

````text
继续开发现有项目：

D:\Codex\survey-system

这是第三轮增量开发。

第一轮和第二轮已经完成并通过验收。

当前测试基线：

220 passed

包括：
- 第一轮原有测试 70 项
- 第二轮题目/API/并发测试 70 项
- validation engine 测试 80 项

严禁重建项目或推倒已有结构。

实施前先完整只读检查：

- 当前源码
- tests
- README
- docs
- MongoDB 索引
- survey/question service
- validation engine
- schema_version 实现

确认现状后在已有设计上继续。

本轮核心目标：

1. 保存不可变问卷 Schema 历史快照
2. 实现 Jump Rule 数据模型与管理
3. 实现 Jump Engine
4. 实现公开问卷读取
5. 实现最小可用公开填写页面
6. 实现 Response 正式提交
7. 落实匿名、截止时间和重复提交规则
8. 保证历史版本 Response 可正确解释
9. 补齐真实 MongoDB 和并发测试

本轮不要实现统计模块。

统计留到下一轮。

==================================================
一、历史 Schema：survey_versions
==================================================

新增 MongoDB collection：

survey_versions

建议结构：

{
    "_id": ObjectId,
    "survey_id": ObjectId,
    "schema_version": 12,
    "questions": [...],
    "jump_rules": [...],
    "created_at": UTC datetime,
    "created_reason": "publish | question_change | jump_rule_change"
}

要求：

建立唯一复合索引：

(survey_id, schema_version)

survey_versions 中的记录必须视为 immutable。

创建后不得修改历史 snapshot。

当前 surveys collection 继续保存当前最新版数据。

不要把所有历史版本无限嵌入 survey 主文档。

==================================================
二、Snapshot 创建策略
==================================================

draft 阶段：

题目可以继续编辑。
schema_version 保持现有第二轮行为继续递增。
不要求每一次 draft 修改都创建 snapshot。

首次：

draft → published

时：

必须为当前 schema_version 创建 snapshot。

只有成功保存 snapshot 后才能完成 publish。

published 状态下：

如果题目或 jump rule 被修改：

- schema_version +1
- 保存新版本完整 snapshot

必须保证新版本 survey 不会处于：

schema_version 已经更新
但对应 snapshot 不存在

的状态。

不要默认 MongoDB standalone 支持 multi-document transaction。

优先采用：
- 唯一索引
- optimistic concurrency
- 明确写入顺序
- 必要的失败补偿

完成一致性保护。

如果本机 MongoDB 实际配置支持 transaction，也不要让系统强依赖 replica set，除非确实必要并明确说明。

snapshot 写入失败时，不能静默继续。

==================================================
三、历史版本读取
==================================================

提供 service：

get_survey_version(survey_id, schema_version)

要求：

- published 过的版本可以读取。
- 不存在的版本返回明确错误。
- snapshot 不能被客户端修改。
- response 后续通过 survey_id + schema_version 找到原始结构。

公开问卷 API 返回当前：

schema_version

客户端提交时必须携带其实际加载的 schema_version。

例如：

{
  "schema_version": 12,
  "answers": ...
}

服务器提交时使用：

survey_versions version 12

进行验证和路径计算。

不要直接使用当前 survey 最新 questions 来解释旧版本答卷。

==================================================
四、Jump Rule 数据模型
==================================================

jump_rules 继续嵌入 surveys。

每条规则：

{
    "id": "r_xxx",
    "source_question_id": "q1",
    "operator": "equals",
    "value": "...",
    "target_question_id": "q5",
    "priority": 1
}

rule id 为稳定字符串。

如果用户没有指定合法 ID，由服务端生成。

同一 survey 内 rule id 唯一。

同一个 source question 的 priority 必须具有确定顺序。

建议禁止同 source 下重复 priority，或提供明确稳定的 tie-break 规则。

不要依赖 MongoDB 数组当前物理顺序决定执行优先级。

==================================================
五、允许的 Jump 条件
==================================================

single_choice：

equals

value 必须是 source question 中实际存在的 option id。

multiple_choice：

contains

value 必须是 source question 中实际存在的 option id。

number：

equals
greater_than
greater_than_or_equal
less_than
less_than_or_equal

value 必须是有限合法数字。

禁止 bool、NaN、Infinity 和超出系统正常数字范围的异常值。

text：

本阶段不能作为 jump rule source。

未知 operator 必须拒绝。

operator 必须与 source question 类型匹配。

==================================================
六、Jump Rule Definition Validation
==================================================

新增统一业务校验，不要把逻辑散落在 router。

至少检查：

- source_question_id 是否存在
- target_question_id 是否存在
- source != target
- source 类型是否支持跳转
- operator 是否适用于 source type
- rule value 是否适用于 operator
- choice rule value 是否对应合法 option
- priority 是否合法
- rule id 是否重复

本阶段只允许前向跳转：

target_question.order > source_question.order

如果 target 位于 source 前面或相同位置：

拒绝规则。

这样第一阶段问卷流程保持无环。

Jump Engine 仍须保留 runtime visited/max-step 防护，不能单纯相信配置永远合法。

==================================================
七、Jump Rule API
==================================================

在现有 owner 权限模型基础上实现：

POST
/api/surveys/{survey_id}/jump-rules

PUT
/api/surveys/{survey_id}/jump-rules/{rule_id}

DELETE
/api/surveys/{survey_id}/jump-rules/{rule_id}

要求：

- 必须登录。
- 只能修改自己的 survey。
- draft 可以编辑。
- published 可以编辑，并产生新 schema_version + snapshot。
- closed 不允许编辑。
- 非法 survey id 不产生 500。
- 不存在 rule 返回明确错误。
- 一次 API 操作最多 schema_version +1。

published 状态修改 jump rule 后，新版本 snapshot 必须保存。

==================================================
八、Question 与 Jump Rule 引用完整性
==================================================

第三轮开始，question 修改必须考虑 jump rule。

如果删除的 question：

- 被作为 source
或
- 被作为 target

则禁止删除。

返回 HTTP 409。

不要静默删除关联 rule。

提示用户先删除相关 jump rule。

如果修改：

- question type
- options
- option id
- number 类型等

会导致现有 jump rule 不再合法：

拒绝该 question 修改。

不要自动删除 jump rule。

仅修改 question title 等不会破坏规则的字段，应正常允许。

确保失败操作：

- question 不改变
- schema_version 不增加
- snapshot 不创建

==================================================
九、Jump Engine
==================================================

核心逻辑放入独立 service，例如：

app/services/jump_engine.py

不要放进 router。

提供类似：

resolve_next_question(
    survey_definition,
    current_question_id,
    answer
)

规则：

1. 取得 current question 对应 rules。
2. 按 priority 确定顺序。
3. 依次判断。
4. 第一个匹配 rule 生效。
5. 返回 target question。
6. 如果无 rule 匹配，返回 order 下一题。
7. 如果当前已经是最后一题，返回完成状态。

同时提供完整路径验证能力，例如：

build_response_path(...)
或
validate_response_path(...)

实际命名可结合现有架构。

必须能够根据：

snapshot questions
snapshot jump_rules
answers

从第一题推导出用户实际应该访问的问题序列。

必须有 visited set 或最大步数保护。

不允许死循环导致请求卡死。

==================================================
十、答案与路径一致性
==================================================

正式 response 提交必须同时验证：

1. answer 本身合法
2. 用户实际答案符合 Jump Engine 得出的路径

假设：

Q1 -> Q5

则 Q2、Q3、Q4 为 skipped。

对 skipped question：

即使它们 required=true，也不能要求填写。

同时禁止客户端额外提交 skipped question 的答案。

否则统计会被污染。

例如：

实际路径：

q1
q5
q6

客户端 answers 包含：

q1
q2
q5
q6

必须拒绝或明确剔除。

优先选择拒绝，并返回清晰错误。

对实际访问的问题：

required=true 必须回答。

optional 问题可以缺失。

Jump Engine 根据实际有效 answer 判断下一题。

==================================================
十一、公开问卷读取
==================================================

实现公开访问。

至少提供 API：

GET
/api/public/surveys/{public_token}

返回当前可填写版本：

- survey id 或必要公开标识
- title
- description
- schema_version
- questions
- 必要 jump 信息或前端填写需要的信息

但不要暴露：

- owner 的敏感信息
- password/session
- 与填写无关的内部字段

只有：

status = published

且未超过 deadline

才能正常进入填写状态。

closed：

不可填写。

deadline 已过：

不可填写。

不存在 token：

返回 404。

==================================================
十二、公开填写页面
==================================================

实现最小可用：

/survey/{public_token}

Jinja2 + 原生 HTML/CSS/少量 JavaScript 即可。

不要引入 React/Vue。

要求：

- 可以显示标题和说明
- 可以显示四类题型
- 可以按题回答
- 能调用 Jump Engine/API 进入正确下一题
- validation 错误能够显示
- 最终可以提交

页面不需要漂亮。

功能正确优先。

复杂问卷编辑器仍不要求本轮实现。

==================================================
十三、Response 正式数据模型
==================================================

responses 最终至少保存：

{
    "_id": ObjectId,
    "survey_id": ObjectId,
    "respondent_user_id": ObjectId | null,
    "survey_schema_version": int,
    "answers": [
        {
            "question_id": "...",
            "value": ...
        }
    ],
    "visited_question_ids": [...],
    "submitted_at": UTC datetime,
    "dedupe_key": optional string
}

如果现有 response model 结构略有不同，可合理兼容，不要为字段名字无意义地大规模重构。

必须可以通过：

survey_id
survey_schema_version

找到历史 snapshot。

不要复制整份 survey schema 到每条 response，除非现有实现有强理由。

==================================================
十四、Response 提交 API
==================================================

实现：

POST
/api/public/surveys/{public_token}/responses

或保持现有 API 风格中的合理等价路径。

请求至少包含：

schema_version
answers

完整行为：

1. 查当前 survey。
2. 检查 status。
3. 检查 deadline。
4. 检查匿名权限。
5. 读取用户提交的 schema_version snapshot。
6. 确认该 snapshot 属于当前 survey。
7. 使用历史 snapshot 的 question definition 校验 answers。
8. 使用历史 snapshot 的 jump_rules 重建实际路径。
9. 验证 required。
10. 验证没有 skipped/extraneous answers。
11. 生成 response。
12. 保存。
13. 返回提交成功结果。

重要：

如果当前 survey 已经升级到 version 13，
用户提交 version 12：

只要：
- version 12 snapshot 存在
- survey 当前仍 published
- deadline 未过
- 其他提交策略允许

则允许按照 version 12 提交。

这用于支持用户打开问卷后，管理员修改问卷的情况。

==================================================
十五、匿名策略
==================================================

沿用之前确认的规则：

allow_anonymous = false

未登录：

拒绝填写/提交。

登录：

允许。

allow_anonymous = true

未登录：

允许，respondent_user_id = null。

登录：

允许，记录 respondent_user_id。

不要声称系统能够可靠识别同一个匿名用户。

匿名用户的重复提交无法通过身份精确限制。

把这个限制写入文档。

==================================================
十六、重复提交
==================================================

登录用户：

allow_multiple_submissions = true

允许同一用户多次 response。

allow_multiple_submissions = false

同一用户只能成功提交一次。

不能仅依赖：

查询是否已有 response
然后 insert

因为存在并发竞态。

为需要禁止重复提交的登录 response 生成：

dedupe_key

例如：

survey:<survey_id>:user:<user_id>

建立：

unique sparse index

或合理的 partial unique index。

只有需要去重的 response 存 dedupe_key。

并发双提交时：

只能一个成功。

另一个返回合理冲突，例如 409。

匿名 response 不使用该身份 dedupe_key。

==================================================
十七、deadline
==================================================

deadline 统一按当前项目 UTC 策略处理。

提交时服务器必须重新检查 deadline。

不能只在加载页面时检查。

如果：

now > deadline

拒绝提交。

明确测试：

- deadline 之前成功
- deadline 已经过期失败
- deadline 为空正常

避免 naive datetime 与 aware datetime 混用。

==================================================
十八、Survey DELETE 策略调整
==================================================

第二轮已经发现：

“先查询 responses，再删除 survey”

存在提交/删除跨集合竞态。

第三轮调整业务规则：

只有 draft survey 可以物理 DELETE。

published：

禁止 DELETE。

提示先关闭问卷。

closed：

禁止物理 DELETE。

保留历史数据。

正式 response 只能提交给 published survey。

因此合法 response 与可物理 DELETE survey 在业务状态上互斥。

请调整现有 DELETE 行为、测试和文档。

如果历史测试依赖合理旧行为，需要更新对应测试并明确说明为什么业务规则发生变化。

不要为了保持一个非课程核心 API 的旧行为而引入分布式锁或强制 MongoDB replica set。

==================================================
十九、测试要求
==================================================

第二轮基线 220 项。

第三轮新增测试必须覆盖实际业务语义。

至少覆盖以下类别。

survey_versions：

- publish 时生成 snapshot
- snapshot version 正确
- snapshot questions 正确
- snapshot immutable
- 同一 survey/version 唯一
- published question 修改后产生新 snapshot
- published jump rule 修改产生新 snapshot
- snapshot 写入失败不会留下 survey 指向不存在版本
- draft 修改不必生成无意义 snapshot

jump rule definition：

- 合法 single equals
- 非法 single operator
- option 不存在
- 合法 multiple contains
- 非法 multiple value
- 合法 number comparison
- number value bool 被拒绝
- NaN/Infinity 被拒绝
- text 作为 source 被拒绝
- source 不存在
- target 不存在
- self jump 被拒绝
- backward jump 被拒绝
- duplicate rule id
- priority 行为确定

jump engine：

- 无 rule 顺序前进
- single 命中
- single 未命中
- multiple contains 命中
- number >、>=、<、<=、equals
- 多 rule 按 priority 选择第一个匹配
- 最后一题结束
- visited/max-step 防护

引用完整性：

- 被 rule 引用的 question 不可删除
- 修改 question type 导致 rule 非法时拒绝
- 删除 rule 后可删除 question
- 失败修改不增加 schema_version

public survey：

- 正确 token
- 非法 token
- draft 不能填写
- closed 不能填写
- deadline 过期
- published 正常
- schema_version 正确

response：

- 普通顺序问卷提交
- jump 后提交
- skipped required 不要求填写
- skipped answer 被拒绝
- visited required 缺失
- optional 缺失
- single/multiple/text/number validation
- 保存 survey_schema_version
- visited path 保存正确
- 历史 version response 提交成功
- 不存在历史版本失败

anonymous：

- allow_anonymous=false 未登录失败
- allow_anonymous=false 登录成功
- allow_anonymous=true 匿名成功
- 匿名 respondent_user_id=null

multiple submissions：

- allow_multiple=true 登录用户可多次
- allow_multiple=false 第二次失败
- 两个并发相同登录提交只能一个成功
- 匿名不伪造身份去重

deadline：

- 未到截止时间成功
- 已过截止时间失败
- 无 deadline 成功

delete：

- draft 可删除
- published 不可物理删除
- closed 不可物理删除

必须尽可能同时覆盖：

mongomock
真实 MongoDB

纯 Jump/Validation 测试无需为了数字重复执行。

==================================================
二十、真实 API / Uvicorn Smoke Test
==================================================

实际启动 Uvicorn。

至少实际完成一次：

注册
→ 登录
→ 创建 survey
→ 添加问题
→ 添加 jump rule
→ publish
→ 获取公开页面/API
→ 按跳转路径填写
→ submit
→ MongoDB 中确认 response
→ 修改 published survey
→ 产生新 schema_version/snapshot
→ 使用旧 schema_version 再完成一次合法提交
→ close
→ 再次提交被拒绝
→ logout

记录真实输出。

测试后清理随机测试数据库。

==================================================
二十一、文档
==================================================

更新：

README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md

新增并说明：

- survey_versions
- schema snapshot 生命周期
- Jump Rule schema
- Jump Engine
- 历史版本 response
- 匿名填写策略
- 重复提交限制
- deadline
- draft/published/closed 删除策略
- 已知限制

database-design.md 必须解释：

为什么：
- current survey 与 historical snapshot 分离
- response 不嵌 survey
- response 不复制完整 schema
- schema_version 如何关联 snapshot
- 为什么 anonymous 无法可靠限制同一人重复提交

==================================================
二十二、AI 日志
==================================================

继续追加：

docs/ai-log.md

必须保存：

- 本次完整 Prompt
- AI 实际设计
- AI 创建和修改文件
- 实际测试
- 实际失败
- 实际修正
- 未解决问题

不要虚构失败。

不要虚构人工参与。

==================================================
二十三、质量检查
==================================================

重点检查：

- ObjectId
- UTC datetime
- bool vs number
- NaN / Infinity
- BSON int64
- schema_version
- snapshot 唯一性
- published 并发修改
- jump priority
- stale version submission
- duplicate submission race
- public/private 字段泄露
- owner 权限
- deadline race
- MongoDB unique index errors

不要：

- catch-all 后假装成功
- 硬编码针对测试
- 在 router 复制 validation/jump 逻辑
- 引入 React/Vue
- 引入 Redis/Celery
- 引入无必要微服务
- 为 DELETE 加复杂分布式架构

==================================================
二十四、最终交付
==================================================

完成后返回：

A. 本轮总体设计

B. 新增/修改文件

C. survey_versions 最终模型

D. snapshot 创建及一致性方案

E. Jump Rule 最终模型

F. Jump Engine 行为

G. Question/Jump 引用完整性策略

H. Public Survey API

I. Response 最终模型

J. Response 提交流程

K. 匿名/登录策略

L. 重复提交并发保护

M. deadline 行为

N. DELETE 新策略

O. 实际执行命令

P. pytest 最终结果、数量和退出码

Q. 真实 MongoDB 测试结果

R. Uvicorn/真实 API smoke test

S. AI 日志更新

T. 本轮所有真实错误与修正

U. 仍未实现功能和下一阶段风险

原始错误及 pytest 完整输出继续保存到：

docs/iteration-3/

不要只返回概述。
````

### 实际文件改动

```text
修改既有源码/启动脚本：
app/core/database.py
app/core/security.py
app/main.py
app/models/response.py
app/routers/responses.py
app/routers/surveys.py
app/schemas/response.py
app/schemas/survey.py
app/services/jump_engine.py
app/services/questions.py
app/services/surveys.py
app/static/style.css
tests/smoke_questions.py
tests/smoke_startup.py

新增源码/测试：
app/schemas/jump_rule.py
app/services/jump_rules.py
app/services/responses.py
app/services/versions.py
app/static/survey.js
app/templates/survey.html
tests/smoke_responses.py
tests/test_jumps.py
tests/test_public_responses.py

更新文档：
README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md
docs/file-manifest.txt

新增证据目录：docs/iteration-3/

```

所有本轮测试、原始命令、环境、原始错误、首次失败与最终成功输出保存在 docs/iteration-3/，旧两轮日志/报告保留。原 test_system.py、test_questions.py、test_validation.py 与 conftest.py 均未改动，原 220 项继续通过。唯一旧 smoke 业务调整是把保护答卷用的 survey 先发布，符合本轮 response 只属于 published 的新政策；启动 helper 仅修 readiness 的明确网络异常重试。

### 实际设计

survey_versions 独立、不可变、(survey_id,schema_version) 唯一。draft 仍只加版本；publish/published 编辑先在 survey 文档 CAS 预留单个 pending 操作，先 insert snapshot，后 CAS 切换当前指针，出错保留旧版本并通过后续请求恢复。MongoDB hello 无 setName，实际为 standalone，不依赖事务/replica set。恢复不覆盖快照，多个协助者按唯一键和 operation ID 幂等；恢复推进版本后旧数组必须 409，禁止隐式 rebase。

Jump Rule 统一校验 ID、source/target/order、operator/value、priority；仅前向，按 priority 首匹配；运行路径有 visited/max-step。question 修改后校验现有规则，破坏引用直接 409，不写版本/快照，不静默清规则。

公开 API 字段白名单，Jinja2+原生 JS 逐题填写，next 调用服务端引擎，最终提交重新用请求的历史 snapshot 校验内容及路径。响应只保存 schema_version 引用、答案和访问路径。匿名记录 null，登录记录真实 ID；禁止多次时数据库 dedupe sparse unique 处理并发，不伪称匿名可精确识别。deadline 在最终准入点复查并处理 BSON 毫秒精度；准入后关闭不撤销已准入请求。

DELETE 改为仅 draft 且无 pending/异常历史答卷可物理删除；published/closed 保留。因此合法 submit 与物理 delete 在状态上互斥，不引入分布式锁或事务设施。

### 实际问题、修正与验证

1. Git 状态检查返回非仓库，退出码 128；如实保留，不创建 Git/远程仓库。
2. 修改前基线：220 passed, 541 warnings in 28.92s，退出码 0。
3. 核心实现接入后原 220 项通过；首轮新增测试 347 passed, 1454 warnings in 51.04s，退出码 0。
4. 首次真实 Uvicorn 探测失败，httpx.ConnectTimeout，退出码 1；服务日志已 startup complete。完整 traceback 在 startup-first.txt/errors-original.md。实际修正：loopback HTTP 不使用环境代理、缩短每次连接探测超时、对 ConnectTimeout/ConnectError 作有界重试，超限仍失败；随后完整流程两次通过，未声称最初超时已被证明由代理导致。
5. 自查修正：将 Pydantic 解析后的默认 priority 规范化入库；为 hidden 元素补 display:none 防止原 form 样式覆盖；准入查询下界向上取整到 BSON 毫秒；恢复后版本已变化时拒绝旧题目数组重定基。这些是实际发现并修改的边界问题，不编造成曾发生的 pytest 失败。
6. 增加默认值、非有限 HTTP JSON、跨 survey 版本、deadline 前后 1μs/等于、快照返回对象不改库以及恢复重定基用例。中间 367 项通过；最终 369 passed, 1687 warnings in 64.85s (0:01:04)，退出码 0。
7. 新公开/存储 API 110、纯 Jump 39；加原 220 总 369。存储部分真实 MongoDB 125、mock 125；纯校验/跳转 119 不重复套后端。全体测试使用既有 db fixture，没有复制测试文件制造计数。
8. 故障注入主动抛 OperationFailure：snapshot 写失败、指针切换失败、publish snapshot 失败，验证 503/版本不推进/恢复。pytest-runtime-final.log 原始 ERROR 是预期测试证据，不是虚构的生产异常。
9. 真实 Uvicorn 完成注册→登录→题目→规则→发布→公开读取→跳转→提交→MongoDB 核验→改 published→新快照→旧版再提交→关闭→拒绝提交→登出，REAL_RESPONSE_API_SMOKE 与 REAL_UVICORN_SMOKE 均 PASS，退出码 0；清理临时进程与随机库。实际确认唯一 snapshot 索引与 sparse unique dedupe 索引。
10. compileall、pip check、JS 语法检查退出码均 0；第三方弃用警告仍保留，未抑制。没有人工修改记录，不编造人工参与。

### 未解决与下一阶段

未实现统计、复杂编辑器、自动化真实浏览器点击与压力测试。匿名无法可靠识别同一人；允许多次/匿名请求暂无通用幂等键，网络重试可能多条。snapshot 不可变由业务代码与受控 DB 写权限保证，数据库管理员直接改写不受 API 约束。pending 可能在故障后等待下一请求恢复，503 不代表永久撤销。历史系统只可补当前已发布定义，无法重造先前未保存的 schema。大文档需考虑 pending 暂存与 MongoDB 16 MB 限制。准入时间早于关闭的请求允许随后落库，不宣称跨集合事务。


### 第三轮交付前补充：分享链接安全读取

自查发现原同源 dependency 同时拦截 GET，会使携带 Sec-Fetch-Site:cross-site 的外站分享链接无法打开。实际修正为 GET/HEAD/OPTIONS 安全方法不执行写操作同源拦截，POST/PUT/DELETE 继续检查。新增一项共享业务测试分别在 mock/真实 MongoDB 上验证：外站 GET 页面/API 成功，跨站 POST 提交仍 403。此问题为自查发现，未伪称曾出现失败的 pytest。

实际再次 compileall、完整 pytest、真实 Uvicorn smoke：最终 **371 passed, 1706 warnings in 62.19s (0:01:02)，退出码 0**；原 220、新公开/持久化 112、新纯 Jump 39；真实 MongoDB 126、mock 126，纯 Validation/Jump 119。真实 smoke 再次通过，退出码 0。当前最终结果以此补充为准，之前 369 项是交付检查中间结果，原文已归档。完整最终输出/错误/报告同步更新在 iteration-3。


## 2026-10-16：第四轮，动态统计与最小管理网页

工具：Codex；本轮在 D:/Codex/survey-system 原项目上开发，未重建、未创建 Git/远程仓库、未新增依赖、未使用子代理。原统计 service/router 是占位模块，本轮落实；原公开填写页和核心认证/Validation/Jump/快照/提交服务保持原样。

### 完整 Prompt 原文

用户粘贴文本逐字保存 iteration-4/prompt-original.txt，已与原附件按字节比对一致；全文如下，不杜撰 Prompt：

````text
继续开发现有项目：

D:\Codex\survey-system

这是第四轮增量开发，也是第一阶段项目最后一轮主要功能开发。

前三轮已经完成并通过验收。

当前测试基线：

371 passed

严禁重建项目、推倒现有架构或无必要重构已经稳定的核心模块。

本轮主要目标：

1. 实现统计系统
2. 实现整份问卷统计
3. 实现单题统计
4. 正确处理历史 schema_version
5. 补齐管理端最小可用 Web UI
6. 完成从创建到统计的网页业务闭环
7. 完成最终功能级回归测试

本轮不要增加与课程要求无关的复杂功能。

不要实现：
- React
- Vue
- 数据可视化大型框架
- Redis
- Celery
- 消息队列
- 微服务
- 实时统计缓存系统
- NLP 文本分析
- 复杂图表系统

统计与管理页面以正确、清楚、可演示为目标。

==================================================
一、实施前检查
==================================================

首先只读检查现有：

- app/
- tests/
- templates/
- static/
- MongoDB collections/indexes
- survey_versions
- responses
- jump engine
- question validation
- survey/question/jump/response service
- public API
- 现有管理页面
- README
- docs

确认当前 371 项基线及现有 UI 后再修改。

不要修改前三轮测试来掩盖回归。

==================================================
二、统计总体原则
==================================================

统计数据来源：

responses

题目结构来源：

survey_versions

不要依赖当前 surveys.questions 去解释历史 response。

不要建立写入时维护的永久统计计数器。

不要在 response 提交时执行：

count += 1

本阶段统计应根据已经保存的 response 动态计算。

原因：

系统支持历史 schema_version，同一个 question_id 在不同版本中可能：

- options 不同
- validation 不同
- 类型不同
- 不存在

强行跨不兼容版本合并会产生错误统计语义。

因此统计必须按 schema_version 明确分组。

==================================================
三、整份问卷统计 API
==================================================

实现或完善：

GET /api/surveys/{survey_id}/stats

必须登录。

必须是 survey owner。

非 owner 保持现有权限策略，例如返回 404。

非法 survey ObjectId 不得产生 500。

建议返回结构：

{
  "survey_id": "...",
  "total_responses": 30,
  "versions": [
    {
      "schema_version": 3,
      "response_count": 20,
      "questions": [...]
    },
    {
      "schema_version": 4,
      "response_count": 10,
      "questions": [...]
    }
  ]
}

要求：

total_responses：

统计该 survey 的全部合法已保存 response。

versions：

按 survey_schema_version 分组。

每一个 version 必须使用对应：

survey_versions

中的 immutable snapshot 解释题目。

不要使用当前 survey 最新结构解释旧答卷。

没有 response 的当前 published version，如果合理，可以返回零统计，但行为必须文档化并保持一致。

==================================================
四、单题统计 API
==================================================

实现或完善：

GET /api/surveys/{survey_id}/questions/{question_id}/stats

必须 owner 才能访问。

返回所有存在该 question_id 且有统计意义的历史 schema version。

例如：

{
  "survey_id": "...",
  "question_id": "q1",
  "versions": [
    {
      "schema_version": 3,
      "question": {...},
      "response_count": 12,
      "statistics": {...}
    },
    {
      "schema_version": 4,
      "question": {...},
      "response_count": 6,
      "statistics": {...}
    }
  ]
}

如果同一个 question_id 历史上改变了 type：

不要合并统计。

分别返回各 schema_version 的结果。

如果 question 在某些版本不存在：

不要伪造零值题目。

==================================================
五、single_choice 统计
==================================================

对单选题至少统计：

- answered_count
- 每个 option 的 count

结构可类似：

{
  "type": "single_choice",
  "answered_count": 20,
  "options": [
    {
      "option_id": "a",
      "label": "苹果",
      "count": 12
    },
    {
      "option_id": "b",
      "label": "香蕉",
      "count": 8
    }
  ]
}

必须使用该 snapshot 中的 option 定义及 label。

不得使用当前最新 survey option label 覆盖历史版本。

如果 response 中出现违反历史 snapshot 的数据：

正常情况下不应发生。

统计 service 不要静默把未知 option 计入一个不存在的合法选项。

采取明确策略并测试，例如：
- 忽略并记录异常
或
- 抛出数据一致性错误

优先选择不会产生错误正常统计结果的安全策略。

==================================================
六、multiple_choice 统计
==================================================

至少统计：

- answered_count
- total_selections
- 每个 option 被选择次数

例如一个 respondent：

["a", "b", "c"]

则：

answered_count +1
total_selections +3

每个对应 option count +1。

不要把多选题：

选项被选择次数

错误解释为：

有多少份 response。

==================================================
七、text 统计
==================================================

至少返回：

- answered_count
- 所有有效文本内容 values

例如：

{
  "type": "text",
  "answered_count": 5,
  "values": [
    "文本1",
    "文本2"
  ]
}

optional 且没有答案：

不计入 answered_count。

skipped question：

不计入。

不要做 NLP、关键词提取或词云。

==================================================
八、number 统计
==================================================

至少返回：

- answered_count
- values
- average

可以额外返回：

- min
- max

但不是强制。

average：

只根据实际存在的合法数字答案计算。

没有数字回答时：

不要出现除零问题。

明确设计：

average = null

或等价安全表达。

必须处理：

- integer
- float
- bool 不得被当作 number
- 非有限数不应存在

如果数据库出现异常历史数据，采取明确安全策略。

==================================================
九、跳转与统计
==================================================

统计以实际 response.answers 为准。

被跳过的问题：

没有 answer

因此：

- 不计入 answered_count
- 不计入选项次数
- 不进入 text values
- 不进入 number average

不要根据所有 response 数量推断每题回答人数。

例如：

100 人提交问卷

只有 30 人经过 q5

则：

q5 answered_count 最大应是 30

而不是 100。

==================================================
十、历史版本统计
==================================================

这是本轮重点。

例如：

version 2：

q1 single_choice
A
B

version 3：

q1 single_choice
A
B
C

version 4：

q1 number

必须分别统计：

version 2 q1
version 3 q1
version 4 q1

禁止生成一个混合 q1 统计。

整份问卷统计必须包含所有有 response 的历史版本，而不是只统计当前版本。

这样旧填写数据不会因为问卷升级而消失。

==================================================
十一、统计 Service
==================================================

核心统计逻辑放入独立 service，例如：

app/services/statistics.py

Router 只负责：

- authentication
- owner dependency
- 参数
- 返回结果

不要在 router 中编写大量：

if question.type == ...

避免不同 API 各复制一套统计逻辑。

建议提供可复用函数，例如：

compute_question_statistics(...)
compute_version_statistics(...)
compute_survey_statistics(...)

具体命名结合现有架构即可。

==================================================
十二、MongoDB 查询
==================================================

检查现有：

responses.survey_id

索引。

如果必要，增加合理复合索引，例如：

(survey_id, survey_schema_version)

不要为了课程规模设计复杂物化视图。

当前统计可以：

1. 查询目标 response
2. 按 schema_version 分组
3. 加载 snapshot
4. 在 service 层计算

如果使用 MongoDB aggregation pipeline 也可以，但必须保持代码可理解。

优先正确性和可维护性。

==================================================
十三、统计权限
==================================================

统计属于问卷创建者。

以下 API：

/api/surveys/{survey_id}/stats

/api/surveys/{survey_id}/questions/{question_id}/stats

只有 owner 能访问。

普通填写用户：

不能通过 public token 获取统计。

不要新增公开统计接口。

==================================================
十四、管理端 Web UI
==================================================

使用现有：

Jinja2
HTML
CSS
少量原生 JavaScript

补齐最小可用管理端。

不要引入 React/Vue。

最终通过浏览器至少能够完成：

1. 注册
2. 登录
3. 查看自己的 survey 列表
4. 创建 survey
5. 编辑：
   - title
   - description
   - allow_anonymous
   - allow_multiple_submissions
   - deadline
6. 添加 question
7. 编辑 question
8. 删除 question
9. 创建 jump rule
10. 编辑或删除 jump rule
11. publish
12. 查看并复制 public URL
13. 打开公开填写页面
14. 实际填写并提交
15. 返回管理端
16. 查看统计
17. close survey
18. logout

界面不需要复杂。

目标：

老师无需使用 curl/Postman，也可以完成主要演示流程。

==================================================
十五、Dashboard
==================================================

提供清楚的 survey 管理页面。

每个 survey 至少显示：

- title
- status
- schema_version
- deadline
- public URL（适当状态下）
- 编辑入口
- 统计入口
- publish / close 等合理操作

用户只能看到自己创建的 survey。

不要让页面通过前端隐藏按钮代替服务端权限检查。

==================================================
十六、Survey 编辑页面
==================================================

至少能够管理：

基本信息

questions

jump rules

清楚显示：

- question order
- question type
- required
- options
- validation
- jump rule source/target/operator/value/priority

不要求实现拖拽排序。

如果现有 API 支持 question order 修改，可以使用简单数字输入或上下调整。

UI 必须调用已有后端规则。

不要在 JavaScript 中重新复制完整 Validation Engine。

服务端仍是最终权威。

==================================================
十七、统计页面
==================================================

提供：

/surveys/{survey_id}/stats

或符合当前 Web 路由风格的等价页面。

显示：

- 总答卷数
- schema version 分组
- 各题统计

single_choice：

表格显示 option + count。

multiple_choice：

显示 option + count，并显示 answered_count。

text：

列出实际文本答案。

number：

显示：
- answered_count
- average
- min/max（如果实现）
- 原始数字值（如果界面合理）

历史 schema version：

必须清楚区分。

不要把不同版本的数据视觉上伪装为一个统计。

不要求图表。

简单表格和列表足够。

==================================================
十八、公开填写 UI 回归
==================================================

第三轮已经实现 public page。

本轮不要重写。

只检查并完善：

- 单选
- 多选
- 文本
- 数字
- validation 错误
- Jump
- required
- submit
- 成功提示
- deadline
- closed
- anonymous/login-required

管理页面复制出来的链接必须能够直接进入该 public page。

==================================================
十九、测试要求
==================================================

当前基线：

371 passed

所有合理旧测试必须继续通过。

新增统计测试至少覆盖：

整体：

- 空问卷无 response
- 一个 response
- 多 response
- total_responses
- schema_version 分组
- 多历史版本统计
- 旧版本数据不会丢失

single_choice：

- option counts 正确
- answered_count 正确
- 未回答不计入
- skipped 不计入

multiple_choice：

- option counts
- answered_count
- total_selections
- 一个用户选择多个选项正确累计

text：

- values
- answered_count
- optional missing
- skipped missing

number：

- average
- min/max（如果实现）
- answered_count
- 无回答 average 安全
- int/float

历史版本：

- 同 question id options 改变
- 同 question id type 改变
- 统计按版本分开
- 使用 snapshot label
- 不使用 current survey definition 错误解释旧 response

权限：

- owner 可以查看
- 非 owner 不可以
- 未登录不可以
- public token 不能绕过 owner statistics 权限

single-question API：

- 正确 question
- question 不存在
- 多版本存在
- 部分版本不存在
- 非法 survey id

异常数据：

至少测试统计 service 对不符合 snapshot 的历史异常 answer 有明确行为，不生成看似正常但错误的结果。

==================================================
二十、Web UI 测试
==================================================

使用当前项目已有测试工具验证管理页面至少：

- register 页面正常
- login 页面正常
- dashboard 需要登录
- dashboard 用户隔离
- 创建页面正常
- survey 编辑页面正常
- stats 页面 owner 正常
- 非 owner stats 页面被拒绝
- public link 正确

如果当前环境已有适合的浏览器测试工具，可以增加真实浏览器 smoke。

如果没有，不要为了本轮强制引入 Playwright/Selenium 及大型浏览器依赖。

可以继续采用：

- FastAPI TestClient
- HTTP smoke
- JavaScript syntax check
- 真实 Uvicorn API/browser-route smoke

==================================================
二十一、完整真实 Smoke
==================================================

实际启动 Uvicorn，并连接真实 MongoDB。

执行完整演示链：

注册 owner
→ 登录
→ 创建 survey
→ 修改基本信息
→ 创建四种题型
→ 设置 validation
→ 创建 jump rule
→ publish
→ 获取 public URL
→ 匿名或登录用户按照配置填写
→ jump
→ submit
→ 再填写若干不同答案
→ 回 owner 管理页面
→ 查看整个 survey statistics
→ 查看单题 statistics
→ 检查 option count
→ 检查 number average
→ 修改 published survey
→ 创建新 schema version
→ 使用新版本提交
→ stats 中同时存在旧版与新版
→ close
→ public submit 被拒绝
→ logout

直接检查 MongoDB 中 response 和 snapshot 数据。

记录真实统计结果，与预期人工计算值核对。

不要只检查 HTTP 200。

==================================================
二十二、第一阶段已知风险处理
==================================================

第三轮留下以下项目：

1. 匿名或 allow_multiple=true 时没有通用 idempotency key

本轮不要求增加复杂通用幂等系统。

继续作为已知限制记录。

2. pending 操作故障恢复依赖后续请求

如果现有恢复机制经过测试可用，本轮不重构。

写入文档已知行为。

3. 第三轮之前未 snapshot 的更早 draft schema 无法恢复

由于 draft 不能合法产生 response，因此不影响正常历史答卷解释。

把边界写清楚即可。

4. survey_versions immutable 依赖业务写入控制

本课程环境下保持当前设计。

README/配置说明应提醒：

MongoDB 不应向不可信远程用户开放直接写权限。

不要为此增加数据库代理层。

==================================================
二十三、文档更新
==================================================

更新：

README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md

新增/完善：

统计设计

包括：

- 为什么动态统计
- 为什么按 schema_version 分组
- single/multiple/text/number 各自统计语义
- skipped question 的统计规则
- 历史 snapshot 如何参与统计

Web UI：

说明：

- 管理页面入口
- 注册登录
- 创建问卷
- 发布
- 分享
- 填写
- 查看统计

README 应让教师从零能够：

安装
→ 配置 MongoDB
→ 启动
→ 浏览器使用
→ 测试

==================================================
二十四、AI 日志
==================================================

继续真实更新：

docs/ai-log.md

保留前三轮。

新增第四轮：

- 完整 Prompt
- AI 实际设计
- 修改文件
- 统计实现
- UI 实现
- 测试
- 实际错误
- 实际修正
- 尚存限制

不要虚构错误。

不要虚构人工修改。

==================================================
二十五、代码与报告自然度
==================================================

代码注释继续保持正常学生项目风格：

解释必要设计。

不要加入大量：

- “enterprise-grade”
- “production-ready”
- “robust scalable architecture”
- AI 模板化自夸
- 与课程无关的审计式描述

文档应准确说明设计及原因。

不要把课程作业写成商业系统白皮书。

==================================================
二十六、质量检查
==================================================

重点检查：

- ObjectId
- UTC
- owner 权限
- survey_schema_version
- snapshot
- skipped questions
- historical option label
- question type changed between versions
- empty statistics
- number average precision
- bool
- malformed historic data
- public/private information
- MongoDB indexes
- JS syntax
- HTML escaping
- CSRF/现有 same-origin 策略不被破坏

不要为了 UI 绕过现有 API 权限。

==================================================
二十七、最终执行
==================================================

至少执行：

- Python compileall
- JavaScript syntax check
- pip check
- 完整 pytest
- 真实 MongoDB 测试
- Uvicorn 启动
- 完整业务 smoke
- 统计结果人工预期值核对

测试后：

- 停止临时 Uvicorn
- 清理随机测试库
- 不删除正常项目文件

==================================================
二十八、第四轮交付格式
==================================================

完成后完整返回：

A. 本轮总体设计

B. 新增/修改文件

C. Statistics Service 设计

D. 整份问卷统计行为

E. 单题统计行为

F. 四种题型统计语义

G. 历史 schema_version 统计策略

H. MongoDB 查询与索引

I. 统计权限

J. 管理端页面及路由

K. 问卷编辑 UI

L. 统计 UI

M. 公开填写 UI 回归

N. 实际执行命令

O. pytest 最终结果与退出码

P. 真实 MongoDB 测试结果

Q. Uvicorn 完整业务 smoke

R. 实际统计数值及人工核对结果

S. AI 日志更新

T. 本轮所有实际错误和修正

U. 当前已知限制

V. 第一阶段尚未完成的任何要求

将：

- pytest 完整输出
- 原始错误
- 命令记录
- smoke 输出
- changed files
- 人工统计核对

保存到：

docs/iteration-4/

不要只返回摘要。
````

### AI 实际新增/修改文件

```text
修改原有源码：
app/main.py
app/core/database.py
app/routers/statistics.py
app/services/statistics.py
app/static/style.css
app/templates/index.html

新增源码/测试：
app/routers/management.py
app/static/management.js
app/templates/account.html
app/templates/base.html
app/templates/dashboard.html
app/templates/edit.html
app/templates/statistics.html
tests/smoke_statistics.py
tests/test_management.py
tests/test_statistics.py

更新文档：
README.md
docs/architecture.md
docs/database-design.md
docs/api.md
docs/testing.md
docs/ai-log.md
docs/file-manifest.txt

新增报告与证据：
docs/project-report.md
docs/iteration-4/

```

### 统计与 UI 设计

统计数据读 responses，结构读 survey_versions，按 survey_schema_version 明确分组；不读当前题目解释历史、不改提交函数、不写永久计数器。每份历史答卷复用已有 Validation/Jump 校验并核对 visited，unknown option/bool/NaN/缺 snapshot 等整体 409，不生成部分正常统计。四类型各自 answered/options/selections/values/average；数字用 Decimal 高精度累计，零回答 null。单题从同一计算结果筛选真实存在的版本。

新增 responses survey_id/version 复合索引。管理页面使用 Jinja2/原生 JS：注册登录、dashboard、基本信息/题目/validation/跳转编辑、版本分组统计、单题页面；表单调用既有 API，前端不重复完整校验。Jinja2 自动转义与 tojson 防止历史文本或标题作为脚本执行。公开页不重写，只随原回归与 smoke 验证。

### 实际环境、问题与修正

- Python 3.12.14、MongoDB 9.0.2 standalone；原业务库当时无集合/答卷/快照，原始检查与实际临时库索引检查已记录。沿用原 requirements 与 venv，未安装新依赖。
- Git 非仓库返回 fatal 原文、128，如实保存；未初始化远程仓库。
- 基线 371 passed, 1706 warnings in 63.48s，退出码 0。
- 首轮扩展 439 passed, 2118 warnings in 78.28s，退出码 0。补充四类型分别 optional missing/required skipped 的语义后，最终 455 passed, 2262 warnings in 85.55s (0:01:25)，退出码 0；旧测试/fixture 字节哈希未改。
- 纯统计实现时主动处理了浮点溢出/消去、bool/非有限数与空平均值；模板读取 values 使用键访问而非 dict.values 方法，转义和历史解释有测试。这些是实际设计与自查补强，没有声称曾发生未记录的失败。
- 实际 Uvicorn 完整业务 smoke 首次即通过，退出码 0，含页面路由、四类题目/校验、跳转、三份旧版答卷、版本升级后一份新答卷、整份/单题统计、数据库 response/snapshot/index 核验、close 后拒绝和 logout。
- 手算预期固定为旧版 single=2/1、multi 两人三次 x=2/y=1、text 两条、number (10+20+30)/3=20；新版 40/1=40，总 4。实际结果逐项断言一致，保存 statistics-check.json。计算与断言由 AI 执行，不虚构人工操作或人工评分。
- 为可选浏览器检查读取 computer-use 技能并仅查询现有窗口；未列出可直接接续浏览器窗口。未操作其他应用、未安装 Playwright/Selenium、未声明真实浏览器点击。按用户允许方式用 TestClient/HTTP/JS syntax 验收。
- compileall、全部 JS 语法、pip check 均退出码 0。原故障注入 ERROR 和本轮异常历史 WARNING 是测试主动触发，完整日志保留；第三方弃用警告未屏蔽。

本轮无意外 pytest、编译或启动失败，无需伪造错误与修复故事。没有人工修改记录，所有本轮设计/实现/自查均记录为 AI 操作。

### 尚存限制与第一阶段边界

匿名/允许多次请求无通用幂等键、pending 依赖后续请求恢复、早期未发布 draft 没有 snapshot、不可变快照依赖业务与 DB 权限控制，这些按要求保留并写入 README。统计加载目标问卷全部答卷，无分页/压力测试/事务报表快照。未做真实浏览器点击 E2E。UI 为最小表单/表格，无拖拽、复杂图表、NLP、导出。课程主要功能与自动化/API 数值验收已实现，教师人工演示、材料打包/提交和评分未执行，不能声称已获最终课程验收。
