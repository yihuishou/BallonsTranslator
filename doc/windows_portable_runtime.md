# 将 venv 改造为内嵌运行环境的可行性

相关：[Windows 启动与桌面快捷方式](launch_windows.md)

## 结论

- **不用改代码**：`launch_win.bat` 与 `launch.py` 已经按 `ballontrans_pylibs_win` 这种内嵌布局设计，只要目录名、位置、`python.exe` 和 `pip` 满足约定即可。
- **但不能靠复制或改名 `venv` 目录实现**：venv 不是自包含环境，它依赖 `C:\Program Files\Python\Python312`。要做成可移植环境，必须重建成 embeddable 布局。
- **若目的只是本机启动且不依赖系统 Python，现状已满足**：现有的 `ballontrans_pylibs_win` 就是这种环境，桌面快捷方式走的也是它，无需任何改动。

## 1. 两套环境的现状

| 项目 | `venv` | `ballontrans_pylibs_win` |
| --- | --- | --- |
| Python | 3.12.10 | 3.10.11（embeddable） |
| 基础解释器 | `C:\Program Files\Python\Python312` | 自身目录（`sys.prefix == sys.base_prefix`） |
| 可执行文件 | `Scripts\python.exe` | 根目录 `python.exe` / `pythonw.exe` |
| `sys.path` 来源 | `pyvenv.cfg` + 当前目录 | `python310._pth`：`python310.zip`、`.`、`..`、`import site` |
| site-packages | 340 项 | 260 项 |
| 附加 DLL 目录 | `Library` 约 25 MB | `Library` 约 646 MB |
| 体积 | 约 5.5 GB | 约 6.9 GB |
| torch | 2.9.0a0+rocm7.0.0rc | 2.3.1+cu118 |
| PyQt6 | 6.12.0 | 6.12.0 |

## 2. 代码侧契约

| 位置 | 约定 |
| --- | --- |
| `launch_win.bat` | PATH 前缀为 `ballontrans_pylibs_win;ballontrans_pylibs_win\Scripts`，`PYTHON=python.exe`，只按目录名找解释器 |
| `launch.py` → `disable_bundled_windows_user_site()` | 仅当 `sys.executable` 的父目录名为 `ballontrans_pylibs_win` 时，设 `PYTHONNOUSERSITE=1`、剔除用户级 site-packages、置 `site.ENABLE_USER_SITE = False`；目录改名会失去这层隔离 |
| `launch.py` → `ensure_core_requirements()` | 启动时自检核心依赖；`utils/package_installer.py` 用 `sys.executable -m pip` 安装，并在 exe 同目录查找 `uv.exe`。因此新环境必须自带 pip（uv 可选） |
| `utils/shared.py` → `_resolve_program_path()` | 从包文件位置向上定位含 `config/`、`data/`、`resources/` 的目录；`launch.py` 随后 `os.chdir()` 过去 |

结论：目录名保持 `ballontrans_pylibs_win`、位于项目根下、内含可用的 `python.exe` 与 `pip`，这四条满足后，`.py` 和 `.bat` 都不用改。

## 3. 直接复制 venv 的失败模式

- **仍依赖系统 Python**：`venv/pyvenv.cfg` 的 `base-prefix` 指向 `C:\Program Files\Python\Python312`，标准库、`python312.dll`、`DLLs` 都在那里。本机改名后能运行，只因系统 Python 仍在；换机器或卸载即失效。
- **控制台脚本失效**：`Scripts` 下 88 个 exe 的 shebang 硬编码 `#!C:\...\venv\Scripts\python.exe`（已实测 `pip.exe`、`pyside6-lrelease.exe`），复制后需重装生成或改用 `python -m`。
- **virtualenv 残留**：`Lib/site-packages/_virtualenv.pth` 是 virtualenv 专属，不应带入 embeddable 环境。
- **ABI 冲突**：venv 的 `.pyd` 是 cp312，不能混入现有 cp310 的 `ballontrans_pylibs_win`；只能整体换成 Python 3.12 的 embeddable。
- **漏带运行时资产**：除 `site-packages` 外还有 `Library/`、`bin/`、`opt/`、`share/`、Qt 插件及 torch 的 DLL 目录，缺一即可能导入失败。
- **隔离性下降**：若目录不叫 `ballontrans_pylibs_win`，用户级 site-packages 会重新混入。

## 4. 正确做法（确实需要时）

1. 下载与 venv 一致的 `python-3.12.10-embed-amd64.zip`，解压到新建目录。
2. 修改 `python312._pth`：取消注释 `import site`，并在 `.` 之后加 `..`（项目根）。
3. 用 `get-pip.py` 安装 pip，并放入 `uv.exe`，保证启动自检与按需安装可用。
4. 复制 `venv/Lib/site-packages` 全部内容，以及第 3 节列出的非 site-packages 运行时资产；去掉 `_virtualenv.pth`。
5. 重新生成 `Scripts` 下的控制台脚本，或改用 `python -m` 调用。
6. 先以并行目录（例如 `ballontrans_pylibs_win_312`）验证 `python -m ballontranslator` 与核心依赖导入，通过后再考虑替换；**保留原目录**，不要原地覆盖。

## 5. 风险与边界

- **版本差异**：torch 从 CUDA 11.8 版换成 ROCm 预发布版，Windows 上需额外 HIP DLL 与驱动支持，跨机器分发风险高；numpy 也从 1.26.3 变为 1.26.4。
- **体积**：单套环境 5.5–6.9 GB，复制与打包代价大。
- **官方脚本的行为**：`scripts/install.ps1` 会先 `Remove-Item -Recurse -Force ballontrans_pylibs_win` 再下载 3.12.10 embeddable 重建，直接运行会删除现有可用环境；发布免配置包应走 `scripts/build_win_minimal.ps1 -UseLocalSource`（默认同样使用 3.12.10 embeddable + pip + uv，依赖运行时按需安装）。
- **模型不在环境内**：`data/models` 下的模型文件需单独随包携带。
- **按需后端**：`onnxruntime` 在两套环境中都未安装，属于选用对应 OCR 模块时才安装的依赖，不算环境缺陷。

## 6. 按目的选择

| 目的 | 建议 |
| --- | --- |
| 本机双击启动、不依赖系统 Python | 维持现状，使用桌面快捷方式 |
| 升级到 Python 3.12 / 产出免配置分发包 | 用 `scripts/build_win_minimal.ps1 -UseLocalSource` 生成 zip |
| 离线固化已装依赖（不联网装包） | 才需要按第 4 节「提取 site-packages」，并行目录验证后再替换 |

## 7. 验证记录

- 已实测：两套解释器的 `sys.version` / `sys.prefix` / `sys.base_prefix` 与 `sys.path`；20 项核心依赖导入（两套均 19 项通过，仅 `onnxruntime` 缺失）；PyQt6、torch、numpy 版本；目录体积；`pip.exe`、`pyside6-lrelease.exe` 的 shebang。
- 未验证：未实际构建新的 embeddable 环境，未启动 GUI 验证完整启动链路。
