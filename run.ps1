# FreightGuard One-Click Launcher for Windows PowerShell
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   FreightGuard — Autonomous Freight Audit & PayPal Payouts" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VenvPython = ".\.venv\Scripts\python.exe"
$SystemPython = "python"

if (Test-Path $VenvPython) {
    $PythonCmd = $VenvPython
    Write-Host "[+] Using virtual environment at .venv" -ForegroundColor Green
} else {
    $PythonCmd = $SystemPython
    Write-Host "[+] Using system Python" -ForegroundColor Yellow
}

# Run test suite verification
Write-Host "[*] Running verification test suite..." -ForegroundColor Cyan
& $PythonCmd -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Warning: Some tests failed. Proceeding with caution..." -ForegroundColor Yellow
} else {
    Write-Host "[✓] All tests passed green!" -ForegroundColor Green
}

# Launch FreightGuard Web Application
Write-Host "[*] Starting FreightGuard on http://localhost:8000 ..." -ForegroundColor Green
& $PythonCmd run_server.py

