# Agent.md

本文档是 BallonsTranslator 的**项目结构地图与协作入口**：说明项目用途、目录组织、模块职责、运行方式与协作约束，供新加入的维护者与自动化 Agent 快速定位代码。

- 代码规范、数据安全、Qt 约束等**强约束规则**见 [AGENTS.md](AGENTS.md)，本文不重复罗列，仅在必要处引用。
- 文本排版/特效/变换等专题细节见 [doc/ui/text_engine.md](doc/ui/text_engine.md) 及其子文档；绘制工具见 [doc/ui/draw_panel.md](doc/ui/draw_panel.md)。

---

## 1. 项目用途

BallonsTranslator 是一个基于 **PyQt/qtpy** 的桌面端**漫画/图片翻译工具**，把"图片 → 文本检测 → OCR → 翻译 → 抹字重绘 → 排版渲染 → 导出"整条流水线做成可视化交互编辑器。

核心能力：

| 环节 | 能力 |
| --- | --- |
| 文本检测 | CTD、CTBD、YOLOv5 系列、Starriver 云端检测 |
| OCR | MIT48px/32px、Manga-OCR、PaddleOCR-VL、Google Lens/Cloud Vision、Windows/macOS 系统 OCR、LLM 视觉 OCR |
| 翻译 | Google/Baidu/DeepL/Yandex/Papago/Sakura/Sugoi/M2M100 等在线或本地模型，以及基于 LLM 的上下文翻译 |
| 抹字 | LaMa、AOT、Flux、PatchMatch、LLM Inpaint 等 |
| 排版渲染 | 富文本 `QTextDocument` + 上下/横排布局、仿射/网格/贝塞尔等变换、描边阴影渐变等特效、竖排注音 |
| 工程能力 | 项目文件持久化、批量流水线、无头（headless）批处理、多语言界面、在线模块安装与模型下载 |

技术栈：Python 3.8–3.12、qtpy（默认 PyQt6，Python 3.8 走 PyQt5）、numpy/opencv/numba、可选 torch 后端。许可证 GPL-3.0-or-later。版本号唯一来源是 [pyproject.toml](pyproject.toml) 的 `project.version`（运行时由 `utils/version.py` 读取）。

---

## 2. 快速开始

### 2.1 运行

```bash
# 源码运行（推荐）
python -m ballontranslator

# 打开指定项目
python -m ballontranslator --proj-dir /path/to/project

# 无头批处理（不出界面，串行跑完队列目录）
python -m ballontranslator --headless --exec_dirs "[DIR_1],[DIR_2]"
```

| 入口 | 说明 |
| --- | --- |
| [launch.sh](launch.sh) | macOS/Linux 启动器，优先使用仓库内 `.venv/bin/python`，未找到则回退系统 `python` |
| [launch_win.bat](launch_win.bat) | Windows 启动器，把 `ballontrans_pylibs_win` 前置到 `PATH`，再执行 `python -m ballontranslator` |
| [scripts/install.sh](scripts/install.sh) / [scripts/install.ps1](scripts/install.ps1) | 下载发行版、建虚拟环境并安装依赖 |
| `ballontranslator` 命令行脚本 | `pyproject.toml` 注册的 console script，等价于 `launch:main` |

### 2.2 常用命令行参数

`launch.py` 在模块导入早期解析参数：

| 参数 | 作用 |
| --- | --- |
| `--proj-dir` | 启动即打开项目目录 |
| `--qt-api {pyqt6,pyside6,pyqt5,pyside2}` | 指定 Qt 绑定，默认 `pyqt6`（Windows 7 默认 `pyqt5`） |
| `--config` / `--config_path` | 指定配置文件，默认 `config/config.json` |
| `--headless` | 无界面运行；`--exec_dirs` 给出待处理项目队列，可用逗号分隔 |
| `--export-translation-txt` / `--export-source-txt` | RUN 结束后导出译文/原文 txt |
| `--system_hf_cache` | 使用系统 HuggingFace 缓存，默认把 `HF_HOME` 指向 `data/models` |
| `--ldpi` | 覆盖逻辑 DPI（高 DPI 缩放调试） |
| `--debug` | 置 `BALLOONTRANS_DEBUG=1`，输出更详细日志 |

