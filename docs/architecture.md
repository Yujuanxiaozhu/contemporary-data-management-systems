# 系统架构

系统在第一阶段结构上继续扩展，使用 FastAPI、PyMongo、MongoDB standalone、Jinja2 和原生 JavaScript。`app/routers/` 负责 HTTP 输入、会话与权限入口；`app/schemas/` 定义请求和返回；`app/services/` 处理领域逻辑；`app/core/` 管理配置、连接与认证；模板和静态文件提供简单网页。没有引入关系数据库、消息队列或要求 MongoDB replica set。

## 第一阶段链路

用户登录后创建问卷，草稿包含本地题目和跳转规则。`validation.py` 校验题目与答案，`jump_engine.py` 根据规则计算可访问路径；公开提交由服务端重新检查路径、身份、截止时间和去重条件。答卷记录 survey ID 与 schema 版本，历史解释读取 `survey_versions`，而不是用当前问卷替代。

## 题目和问卷版本

第二阶段将可复用题目的身份放到 `questions`（题目族）与 `question_versions`（不可变定义）中。`question_bank.py` 使用操作记录、条件更新和恢复接口创建版本；恢复旧版也创建一个新版本。问卷中的 `question_bindings` 将局部题目位置固定到具体全局版本；位置的必答覆盖不改全局版本。

`draft_bindings.py` 负责草稿结构提交和重试。发布时 `versions.py` 保存快照并切换状态；published/closed 的题目和跳转结构只读。`revisions.py` 从确定快照创建新 ID、新链接的独立草稿，原问卷和答卷保持不变。它在中断时可能保留待恢复记录，不等同多集合事务。

## 分享、题库与追踪

`question_shares.py` 只授予某一版本的使用权。`share_publish.py` 将准入与确定操作、授权代次绑定；撤销不删除已发布历史。`banks.py` 管理私人题库和成员默认版本，题库不构成题目所有权或问卷历史。

`usage.py` 将本人草稿绑定与发布快照投影为可重建的使用索引；查询检查来源、逐来源清单、代次状态及权限。`cross_question_statistics.py` 在通过上述检查后，以答卷自己的 schema 和历史快照按题目版本统计。题目分享不授权读取他人的问卷或答卷。

## 一致性与限制

系统主要依靠不可变记录、唯一索引、单文档条件更新和可恢复操作，而不是数据库跨集合事务。usage 和统计是动态视图；查询期间会复核来源与权限，但不承诺跨集合事务快照。需要重建索引时必须显式指定数据库和用户。legacy 只接受已批准的明确来源转换，不按文本推断。

代码按课程规模实现；真实进程强杀、网络未知确认、大规模压力和 BSON 大文档边界没有完整测试。原始阶段记录位于 [stage2](stage2/README.md)，最终实际结果见 [testing.md](testing.md)。
