# 切片2交付与复审入口（2026-10-25）

实现已完成，停止等待审查；不自动进入分享、usage或跨问卷统计。完整套件有真实冲突失败，不能称全绿。

## 最终实际结果

```text
full-release: 36 failed, 532 passed, 2958 warnings in 80.06s
exit_code=1
smoke-release: SLICE2_FIXED_BINDINGS_REQUIRED_SNAPSHOT_AND_RESPONSES=PASS
REAL_UVICORN_SMOKE=PASS
exit_code=0
```

568实例=切片1的522+新增46。原522中486个无冲突实例全部通过；36个真实旧失败：28发布冻结冲突、8“questions集合不存在”的旧存储模型断言冲突（明确不是冻结）。原455中的419通过、36冲突；切片1新增67全部通过。本轮新增46全部通过（23真实Mongo+23mock），17个函数的参数实例明细见test-results.json。完整Mongo211实例中193通过、18冲突失败；mock同样193通过/18冲突，纯逻辑146通过。完整回归已包含integration，不额外重复相同子集凑数。

首轮完整42失败含6个非预期旧错误形状回归；已经修复recent_replay对非有限值的提前拒绝，最终6项均通过。原断言没有修改；没有skip/xfail或隐藏失败。逐节点原失败语句、位置、实际异常、是否冻结及新增替代覆盖见failure-classification.json和.md。KeyError场景原日志未打印独立HTTP码，不把源码推断冒充实测；冲突用例中止后的其余断言没有运行，不宣称通过。

## 文件与实现

| 文件 | 实际修改目的 |
|---|---|
| app/models/survey.py | 新草稿初始化空固定绑定列表；无业务全库适配。 |
| app/schemas/survey.py | 管理输出新增bindings，BSON ID显式转字符串，旧缺字段兼容空列表。 |
| app/routers/surveys.py | 旧题目端点可选幂等key；新增固定引用、绑定换版、操作查询恢复；快照绑定序列化。 |
| app/services/questions.py | 保留Validation/Jump/局部ID/顺序；草稿写入委托恢复协议，支持位置required及显式new_family，服务层冻结。 |
| app/services/draft_bindings.py | 新增固定版本计划、有效定义、幂等/收据/CAS恢复、权限/发布一致性校验。 |
| app/schemas/binding.py | 新增严格ReferenceInput/BindingInput，拒绝未知字段及非法覆盖。 |
| app/services/surveys.py | 恢复本草稿pending、发布前复验绑定、元信息字段/状态目标白名单、防止并发删pending。 |
| app/services/versions.py | 发布快照复制固定绑定与有效结构，底层拒绝published/closed结构改写和legacy pending自动改题。 |
| tests/test_draft_bindings.py | 新增17个函数/46个mock及真实Mongo实例；原测试未改。 |
| tests/smoke_draft_bindings.py | 新增适用真实HTTP smoke，不改原统计smoke原文。 |
| docs/stage2/architecture-and-data-model.md | 追加实际集合/位置/收据模型与风险。 |
| docs/stage2/api-contract.md | 追加实际端点、required旧格式语义、错误和幂等作用域精化。 |
| docs/stage2/requirements-matrix.md | 更新R1/R3/R5、U7部分实现及其他需求未完成状态。 |
| docs/stage2/test-plan.md | 记录用户批准的冲突口径、新增验收组及未执行边界。 |
| docs/stage2/ai-log.md | 追加真实实施/失败/修复/重跑/保护日志。 |

其他新增文件仅本目录实施协议/runner/原始日志/审计/差异和保护清单；全部路径见new-files.json。既有源文件改动6份，新业务源码2份，新测试2份，根stage2文档5份。原app/main.py/database.py的切片1差异保留，本轮未修改；切片1的题目版本router/service/schema及原测试均保护。

## 固定版本、required和兼容

question_bindings记录稳定local_question_id、BSON family/version ID、required_override、版本content_hash和有效定义effective_hash；questions保留原引擎可执行结构，不把元数据塞进QuestionDefinition。永远解析指定版本，latest变化不回写任何草稿/快照。null继承默认，true/false覆盖，发布前验证并在快照冻结最终值。

旧PUT字段仍可用，按已有绑定同family创建新内容版本，位置required/顺序变化不改版本；旧required表达位置实际必答值，不偷偷改不可变默认。new_family=true显式新身份，不猜文本含义。可选key重放同结果/冲突409；新固定引用端点必填key。无key PUT对当前相同结构no-op；任意延迟重放与新编辑无法可靠区分，复杂客户端应给可选key，旧客户端不被强制迁移。无key无自定ID旧POST紧邻相同内容重试复用结果，明确重复位置请用不同key；原自定ID重复仍409。端点和具体作用域见protocol及根api-contract切片2增补。

draft_operations先耐久记录确定计划，再draft+schema CAS预留；每个子版本用确定key调用切片1协议；resolved结构耐久后，survey CAS同时写结构/schema和_binding_commits收据，再标操作COMMITTED。结构已成功而操作状态落后由收据恢复，不重复版本。家族CAS终结冲突标FAILED并释放草稿预留，旧结构不改、审计/不可变版本保留。GET操作只读，POST resume恢复原payload；正常get_owned延续原帮助恢复模式，仅恢复已由明确写操作发起的pending，不发起迁移。