### 2.3 依赖边界

[requirements.txt](requirements.txt) 只包含**启动 UI 与共享图像/项目逻辑所必需**的依赖；具体模块后端（torch、paddle、onnxruntime、各家 SDK 等）由应用内包管理器在首次使用/显式安装时按需装入。因此"模块列表里有但跑不起来"通常是缺少可选依赖，而非注册失败。

---

## 3. 目录结构总览

```text
BallonsTranslator/
├── ballontranslator/          # 主包（唯一需要打包的代码）
│   ├── __main__.py            # python -m ballontranslator 入口
│   ├── launch.py              # 启动、依赖自检、Qt 环境、字体、headless
│   ├── assets/                # 包内资源（字体热刷新演示字体）
│   ├── ui/                    # 全部界面、画布、面板、工作线程、文本引擎
│   ├── modules/               # 检测/OCR/翻译/抹字 实现与注册体系
│   └── utils/                 # 配置、项目持久化、字体、IO、工具函数
├── config/                    # 运行时配置（config.json、textstyles/）※ git 忽略
├── data/                      # 模型、词典、原生库（models/、libs/）※ 大文件忽略
├── resources/                 # 主题、样式表、图标、Qt 翻译 .ts/.qm
├── doc/                       # 维护者文档与多语言 README
├── tests/                     # pytest 用例（96 个文件，含 1 个共享 support 模块）
├── scripts/                   # 安装、构建、翻译同步、模块调试脚本
├── custom_modules/            # 用户自定义模块放置目录
├── fonts/                     # 用户字体目录（内容 git 忽略）
├── logs/                      # 运行日志输出（git 忽略）
├── tmp/                       # 启动脚本临时 stdout/stderr
├── ballontrans_pylibs_win/    # Windows 便携 Python 运行时（git 忽略）
├── venv/ .venv/               # 本地虚拟环境（git 忽略）
├── launch.sh / launch_win.bat # 平台启动脚本
├── pyproject.toml             # 打包、版本、pytest 配置
├── requirements.txt           # 核心依赖
├── AGENTS.md                  # 代码与协作强约束（先读）
└── Agent.md                   # 本文件：结构地图
```

> 仓库根目录下的 `ui/`、`utils/`、`modules/` 仅含 `__pycache__`/`.pyc` 残留（历史编译产物），**不是源码目录**，改动请一律指向 `ballontranslator/` 下的同名包。清理前需按 AGENTS.md 的数据安全规则征得确认。

---

## 4. 运行时架构

### 4.1 启动链路

```text
__main__.py
  └─ launch.main()
       ├─ 早期参数解析 → 设置 QT_API / HF_HOME / NUMBA_CACHE_DIR
       ├─ preload_msvc_runtime()           Windows 下先加载 VC 运行时，避免 Qt 抢先解析 msvcp140.dll
       ├─ setup_logging(logs/) + ensure_resource_theme_files()
       ├─ auto_fill_network_mirrors()      按网络情况自动填 PyPI/HF 镜像
       ├─ ensure_core_requirements()       缺失核心依赖则安装并重启进程
       ├─ shared.load_cache() / config.load_config()
       ├─ QApplication + QTranslator + 字体注册表（FONT_REGISTRY / 字体别名）
       └─ MainWindow(app, config, open_dir=...) → app.exec()
```

`utils/shared.py` 是**全局运行时状态与路径中心**：解析 `PROGRAM_PATH`（依次尝试 `BALLOONTRANS_APP_ROOT`、当前工作目录、包父目录），并暴露 `CONFIG_PATH`、`RESOURCE_DIR`、`LOGGING_PATH`、`cache_path`、`HEADLESS`、`FLAG_QT6`、`FONT_REGISTRY` 等。跨模块共享的"环境开关"应放这里，避免各处重复探测平台。

