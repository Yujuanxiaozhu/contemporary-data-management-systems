# 设计协调 R2 验收与差异记录

日期2026-10-24，工作分支stage2-question-bank。任务仅修订设计文档，未编码、未运行或重跑基线测试、未接触业务数据库、未commit/push/上传。

## 变更依据与来源

本轮用户确认五项不变量：题目/跳转结构冻结；明确版本分享及接收者派生；本人问卷默认统计范围；旧快照/答卷不改写及不猜测合并；恢复新增版本。没有新批准元信息冻结、修订ID/token或撤销细节。所有S/Q继续待确认，T仍为教师要求，不由Codex技术建议替代。

## 逐文件差异

以下为本轮读取原文与修订后文本的行级增删概况（LCS统计，不是Git已提交diff；design-rules在随后补充两行遗留pending边界）。原有设计文件本来均未跟踪，故git diff不会展示这些内容差异。

| 文件 | 增删概况 |
|---|---|
| ai-log.md | 约+28/-0行 |
| api-contract.md | 约+12/-12行 |
| architecture-and-data-model.md | 约+15/-15行 |
| decision-log.md | 约+47/-31行 |
| design-rules.md | 新增 |
| migration-compatibility.md | 约+5/-3行 |
| README.md | 约+6/-4行 |
| requirements-matrix.md | 约+9/-9行 |
| test-plan.md | 约+49/-4行 |
| design-finalization-review.md | 新增，本记录不自统计 |

| 文件 | 实际解决的问题 |
|---|---|
| design-rules.md | 新增D1–D7，集中列字段边界、修订身份、逐share授权/发布状态机、legacy判据、usage代次完整性、撤销后本人统计、错误catalog；含规则/测试ID和待确认状态 |
| decision-log.md | U1收窄为用户明确的结构范围；Q1拆Q1-R/Q1-M；S3与Q2不再笼统说所有未发布一律失效；S7收紧；新增S9/10/11及Q8/9/10，映射验收ID |
| architecture-and-data-model.md | 同步grant_epoch/有界票据、usage_manifest/generation、结构冻结及元信息待决、S11窄历史证明；required归属条件化；列表时间字段按资源区分 |
| api-contract.md | 新选入与换版引用冲突统一409；补授权/usage/统计规则引用、Share状态、Operation状态说明、coverage与映射异常，不暗改旧PUT |
| migration-compatibility.md | 不再凭survey+local自动归谱系；区分审计重用/新关联/冲突；usage按D5校验；遗留published改题pending只列待决不自动执行 |
| test-plan.md | 新增34个未来验收场景和原需求ID别名；将多share单一准入点改成逐share+survey封存；S场景预期须获批才生效 |
| requirements-matrix.md | R1–R8现状保留，更新D/S/Q和细化验收ID，标明本轮未测、修订新token仍待审 |
| README.md | 统一阅读入口、结构与元信息边界、当前文档阶段，声明旧baseline清单为历史快照不再代表修订文档hash |
| ai-log.md | 仅追加本轮真实任务、工具错误及修正、修改内容、静态验收性质和未决项；上一轮文本前缀保留 |
| 本记录 | 汇总设计验收、保护边界、差异与后续计划 |

## 设计静态验收结果

- 六份核心设计及README/日志的相对文件链接已检查；新增本文后再复核链接。D1–D7均有规则正文，验收细化为34个唯一ID，无重复或引用未定义的新ID。
- 字段表区分U1确认结构、S2待决元信息、已有close/准入行为；修订新ID/token为S1待确认。没有扩大用户批准。
- D3将每个share的准入/撤销CAS与survey封存CAS分开，不宣称跨集合原子授权。普通draft和已授票据在途operation区别明确；多依赖、崩溃、重授epoch、容量及终结均有验收场景。
- D4对缺可信来源不自动合并；逐位置拆分/needs_review仍由用户决定。D5先权威枚举再逐代校验，缺整份索引、半代及源变化不能报零。
- D6单独定义S11候选权限：历史binding仅证明本人数据查询，不给新使用或原题目录权；是否批准仍为Q8。
- D7统一既存引用冲突409、输入定义非法422，并区分已知操作授权冲突与任意不可见版本404；不一次性重写所有旧API响应。
- 上述是文字/链接/追踪一致性检查；没有运行这些未来测试，不证明算法已经实现或并发正确，也不替代ChatGPT与用户评审。

## 证据与源码保护

修订前记录并在修订后只读比对216个受保护文件：142个原已跟踪项目文件，加baseline目录74个文件（包括其原始输出、失败记录、入口和忽略缓存）。结果无hash变化。HEAD=0b845575fef4863e49be1e22b20d1882c5c78f66，stage1-final目标=96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9，分支未变，已跟踪工作区和暂存区差异为空。

baseline/results.json、commands.md、git-after.json、preservation.json、new-files.json、原日志均未改。旧new-files清单曾覆盖的设计文件现已合法修订，所以不能再声称其38项全部匹配当前设计；该清单只证明基线轮产物，保留原字节不重新生成。基线455/2262/55.49s仍是上一轮实测，本轮没有新的pytest结果。

## 待用户决定与实施闸门

详见decision-log：Q1-R修订身份、Q1-M元信息；Q2在途撤销策略；Q3来源摘要；Q4 required/题库/重复位置；Q5旧题关联和遗留pending；Q6分布；Q7课程通知；Q8撤销后本人历史查询；Q9usage扫描与严格错误；Q10幂等和旧PUT兼容。

下一阶段先让ChatGPT审查D1–D7和状态机；用户确认相关Q后，才选择最小切片实施独立题目/不可变版本及固定引用。之后依赖顺序为发布/修订→分享→题库→usage→跨问卷统计→隔离迁移演练→完整验收。不得在本轮继续写功能、测试代码或执行迁移。未决定的模块保持blocked-by-decision状态，不偷用建议默认值。

