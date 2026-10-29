# MongoDB 数据库设计

## 基础集合

| 集合 | 主要内容与用途 |
|---|---|
| `users` | 用户名、密码哈希和创建时间；用户名唯一。 |
| `sessions` | 会话 token 哈希及过期时间；TTL 索引处理过期会话。 |
| `surveys` | owner、标题、状态、公开 token、当前 questions/jump_rules、schema_version 和 question_bindings。 |
| `survey_versions` | 发布时的题目、规则和固定绑定快照；`(survey_id, schema_version)` 唯一。 |
| `responses` | survey_id、survey_schema_version、局部题 ID 答案、访问路径和提交时间；独立存储避免问卷文档随答卷无限增长。 |

问卷中嵌入展示与跳转所需的题目结构，便于一次读取；可跨问卷复用的全局题目和版本独立存储。历史快照和答卷保留自己的 schema 对应关系。

## 全局题目与操作

`questions` 保存题目族 `_id`、`owner_id`、状态、版本指针和 revision；`question_versions` 保存 `question_id`、`version_no`、题目定义、内容摘要、创建者、parent/restored_from 等。派生版本还记录 `derived_from_version_id`。`stage2_operations` 保存创建、改版、恢复、派生的幂等操作状态；唯一键包含 owner、action 和 key。版本定义只新增，不原位覆盖。

`surveys.question_bindings` 的每项包含 `local_question_id`、全局 `question_id`、`question_version_id`、必答覆盖和内容/有效定义摘要。local ID 仅在该问卷内定位位置，不作为跨问卷身份。`draft_operations` 和 `revision_operations` 保存草稿结构及修订创建的恢复状态。已发布的 `survey_versions.question_bindings` 是历史快照的一部分。

## 分享与私人题库

`question_shares` 按 `(question_version_id, grantee_user_id)` 唯一，记录 owner、状态、revision、grant_epoch 和在途准入；`share_publish_operations` 保存与确定发布内容绑定的准入和恢复状态。分享不能改变原题所有权或开放接收者的问卷。撤销后已有合法发布快照仍可解释，未确认的草稿使用需重新校验。

`question_banks` 保存私人题库名称、说明、owner、revision 和归档状态。`bank_items` 以 `(bank_id, question_id)` 唯一，保存 `selected_version_id`、添加者和 revision；API 另提供等值 `default_version_id`。删除成员或归档题库不删除题目、版本和问卷历史。

## 使用追踪与重建

`question_usages` 是投影而非权威数据，记录 owner、survey、schema、全局题/version、local ID、位置及来源；唯一身份为 generation、source 和 local ID。`usage_manifests` 逐来源保存摘要和预期行数，`usage_generations` 保存 BUILDING/READY/FAILED 与来源集合摘要，`usage_heads` 以 owner 和 scope 指向活动代次。查询检查来源、行数和摘要，缺失或陈旧返回 409，不把部分结果当完整结果。

重建是维护命令，必须显式给出 URI、数据库、owner ID 和 `--apply`，不会从默认配置选库。应先备份并确认目标；以下仅示意参数，必须替换为明确授权的测试库和该库中的用户 ID：

```powershell
.\.venv\Scripts\python.exe -B scripts/rebuild_question_usages.py --uri mongodb://127.0.0.1:27017 --database <测试库名> --owner-id <用户ID> --scope all --apply
```

PowerShell 中不要原样输入尖括号；使用实际参数或变量。重建不修改问卷快照及答卷，但会写派生索引。详细的旧数据边界见 [迁移记录](stage2/migration-compatibility.md)。

## 旧数据

旧快照和答卷不重写。缺少可信来源时不能按题名、局部 ID 或 hash 推断全局题目；usage 需要覆盖而没有映射时返回 `legacy_mapping_required`。U11 只允许对明确来源快照的显式修订逐位置转换，不能推出全库自动迁移。隔离演练中故障后有可恢复的中间记录，恢复完成后旧快照仍不变；不是无中间状态的事务。