### 4.2 流水线数据流

```text
ProjImgTrans（项目：页 → TextBlock 列表）
   ↓ 图片数组
文本检测 TextDetector.detect(img, proj)      → (掩码, TextBlock 列表)
   ↓
OCR           OCRBase.run_ocr(img, blk_list) → TextBlock.text（原文）
   ↓
翻译          BaseTranslator.translate()     → TextBlock.translation（译文）
   ↓
抹字          Inpainter.inpaint(img, mask)   → 抹字结果图
   ↓
排版渲染 TextBlkItem + SceneTextLayout + TextEffectRenderer
   ↓
保存/导出（图片、txt、docx、项目 JSON）
```

- 完成状态用位掩码表达：`RunStatus.FIN_DET/OCR/INPAINT/TRANSLATE`，`FIN_ALL = 15`；配置里对应 `module.finish_code`。
- 中文排版相关的"竖排/横排、自动直排、字距、描边"等属于**渲染层**，不写回项目持久化的逻辑矩形。

### 4.3 模块注册体系（关键设计）

模块**不在 `__init__.py` 中 eager import**，而是"静态扫描元数据 + 按需导入实现"两段式：

| 组件 | 位置 | 职责 |
| --- | --- | --- |
| `Registry` / `ModuleSpec` | [utils/registry.py](ballontranslator/utils/registry.py) | 保存 `key → spec`，`spec.resolved_class` 延迟解析 |
| AST 扫描器 | [modules/lazy_registry.py](ballontranslator/modules/lazy_registry.py) | 读源码 AST 提取装饰器 key、`params`、语言表，**不 import、不构造、不发网络请求** |
| `SafeEval` | 同上 | 只允许字面量与纯函数式表达式求值，保证配置元数据无副作用 |
| 注册入口 | [modules/__init__.py](ballontranslator/modules/__init__.py) | `init_module_registries()` → 注册 `ModuleSpec`；`MODULETYPE_TO_REGISTRIES` 映射四类注册表 |
| 基类生命周期 | [modules/base.py](ballontranslator/modules/base.py) | `params`、`dependencies`、`download_file_list`、`_load_model_keys` 与 `load_model()/unload_model()` |

发现范围：`MODULE_SCRIPTS` 指定的包内目录（`textdetector/`、`ocr/`、`translators/`、`inpaint/`）+ `EXTRA_MODULE_FILES` + 仓库根 `custom_modules/`。自定义模块扫描失败只告警，内置模块扫描失败直接抛错。

因此新增模块的硬性要求是：**元数据必须能被静态读取**（字面量 `params`、字面量语言赋值），且注册 key 一旦写入用户配置就不能随意改名（改名需保留兼容别名）。

### 4.4 项目文件与磁盘布局

`ProjImgTrans` 管理"一个漫画目录 = 一个项目"：

```text
<project_dir>/
├── <project_name>.json   # 页 → TextBlock 列表、项目元信息（唯一可持久化状态）
├── mask/                 # 每页文本掩码
├── inpainted/            # 每页抹字结果
└── <图片文件>            # 源图（不修改、不删除）
```

只有**已提交的 `TextBlock` 与 `FontFormat` 状态**进 JSON；`QTextDocument`、光标、选区、布局缓存、预览 pixmap 都是派生数据，不落盘。加载必须宽容：未知/损坏/越界字段只丢弃该部分并告警，绝不能用空模板覆盖已有文件。

### 4.5 配置体系

[utils/config.py](ballontranslator/utils/config.py) 用 `utils/structures.py` 的 `Config`（基于 dataclass 的嵌套结构）定义：

