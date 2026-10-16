# 第三轮实际命令

沿用 D:/Codex/survey-system 和既有 .venv，无新依赖安装、无 Git init/远程仓库、无子代理。

```powershell
Get-Content -Raw 'C:/Users/lenovo/.codex/attachments/95f86740-f91c-4a76-8363-5c17446cca91/已粘贴的文本.txt'
git -C D:/Codex/survey-system status --short
rg --files survey-system/app survey-system/tests survey-system/docs -g '!*.pyc'
Get-ChildItem survey-system/app -Recurse -File -Filter *.py | ForEach-Object { Get-Content $_.FullName }
# 分批读取 tests/README/docs，以及 survey/question/validation service。
Get-ChildItem survey-system/app,survey-system/tests -Recurse -File | Where-Object { $_.FullName -notmatch '__pycache__' } | Get-FileHash -Algorithm SHA256
Copy-Item -LiteralPath 'C:/Users/lenovo/.codex/attachments/95f86740-f91c-4a76-8363-5c17446cca91/已粘贴的文本.txt' -Destination survey-system/docs/iteration-3/prompt-original.txt
$env:TEST_MONGODB_URI='mongodb://127.0.0.1:27017'
$env:PYTHONIOENCODING='utf-8'
cd survey-system
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m compileall -q app tests
.venv/Scripts/python.exe -m pytest -v
.venv/Scripts/python.exe -m pytest -v --log-file=docs/iteration-3/pytest-runtime.log --log-file-level=ERROR
.venv/Scripts/python.exe tests/smoke_responses.py
# 首次超时后修正启动 readiness；重跑通过。
.venv/Scripts/python.exe tests/smoke_responses.py
.venv/Scripts/python.exe -m compileall -q app tests
.venv/Scripts/python.exe -m pip check
node --check app/static/survey.js
.venv/Scripts/python.exe -m pytest -v --log-file=docs/iteration-3/pytest-runtime-final.log --log-file-level=ERROR
# 自查恢复边界补强后最终复跑完整集；同一路径保留最终输出，中间结果另存。
.venv/Scripts/python.exe -m compileall -q app tests
.venv/Scripts/python.exe -m pytest -v --log-file=docs/iteration-3/pytest-runtime-final.log --log-file-level=ERROR
.venv/Scripts/python.exe tests/smoke_responses.py
```

另外实际通过项目 Python + PyMongo 读取 hello、server_info、已有库索引；standalone=true，MongoDB 9.0.2；主业务库当时无集合，未写用户业务数据。真实 smoke 临时库内检查 survey_versions 唯一复合索引、responses dedupe unique sparse 索引，原文在 startup-final.txt。

代码、测试与文档通过 PowerShell here-string 管道给项目 Python 增量修改。每次运行输出均保存在 docs/iteration-3/；Git 128、首次 smoke 1，其他验证退出码 0，详见 verification.json。真实启动子命令由既有 smoke_startup.py 执行 `<项目 Python> -m uvicorn app.main:app --host 127.0.0.1 --port <空闲端口>`，完成后清理随机测试库和临时进程。

最终外站分享 GET 边界修正后，实际再次执行 compileall、同一完整 pytest 命令、smoke_responses.py，退出码均 0；最终为 371 passed, 1706 warnings in 62.19s (0:01:02)。旧 369 项日志另存 pytest-before-shared-link-fix.txt。
