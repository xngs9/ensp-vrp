$Host.UI.RawUI.WindowTitle = 'eNSP Console Manual Test'
$Host.UI.RawUI.BackgroundColor = 'Black'
$Host.UI.RawUI.ForegroundColor = 'Yellow'
Clear-Host

$logDir = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir 'manual_console_input.log'
"=== manual console opened $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Add-Content -Path $logPath -Encoding UTF8

Write-Host '[Huawei] 黑色测试窗口已打开。'
Write-Host '[Huawei] 这里标题含 eNSP，VRP 助手会把它当 Console。'
Write-Host '[Huawei] 你可以输入 dis 后按数字选择，也可以输入 display ip interface brief。'
Write-Host '[Huawei] 输入 exit 可以关闭这个窗口。'
Write-Host ''

while ($true) {
    $line = Read-Host '[Huawei]'
    "$(Get-Date -Format 'HH:mm:ss') $line" | Add-Content -Path $logPath -Encoding UTF8
    if ($line -eq 'exit') {
        break
    }
    Write-Host "输入结果: $line"
}
