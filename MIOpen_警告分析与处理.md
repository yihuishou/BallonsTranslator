# MIOpen 警告分析与处理

> 记录日期：2026-11-20
> 环境：Windows 10 + PyTorch 2.15.0+rocm10.2.0 + ROCm 10.2 tarball（`C:\ROCm`）+ RX 7900 XTX（gfx1100）

## 结论速览

这四条警告**不影响 OCR 结果的正确性，不需要修复也能正常工作**。

| 警告 | 来源 | 性质 | 功能影响 |
|---|---|---|---|
| `[transformers] Please pass return_numpy=True` | transformers 5.x | API 弃用提示 | 无 |
| `MIOpen [ParseAndLoadDb] File is unreadable` | MIOpen 运行库 | 性能数据库缺失 | 仅可能影响卷积算法选择速度 |
| `MIOpen [LgbmMetadata] LGBM metadata load failed` | MIOpen 运行库 | 启发式模型缺失 | 同上 |
| `MIOpen [LgbmPcfgMetadata] lgbm_pcfg: cannot open` | MIOpen 运行库 | 启发式配置缺失 | 同上 |

注意：这些警告**不在 `logs/` 下的应用日志里**。MIOpen 是原生库，警告直接写 stderr；transformers 那条走 Python logger。它们出现在 PyCharm / 终端的运行控制台。

---

## 原始错误信息

以下为用户运行 PaddleOCRVLManga 时在控制台看到的原文（路径已保留原样）：

```text
[transformers] Please pass `return_numpy=True`, returning a PIL.Image.Image is deprecated.
MIOpen: Warning [ParseAndLoadDb] File is unreadable: "C:\\Users\\EvilEnergySeaUrchin\\PycharmProjects\\BallonsTranslator\\venv\\Lib\\site-packages\\_rocm_sdk_libraries\\bin\\gfx110060.HIP.fdb.txt"
MIOpen: Warning [LgbmMetadata] LGBM metadata load failed (DESKTOP-SEA:C:/home/runner/_work/rockrel/rockrel/rocm-libraries/projects/miopen/src/include\miopen/conv/heuristics/ai_heuristics.hpp:123: Unable to load file: C:\Users\EvilEnergySeaUrchin\PycharmProjects\BallonsTranslator\venv\Lib\site-packages\_rocm_sdk_libraries\bin\lgbm_model_meta.json); picker will abstain
MIOpen: Warning [LgbmPcfgMetadata] lgbm_pcfg: cannot open "C:\\Users\\EvilEnergySeaUrchin\\PycharmProjects\\BallonsTranslator\\venv\\Lib\\site-packages\\_rocm_sdk_libraries\\bin\\lgbm_pcfg.bin"; picker will abstain
```

---

## 逐条解释

### 1. transformers 弃用提示

```text
Please pass `return_numpy=True`, returning a PIL.Image.Image is deprecated.
```

- **来源**：`venv/Lib/site-packages/transformers/image_transforms.py:776`，由 `ocr_paddleVL_manga.py:101` 的 `processor(text=[text], images=[img], return_tensors="pt")` 触发。
- **含义**：transformers 5.x 宣布 processor 默认返回 `PIL.Image` 的做法过时，建议调用方显式传 `return_numpy=True`。未来版本可能真的改变默认行为。
- **影响**：纯 API 用法提示，当前结果正确，可以不管。

### 2. MIOpen `[ParseAndLoadDb]`

```text
File is unreadable: ...gfx110060.HIP.fdb.txt
```

- **fdb** = Find Database。MIOpen 用它预存"某种卷积配置 → 最优算法"的查询结果，避免每次运行时重新做耗时的在线 benchmark。
- 这条是说该文件读不到，MIOpen 无法使用预调优数据。

### 3–4. MIOpen `[LgbmMetadata]` / `[LgbmPcfgMetadata]`

```text
LGBM metadata load failed ... lgbm_model_meta.json); picker will abstain
lgbm_pcfg: cannot open ... lgbm_pcfg.bin; picker will abstain
```

- **LGBM** = LightGBM。MIOpen 用训练好的机器学习模型预测卷积该用哪个算法（heuristic picker），`lgbm_model_meta.json` 和 `lgbm_pcfg.bin` 就是这个模型的元数据与配置。
- `picker will abstain` = 预测器"弃权"，不给出推荐，MIOpen 回退到内置的传统启发式规则。

