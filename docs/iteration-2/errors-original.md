# 本轮原始错误与警告

本轮唯一工具错误是实施前 Git 状态检查（项目本来没有 Git 仓库）。原始输出、退出码 128：

```text
fatal: not a git repository (or any of the parent directories): .git

```

未初始化 Git、未创建远程仓库，继续在原目录增量修改。基线 70 项、首轮扩展 208 项、最终 220 项测试均通过，没有失败 traceback，不虚构修复记录。

## 最终 pytest 原始警告

以下警告保持原文，未 filter/屏蔽：

```text
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Codex\survey-system\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

tests/test_questions.py: 358 warnings
tests/test_system.py: 182 warnings
  D:\Codex\survey-system\.venv\Lib\site-packages\mongomock\helpers.py:73: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return datetime.utcnow()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
===================== 220 passed, 541 warnings in 16.60s ======================

```

第一轮原始错误仍在 ../errors-original.md，本轮不重写历史记录。日志中非 2xx HTTP 状态是被测试的预期拒绝行为，不是失败后伪装成功。