| 配置类 | 覆盖范围 |
| --- | --- |
| `ProgramConfig` | 顶层：`module`、`package_manager`、`mirrors`、`drawpanel`、`auto_tate_chu_yoko`、字体后端、搜索/显示偏好、最近项目等 |
| `ModuleConfig` | 四类模块的当前选择、`*_params`、LLM profile/context/glossary、源/目标语言、`finish_code` |
| `DrawPanelConfig` | 画笔、形状填充、抹字工具参数 |
| `PackageManagerConfig` / `NetworkMirrorsConfig` | 包安装与镜像设置 |
| `AutoTateChuYokoConfig` | 自动直排（Tate-Chu-Yoko）规则 |

相关路径：配置文件 `config/config.json`；文本样式 `config/textstyles/*.json`；缓存 `.btrans_cache/cache.json`；日志 `logs/`（保留份数 `shared.MAX_NUM_LOG`）。API 密钥由 `utils/secret_store.py` 管理，配置里只存 `keyring://BallonsTranslator/llm/...` 引用，实际值在系统 keyring（不可用时回退便携式加密存储）。

---

## 5. 主要模块职责

### 5.1 `ballontranslator/`

| 文件 | 职责 |
| --- | --- |
| `launch.py` | 早期参数解析、进程级 Qt 环境（`-platform`、GDI/freetype 字体后端、offscreen）、VC 运行时预载、核心依赖修复与重启、日志/镜像/字体初始化、构造 `MainWindow` |
| `__main__.py` | 仅转调 `launch.main()` |

### 5.2 `ballontranslator/ui/`

| 文件 | 职责 |
| --- | --- |
| `mainwindow.py` | `MainWindow`：装配画布、左右面板、标题/底栏，持有 `ProjImgTrans` 与 `ModuleManager`，负责打开/保存项目、菜单与快捷键、批量 RUN、样式与主题应用 |
| `canvas.py` | `Canvas(QGraphicsScene)` + `CustomGV(QGraphicsView)`：场景、缩放/拖拽、图元管理、导出渲染 |
| `module_manager.py` | **工作线程与模块调用的唯一所有者**：`ModuleThread` 及 `InpaintThread/TextDetectThread/OCRThread/TranslateThread`、`ImgtransThread`（整页流水线）、模块选择与参数变更、取消/进度信号 |
| `drawingpanel.py` | 绘制/抹字工具面板：画笔、矩形、形状填充、工具参数与状态切换 |
| `configpanel.py` | 设置面板（无边框窗口 + `ConfigBlock/ConfigSubBlock` 半自动表单），按 `Config` 结构生成 UI；General 分组含 `lptxt` 页（「备注」仿 CodeX 提示词的 `QPlainTextEdit` + 「Photoshop 动作分组」可增删改列表，每项含可选字体、列表显示 `序号. 名称    字体：X`；说明文字为小字且可换行；1-based 序号与字体仅显示，真实值存 `UserRole` 为 `{"name","font"}`；分组定义变化时发 `lptxt_groups_changed` 信号） |
| `mainwindowbars.py` | `TitleBar` / `LeftBar` / `BottomBar`：工具入口、状态指示、翻页与进度 |
| `framelesswindow/` | `FramelessWindow`、`FramelessMoveResize`、`OutsideClickFramelessMixin`：统一无边框窗口基座 |
| `custom_widget/` | 通用控件库：复选框、下拉框、流式布局、滑块、滚动条、消息框、`Widget/ViewWidget` 基类 |
| `text_engine/` | 文本排版/编辑/特效/变换引擎（见 5.3） |
| `module_parse_widgets.py` / `module_param_i18n.py` / `_generated/` | 由模块 `params` 元数据自动生成参数对话框，并做参数名本地化（`_generated` 为生成文件） |
| `io_thread.py` | 后台导入/导出/保存线程（docx、图片批量导出） |
| `update_thread.py` / `update_dialog.py` / `updater` 相关 | 版本检查与更新提示（配合 `utils/updater.py`） |
| `package_manager.py` / `packageinstall_thread.py` / `torch_install_dialog.py` | 应用内依赖/模块安装与 torch 版本选择 |
| `llm_*.py`、`codex_*.py` | LLM 配置编辑、多模态开关、上下文编辑器、Codex 账号与登录 |
| `font_refresh.py`、`font_change_detection.py`、`funcmaps.py` | 运行时字体刷新、字体变更检测、文本功能映射 |
| `misc.py`、`menu_style.py`、`icon_rendering.py`、`spellcheck.py`、`shared_widget.py`、`merge_dialog.py`、`*search*.py`、`run_pipeline_dialog.py`、`ps_bridge_dialog.py` | 样式解析、菜单风格过滤、SVG 图标渲染、拼写检查、共享控件注册表（`SW`）、区域合并、页内/全局搜索、流水线参数对话框、Photoshop 桥接 |

