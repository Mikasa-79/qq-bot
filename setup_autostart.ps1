# ============================================================
#  QQ Bot 开机自启配置脚本
# ------------------------------------------------------------
#  用法(任选其一):
#    1. 右键本文件 -> "使用 PowerShell 运行"
#       (如果窗口一闪而过,用下面第 2 种)
#    2. 以管理员身份打开 PowerShell,执行:
#       powershell -ExecutionPolicy Bypass -File setup_autostart.ps1
#
#  ⚠️ 必须用【管理员权限】运行,否则创建计划任务会失败
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===== QQ Bot Auto-Start Setup =====" -ForegroundColor Cyan
Write-Host ""

# --- 0. 检查管理员权限 -------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] Not running as Administrator!" -ForegroundColor Red
    Write-Host "        Please right-click -> Run as administrator" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Running as Administrator" -ForegroundColor Green

# --- 1. 输入 API Key ---------------------------------------------------
$API_KEY = Read-Host "Enter your LLM API Key (starts with sk-)"
if ([string]::IsNullOrWhiteSpace($API_KEY)) {
    Write-Host "[ERROR] API Key is empty, aborted." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 设置成"用户级"环境变量(永久有效,重启后还在)
[Environment]::SetEnvironmentVariable("LLM_API_KEY", $API_KEY, "User")
Write-Host "[OK] Env var LLM_API_KEY saved (User level)" -ForegroundColor Green

# --- 2. NapCat 自启任务(需要最高权限)---------------------------------
$napcatDir = "E:\NapCatShell"
if (-not (Test-Path (Join-Path $napcatDir "launcher.bat"))) {
    Write-Host "[ERROR] launcher.bat not found in $napcatDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$action1 = New-ScheduledTaskAction -Execute (Join-Path $napcatDir "launcher.bat") -WorkingDirectory $napcatDir
$trigger1 = New-ScheduledTaskTrigger -AtLogOn
$principal1 = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest
Register-ScheduledTask -TaskName "NapCat-AutoStart" `
    -Action $action1 -Trigger $trigger1 -Principal $principal1 -Force | Out-Null
Write-Host "[OK] Task created: NapCat-AutoStart (Highest)" -ForegroundColor Green

# --- 3. NoneBot 机器人自启任务 ----------------------------------------
# 用 $PSScriptRoot 拿到脚本所在目录,避免中文路径乱码
$botDir = $PSScriptRoot
$pythonPath = Join-Path $botDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Host "[ERROR] python.exe not found: $pythonPath" -ForegroundColor Red
    Write-Host "        Is this script in the qq-bot folder?" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

$action2 = New-ScheduledTaskAction -Execute $pythonPath -Argument "bot.py" -WorkingDirectory $botDir
$trigger2 = New-ScheduledTaskTrigger -AtLogOn
$principal2 = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Limited
Register-ScheduledTask -TaskName "QQBot-AutoStart" `
    -Action $action2 -Trigger $trigger2 -Principal $principal2 -Force | Out-Null
Write-Host "[OK] Task created: QQBot-AutoStart" -ForegroundColor Green

# --- 4. 验证 ----------------------------------------------------------
Write-Host ""
Write-Host "===== Created tasks =====" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "NapCat-AutoStart", "QQBot-AutoStart" |
    Select-Object TaskName, State | Format-Table -AutoSize

Write-Host "Done! Restart your PC to test." -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
