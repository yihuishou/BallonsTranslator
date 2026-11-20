# BallonsTranslator 项目环境升级到 PyTorch 2.15.0 + ROCm 10.2

> 更新日期：2026-11-20
> 目标：把项目环境里的 torch 换成 `2.15.0+rocm10.2.0`，配合 ROCm 10.2 tarball（`C:\ROCm`）与 Adrenalin 26.11.2，显卡为 RX 7900 XTX（gfx1100）。

## 一、先确认项目现状

我实际检查了项目目录，结果与常见假设有出入，先说清楚：

| 环境 | Python | torch | 状态 |
| --- | --- | --- | --- |
| `ballontrans_pylibs_win`（文档所称的"内嵌库"） | — | — | **空目录**，无 `python.exe`，无法使用 |
| `venv` | 3.12.10 | `2.9.0a0+rocm7.0.0rc` | **实际可用**，含 torch |

`doc/windows_portable_runtime.md` 里记录的 `ballontrans_pylibs_win`（Python 3.10.11 embeddable + torch 2.3.1+cu118）是当时状态，现在该目录已被清空。**当前真正带 torch 的环境是 `venv`。**

## 二、三个必须避开的坑

### 坑 1：Python 版本不兼容

AMD 官方 wheel 索引中 `torch-2.15.0+rocm10.2.0` 的 Windows 版只提供：

- `cp311-cp311-win_amd64`
- `cp312-cp312-win_amd64`
- `cp313-cp313-win_amd64`
- `cp314-cp314-win_amd64`

**没有 cp310**。所以：

- 旧的 3.10 内嵌库（即使重建）**装不了** torch 2.15，必须用 3.11+
- 现有 `venv`（3.12.10）正好兼容

### 坑 2：项目安装器不认识 AMD

`ballontranslator/utils/torch_install_helper.py` 中：

```python
TORCH_INSTALL_DEVICE_OPTIONS = ('cpu', 'cuda', 'xpu')
```

设备选项只有 CPU / CUDA / XPU，没有 ROCm/AMD。自动探测逻辑：

- 检测到 NVIDIA GPU → CUDA profile
- 检测到 Intel XPU → XPU profile
- 都没有（**AMD 卡属于这种情况**）→ 落到 **CPU profile**

也就是说，如果走项目 UI 的自动安装，AMD 卡会被当成没有加速设备，装成 CPU 版 torch。

### 坑 3：绕过 device 改写的方法

`_has_plain_unpinned_torch()` 只在 torch 是"裸写、无版本约束"时才触发 profile 改写：

```python
if req.specifier or req.marker or req.url or req.extras:
    continue
```

因此只要 requirements 里的 torch **带 `==` 版本号**（或带 extra），就不会被改写，可以按指定源安装。手动 pip 命令天然满足这一点。

## 三、推荐做法：手动装进 venv

在项目根目录执行（PowerShell）：

