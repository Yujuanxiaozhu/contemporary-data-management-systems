# 实际执行命令

以下是本轮实际执行命令（路径按 PowerShell 原执行环境记录；多行文档和代码写入的内容直接以对应文件为准）。未执行的安装命令单独标明。

```powershell
Get-Location
Get-ChildItem -Force
python --version
py --list-paths
Get-Command mongod,mongosh,rg -ErrorAction SilentlyContinue
rg --files -g AGENTS.md -g '!node_modules' -g '!.git' D:/Codex
rg --files -g '*survey*' -g '*问卷*' -g '*requirements*' -g '*pyproject*'
Get-Service *mongo* -ErrorAction SilentlyContinue
Get-CimInstance Win32_Service -Filter "Name='MongoDB'"
& 'C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' --version
& 'C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m venv D:/Codex/survey-system/.venv
& D:/Codex/survey-system/.venv/Scripts/python.exe -m pip install fastapi uvicorn pymongo pydantic-settings 'pwdlib[argon2]' jinja2 pytest httpx mongomock
# 首次网络连接失败；相同命令经 require_escalated 安装成功，输出 docs/dependency-install.txt
& D:/Codex/survey-system/.venv/Scripts/python.exe -m pip freeze
& D:/Codex/survey-system/.venv/Scripts/python.exe -c "from pymongo import MongoClient; c=MongoClient('mongodb://127.0.0.1:27017',serverSelectionTimeoutMS=3000); print(c.admin.command('ping')); print(c.server_info()['version'])"
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
$env:PYTHONIOENCODING='utf-8'
cd D:/Codex/survey-system
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe tests/smoke_startup.py
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m compileall -q app tests
```

另外实际通过 Python 标准库 zipfile + ElementTree 只读提取 DOCX 原文；通过 Python 从本聊天 JSONL 原样提取用户 Prompt 与发生错误的工具返回；通过项目内临时生成脚本写入源码（bootstrap.py、add_tests.py 已删除，仅删除本轮自建临时文件）。代码和文档最终内容在 file-manifest.txt 中列出。

smoke_startup.py 实际启动子命令：`<本项目 python> -m uvicorn app.main:app --host 127.0.0.1 --port <系统空闲端口>`，临时数据库名随机，环境覆盖 MONGODB_DATABASE。端口与进程输出见 startup-server.txt。

曾申请 `pip install httpx2`，自动审核因账户额度失败，命令没有执行；不将其列作成功安装。原始原因完整见 errors-original.md。
