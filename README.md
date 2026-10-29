# 基于 MongoDB 的问卷系统

这是一个两阶段课程项目。系统使用 FastAPI、MongoDB、Jinja2 和原生 JavaScript：第一阶段实现账户、问卷、题目校验、跳转、填写和统计；第二阶段在原代码上加入可复用题目、固定版本、分享、题库、使用追踪和本人跨问卷统计。已发布问卷的结构不可直接修改，需要创建修订草稿。

## 环境与启动

需要 Python 3.12、MongoDB standalone 和 Node.js（后者仅供部分 JavaScript 测试）。以下为 Windows PowerShell 示例：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`.env` 默认连接 `mongodb://127.0.0.1:27017` 的 `survey_system`。按本机环境调整，生产环境应启用认证、限制数据库写权限，并在 HTTPS 下设置 `COOKIE_SECURE=true`。不要提交 `.env` 或真实凭据。访问 `http://127.0.0.1:8000`；交互式 API 文档为 `/docs`。MongoDB 连接失败时应用不会自动切换为假数据库。

## 使用流程

1. 注册并登录，在“我的题库”创建题目族和第一个不可变版本，或在问卷草稿中创建题目。
2. 可创建私人题库，将本人题目或当前获授权的共享版本加入；题库默认版本只影响以后选题。
3. 创建问卷草稿，添加题目或从题库选择明确版本，设置单选、多选、文本、数字校验和向前跳转规则。
4. 发布后通过公开链接填写。系统按提交时的问卷快照校验和保存答卷；发布或关闭后的结构不能直接改写。
5. 需要改变已发布结构时创建独立修订草稿，再修改和发布；旧链接、快照和答卷保留。
6. 在题目历史页可以创建新版本、恢复旧版本、分享某个确定版本；接收者只能使用或派生自己的题，不能修改原题或转分享；派生当前通过 API 提供。
7. usage 与跨问卷单题统计读取本人问卷。首次使用或来源变化后，需要由有权限的维护者为本人显式重建 usage 索引，见 [数据库设计](docs/database-design.md#使用追踪与重建)。页面显示“有效回答次数”，不同题目版本分别统计。

分享撤销后不能新选入该版本；已有草稿的失效引用保留并提示移除或重新授权，已发布快照不被改写。撤销后仅凭本人历史绑定继续访问原共享题的窄权限尚未批准。

## 验证情况

Slice 1–7 根据用户提供的独立复审结论均为 PASS。最终功能代码的完整回归为 **810 passed、36 failed、5932 warnings，退出码 1**；与 Slice 7 之前的 831 个节点逐项比较，原节点状态不变，新增 15 项全部通过，无新增失败。36 项是已确认的旧断言冲突：28 项与发布结构冻结要求冲突，8 项与固定绑定/旧存储模型冲突。没有修改、删除、skip 或 xfail 这些断言，也没有为得到全绿退回旧语义。原始记录见 [测试文档](docs/testing.md) 和 [Slice 7 验证记录](docs/stage2/slice7/README.md)。

最终集成另在随机 UUID 数据库中执行了 legacy 只读盘点、隔离故障恢复和真实 MongoDB/Uvicorn smoke；没有重新运行完整 pytest，见 [集成记录](docs/stage2/final-integration-20261029/README.md)。

## 文档与边界

- [架构](docs/architecture.md) · [数据库设计](docs/database-design.md) · [API](docs/api.md) · [测试](docs/testing.md)
- [项目报告](docs/project-report.md) · [AI 使用日志](docs/ai-log.md) · [第二阶段设计记录](docs/stage2/README.md)

使用和统计查询需完整 READY 的 usage 代次；来源变化后应重建。legacy 没有可信映射时明确报错，不按题名、局部 ID 或相似内容推断。旧快照及所有引用若早已消失，现有数据无法证明它曾存在。故障恢复协议不是跨集合事务：中断可能留下待恢复操作及已提交版本，需要按原操作恢复。匿名填写无法可靠识别自然人；强杀、断网和大规模压力测试尚未完成。
