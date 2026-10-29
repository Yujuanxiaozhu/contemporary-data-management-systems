# 最终集成记录（2026-10-29）

## 执行边界

依据用户提供的独立复审结论，Slice 1–7 均为 PASS。本轮没有重新审计各切片，也没有修改 `app/`、`tests/`、`scripts/` 中正式运行代码；未重跑完整 pytest。最终功能代码的完整回归继续采用 [Slice 7 结果](../slice7/README.md)：846 节点、810 passed / 36 failed、退出码 1；此前 831 节点状态无变化，新增 15 全部通过，失败集合一致。36 项包括 28 项发布冻结和 8 项旧绑定/存储模型冲突，不称全绿。

## legacy 盘点与恢复演练

`legacy_dry_run.py` 使用 loopback 和随机 `survey_test_legacy_<UUID>`。先在隔离库构造两个同标题的旧位置，兼容读取旧 survey 和 snapshot；只读盘点期间 Mongo 命令监听记录 10 次 find、0 次写操作，原 survey 与 snapshot 摘要不变。没有可信映射时两个位置保持 unmapped，usage 返回 `409 legacy_mapping_required`，未根据标题或局部 ID 猜测。

随后在同一个**临时测试库**显式演练已批准的 U11 修订：在第一位置转换后注入 `AutoReconnect`，得到 503；原 survey/snapshot 不变，尚无修订草稿，但保留一个已提交题目版本和 PREPARED 修订操作。使用同一 key 重试后，两个位置均可通过已有修订操作识别，分别属于两个题目族，不创建重复版本，旧数据仍不变。`legacy-dry-run.json` 和 `legacy-dry-run.log` 保存细节；测试库已删除且集合为空。

**边界：**故障期间确实存在可恢复的中间状态和已提交版本，恢复后才完成转换。如果“故障时绝不留下任何部分转换状态”被严格视为验收要求，本次演练没有证明这一要求；当前实现提供的是保留旧数据、按原操作恢复，而不是跨集合原子回滚。此处不将恢复成功描述为无中间状态。没有访问或修改正式业务数据，也没有实施全库迁移；未映射旧位置仍需明确方案或人工处理。

## 真实 MongoDB / Uvicorn smoke

使用 `127.0.0.1` 和随机 `survey_test_smoke_<UUID>`，启动真实 Uvicorn；HTTP 链路覆盖：

- 创建题目 v1/v2、草稿固定绑定、发布并核对快照及提交答卷。
- 分享 v1、接收者建立私人题库、添加成员并从题库绑定到自己的问卷。
- 对两位用户分别显式重建 usage；查询 usage 和按版本分组的本人统计。
- 核对 owner 不能读接收者问卷及单问卷统计，反向同样不可读；跨问卷统计不混入对方答案。
- 撤销后，接收者不能新绑定或读取原共享版本/跨问卷统计，失效题库成员不可用；已发布历史仍可由问卷 owner 查看。
- 首页、健康、OpenAPI、题库及编辑页面正常响应。

`smoke-final.txt` 记录各步骤 PASS；`smoke-final-launch.json` 保存 Uvicorn 与 CLI 显式启动参数，`smoke-final-uvicorn-server.log` 保存 HTTP 服务日志。服务停止后测试库 drop，`smoke-final-cleanup.json` 为空集合；父进程 Mongo 监听不覆盖 Uvicorn/CLI 子进程的全部命令，需结合启动参数和清理记录理解。没有发现需要修改业务源码的 smoke 阻断问题。

## 保护与交付

`protected-before.json` 记录入轮文件哈希；仅授权的正式文档、stage2 总入口及本目录新增证据允许变化。原文档副本和工作区历史材料保留在本地（未纳入 Git 提交），本目录只提交必要的说明与结果；候选包另行复制必要的源码、配置、测试、正式文档和精简结果，不删除工作区历史过程材料。教师原始交付内容摘要见 `course-submission-requirements.md`；实际命名和提交方式仍应核对课程通知。

本轮未运行 BFCache、压力、强杀或断网测试，未 commit、push 或上传。若要求 legacy 故障后绝无中间状态，须先由用户决定是否接受现有可恢复语义或另行安排设计修改和回归。
