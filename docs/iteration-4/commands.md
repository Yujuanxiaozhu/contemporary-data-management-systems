# 第四轮实际命令记录

工作目录 D:/Codex，项目仍是 survey-system，沿用原 .venv/requirements，无新增依赖。

```powershell
Get-Content -Raw 'C:/Users/lenovo/.codex/attachments/834e1120-1cbb-4103-88d5-b9a426c4713e/已粘贴的文本.txt'
git -C D:/Codex/survey-system status --short
Get-ChildItem -Force D:/Codex/survey-system
rg --files survey-system/app survey-system/tests -g '!*.pyc'
# 分批 Get-Content 检查 app/tests/templates/static/README/docs 及各 service。
Get-ChildItem survey-system/app,survey-system/tests -Recurse -File | Where-Object { $_.FullName -notmatch '__pycache__' } | Get-FileHash -Algorithm SHA256
Copy-Item -LiteralPath 'C:/Users/lenovo/.codex/attachments/834e1120-1cbb-4103-88d5-b9a426c4713e/已粘贴的文本.txt' -Destination survey-system/docs/iteration-4/prompt-original.txt
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
$env:PYTHONIOENCODING='utf-8'
cd survey-system
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall -q app tests
.venv/Scripts/python.exe -m pytest -v --log-file=docs/iteration-4/pytest-runtime.log --log-file-level=WARNING
.venv/Scripts/python.exe tests/smoke_statistics.py
node --check app/static/management.js
.venv/Scripts/python.exe -m compileall -q app tests
.venv/Scripts/python.exe -m pip check
Get-ChildItem app/static/*.js | ForEach-Object { node --check $_.FullName }
.venv/Scripts/python.exe -m pytest -v --log-file=docs/iteration-4/pytest-runtime-final.log --log-file-level=WARNING
```

另外实际用 PyMongo 查询 hello/server_info/collections/indexes、responses 与 snapshot 数量，检查原业务库当时为空；真实 smoke 在随机库中检查四条答卷、两份快照和新增复合索引。

源码/测试/文档用 PowerShell here-string 管道给项目 Python 增量写入。Computer-use 读取 skill 后仅调用现有 sky.list_apps 检查可用窗口，未控制其他应用或浏览器，不作真实点击通过的声明。

基线 371、首轮新增 439、最终 455 项全通过；Git 128，compileall/pip/JS/pytest/smoke 均 0。smoke_startup.py 实际启动 `<项目 Python> -m uvicorn app.main:app --host 127.0.0.1 --port <空闲端口>`，复用原测试框架，结束后终止进程并删除随机库。完整 HTTP 输出 startup-first.txt 与 startup-final.txt 内容相同（同一次实际通过的执行，不伪称又执行一次）。