`shared_widget.py`（导入别名 `SW`）是 UI 层的轻量服务定位器（`SW.canvas` 等），用于避免把主窗口逐层透传；新增全局可访问控件时应注册到此处而不是新增单例。

### 5.3 `ballontranslator/ui/text_engine/`

文本引擎按"持久化状态 → Qt 模型 → 布局 → 特效 → 几何 → 场景"分层，详细契约见 [doc/ui/text_engine.md](doc/ui/text_engine.md)。

| 子模块 | 职责 |
| --- | --- |
| `item.py` | `TextBlkItem`：`TextBlock` 与 Qt 图元的集成点（`initTextBlock()` 是真实构造路径） |
| `layout.py` / `horizontal_layout.py` / `vertical_layout.py` | `SceneTextLayout`：字形排布、书写模式、间距与放置 |
| `geometry.py` / `shape_control.py` / `transforms/` | 坐标空间映射、包围盒、变换控件与网格/正弦/弯曲等变形 |
| `effects/` | 特效合成、alpha 掩码、阴影/描边/渐变、滤镜、`paint_numba` 加速、渲染器与编辑会话 |
| `editing/` | 源/译文成对编辑框、场景文本管理、移动会话、右键菜单、撤销命令 |
| `formatting/` | 字号/字距/对齐等格式化命令、预设与拖拽交互 |
| `rendering/` | 字形、栅格、注音（ruby）、直排、倾斜、强调等底层绘制 |
| `annotations.py` | 富文本导入导出与注解转换 |
| `cache.py` | 布局/渲染缓存与失效策略 |
| `pipeline_formatting.py` | RUN 流水线中的自动排版（如自动直排） |

### 5.4 `ballontranslator/modules/`

| 路径 | 职责 |
| --- | --- |
| `base.py` | `BaseModule`（参数、依赖、模型加载生命周期）、设备选择、torch 可用性探测、`merge_config_module_params`、注册表初始化入口 |
| `lazy_registry.py` | AST 元数据扫描、`SafeEval`、`ModuleSpec` 校验 |
| `textdetector/` | `TextDetectorBase` + CTD/CTBD/YOLOv5/Starriver 实现，`panel_finder.py`（分格）、`db_utils.py` |
| `ocr/` | `OCRBase` + `OCR` 注册表与各 OCR 后端；`utils/` 下含 Lens protobuf、ONNX OCR、ScreenAI proto |
| `translators/` | `BaseTranslator`（含 `LANGMAP_GLOBAL`、分页/上下文/术语表契约）+ 各翻译服务；`llm_translation_contract.py` 定义 LLM 翻译结构约定 |
| `inpaint/` | `InpainterBase` + LaMa/AOT/Flux/PatchMatch/LLM 抹字，含 diffusers 管线封装 |
| `context/` | 翻译上下文：历史、术语表、token 预算、错误与统计 |
| `llm_chat.py` / `llm_vision.py` / `llm_image.py` | LLM 对话、视觉、图像生成能力封装 |
| `openai_responses.py` / `responses_ws.py` / `codex.py` | Responses API 与 WebSocket 传输、Codex 集成 |
| `package_import_names.py` | 模块 → pip 包名映射，供包管理器按需安装 |
| `prepare_local_files.py` | 本地模型/资源准备与校验 |
| `image_generation.py` | 图像生成类模块的公共入口 |

### 5.5 `ballontranslator/utils/`

