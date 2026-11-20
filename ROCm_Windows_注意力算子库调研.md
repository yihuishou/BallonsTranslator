# ROCm Windows 下注意力算子库（FA2 / SageAttention）调研

> 调研日期：2026-11-20
> 目标环境：Windows 10 + ROCm 10.2.0（tarball）+ PyTorch 2.15.0 + AMD RX 7900 XTX（gfx1100 / RDNA3）

## 结论速览

**AMD 官方 wheel 仓库里没有任何独立的 FA2 / SageAttention 预编译包**。但 flash attention 已经内置在 PyTorch 里，无需单独安装——这是官方推荐、最稳的路径。

| 方案 | 是否需要安装 | 官方支持 | gfx1100 表现 | 推荐度 |
|------|------------|---------|-------------|--------|
| 1. PyTorch SDPA + AOTriton | 否，torch 自带 | 官方默认 | 开箱可用，最稳 | ⭐ 首选 |
| 2. flash-attn (Dao-AILab) | 是，源码编译 | 部分支持 | 吞吐最高，但需编译 | 次选 |
| 3. SageAttention（"SEGA"） | 是，社区方案 | 明确不支持 | 普遍慢于 SDPA | 不推荐 |

---

## 方案 1：PyTorch SDPA + AOTriton（推荐）

AMD 官方默认的 flash attention 后端，随 torch 一起安装，**无需任何额外操作**。在 Windows + gfx1100 上开箱可用。

- 接口：`torch.nn.functional.scaled_dot_product_attention`
- ComfyUI 中启用：`--use-pytorch-cross-attention`
- 环境变量：`TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`（ComfyUI 默认已设，会启用 AOTriton 支撑的 memory-efficient attention）
- Flash Attention 与 Memory Efficient Attention 在 ROCm 上走同一套内核，默认 AOTriton

**注意**：CK 后端（`TORCH_ROCM_FA_PREFER_CK=1` 或 `torch.backends.cuda.preferred_rocm_fa_library("ck")`）在 RDNA 架构上**官方明确不支持**，不要启用。

---

## 方案 2：flash-attn（Dao-AILab）

吞吐最高，但需要源码编译。

**现状**：AMD 官方 wheel 仓库 `https://stable.repo.amd.com/rocm/whl-next/` 中**没有** flash-attn 或 aiter 的预编译包（已逐个核对目录列表，只有 torch / torchvision / torchaudio / triton / rocm-sdk 系列及依赖）。

**安装方式**：
```bash
git clone https://github.com/Dao-AILab/flash-attention
cd flash-attention
# Triton AMD 后端
set FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE
pip install --no-build-isolation .
```

**前置条件**：
- Windows 上需 VS Build Tools 2022（C++ 桌面开发负载）
- `pip install triton-windows`
- 可选：`pip install --no-build-isolation git+https://github.com/ROCm/aiter.git`（走 Aiter/Triton 路径时）

**高级调优**（可选）：
- `FLASH_ATTENTION_TRITON_AMD_AUTOTUNE="TRUE"`：自动搜索最优配置，有一次预热开销
- `FLASH_ATTENTION_FWD_TRITON_AMD_CONFIG_JSON`：手动指定 attn_fwd 的 triton 配置

**坑点**：flash-attn 版本必须与 torch 2.15 / Python 3.12 **严格对应**，否则装不上或运行时报错。社区有第三方编译好的 wheel（如针对 ROCm 10.0 + torch 2.13 的 CK 版本），但要匹配 10.2 + torch 2.15 需要自己找对应构建。

---

## 方案 3：SageAttention（用户所说的 "SEGA"）

INT8 量化的注意力加速算子，SD / 视频生成社区常用。

**官方态度**（原文）：
> "Currently, sageattention is not an officially supported package from AMD, it is limited to CUDA stack and should be used for experimental purposes."

即 AMD 明确**非官方支持**，靠 Triton 社区补丁在 ROCm 上跑。

**安装**：
```bash
pip install "sageattention<2"
```
- gfx1100 / gfx1151：开箱可用（无需 patch）
- gfx12xx（RX 9000 系列）：需要 patch，见 thu-ml/SageAttention#365（Triton 编译错误）

**性能现实**：
- AMD 官方在 Navi31（gfx1100）和 Strix Halo 上的实测：SageAttention **普遍慢于 PyTorch SDPA (AOTriton)**，仅在个别负载下略优；Navi48 上甚至出现 memory access fault
- 社区报告 30% 提速多来自特定 ComfyUI / 视频生成工作流，且通常需要编译 patched 版本，收益因模型而异
- 结论：在 gfx1100 上收益存疑，不推荐为此单独折腾

---

## 最终建议

1. **先用方案 1**：升级到 PyTorch 2.15.0 + ROCm 10.2 后，`scaled_dot_product_attention` / ComfyUI 的 `--use-pytorch-cross-attention` 已经能调用 AOTriton 的 flash 内核，零成本、官方支持、最稳。
2. **确有吞吐瓶颈再上方案 2**：愿意折腾 VS 工具链 + 版本匹配时，flash-attn 能带来最高吞吐（AMD 实测相对 SDPA 提升约 20%~50%，因模型和硬件而异）。
3. **方案 3 谨慎**：SageAttention 在你的 gfx1100 上收益不明确，且非官方支持。

### Windows 特别提醒

AMD 官方博客的 attention 后端分析基于 Linux，原文：
> "Linux supports all of the listed backends, while some of them might have limited support on Windows."

方案 1 随 torch wheel 在 Windows 上可用；方案 2/3 在 Windows 上编译坑明显更多（VS 工具链、版本匹配），Windows 10 又是 ROCm 10.2 未验证组合。

---

## 来源

- [AMD 官方博客：Understanding Attention Algorithms and Their Backends](https://rocm.blogs.amd.com/software-tools-optimization/comfyui-fa-backends/README.html)
- [AMD stable wheel 仓库索引](https://stable.repo.amd.com/rocm/whl-next/)
- [ROCm 7 on Windows: Triton, FlashAttention, SageAttention & bitsandbytes](https://github.com/guinmoon/rocm7-triton-flash-attention-sage-attention-bnb)
- [TheRock Windows 安装指南（attention modes 章节）](https://github.com/deepbeepmeep/WanGP/blob/main/docs/AMD-INSTALLATION.md)
- [Dao-AILab/flash-attention AMD ROCm support](https://github.com/Dao-AILab/flash-attention#amd-rocm-support)
- [ROCm/aiter](https://github.com/ROCm/aiter)