路径中的 `DESKTOP-SEA:C:/home/runner/_work/rockrel/...` 是 **AMD 构建机上编译时的源码路径**被写进了错误信息，不是本机真有这个路径，无需处理。

---

## 触发原因（实测核查）

问题根因是 **PyTorch wheel 自带的 MIOpen 运行库缺少性能调优数据文件**。

对两个目录做了实际检查：

| 位置 | 内容 |
|---|---|
| `venv\Lib\site-packages\_rocm_sdk_libraries\bin\` | 共 22 项，全是 DLL（`MIOpen.dll`、`hipblas.dll`、`rocblas.dll` 等），**没有任何 fdb / lgbm 文件** |
| `C:\ROCm\bin\`（10.2 tarball） | 文件齐全：`gfx1030_36.HIP.fdb.txt` 38 MB、`lgbm_model_meta.json` 80 KB、`lgbm_pcfg.bin` 46 MB、`lgbm_rank.bin` 5 MB |

也就是说，AMD 的 `torch-2.15.0+rocm10.2.0` wheel 在打包 Windows 运行库时省略了这些性能数据库文件；而之前手动解压的 tarball 里是有的。这是两套独立的 ROCm 分发（详见 `项目环境_PyTorch2.15_ROCm10.2_升级说明.md`）。

MIOpen 在初始化时按约定路径去找这些文件，找不到就打印警告并走回退路径——**不是文件损坏，也不是权限问题，是打包时就没带**。

---

## 影响评估

- **正确性**：无影响。卷积仍会执行，只是由默认启发式而非 ML 预测器 / 预调优数据库来选算法。
- **性能**：理论上首次遇到某种卷积配置时可能多花时间做在线搜索，长期性能可能略低于最优选择。对本项目 OCR 场景（VLM 推理，主要是矩阵乘法，卷积集中在视觉编码器）影响很小。
- **与 jinja2 报错无关**：那是另一个独立问题（transformers 5.x 要求 `jinja2>=3.1.6`），已通过在模块 `dependencies` 加 `jinja2>=3.1.6` 解决。

---

## 处理方案

按推荐程度排序：

### 方案 1 · 忽略（推荐）

四条都是警告不是错误，不修也能正常跑。

### 方案 2 · 隐藏 MIOpen 警告

设环境变量 `MIOPEN_LOG_LEVEL=3`（仅错误；默认 0 相当于 release 版的 4 = 错误+警告）。只是隐藏输出，不解决底层缺失。

### 方案 3 · 补齐 lgbm 文件（可选）

把 `C:\ROCm\bin\` 下的三个 `lgbm_*` 文件复制到 `venv\Lib\site-packages\_rocm_sdk_libraries\bin\`，可消除后两条警告。

⚠️ 两个限制：
- `gfx1030_36.HIP.fdb.txt` 是 **gfx1030（RX 6000 架构）** 的预调优数据，与 gfx1100 不匹配，复制过去也无效；
- pip 升级 `rocm-sdk` 时会覆盖这个目录，补丁会被冲掉。

### 方案 4 · 消除 transformers 提示（可选）

`ocr_paddleVL_manga.py:101` 的 processor 调用加 `return_numpy=True`：

```python
inputs = self.processor(text=[text], images=[img], return_tensors="pt", return_numpy=True)
```

需确认该参数与后续 tensor 转换逻辑兼容（当前代码随后用 `v.to(self.model.device)` 处理张量，通常无影响）。这是面向未来的小改动，非必需。

---

## 参考来源

- [AMD MIOpen · Using the find database](https://rocm.docs.amd.com/projects/MIOpen/en/docs-6.2.1/conceptual/finddb.html)
- [AMD MIOpen · Logging and debugging（MIOPEN_LOG_LEVEL 取值）](https://rocm.docs.amd.com/projects/MIOpen/en/docs-7.0.0/how-to/debug-log.html)
- [MIOpen issue #26 · File is unreadable](https://github.com/ROCmSoftwarePlatform/MIOpen/issues/26)
- [ComfyUI-Zluda wiki · MIOPEN_FIND_MODE 与性能数据库](https://github.com/patientx/ComfyUI-Zluda/issues/350)
