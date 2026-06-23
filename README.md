# 项目档案本地管理系统 V0.2

Windows 单机版项目档案管理应用，运行时锁定为 Python 3.11。

## V0.2 功能

- 大项目—子项目树形管理；
- 施工单位、设计单位、设计金额、完工日期等项目资料；
- 原件/复印件独立库存，多人按份数并行借阅；
- 借阅详情、联系电话、事由、预计归还日期及永久历史；
- 全局搜索结果保持，可连续操作后再显式定位项目；
- 勾选式批量移入回收站和恢复；
- 单项目 Excel 导入导出、整库 Excel 迁移；
- `.pambak` 完整数据库备份与恢复；
- 可选本机应用锁；
- V0.1 数据库自动升级，升级前自动保留数据库副本；
- Windows GUI 构建不显示控制台黑窗口。

## 本地运行

```bash
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Windows 数据位于：

```text
%LOCALAPPDATA%\ProjectArchiveManager\data\
```

数据库中的档案状态不单独保存，而是根据未归还借阅记录与库存实时计算。

## 自动化测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

无桌面环境：

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## Windows EXE 打包

```powershell
.\build_windows.ps1
```

输出：

```text
installer_output\项目档案本地管理系统-Setup.exe
```
