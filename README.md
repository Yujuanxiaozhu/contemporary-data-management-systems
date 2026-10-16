# 基于 MongoDB 的问卷系统

课程项目第一阶段成果。四轮在同一项目上迭代：账户与问卷基础 → 题目和校验 → 历史快照、跳转、公开提交 → 版本统计与管理网页。后续须继续修改此代码，不推倒重建。

## 环境与安装

Windows PowerShell，Python 3.12+，MongoDB 8/9。实际验证 Python 3.12.14、MongoDB 9.0.2 standalone；不要求 replica set。所有数据存 MongoDB，无关系数据库。

```powershell
cd D:\Codex\survey-system
# 新机器使用已安装的 Python 3.12+
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

本机虚拟环境已存在，可直接使用 `.venv\Scripts\python.exe`；普通 python 不在 PATH，py 默认 Anaconda 3.9。本机创建 venv 使用：
`C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。

## MongoDB / .env

- `MONGODB_URI=mongodb://127.0.0.1:27017`；远程连接自行配置认证 URI，勿提交凭据。
- `MONGODB_DATABASE=survey_system`。
- `SESSION_TTL_SECONDS=86400`，`COOKIE_NAME=survey_session`。
- `COOKIE_SECURE=false` 仅用于本地 HTTP，HTTPS 部署改为 true。

.env 按项目路径读取，已被 .gitignore 忽略。启动会 ping 并创建必要索引，失败不会回退假库。数据库账号需创建集合/索引权限；不要向不可信远程用户开放 MongoDB 直接写权限。历史快照不可变依赖受控业务写入，不加数据库代理层。

## 浏览器演示步骤

1. 打开 http://127.0.0.1:8000 ，进入 `/register` 注册，再到 `/login` 登录。
2. `/dashboard` 仅列出本人问卷，点击“创建问卷”。
3. 创建/编辑标题、说明、匿名/重复政策和截止时间。编辑页输入的是本地时间，数据库/API 使用 UTC。
4. 添加四种题型。选项每行写 `id|文字`；稳定 ID 留空自动生成。校验规则使用相应数值输入，留空表示不设置。编辑按钮会填回原字段，ID 保持不变。
5. 配置跳转规则，选择 source/target、operator、比较值和 priority。服务端拒绝无效或非前向规则。
6. 回 dashboard 发布，复制公开 URL 或“打开填写页”。允许匿名可直接分享；禁止匿名需先登录。
7. 公开页按题作答，校验和跳转由后端执行，最后提交。
8. 回管理端点“统计”，按 Schema 版本看整份统计；点单题链接看该题历史版本。没有合并不同版本。
9. 可编辑 published 问卷，新结构产生新快照；旧答卷仍按旧版本显示。最后在 dashboard 关闭，再登出。

closed 的题目/规则只读，但可查看历史统计；只有 draft 可物理删除。页面不是权限边界，所有管理 API 与统计都验证 owner。不要求教师使用 curl/Postman；`/docs` 仍提供完整 API 调试。

## 已实现

注册/登录/登出、当前身份、问卷 CRUD/发布/关闭、owner 隔离、四题型与统一 Validation Engine、题目排序、前向 Jump Rule 与引擎、不可变 survey_versions、旧版提交、匿名/截止/登录去重、公开填写页、整份/单题动态版本统计，以及最小管理网页。

统计以 responses 为数据来源、snapshot 为结构来源；不写永久统计计数器。单选为人数/选项次数，多选另给总选择数，文本列内容，数字给 values/average/min/max。空数字平均值为 null，skipped/optional missing 不计回答。异常历史数据返回 409，一致性错误不伪装成部分正常结果。

## 测试与实际日志

```powershell
# 仅 mock 后端；纯函数测试不需要真实 MongoDB
.\.venv\Scripts\python.exe -m pytest -v
# 同一套持久化/API 测试同时跑 mock 与真实 MongoDB
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
.\.venv\Scripts\python.exe -m pytest -v
# 仅真实后端实例
.\.venv\Scripts\python.exe -m pytest -v -m integration
# 实际 Uvicorn + MongoDB + 页面路由 + 统计数值核对
.\.venv\Scripts\python.exe tests/smoke_statistics.py
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pip check
node --check app/static/management.js
```

测试只创建并删除 UUID 命名的 `survey_test_*` 临时库，不清理业务库。真实后端启用后连接失败会失败，不静默跳过。当前最终数量与完整输出见 docs/testing.md、docs/iteration-4/pytest-final.txt。

第三方 Starlette/httpx、mongomock 有弃用警告，未屏蔽。无新增依赖、React/Vue、大型图表库或浏览器测试包。页面通过 TestClient、真实 HTTP 路由/业务 smoke、转义与 JS 语法验收，不声称做过真实浏览器点击 E2E。

## 已知边界

- 匿名或允许多次提交暂无通用幂等键，网络重试可能多条；不能可靠识别匿名自然人。
- pending 故障操作依靠后续请求恢复；503 后应重读确认，不能认定永久撤销。
- 未发布的旧 draft 没有历史快照，也不能合法提交，不影响正式历史答卷。
- 关闭前已准入的提交可能稍后落库；关闭后无新准入。
- 统计动态加载目标问卷答卷，课程数据规模适用；没有分页、实时缓存或大数据压力测试。统计期间并发新提交可能在下次刷新才出现。
- 历史数据损坏会停止统计，需修复数据后重试；不直接删掉异常记录凑正常结果。
- 管理端是简单表单，无拖拽、复杂图表、导出或 NLP。大文档仍须考虑 BSON 16 MB 和 pending 暂存大小。

## 文档

- docs/architecture.md：分层、快照/提交与统计设计。
- docs/database-design.md：集合、索引、嵌入/引用与版本语义。
- docs/api.md：管理、公开填写、统计和页面路由。
- docs/testing.md：各轮实际环境、测试与结果。
- docs/ai-log.md：四轮完整 Prompt 和真实 AI 操作；没有虚构人工修改。
- docs/iteration-4/delivery-report.md：本轮 A–V 交付和数值核对。
- docs/project-report.md：第一阶段项目说明与完成边界。

前三轮原始日志和报告保留在原位置。本轮命令、完整 pytest、原始错误、smoke、changed files 和统计核对均保存在 docs/iteration-4/。