```powershell
# 1. 记录当前版本（回退依据）
.\venv\Scripts\python.exe -c "import torch; print(torch.__version__)"

# 2. 卸载旧栈
.\venv\Scripts\python.exe -m pip uninstall -y torch torchvision torchaudio rocm rocm-sdk-core rocm-sdk-devel triton-windows triton

# 3. 安装 PyTorch 2.15.0 + ROCm 10.2
.\venv\Scripts\python.exe -m pip install -i https://stable.repo.amd.com/rocm/whl-next/ "torch[device-gfx1100]==2.15.0" "torchvision[device-gfx1100]==0.29.2" "torchaudio==2.11.1"

# 4. 验证
.\venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.hip, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

期望输出：`2.15.0+rocm10.2.0`、`True`、`AMD Radeon RX 7900 XTX`。

### 关键参数说明

- **`-i`（`--index-url`）必须是 AMD 仓库**：用 `--extra-index-url` 或不加，pip 会从 PyPI 拉到 CPU/CUDA 版
- **`[device-gfx1100]` 不能省**：它会一并安装预编译的 GPU kernel 包（`amd-torch-device-gfx1100` 等），缺少时 fused attention 等算子会失败
- **三个版本必须成对指定**：torch 2.15.0 / torchvision 0.29.2 / torchaudio 2.11.1，否则 pip 可能解析到其他组合
- 下载量约 1.1 GB

### 回退

如果升级后依赖 torch 的项目包（如 `open_clip_torch`、`PoPE-pytorch`、`torch-einops-utils` 等）出现 ABI/API 不兼容：

```powershell
.\venv\Scripts\python.exe -m pip install -r C:\Users\EvilEnergySeaUrchin\pip-backup-before-rocm102.txt
```

（该备份是全局 pip freeze；若只需回退 venv，应从升级前重新 `pip freeze > 备份路径`。）

## 四、项目依赖中哪些必须来自 AMD 仓库

上一节的安装命令只装 torch 家族，其余依赖仍需从 PyPI 装。哪些该走 AMD 源、哪些不该，做一次精确交叉比对后结论如下。

提取项目全部 **62 个去重依赖**（各模块的 `dependencies` + 根 `requirements.txt`），与 AMD 仓库约 30 个包求交集，**只有 6 个重合**。再按"是否真的必须从 AMD 装"分类：

### 1. 必须走 AMD 源（2 个）

| 包 | 原因 |
| --- | --- |
| `torch` | PyPI 版是 CPU/CUDA 构建，无 ROCm 支持。目标版本 `2.15.0+rocm10.2.0` |
| `torchvision` | 必须与 ROCm torch 版本配套，目标 `0.29.2+rocm10.2.0` |

这两个靠 `[device-gfx1100]` extra 自动拉入真正的 GPU kernel 包 `amd-torch-device-gfx1100` / `amd-torchvision-device-gfx1100`。这些 `amd-torch-device-*` / `rocm-sdk-*` 包**只在 AMD 仓库有**，但由 torch 安装时自动带入，无需手动列出。

### 2. 同一套栈、但项目没声明（1 个）

`torchaudio` —— 项目代码里没有任何模块依赖它。当前环境装了 `2.11.1+rocm10.2.0`；如将来要用，也只能从 AMD 源装。

### 3. AMD 仓库有镜像，但只是标准 wheel（4 个）

`numpy`、`pillow`、`networkx`、`jinja2` —— AMD 仓库里放的是 PyPI 同款通用 wheel（已核对 numpy 索引，就是标准 `win_amd64` / `manylinux` 文件，无 ROCm 特殊构建）。**从 PyPI 装效果完全相同，没必要指定 AMD 源。**

### 4. AMD 仓库没有，只能走 PyPI（其余 56 个）

包括 `PyQt6`、`transformers`、`opencv-python`、`einops`、`diffusers`、`safetensors`、`numba`、`onnxruntime`、`ultralytics`、`pywin32` 等。AMD 仓库全都没有。

### 5. 特例：triton

AMD 仓库的 `triton` **只有 Linux wheel**（`linux_x86_64`），Windows 上装不了。项目代码也没声明它，当前 venv 里未安装，无需处理。

### 关键警告：不要把 AMD 仓库设为全局唯一 index

AMD 仓库不是 PyPI 的完整镜像，只有约 30 个包；把它设为全局 `--index-url` 去装整个 `requirements.txt`，缺失的 56 个会全部安装失败。正确做法是分两步：

```powershell
# 第一步：AMD 源，只装 torch 家族
.\venv\Scripts\python.exe -m pip install -i https://stable.repo.amd.com/rocm/whl-next/ "torch[device-gfx1100]==2.15.0" "torchvision[device-gfx1100]==0.29.2" "torchaudio==2.11.1"

# 第二步：默认 PyPI 源，装项目其余依赖
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

第二步若 pip 看到 requirements 里的裸 `torch`（不指定版本）已满足，通常不会改动它，但**不要带 `--upgrade`**，否则会把 ROCm torch 换成 PyPI 的 CPU 版。

结合"坑 2"可知：这两步只能手动执行。项目 UI 的安装路径没有 ROCm profile，装不出 `2.15.0+rocm10.2`。

## 五、为什么不能走项目 UI 的"重装 Torch"

项目的安装器 `package_installer.build_install_command()` 支持通过环境变量注入源：

```python
index_url = env.get('INDEX_URL')
index_args = ['-i', index_url] if index_url else []
find_links = env.get('FIND_LINKS')
find_links_args = ['-f', find_links] if find_links else []
```

所以源可以指向 AMD：

```powershell
$env:INDEX_URL = "https://stable.repo.amd.com/rocm/whl-next/"
```

**但仍有硬限制**：

1. UI 的 device 选项只有 cpu/cuda/xpu，无法传入 `device-gfx1100` extra
2. profile 改写会把 torch 固定成 `torch==2.10.0`（CUDA profile）或 CPU profile 的同版本
3. 结果是装不出 `2.15.0+rocm10.2.0`

要走 UI 路径，必须先给 `torch_install_helper.py` 增加一个 ROCm profile（新增 `TORCH_INSTALL_DEVICE_OPTIONS` 的 `rocm` 选项、对应 `TorchInstallProfile`、以及 gfx 架构选择逻辑）——这属于代码改动，不在本说明范围内。

## 六、关于"内嵌库"本身

如果你要的是真正自包含、不依赖系统 Python 的内嵌运行环境（而非 `venv`），需按 `doc/windows_portable_runtime.md` 第 4 节重建一个 **Python 3.12 embeddable** 布局，因为 3.10 无法安装 torch 2.15。要点：

