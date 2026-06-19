# 项目档案本地管理系统

Windows 单机版项目档案管理应用，运行时锁定为 Python 3.11。

## 工程结构

```text
project-archive-manager/
├── main.py                    # 统一应用入口
├── database.py                # SQLite 连接、建表、约束与动态状态查询
├── requirements.txt           # Python 3.11 依赖
├── requirements-dev.txt       # 自动化测试依赖
├── environment.yml            # Conda Python 3.11 环境
├── README.md
├── data/                      # 首次运行时自动创建，不提交数据库
│   └── project_archives.db
├── services/
│   ├── file_service.py
│   ├── borrow_service.py
│   ├── excel_service.py
│   └── directory_scan_service.py
├── ui_main.py                 # 主界面、全局搜索与表格操作
├── dialogs/                   # 项目、档案、借阅和归还对话框
├── tests/                     # 数据库、服务、Excel 和 UI 测试
└── build_windows.ps1          # pyside6-deploy Windows 构建脚本
```

## 本地运行

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Windows 数据库默认创建在
`%LOCALAPPDATA%\ProjectArchiveManager\data\project_archives.db`。
Linux 开发验证时使用源码目录的 `data/project_archives.db`。`Files` 表不包含 `status`
字段，档案状态始终通过未归还的 `BorrowRecords` 记录动态计算。

## 自动化测试

```bash
python -m pytest -q
```

Linux 无桌面服务器可使用：

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## Windows EXE 打包

在 Windows PowerShell 中激活 Python 3.11 环境后：

```powershell
.\build_windows.ps1
```

脚本使用 `pyside6-deploy`（底层 Nuitka）生成 EXE，再使用 Inno Setup 6
生成 `installer_output\项目档案本地管理系统-Setup.exe`。
