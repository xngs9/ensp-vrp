# eNSP VRP 输入法候选助手 —— 一键打包
# 用法：
#   powershell -ExecutionPolicy Bypass -File build.ps1            # 自动找 Python，打对应位数
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Arch 32   # 强制打 32 位（需要 32 位 Python）
# 产物：本目录下的  便携版-64\  或  便携版-32\

param([ValidateSet('auto','64','32')][string]$Arch = 'auto')

$ErrorActionPreference = 'Continue'   # 注意：不能设 Stop，否则原生程序往 stderr 写的警告会被当成致命错误
$root = $PSScriptRoot
$srcDir = Join-Path $root 'src'
$entry = Join-Path $srcDir 'ensp_vrp_ime_helper.py'
if (-not (Test-Path $entry)) { Write-Host "找不到源码: $entry" -ForegroundColor Red; exit 1 }

function Get-PythonInfo($exe, $pre) {
    $args = @()
    if ($pre) { $args += $pre }
    $probe = @('import struct,sys;print(struct.calcsize(''P'')*8, sys.version.split()[0])')
    try {
        $out = & $exe @($args + @('-c') + $probe) 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $parts = ("$out").Trim().Split(' ')
        if ($parts.Count -lt 2) { return $null }
        return [pscustomobject]@{ Exe = $exe; Pre = $args; Bits = [int]$parts[0]; Ver = $parts[1] }
    } catch { return $null }
}

function Find-Python([int]$wantBits) {
    $found = @()
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($v in @('3.12','3.11','3.10','3.13','3.14','3.9','3.8')) {
            $info = Get-PythonInfo 'py' "-$v"
            if ($info) { $info | Add-Member -NotePropertyName Tag -NotePropertyValue "py -$v" -Force; $found += $info }
        }
    }
    foreach ($name in @('python','python3')) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $info = Get-PythonInfo $name $null
            if ($info) { $info | Add-Member -NotePropertyName Tag -NotePropertyValue $name -Force; $found += $info }
        }
    }
    return $found | Where-Object { $_.Bits -eq $wantBits } | Select-Object -First 1
}

Write-Host ''
Write-Host '=== eNSP VRP 输入法候选助手 · 打包 ===' -ForegroundColor Cyan
Write-Host ''

$wanted = @()
if ($Arch -eq 'auto') { $wanted = @(64, 32) } else { $wanted = @([int]$Arch) }

$built = @()
foreach ($bits in $wanted) {
    Write-Host "[$bits 位] 查找 Python ..."
    $py = Find-Python $bits
    if (-not $py) {
        Write-Host "  ✗ 没找到 $bits 位的 Python，跳过" -ForegroundColor Yellow
        if ($bits -eq 32) { Write-Host '    （32 位需要单独装一个 32 位 Python，例如 python-3.11.x-32.exe）' -ForegroundColor DarkGray }
        continue
    }
    Write-Host ("  ✓ 用 " + $py.Tag + "  (Python " + $py.Ver + ", " + $py.Bits + " 位)") -ForegroundColor Green

    $deps = & $py.Exe @($py.Pre + @('-c', 'import PyInstaller;print(PyInstaller.__version__)')) 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '  · 装 PyInstaller ...'
        & $py.Exe @($py.Pre + @('-m', 'pip', 'install', '--upgrade', 'pyinstaller')) 2>&1 | Out-Null
    } else {
        Write-Host ("  · PyInstaller " + $deps)
    }

    $tag = "build-$bits"
    $dist = Join-Path $root "$tag\dist"
    $work = Join-Path $root "$tag\work"
    Write-Host "  · 开始打包 ..."
    & $py.Exe @($py.Pre + @('-m', 'PyInstaller', '--noconfirm', '--onefile', '--noconsole',
        '--name', 'ensp-vrp-ime-helper',
        '--distpath', $dist, '--workpath', $work, '--specpath', (Join-Path $root $tag),
        $entry)) 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "  ✗ 打包失败" -ForegroundColor Red; continue }

    $exe = Join-Path $dist 'ensp-vrp-ime-helper.exe'
    if (-not (Test-Path $exe)) { Write-Host "  ✗ 没生成 exe" -ForegroundColor Red; continue }

    $out = Join-Path $root ("便携版-" + $bits)
    if (Test-Path $out) { Remove-Item $out -Recurse -Force }
    New-Item -ItemType Directory -Force $out | Out-Null
    Copy-Item $exe $out -Force
    foreach ($d in @('data','rules','scripts')) {
        $s = Join-Path $root $d
        if (Test-Path $s) { Copy-Item $s (Join-Path $out $d) -Recurse -Force }
    }
    New-Item -ItemType Directory -Force (Join-Path $out 'logs') | Out-Null
    Get-ChildItem (Join-Path $root 'docs') -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item $_.FullName $out -Force
    }
    Write-Host ("  ✓ 完成 -> " + $out) -ForegroundColor Green

    # 顺手自检
    Write-Host '  · 冒烟自检 ...'
    Push-Location $out
    $smoke = & (Join-Path $out 'ensp-vrp-ime-helper.exe') --paging-smoke-test 2>$null
    Pop-Location
    if ($smoke -and (($smoke | Select-String '^FAIL') | Measure-Object).Count -eq 0 -and (($smoke | Select-String '^PASS') | Measure-Object).Count -gt 0) {
        Write-Host '  ✓ 翻页自检全过' -ForegroundColor Green
    } else {
        Write-Host '  ⚠ 自检没全过（--noconsole 可能吞了输出），请手动跑一次确认' -ForegroundColor Yellow
    }
    $built += $out
}

Write-Host ''
if ($built.Count -eq 0) {
    Write-Host '什么都没打出来。请先装 Python（32 位版需要 32 位 Python）。' -ForegroundColor Red
    exit 1
}
Write-Host '打包完成：' -ForegroundColor Cyan
$built | ForEach-Object { Write-Host ('  ' + $_) }
