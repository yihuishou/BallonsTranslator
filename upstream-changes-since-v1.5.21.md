# 上游更新摘要：v1.5.21 之后（2026-11-09 → 2026-11-15）

> 仓库：`git@github.com:yihuishou/BallonsTranslator.git`
> 区间：`1cdcbb5c`（release v1.5.21，2026-11-09 21:03）→ `97a61b1e`（origin/py12，2026-11-15 18:19）
> 分支：`dev`（origin/HEAD，`154b82af`）与 `py12`（`97a61b1e`）；`py12` 已包含 `dev` 的全部提交
> 统计：**35 个提交 / 62 个文件 / +10098 −957**
> 生成本文档时（2026-11-19）远程无更新：本地 `py12` HEAD `ec019bf2` 落后上游 0 个提交，领先 1 个未推送提交

---

## 一、多遍取字工作流（本批次最大改动）

同一页可串行跑最多 **3 组** detector + OCR 组合，再对结果做归并。

- `ballontranslator/utils/multi_extract.py`（新增 402 行）：多遍结果合并的核心逻辑。
  - 框按 **bbox IoU 贪心匹配**，每对 pass 最多配一次，避免相邻气泡被串成一组。
  - **区域取各遍并集**：只有一遍检出的框也会保留，不会因为某个检测器漏检而丢字，但会被标记为“弱支持”。
  - **文本绝不静默择一**：参考遍保持页面原样，凡各遍文本不一致的块都会连同全部候选一起上报，交由用户挑选，因此合并结果永远可复核。
- `ballontranslator/ui/multi_extract_review_dialog.py`（新增 483 行）：冲突复核对话框。
  - 选中某条复核项时，画布会定位并显示对应文本框。
  - 复核徽标画在文本框**内部**，不遮挡排版。
  - 多遍读数不一致的字符会**描边**提示。
- 配置与数据模型：
  - `ModuleConfig.MULTI_EXTRACT_MAX_SLOTS = 3`、`multi_extract_slots`（每槽 `{enabled, textdetector, ocr}`）。
  - `normalized_multi_extract_slots()` 始终补齐 3 个完整槽位；旧版本配置的空缺项回落到当前选中的检测器/OCR，保证仍能跑第二、三遍。
  - `TextBlock.multi_extract` 保存未解决的分歧；单遍结果该字段为空。
- Run 对话框新增 `multi_extraction` 工作流模式（`WORKFLOW_MODES`），带独立的槽位配置页与独立的页码范围，切换工作流不会串页。

## 二、中文校对（proofreading）阶段

- `ballontranslator/ui/proofread_thread.py`（新增）：后台校对线程，只产出文本，`proofread_done` 信号回到 UI 线程后再更新块，工作线程不触碰项目列表。
- `ballontranslator/modules/text_correction.py`（新增 417 行）：校对模型封装，支持模型目录、设备、batch、常驻内存（`text_correction_keep_loaded`）。
- 配置新增 `enable_proofread`（默认关）、`RunStatus.FIN_PROOFREAD = 16`、`FIN_ALL = 31`。
- `TextBlock.proofread` 只保存真正发生的修正，检查器没改动时为空，项目文件不会被空值污染。
- 校对作用于页面上**已存的译文**，因此可以在成品项目上单独重跑，也可作为流水线中的独立阶段（Run 对话框里命名为单独的“校对”阶段），导入的译文同样可走此流程。
- 移除了硬编码的校对模型路径（`affa94a6`）。

## 三、Label TXT 导出与分组

- `ballontranslator/utils/lptxt_export.py`（新增 271 行）：把项目 JSON 导出为 LabelPlus 风格译文 txt，供 LabelPlus / PS / InDesign 使用；与 `ProjImgTrans.dump_txt` 的 `### page` / `1. text` 格式刻意区分。
  - 坐标归一化到 0–1，保留 3 位小数；页面尺寸无法自动判定时抛 `LPTxtPageSizeError`。
  - 导出表头可配：`lptxt_note`（默认“备注”）、`lptxt_text_labels`（默认“框内/框外”，每项含 `name` + `font`）。
