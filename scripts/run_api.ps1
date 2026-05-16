Set-Location -LiteralPath (Resolve-Path "$PSScriptRoot\..")
& "C:\Program Files\Python312\python.exe" -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