| 分组 | 文件 |
| --- | --- |
| 配置与状态 | `config.py`、`shared.py`、`structures.py`、`llm_profiles.py`、`secret_store.py`、`lock.py` |
| 项目与持久化 | `proj_imgtrans.py`（项目/页/图片状态与保存）、`io_utils.py`（JSON/np/图片读写）、`raster_assets.py`（内容寻址位图资源引用） |
| 文本领域模型与区域处理 | `textblock.py`（`TextBlock` 核心对象）、`text_effects.py`、`text_alpha_mask.py`、`text_layout.py`、`text_processing.py`、`textblock_mask.py`、`split_text_region.py`、`textlines_merge.py`、`merger.py`（相邻区域合并）、`stroke_width_calculator.py` |
| 字体与字型 | `fontformat.py`（`FontFormat` 排版/特效数据）、`font_registry.py`（字体注册表与别名）、`font_detect.py`（OCR 后字体探测）、`font_refresh.py`（运行时字体刷新边界） |
| 图像 | `imgproc_utils.py`、`rgba.py` |
| 模块与依赖 | `registry.py`、`core_requirements.py`、`package_installer.py`、`py_package_manager.py`、`torch_install_helper.py`、`download_util.py`、`network_mirrors.py` |
| 运行支撑 | `logger.py`、`message.py`、`global_callbacks.py`（停止请求等全局回调）、`updater.py`、`version.py` |

### 5.6 资源、文档与脚本

| 目录 | 内容 |
| --- | --- |
| [resources/](resources/) | `stylesheet.css` + `themes.json`（主题令牌）、`icons/`（SVG）、`translate/*.ts` 与编译产物 `*.qm`、`font_registry_overrides.json` |
| [doc/](doc/) | `ui/` 文本引擎系列、`modules/llm_translator.md`、`localization.md`、`how_to_add_new_translator.md`（含中/俄版本）、`CHANGELOG*.md`、多语言 README |
| [tests/](tests/) | pytest，覆盖文本引擎、画布生命周期、模块注册、LLM 契约、配置迁移等 |
| [scripts/](scripts/) | `install.*`（安装）、`build_win_minimal.ps1`（Windows 便携构建）、`run_module.py`（单独调试某个模块）、`update_translation.py` / `merge_zh_translation.py`（Qt 翻译同步）、`BTjson_to_LPtxt.py`（LabelPlus txt 命令行/GUI 导出入口，逻辑见 `ballontranslator/utils/lptxt_export.py`；命令行 `--groups` / GUI 输入框可指定分组列表，顺序即分组序号；主程序入口为「工具」菜单的「导出 Label TXT」，输出纯译文、不含字体字号，见 `ui/mainwindowbars.py` → `ui/mainwindow.py:on_export_lptxt`，直接传内存工程数据）、`export to photoshop/` |
| [.github/](.github/) | Issue 模板；`workflows/release.yml` 在推送 `v*` 标签时用 `build_win_minimal.ps1` 构建并发布 Windows 包 |

---

## 6. 开发方式