- 分组：
  - `TextBlock.group` 保存该块的 Label TXT 分组（对应配置里的 Photoshop 动作组），空值表示未分配，解析时落到第一个已配置分组。
  - `effective_font_family` / `group_font_override`：分组带字体时在**渲染时**覆盖块自身 `font_family`，实时生效。
  - 面板上分组以对齐行下方的**行内按钮**展示，每个块的分组号写入导出文本；分组字体用可搜索的 `FontFamilyComboBox` 选择。
  - 工具栏新增分组号显示开关（`imgtrans_group_display`）与 **1–9 数字快捷键**批量改选中块的分组。
- 入口与脚本：Tools 菜单新增 Label TXT 导出项；`scripts/BTjson_to_LPtxt.pyw` 替换为 `scripts/BTjson_to_LPtxt.py`（复用同一模块，旧命令行输出保持字节一致）。

## 四、文本导入（TXT / markdown）

- `ProjImgTrans.load_source_from_txt()` / `load_translation_from_txt()`：从纯文本或 markdown 导入原文与译文。
- 导入内容格式异常时只丢弃出错部分并继续，不会用空状态覆盖既有项目文件（`tests/test_txt_import_save_state.py` 覆盖该行为）。
- 文件菜单与中文翻译同步更新。

## 五、性能与缺陷修复

| 提交 | 修复内容 |
|---|---|
| `ef8eb654` | manga-ocr 的 no-repeat-ngram 屏蔽改为**向量化**实现，去掉逐 token 的 Python 循环 |
| `29bbd75b` | ezTrans：msl-loadlib 命名空间检查、韩→日列表后处理、32-bit 下的列表递归 |
| `6634ce14` | 翻译后空文本块不再被压塌 |
| `c1014138` | 全局搜索中替换框宽度与查找框对齐 |
| `0d7f40ec` / `24cef6ad` | （v1.5.21 前合入）间距预览保留撤销历史、渲染前保存未保存的页面编辑 |

## 六、UI、i18n 与文档

- `resources/stylesheet.css` 新增 62 行、`resources/icons/` 新增分组显示图标（普通态 + 激活态）。
- `resources/translate/zh_CN.ts` 大幅更新（1520 行变动），`zh_CN.qm` 重新编译；新增工作流名、导入项、导出设置等条目均已汉化。
- 新增文档：
  - `Agent.md`（401 行，项目结构图）
  - `doc/launch_windows.md`（Windows 启动）
  - `doc/windows_portable_runtime.md`（便携运行时）
  - `doc/modules/flux_inpaint.md`（FLUX 修复模型维护指南）
  - `doc/ui/spellcheck.md`（拼写检查维护指南）
- `.gitignore` 增加本地工具状态与构建临时目录。

## 七、测试

新增约 3000 行测试，覆盖新功能的主要路径：

`tests/test_multi_extract.py`、`test_multi_extract_badge.py`、`test_multi_extract_mainwindow.py`、`test_multi_extract_review_dialog.py`、`test_multi_extract_run.py`、`test_proofread_stage.py`、`test_lptxt_export.py`、`test_lptxt_groups.py`、`test_lptxt_settings.py`、`test_txt_import_save_state.py`、`test_eztrans.py`、`test_manga_ocr_ngram.py`、`test_proj_imgtrans_translation_context.py`、`test_global_search_layout.py`、`test_run_pipeline_dialog.py`（扩充）、`test_canvas_save_state.py`（扩充）。

---

## 八、提交清单（新 → 旧）

