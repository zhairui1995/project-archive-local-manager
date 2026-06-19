$ErrorActionPreference = "Stop"

if ($null -eq $env:VIRTUAL_ENV -and $null -eq $env:CONDA_PREFIX) {
    Write-Warning "建议先激活 Python 3.11 虚拟环境。"
}

$version = python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($version -ne "3.11") {
    throw "打包环境必须为 Python 3.11，当前为 Python $version。"
}

python -c "import PySide6, pandas, openpyxl; print('依赖检查通过')"
pyside6-deploy main.py --name "ProjectArchiveManager" --force --keep-deployment-files

$exe = Get-ChildItem -Path ".\deployment" -Filter "ProjectArchiveManager.exe" -Recurse |
    Select-Object -First 1
if ($null -eq $exe) {
    throw "未在 deployment 目录找到 ProjectArchiveManager.exe。"
}

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($null -eq $iscc) {
    throw "未安装 Inno Setup 6。请先执行：winget install JRSoftware.InnoSetup"
}

& $iscc ".\installer.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup 安装包构建失败。"
}

Write-Host "构建完成：installer_output\项目档案本地管理系统-Setup.exe"
