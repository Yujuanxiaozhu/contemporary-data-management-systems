# 第四轮原始错误、异常测试与警告

## 实际 Git 状态错误，退出码 128

```text
fatal: not a git repository (or any of the parent directories): .git

```

现有项目不是 Git 仓库，如实记录；未创建远程仓库或覆盖现有项目。其余本轮实际命令均通过，没有意外 pytest/启动失败，不虚构修复失败记录。

## 原始测试运行日志

下面的 OperationFailure 是前三轮原故障注入回归；Statistics data inconsistency 警告是本轮主动播种异常历史数据验证 409 的预期结果。不是用户业务库真实数据损坏。日志原样保留：

```text
ERROR    app.main:main.py:39 MongoDB request failed
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\telemetry\_api.py", line 244, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\routers\surveys.py", line 45, in update_question
    return survey_out(questions.update_question(db, survey_id, question_id, user, data))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 90, in update_question
    return commit_structure(db, survey, user, {'questions': questions})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 26, in commit_structure
    return snapshot_commit(db, survey, {**changes, 'schema_version': survey['schema_version'] + 1}, reason)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 56, in snapshot_commit
    return finish_pending(db, reserved)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 19, in finish_pending
    db.survey_versions.insert_one(deepcopy(snapshot))
  File "D:\Codex\survey-system\tests\test_public_responses.py", line 229, in injected
    raise OperationFailure('INJECTED_'+failure_stage.upper()+'_WRITE_FAILURE')
pymongo.errors.OperationFailure: INJECTED_SNAPSHOT_WRITE_FAILURE
ERROR    app.main:main.py:39 MongoDB request failed
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\telemetry\_api.py", line 244, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\routers\surveys.py", line 45, in update_question
    return survey_out(questions.update_question(db, survey_id, question_id, user, data))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 90, in update_question
    return commit_structure(db, survey, user, {'questions': questions})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 26, in commit_structure
    return snapshot_commit(db, survey, {**changes, 'schema_version': survey['schema_version'] + 1}, reason)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 56, in snapshot_commit
    return finish_pending(db, reserved)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 26, in finish_pending
    updated = db.surveys.find_one_and_update(
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\tests\test_public_responses.py", line 229, in injected
    raise OperationFailure('INJECTED_'+failure_stage.upper()+'_WRITE_FAILURE')
pymongo.errors.OperationFailure: INJECTED_POINTER_WRITE_FAILURE
ERROR    app.main:main.py:39 MongoDB request failed
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\telemetry\_api.py", line 244, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\routers\surveys.py", line 45, in update_question
    return survey_out(questions.update_question(db, survey_id, question_id, user, data))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 90, in update_question
    return commit_structure(db, survey, user, {'questions': questions})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 26, in commit_structure
    return snapshot_commit(db, survey, {**changes, 'schema_version': survey['schema_version'] + 1}, reason)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 56, in snapshot_commit
    return finish_pending(db, reserved)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 19, in finish_pending
    db.survey_versions.insert_one(deepcopy(snapshot))
  File "D:\Codex\survey-system\tests\test_public_responses.py", line 229, in injected
    raise OperationFailure('INJECTED_'+failure_stage.upper()+'_WRITE_FAILURE')
pymongo.errors.OperationFailure: INJECTED_SNAPSHOT_WRITE_FAILURE
ERROR    app.main:main.py:39 MongoDB request failed
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\telemetry\_api.py", line 244, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\routers\surveys.py", line 45, in update_question
    return survey_out(questions.update_question(db, survey_id, question_id, user, data))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 90, in update_question
    return commit_structure(db, survey, user, {'questions': questions})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\questions.py", line 26, in commit_structure
    return snapshot_commit(db, survey, {**changes, 'schema_version': survey['schema_version'] + 1}, reason)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 56, in snapshot_commit
    return finish_pending(db, reserved)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 26, in finish_pending
    updated = db.surveys.find_one_and_update(
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\tests\test_public_responses.py", line 229, in injected
    raise OperationFailure('INJECTED_'+failure_stage.upper()+'_WRITE_FAILURE')
pymongo.errors.OperationFailure: INJECTED_POINTER_WRITE_FAILURE
ERROR    app.main:main.py:39 MongoDB request failed
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\telemetry\_api.py", line 244, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\routers\surveys.py", line 31, in publish
    return survey_out(surveys.transition(db, survey_id, user, 'published'))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\surveys.py", line 46, in transition
    return snapshot_commit(db, existing, {'status': 'published'}, 'publish')
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 56, in snapshot_commit
    return finish_pending(db, reserved)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 19, in finish_pending
    db.survey_versions.insert_one(deepcopy(snapshot))
  File "D:\Codex\survey-system\tests\test_public_responses.py", line 246, in fail
    if collection.name=='survey_versions':raise OperationFailure('INJECTED_PUBLISH_SNAPSHOT_FAILURE')
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pymongo.errors.OperationFailure: INJECTED_PUBLISH_SNAPSHOT_FAILURE
ERROR    app.main:main.py:39 MongoDB request failed
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 151, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 727, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\routing.py", line 362, in run_endpoint_function
    return await run_in_threadpool(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\starlette\concurrency.py", line 34, in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\to_thread.py", line 65, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 2706, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 1100, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\telemetry\_api.py", line 244, in _run_sync_endpoint
    return function(**arguments)
           ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\routers\surveys.py", line 31, in publish
    return survey_out(surveys.transition(db, survey_id, user, 'published'))
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\surveys.py", line 46, in transition
    return snapshot_commit(db, existing, {'status': 'published'}, 'publish')
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 56, in snapshot_commit
    return finish_pending(db, reserved)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\app\services\versions.py", line 19, in finish_pending
    db.survey_versions.insert_one(deepcopy(snapshot))
  File "D:\Codex\survey-system\tests\test_public_responses.py", line 246, in fail
    if collection.name=='survey_versions':raise OperationFailure('INJECTED_PUBLISH_SNAPSHOT_FAILURE')
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pymongo.errors.OperationFailure: INJECTED_PUBLISH_SNAPSHOT_FAILURE
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114d921873b15c0af87f4: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114d921873b15c0af87f9: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114da21873b15c0af87fe: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114da21873b15c0af8803: 答卷对应历史快照缺失，不能使用当前题目代替
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114da21873b15c0af8808: 历史答卷包含重复题目答案
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114da21873b15c0af880d: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114da21873b15c0af8812: 历史答卷版本非法
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114db21873b15c0af8817: 历史答卷字段结构非法
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114db21873b15c0af881d: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114db21873b15c0af8823: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114dc21873b15c0af8829: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114dc21873b15c0af882f: 答卷对应历史快照缺失，不能使用当前题目代替
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114dc21873b15c0af8835: 历史答卷包含重复题目答案
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114dd21873b15c0af883b: 历史答卷答案或访问路径不符合快照
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114dd21873b15c0af8841: 历史答卷版本非法
WARNING  app.services.statistics:statistics.py:113 Statistics data inconsistency for survey 6ad114dd21873b15c0af8847: 历史答卷字段结构非法

```

## 最终第三方警告原文

```text
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_management.py: 91 warnings
tests/test_public_responses.py: 1165 warnings
tests/test_questions.py: 358 warnings
tests/test_statistics.py: 465 warnings
tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================ 455 passed, 2262 warnings in 85.55s (0:01:25) ================

```

浏览器能力检查只观察到工具未列出可接续的浏览器窗口，未报自动化故障，未尝试控制无关应用或新增浏览器依赖，未虚构实际浏览器点击。详见 browser-check.txt。
