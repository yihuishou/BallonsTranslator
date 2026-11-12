# Windows 启动与桌面快捷方式

适用环境：本机 Windows，项目根目录 `C:\Users\EvilEnergySeaUrchin\PycharmProjects\BallonsTranslator`。

## 1. 启动入口

程序入口是 `python -m ballontranslator`。资源路径不依赖启动时的工作目录：`shared._resolve_program_path()` 从包位置向上查找含 `config/`、`data/`、`resources/` 的目录，`launch.py` 随后 `os.chdir()` 过去。但 `-m` 能否找到包取决于 `sys.path`——内嵌环境的 `python310._pth` 已含 `..`（项目根），从任意目录都能启动；venv 方式则要求 cwd 为项目根目录。下面的命令统一在项目根目录执行。

| 方式 | 命令 | 说明 |
| --- | --- | --- |
| 官方启动脚本（推荐） | `launch_win.bat` | 把 `ballontrans_pylibs_win` 加入 PATH，检查 python 与 pip 后执行 `-m ballontranslator`；结尾 `pause`，窗口保留以便查看报错 |
| 内嵌环境直调 | `ballontrans_pylibs_win\python.exe -m ballontranslator` | Python 3.10.11 embeddable，已含 PyQt6 / qtpy；`python310._pth` 含 `.` 与 `..`，`sys.prefix` 指向自身目录，不依赖系统 Python |
| venv 直调 | `venv\Scripts\python.exe -m ballontranslator` | Python 3.12.10，PyQt6 / qtpy 同样可用；不经过 bat 的 PATH 与环境变量设置 |

在项目根目录的 cmd 中运行：

```cmd
cd /d C:\Users\EvilEnergySeaUrchin\PycharmProjects\BallonsTranslator
launch_win.bat
```

macOS / Linux 使用 `./launch.sh`，优先取 `.venv/bin/python`，否则回退到系统 `python` / `python3`。

## 2. 桌面快捷方式

桌面上的 `BallonsTranslator.lnk` 配置如下，双击即可启动：

| 字段 | 值 |
| --- | --- |
| 目标 | `C:\Users\EvilEnergySeaUrchin\PycharmProjects\BallonsTranslator\launch_win.bat` |
| 起始位置 | `C:\Users\EvilEnergySeaUrchin\PycharmProjects\BallonsTranslator` |
| 图标 | `%LOCALAPPDATA%\BallonsTranslator\logo.ico` |

图标由 `resources/icons/logo.svg` 渲染成多尺寸 ico，与应用窗口图标同源。快捷方式右键可“固定到任务栏”或“固定到开始屏幕”。

若需重建：桌面右键 → 新建 → 快捷方式，按上表填写目标和起始位置，再在“属性 → 更改图标”中指向该 ico。

**无控制台变体**：把目标改为 `ballontrans_pylibs_win\pythonw.exe`、参数写 `-m ballontranslator`、起始位置不变，可隐藏控制台窗口；代价是异常时看不到 traceback，建议只在确认能正常运行后使用。

## 3. 失败模式与排查

- 双击后控制台一闪而过：在项目根目录手动运行 `launch_win.bat`，检查 `tmp\stdout.txt` / `tmp\stderr.txt`。
- 报 `msvcp140.dll`、`c10.dll` 或 `[WinError 1114]`：安装或更新 [Microsoft Visual C++ Redistributable x64](https://aka.ms/vc14/vc_redist.x64.exe)（VS 2015-2022）。
- 首次启动会自检核心依赖；选用需要额外库的模块时，程序会提示安装缺失的可选依赖（也可在设置中启用自动安装）。
- 启动后界面语言由 `config/config.json` 的 `display_lang` 决定，切换后**需重启**才生效。
- 一键翻译前先在设置里配好源语言与目标语言，再打开含图片的文件夹点击 Run。

## 4. 验证范围

已验证：两套 Python 版本与 `qtpy` / `PyQt6.QtWidgets` 导入正常；快捷方式文件结构（目标、起始目录、图标字段）回读校验一致；ico 图像可正常渲染。

未验证：未实际双击运行快捷方式启动 GUI。若 Windows 提示快捷方式不可用，按第 2 节重建即可。

环境本身的结构差异、以及把 venv 改造成内嵌运行环境的可行性，见 [将 venv 改造为内嵌运行环境](windows_portable_runtime.md)。
