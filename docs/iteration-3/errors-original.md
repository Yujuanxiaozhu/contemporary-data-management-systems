# 第三轮原始错误与故障测试记录

## Git 非仓库（退出码 128）

```text
fatal: not a git repository (or any of the parent directories): .git

```

这是环境事实；未初始化或创建远程仓库。

## 首次真实启动探测失败（退出码 1）

服务器当时已输出 startup complete，但客户端探测遇到 ConnectTimeout。下文完整原文；未将失败描述为成功。修正为 loopback 不使用环境代理、有限连接超时重试，随后真实流程两次通过（退出码 0）。不能仅凭现有证据断言最初超时一定由代理造成。

```text
Temporary server stopped; disposable test database removed.
Traceback (most recent call last):
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_transports\default.py", line 101, in map_httpcore_exceptions
    yield
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_transports\default.py", line 250, in handle_request
    resp = self._pool.handle_request(req)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_sync\connection_pool.py", line 256, in handle_request
    raise exc from None
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_sync\connection_pool.py", line 236, in handle_request
    response = connection.handle_request(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_sync\connection.py", line 101, in handle_request
    raise exc
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_sync\connection.py", line 78, in handle_request
    stream = self._connect(request)
             ^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_sync\connection.py", line 124, in _connect
    stream = self._network_backend.connect_tcp(**kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_backends\sync.py", line 207, in connect_tcp
    with map_exceptions(exc_map):
         ^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\contextlib.py", line 158, in __exit__
    self.gen.throw(value)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpcore\_exceptions.py", line 14, in map_exceptions
    raise to_exc(exc) from exc
httpcore.ConnectTimeout: timed out

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "D:\Codex\survey-system\tests\smoke_responses.py", line 53, in <module>
    main(extension=verify_responses,log_name='iteration-3/startup-server.txt')
  File "D:\Codex\survey-system\tests\smoke_startup.py", line 30, in main
    response = client.get('/health')
               ^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_client.py", line 1053, in get
    return self.request(
           ^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_client.py", line 825, in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_client.py", line 914, in send
    response = self._send_handling_auth(
               ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_client.py", line 942, in _send_handling_auth
    response = self._send_handling_redirects(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_client.py", line 979, in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_client.py", line 1014, in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_transports\default.py", line 249, in handle_request
    with map_httpcore_exceptions():
         ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\contextlib.py", line 158, in __exit__
    self.gen.throw(value)
  File "D:\Codex\survey-system\.venv\Lib\site-packages\httpx\_transports\default.py", line 118, in map_httpcore_exceptions
    raise mapped_exc(message) from exc
httpx.ConnectTimeout: timed out

```

## 故障注入（主动预期失败，非意外 pytest 失败）

```text
ERROR    app.main:main.py:37 MongoDB request failed
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
ERROR    app.main:main.py:37 MongoDB request failed
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
ERROR    app.main:main.py:37 MongoDB request failed
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
ERROR    app.main:main.py:37 MongoDB request failed
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
ERROR    app.main:main.py:37 MongoDB request failed
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
ERROR    app.main:main.py:37 MongoDB request failed
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

```

## 最终第三方警告全文

```text
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_public_responses.py: 1165 warnings
tests/test_questions.py: 358 warnings
tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================ 371 passed, 1706 warnings in 62.19s (0:01:02) ================

```

自查修正默认 priority、hidden CSS、deadline 毫秒边界、恢复后旧数组 rebase 防护和外站分享 GET 的同源检查。没有伪造 pytest 失败；各次 pytest 均通过。首次实际 smoke ConnectTimeout 的完整 traceback 已保留在上文。