### 6.1 环境

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m ballontranslator
```

Python 版本决定 Qt 绑定：`>3.8` 用 PyQt6，`3.8` 用 PyQt5。新增第三方依赖需经批准，并优先通过模块的 `dependencies` 字段按需安装，避免扩大核心依赖面。

### 6.2 测试与验证

```bash
pytest                        # pyproject 已配置 pythonpath=["."]
pytest tests/test_lazy_metadata.py -q
python -m py_compile <改动的文件>
git diff --check
```

UI 相关改动建议再做一次 offscreen 冒烟：`python -m ballontranslator --headless`。验证标准与例外情形见 [AGENTS.md](AGENTS.md#verification)。

### 6.3 新增模块

以翻译器为例（完整说明见 [doc/how_to_add_new_translator.md](doc/how_to_add_new_translator.md)）：

1. 内置实现放 `ballontranslator/modules/translators/trans_<name>.py`；本地扩展放 `custom_modules/trans_<name>.py`。
2. 用 `@register_translator("unique_key")` 注册；key 会写入用户配置，必须稳定。
3. 重写 `_translate(list) -> list`（长度与顺序必须一致），在 `_setup_translator()` 里填 `lang_map`。
4. 参数以类级 `params` 声明；模型等重资源走 `_load_model_keys` / `_load_model()`。
5. 重启应用即可被发现；**不要**在 `__init__.py` 里加 eager import。

检测器、OCR、抹字同理，分别使用 `register_textdetectors` / `register_OCR` / `register_inpainter` 装饰器与对应基类（`TextDetectorBase` / `OCRBase` / `InpainterBase`）。

### 6.4 本地化

界面文案用 `QApplication.translate`，资源为 `resources/translate/*.ts`，用 `scripts/update_translation.py` 同步（该脚本同时重新生成 `ui/_generated/module_param_dialog_i18n_catalog.py`，**不要手改**）、`merge_zh_translation.py` 合并，再用 Qt `lrelease` 生成 `.qm`。新增语言需同时登记到 `shared.DISPLAY_LANGUAGE_MAP`（或直接提供对应 `.qm`）。详见 [doc/localization.md](doc/localization.md)。

### 6.5 构建发布

Windows 便携包由 `scripts/build_win_minimal.ps1` 生成（CI 使用 Python 3.12.10），产物为 `Ballonstranslator_win_minium.zip`，推 `v*` 标签自动发布。版本号只改 `pyproject.toml`。

---

## 7. 协作注意事项

以下为高频踩坑点，完整清单以 [AGENTS.md](AGENTS.md) 为准。

### 7.1 数据安全（最高优先级）

- 预设的 config、备份、凭据、项目、模型文件属于用户资产：**未经明确授权不得删除、覆盖、移动或"清理"**。
- 被动加载必须宽容：遇到未知/已移除/改名/格式错误的可选数据只告警并丢弃该部分，**禁止**用空态覆盖已有文件。
- 项目保存沿用既有备份策略；源图只读。
- 新增持久化字段必须为旧项目提供默认值。

### 7.2 线程与 Qt 生命周期

- 推理、IO、下载、模型加载一律不占 Qt 主线程；线程与信号编排的唯一归属是 `ui/module_manager.py`，改动前先梳理信号顺序。
- 不要把子对象/短生命周期信号连到捕获父对象的 lambda、闭包或 `partial`；优先用绑定的 QObject slot、`sender()` 读数据或类型化行信号。
- `close()`/`hide()` 不销毁对象；一次性模态对话框在 `exec_()` 后读状态并在 `finally` 里 `deleteLater()`；有意缓存的常驻面板保留 `hide()`。
- headless 模式下流水线必须能跑通或安全 no-op。

### 7.3 UI 样式与事件过滤

- 轻量设置/工具窗复用 `OutsideClickFramelessMixin` + 无边框 `QFrame` + 主题令牌样式；确认/进度类流程不得点击外部即关闭。
- 样式按 object/section name 限定作用域，禁止宽泛控件选择器；颜色优先用 `resources/themes.json`、`resources/stylesheet.css` 的令牌。
- 绝不在 `Polish`/`StyleChange`/`Paint` 里改样式机制（`setStyle`、`setStyleSheet`、`polish` 等），否则可能崩溃 Qt。
- 应用级事件过滤器是全局钩子：仅在生效期间安装，并在隐藏/关闭/销毁时移除；先判断可见性、接收者与事件类型，再访问 `event.type()` 与全局坐标。

### 7.4 模块与配置兼容

- 使用既有注册表与稳定 key；改名必须提供兼容别名。
- 配置 UI 元数据必须是惰性、`SafeEval` 兼容且纯粹的：不得执行初始化、`_setup_*`、`flush`、模型加载、下载或网络请求。
- 保持惰性/即时加载行为不变；可选集成的失败要给出清晰的安装提示，而不是崩溃。
- 令人意外的行为应通过配置项显式开启，并在 UI 中可发现。

### 7.5 代码风格与性能

- 先追调用链再改代码；优先复用或扩展现有实现，避免为单一场景引入抽象层与透传包装。
- 高频路径上避免重复查找/转换/校验/IO；修复重复调用要在其所有者处修，而不是加缓存。
- 只更新变化的数据与控件；整个面板重建仅用于重置/恢复。
- 状态迁移只有一个明确所有者；避免冗余同步路径与掩盖死循环的 `blockSignals()`。
- 新增/修改函数补类型标注，动态边界才用 `Any`。

### 7.6 提交前自检

1. 行为变化是否是最小、可评审的？
2. 旧项目/旧配置是否仍能加载？
3. 是否所有重活都在工作线程？
4. 是否补了针对可观察行为与失败模式的测试？
5. 是否清理了被替换的旧路径（无用的 helper、shim、重复状态）？
6. 文档/注释是否只补充了缺失或已变更的契约？

---

## 8. 常见任务定位

| 我要改… | 先看这里 |
| --- | --- |
| 启动流程、命令行参数、依赖自检 | `ballontranslator/launch.py`、`utils/core_requirements.py` |
| 全局路径、平台开关、运行时缓存 | `utils/shared.py` |
| 配置项与默认值 | `utils/config.py`（`ProgramConfig` / `ModuleConfig` / `DrawPanelConfig`） |
| 项目 JSON 结构、页/图状态 | `utils/proj_imgtrans.py`、`utils/textblock.py` |
| LabelPlus txt 导出、头部备注/Photoshop 动作分组 | `utils/lptxt_export.py`（`build_lptxt_header`，默认备注为「备注」；`_label_names` / `_group_no` 决定每个文本块坐标三元组末尾的分组序号）、`ui/configpanel.py` 的 `lptxt` 页、`ProgramConfig.lptxt_note` / `lptxt_text_labels`（序号即分组序号，写入 txt 的坐标三元组） |
| 文本框分组标识与分组字体覆盖 | `utils/textblock.py` 的 `TextBlock.group` / `effective_font_family` / `group_font_override`、`utils/config.py` 的 `first_lptxt_group_name` / `resolve_lptxt_group_name` / `get_lptxt_group_font`、`ui/text_engine/formatting/panel.py` 的 `FontFormatPanel.group_buttons`（分组按钮组平铺展示全部分组，位于「对齐」行下方，无文字标签、`AdaptiveWrapLayout` 居中换行排列，当前分组高亮、点击即改分组并写入 `blk.group`，发 `group_changed`）、`ui/text_engine/item.py` 的 `set_fontformat`/`get_fontformat`（分组字体只覆盖渲染，不覆盖存储）、`ui/mainwindow.py:on_lptxt_groups_changed`（设置改动后批量重算） |
| 文本排版、字体、描边特效、变换 | `ui/text_engine/` + `doc/ui/text_engine.md` |
| 画布交互、绘制工具、抹字手势 | `ui/canvas.py`、`ui/drawingpanel.py` + `doc/ui/draw_panel.md` |
| 流水线执行、线程、进度与取消 | `ui/module_manager.py` |
| 模块发现/注册/参数元数据 | `modules/lazy_registry.py`、`utils/registry.py`、`modules/base.py` |
| 某个检测/OCR/翻译/抹字后端 | `modules/<类别>/` |
| LLM 上下文、术语表、token 统计 | `modules/context/`、`utils/llm_profiles.py` |
| 主题、图标、界面翻译 | `resources/`、`scripts/update_translation.py` |
| 打包与发布 | `scripts/build_win_minimal.ps1`、`.github/workflows/release.yml` |

---

## 9. 本文档的维护

- 目录或模块职责发生变化时更新第 3、5 节；新增跨模块契约时更新第 4 节。
- **不要**把代码规范复制进来：规范属于 `AGENTS.md`，专题细节属于 `doc/`，每个事实只写一处。
- 实现细节放在代码与测试中，调查过程放在 PR 里。
