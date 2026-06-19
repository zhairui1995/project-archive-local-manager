# Windows 安装包构建说明

正常用户无需执行本文件；安装包发布者使用。

## 本地 Windows 构建

要求：

- Windows 10/11 x64；
- Python 3.11；
- Inno Setup 6。

PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
winget install JRSoftware.InnoSetup
python -m pytest -q
.\build_windows.ps1
```

成功后输出：

```text
installer_output\项目档案本地管理系统-Setup.exe
```

## GitHub Actions 构建

仓库包含 `.github/workflows/build-windows-installer.yml`。在 GitHub 仓库的
Actions 页面手动运行 `Build Windows Installer`，完成后下载
`ProjectArchiveManager-Windows-Installer` artifact。