- 用 `python-3.12.10-embed-amd64.zip`，修改 `python312._pth`（取消注释 `import site`，`.` 之后加 `..`）
- 用 `get-pip.py` 装 pip，放入 `uv.exe`
- 复制 venv 的 `Lib/site-packages` 及非 site-packages 运行时资产（`Library/`、`bin/`、`opt/`、`share/`、Qt 插件、torch DLL 目录），去掉 `_virtualenv.pth`
- 重新生成 `Scripts` 下的控制台脚本
- 用并行目录（如 `ballontrans_pylibs_win_312`）验证后再替换，保留原目录

注意：`scripts/install.ps1` 会先删除 `ballontrans_pylibs_win` 再重建，直接运行会破坏现有环境。

## 七、附：jinja2 版本过低修复方案

升级 torch 后跑 OCR 时发现一个**与 ROCm/torch 无关**的独立问题，一并记录。

### 问题现象

`PaddleOCRVLManga` 模块运行失败，日志（`logs/_2026_11_20-12_04_33.log`）报错：

```
ImportError: apply_chat_template requires jinja2>=3.1.6 to be installed. Your version is 3.1.5.
```

调用链：`ocr_paddleVL_manga.py` → `processor.apply_chat_template()` → transformers 编译 chat template 时检查 jinja2 版本 → 不通过 → OCR 中断。

### 根因

| 包 | 当时 venv 版本 | 安装时间 |
| --- | --- | --- |
| transformers | 5.23.0 | 2026-11-19（新装） |
| jinja2 | 3.1.5 | 2025-02-26（遗留） |

transformers 5.x 把 `jinja2>=3.1.6` 放在 extras（`chat-template` / `all` / `dev`）里，普通 `pip install transformers` **不会带出这个下限**；而 `apply_chat_template` 运行时直接检查该下限，于是新代码撞上遗留旧库。项目根 `requirements.txt` 和 runtime constraint 都没锁 jinja2，AMD wheel 仓库里也只有 3.1.6（不是 3.1.5 的来源）。

### 修复方案（两层）

**第一层 · 立即修复当前环境**（手动执行一次）：

```powershell
.\venv\Scripts\python.exe -m pip install -U "jinja2>=3.1.6"
```

pip 会自动处理配套的 `markupsafe`（当前 3.0.2，已满足）。

**第二层 · 防止复发**（已落实到代码）：

单纯手动升级只修一次，换环境或重装又会退回 3.1.5。因此按项目架构，把约束加到**模块级 `dependencies`**（不进根 `requirements.txt`——那里是核心启动依赖，jinja2 属于按需模块依赖）：

```python
# 各模块 dependencies 列表里，紧邻 transformers 加上 jinja2>=3.1.6
dependencies = ['torch', 'torchvision', 'transformers>=5.1,<6', 'jinja2>=3.1.6', 'einops']
```

`PyPackageManager._requirement_satisfied()` 会用 `req.specifier.contains(version)` 校验，版本偏低时判定不满足并触发按需升级——这是防复发的关键。已实测该机制：3.1.6 满足、`>99` 不满足，低版本会被拦截。

已修改的 5 个文件（均允许装到 transformers 5.x）：

| 文件 | 改动 |
| --- | --- |
| `modules/ocr/ocr_paddleVL_manga.py` | 加 `jinja2>=3.1.6`（报错源头） |
| `modules/ocr/ocr_hayai_supernova.py` | 加 `jinja2>=3.1.6` |
| `modules/ocr/ocr_manga.py` | 加 `jinja2>=3.1.6` |
| `modules/textdetector/detector_koharu.py` | 加 `jinja2>=3.1.6` |
| `modules/inpaint/inpaint_default.py` | 加 `jinja2>=3.1.6` |

`trans_m2m100.py` 锁死 `transformers==4.57.6`，4.x 对 jinja2 要求低，未改。

> 另一种等价写法是 `transformers[chat-template]>=5.1,<6`，让 pip 自动带出下限；但依赖 extras 命名，不如显式声明可控，故采用上表做法。

### 当前状态

venv 的 jinja2 已升级到 **3.1.6**（已手动执行第一层修复），当前环境无此报错。第二层的 5 处代码改动也已完成并 grep 验证生效。

## 参考

- AMD stable wheel 索引（根）：https://stable.repo.amd.com/rocm/whl-next/
- torch wheel：https://stable.repo.amd.com/rocm/whl-next/torch/
- 项目安装机制：`ballontranslator/utils/torch_install_helper.py`、`py_package_manager.py`、`package_installer.py`
- 内嵌运行时文档：`doc/windows_portable_runtime.md`
- 算子库结论：项目根目录 `ROCm_Windows_注意力算子库调研.md`
