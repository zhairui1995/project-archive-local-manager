$ErrorActionPreference = "Stop"

if ($null -eq $env:VIRTUAL_ENV -and $null -eq $env:CONDA_PREFIX) {
    Write-Warning "建议先激活 Python 3.11 虚拟环境。"
}

$version = python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($version -ne "3.11") {
    throw "打包环境必须为 Python 3.11，当前为 Python $version。"
}

python -c "import PySide6, openpyxl; print('Dependency check passed')"

if (Test-Path ".\pysidedeploy.spec") {
    Remove-Item ".\pysidedeploy.spec" -Force
}
pyside6-deploy main.py --init

$spec = Get-Content ".\pysidedeploy.spec" -Raw
$spec = $spec -replace "title = .*", "title = ProjectArchiveManager"
$spec = $spec -replace "extra_args = .*", "extra_args = --quiet --windows-console-mode=disable --noinclude-qt-translations --assume-yes-for-downloads"
Set-Content ".\pysidedeploy.spec" $spec -Encoding UTF8

pyside6-deploy -c ".\pysidedeploy.spec" --force --keep-deployment-files

$exe = Get-ChildItem -Path "." -Filter "main.exe" -Recurse |
    Select-Object -First 1
if ($null -eq $exe) {
    throw "未找到 pyside6-deploy 生成的 main.exe。"
}
New-Item -ItemType Directory -Path ".\deployment" -Force | Out-Null
Copy-Item $exe.FullName ".\deployment\ProjectArchiveManager.exe" -Force

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