## 冻结路径与历史兼容

1. 路由调用questions._editable，published/closed题目/规则/引用/绑定写409。
2. commit_structure再次guard，draft_bindings.execute的预留/提交CAS均限制draft及原schema；绕过路由也不可写。
3. surveys.update_survey白名单拒绝结构字段，transition禁止直接重开draft；元信息既有可变性保持，未擅自批准S2冻结策略。
4. snapshot_commit不允许非draft更新/重新开放，draft快照只用于发布；publish复验绑定/定义/hash/权限/Jump。
5. finish_pending在写snapshot前拒绝旧published改题pending；首次draft发布恢复仍保留。
6. 快照保存最终题目/局部ID/顺序/Jump/绑定，不改responses或既有snapshot。缺binding旧published/closed仍按原snapshot解释；legacy draft只在用户明确草稿写时逐位置适配，无全库扫描。

精确本轮diff见changes.diff及source-and-tests.diff，before/保留授权修改前原文；新文件完整内容在项目对应路径，不用Git diff遗漏untracked文件。

## 新增验收实例

| 实际函数 | 通过实例数 |
|---|---|
| test_two_drafts_pin_history_and_old_put_creates_new_version | 2 |
| test_required_overrides_freeze_in_snapshot | 6 |
| test_same_version_different_override_and_explicit_binding | 2 |
| test_legacy_put_optional_new_family_and_idempotency | 2 |
| test_required_only_old_put_and_null_override_do_not_mutate_version | 2 |
| test_all_published_structure_paths_frozen_and_data_unchanged | 4 |
| test_jump_and_local_order_preserved_and_conflict_has_no_versions | 2 |
| test_unowned_missing_versions_and_invalid_binding_are_rejected | 2 |
| test_binding_interruption_recovers_without_duplicate_versions | 8 |
| test_slice1_child_interruption_is_resumed_by_draft_operation | 2 |
| test_publish_rejects_binding_tamper_and_legacy_draft_adapts_only_on_write | 2 |
| test_history_statistics_through_legal_separate_drafts_and_legacy_snapshot | 2 |
| test_reference_conflicts_and_effective_required_validation | 2 |
| test_legacy_published_pending_is_not_auto_completed | 2 |
| test_concurrent_binding_resumes_and_current_structure_are_idempotent | 2 |
| test_legal_new_draft_preserves_historical_options_and_new_family_statistics | 2 |
| test_family_cas_conflict_audited_without_stranding_draft | 2 |

原始完整日志full-attempt1/full-final/full-acceptance/full-release均保留；new-attempt1/new-attempt2/new-final为逐步补齐的独立新增验收；smoke/smoke-final/smoke-release为适用HTTP验证。新源码/保护路径或新断言发生变化后才重跑，没有重新执行历史baseline。最后full-release及smoke-release对应最终源码。commands.md/results.json及每个*-result.json记录实际命令/退出码和耗时，旧证据不重签。2958 warnings主要为mongomock datetime.utcnow及Starlette/httpx弃用；冲突提前中止会减少旧路径执行次数，不能把warning净差直接当成新增测试警告数。

## 数据隔离与Git保护

所有运行显式loopback MongoDB9.0.2 standalone；原夹具新survey_test_UUID、finally drop，Uvicorn强制新survey_test_smoke_UUID。共902个不同测试库，命令审计unexpected均空，各有drop记录和当次空集合清单核验；database-isolation-summary及各原始audit/cleanup保留。父listener不等于子Uvicorn完整Mongo命令监听，子env另验，未夸大。未访问默认业务数据库、未迁移业务数据。

开始/结束stage2-question-bank，HEAD保持0b845575fef4863e49be1e22b20d1882c5c78f66，stage1-final peeled保持96f1a39ff6b8e852df3f58b64c300ebaac5fbcb9；暂存区空。384个既有文件保护核验，原12份测试/夹具/smoke与HEAD、tag、切片1前hash相同，slice1业务源码和baseline/visibility原证据未改。精确变化清单和git原输出见preservation.json/git-before.json/git-after.json。没有commit/push/水杉、reset或分支切换。

## 未执行、限制与下一步

未运行旧smoke_statistics中已禁止的published编辑流程，改用独立适用扩展；原文件原文仍在。未做页面E2E、全库业务迁移/恢复演练、真实进程强杀/未知写确认、压测，也未重跑pip check/JS语法（无依赖或JS改动）。没有修订ID/token产品策略、新页面、分享/撤销、usage或跨问卷统计功能。

长期操作/收据与大候选计划受BSON16MB及容量限制；无后台恢复。无key旧请求不承诺跨其他编辑的exactly-once，见上述说明。接口按owner+survey作用域复用key，不同survey可使用同文本key，切片1题目API作用域不改；该具体契约已明确精化原D7草案。

下一步先审查本轮源码、失败分类与证据；确认后优先处理题库/选题管理页面和修订新草稿的ID/token决策，再单独安排后续切片。当前不自动执行，也不把R2/R6/R7/R8整体标记完成。