| 日期 | 提交 | 说明 |
|---|---|---|
| 11-15 18:19 | `97a61b1e` | ✨ 分组显示开关，徽标显示分组名，1–9 快捷键切分组 |
| 11-15 15:18 | `6634ce14` | 🐛 翻译后空文本块不再被压塌 |
| 11-15 15:18 | `29bbd75b` | 🐛 ezTrans 修复（msl-loadlib 命名空间、韩→日后处理、32-bit 列表递归） |
| 11-13 12:38 | `affa94a6` | 🔥 移除硬编码的校对模型路径 |
| 11-13 01:35 | `0bd7926e` | ✨ 导入的译文可走校对工作流 |
| 11-13 01:26 | `3ebf2348` | ✨ Run 对话框中为校对阶段命名 |
| 11-13 01:26 | `244d0066` | 💄 校对设置文字换行，缩小重置按钮 |
| 11-13 01:14 | `8622ebce` | ✨ 设置中可配校对 prompt 与模型 |
| 11-13 01:07 | `6c523686` | ✨ 中文译文校对作为流水线阶段 |
| 11-13 00:35 | `16e9dc0b` | 💄 Label TXT 分组按钮改为与 Add 按钮一致的扁平样式 |
| 11-13 00:29 | `462b980e` | ✨ 多遍复核徽标收进文本框内部 |
| 11-12 19:28 | `b606f5a0` | ✨ 选中复核项时画布显示对应块 |
| 11-12 18:25 | `0910f1b6` | ✨ 每个 Label TXT 块写入分组号 |
| 11-12 18:16 | `ded66071` | ✨ 分组以对齐行下方行内按钮展示 |
| 11-12 17:26 | `746fbbea` | ✨ 每块独立分组 + 分组字体实时覆盖 |
| 11-12 16:41 | `396de42a` | ♻️ 分组字体改用可搜索的 FontFamilyComboBox |
| 11-12 16:27 | `4b7ce08d` | ✨ Label TXT 设置支持可选分组字体（下拉选择） |
| 11-12 15:41 | `6c689d0b` | ✨ 可配置的 Label TXT 导出设置 |
| 11-12 14:50 | `4b0d236c` | ✨ 简化 Label TXT 导出并取整坐标 |
| 11-12 14:29 | `2e3daac8` | 🌐 更新简体中文翻译资源 |
| 11-12 14:27 | `c1d8897c` | ✨ Tools 菜单新增 Label TXT 导出 |
| 11-12 14:16 | `6d36a6e7` | ♻️ LabelPlus txt 导出重构为可复用模块 |
| 11-12 13:17 | `8aa4a8bb` | 📝 拼写检查维护指南 |
| 11-12 12:31 | `bc24e1e0` | 📝 FLUX 修复模型维护指南 |
| 11-12 12:30 | `f0d22ff5` | 🙈 忽略本地工具状态与构建临时目录 |
| 11-12 12:29 | `5df912f4` | 📝 新增结构图与 Windows 运行时文档 |
| 11-11 23:44 | `154b82af` | ✨ 多遍读数差异字符描边 |
| 11-11 22:46 | `54928e1f` | ✨ 多遍取字工作流 + 冲突复核 |
| 11-11 20:53 | `ef8eb654` | ⚡ manga-ocr no-repeat-ngram 屏蔽向量化 |
| 11-11 20:27 | `5543d3ed` | 🧪 运行对话框测试不再读写真实配置文件 |
| 11-11 20:13 | `6432323d` | 🌐 取字工作流名称汉化 |
| 11-11 20:13 | `d5b6ed2b` | ✨ Run 对话框新增取字工作流 |
| 11-11 20:00 | `783aa91e` | 🌐 导入菜单项汉化 |
| 11-11 20:00 | `203f00b8` | ✨ 从 TXT/markdown 导入原文 |
| 11-11 19:35 | `c1014138` | 🎨 全局搜索替换框宽度对齐查找框 |

---

## 九、与本地工作区的差异

- 本地 `py12` 分支已包含上述全部 35 个提交，无需再合并。
- 唯一未推送提交：`ec019bf2` 🐛 Apply group font override to rendered glyph fragments（2026-11-15 23:00），仅改 `ballontranslator/ui/text_engine/item.py`（+62 −2），把分组字体覆盖应用到实际渲染的字形片段，属于对 `97a61b1e` 分组字体功能的补充修复。
