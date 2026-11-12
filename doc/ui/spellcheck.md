# 拼写检查（Spell Check）

改文本编辑交互前先读 [Text engine](text_engine.md)。拼写检查是**编辑器层的可选辅助功能**：对编辑框里的拉丁字母单词做「输入时标红 + 选中后给纠错建议」，不属于 OCR、翻译或修复流水线，不影响文本块内容与项目数据。它默认关闭，只在 GUI 编辑器构造时实例化，headless 模式不会触发；运行时依赖第三方 `pyspellchecker`，缺失时功能静默停用。

## 所有权

| 职责 | 所有者 |
| --- | --- |
| 单例、三层词典状态、后台加载、判定与候选生成、自定义词库持久化 | [`ui/spellcheck.py`](../../ballontranslator/ui/spellcheck.py) 的 `SpellCheckManager` |
| 可检查词切分与 Qt UTF-16 偏移换算 | 同文件 `iter_spellcheck_words`、`_SPELLCHECK_WORD_PATTERN` |
| 红色波浪下划线、按词结果缓存 | 同文件 `SpellCheckHighlighter` |
| 仓库词典下载（QThread）、词库管理对话框 | 同文件 `DictDownloadThread`、`DictionaryManagerDialog` |
| 编辑器挂载、选区守卫、异步建议与浮窗 | [`text_engine/editing/widgets.py`](../../ballontranslator/ui/text_engine/editing/widgets.py) 的 `SourceTextEdit` / `TransTextEdit`、`FloatingSuggestionLabel` |
| 开关、编辑距离、仓库/外部词典列表 | [`ui/configpanel.py`](../../ballontranslator/ui/configpanel.py) |
| 持久化字段 | [`utils/config.py`](../../ballontranslator/utils/config.py) 的 `pcfg` |
| 回归测试 | [`tests/test_spellcheck.py`](../../tests/test_spellcheck.py) |

## 配置契约

| 字段 | 默认值 | 含义 |
| --- | --- | --- |
| `spellcheck_enabled` | `False` | 总开关 |
| `spellcheck_on_source_enabled` | `False` | 是否也检查源文本；默认只检查译文 |
| `spellcheck_distance` | `1`（范围 1–4） | 生成纠错候选时的编辑距离，越大越慢 |
| `spellcheck_repo_dicts` | `""` | 已启用的仓库词典文件名，逗号分隔 |
| `spellcheck_external_dict_path` | `""` | 外部词典文件路径，分号分隔 |

`SourceTextEdit.is_source_text_edit` 为 `True`，`TransTextEdit` 覆写为 `False`；高亮器和选区处理两处都据此做守卫。勾选总开关时若依赖未安装，配置面板先取消勾选再询问是否安装（`PackageInstallThread`），安装成功后才真正写 `pcfg.spellcheck_enabled = True`；`setupConfig()` 会把「配置里开着但依赖缺失」的状态纠正为关闭，避免界面与配置漂移。

## 切词契约

`_SPELLCHECK_WORD_PATTERN` 匹配**至少 2 个连续字母**的片段，数字、下划线、标点以及中日韩、谚文、假名等 CJK 区间都充当分隔符，因此 `helo世界wrld` 会拆成 `helo`、`wrld` 分别检查，CJK 文本本身完全不检查。单字母词、数字和标点不进入判定。

`iter_spellcheck_words()` 返回 `(start, length, word)`，其中位置是 **Qt 的 UTF-16 code unit**：纯 ASCII 或整段位于 BMP 时走快速路径；出现 astral 字符（代理对占 2 个位置）时逐段换算，保证 `setFormat` 不错位。修改正则或迭代器必须维持这个契约。

## 判定契约

`SpellCheckManager.is_correct()` 把词转为小写后按以下顺序判定，任一层命中即为「正确」：

1. `custom_words`：自定义词库 `config/custom_dictionary.txt`，一行一词；
2. `external_words`：已启用的仓库词典与用户添加的外部 `.txt/.dic`；
3. `spell.known([word])`：`SpellChecker(language=['en', 'ru'])` 的内置词频表。

非纯字母词一律视为正确。词典文件按 UTF-8 读取，解码失败回退 `cp1251`；跳过空行、`#` 注释、纯数字行（`.dic` 首行是词数），`/` 之后的 Hunspell 词缀标记丢弃，词条统一小写。

`SpellCheckHighlighter` 逐 block 调用 `is_correct`，未命中时用 `QTextCharFormat.WaveUnderline`、`rgb(235, 75, 75)` 画波浪线；总开关关闭、依赖不可用、或「源文本且未开启源文本检查」时直接返回，不做任何扫描。每个高亮器有按词的 `_cache`，管理器用 `weakref.WeakSet` 持有全部高亮器。以下事件统一清空缓存并重新高亮：配置变更 `notify_config_changed()`、后台词库加载完成 `dicts_loaded`、`add_to_dictionary()`、词库管理对话框关闭。

## 纠错建议

选中文本时 `on_selection_changed()` 要求选区**恰好是一个可检查词**且确实拼错，才在后台 `threading.Thread` 中调用 `get_suggestions()`：词长超过 15 直接放弃，取 `spell.candidates()` 的前 5 个，并按原词的首字母大写/全大写还原大小写。结果经 `suggestions_ready` 信号回到主线程，弹出 `FloatingSuggestionLabel`（光标上方，越界则改到下方）；显示前会**重新核对一次开关**，避免等待期间配置已变化。点击候选替换选中词，点击 `+ Add` 把词写入自定义词库并触发全局刷新。

## 词典来源与后台加载

- 内置：`pyspellchecker` 的 en + ru 词频词典。
- 仓库：`DICTIONARY_URLS` 中约 34 个 LibreOffice 词典地址；列表项**勾选时才下载**到 `data/dictionaries/`，下载成功后才记为启用，`setupConfig()` 会同步剔除已被手工删除的文件。
- 外部：用户选择的 `.txt` / `.dic` 文件，路径存于 `spellcheck_external_dict_path`。
- 自定义：`config/custom_dictionary.txt`，由词库管理对话框增删改，关闭时保存。

`load_spellchecker_async()` 用 `threading.Thread`（非 QThread）创建 `SpellChecker` 并读取上述词典文件；`distance` 变化会重建实例，`_reload_queued` 合并加载期间的连续配置变更，开关被关闭则丢弃结果。完成后 `dicts_loaded.emit()` 由 Qt 队列回到主线程触发重新高亮。加载期间 `spell is None`，`is_correct()` 返回 `True`、`get_suggestions()` 返回空列表。词典文件下载另用 `DictDownloadThread`（QThread，支持进度与取消）。

## 失败模式与已知限制

- 依赖未安装、正在加载、`known()` / `candidates()` 抛异常时，一律视为「正确」或无建议；这是宁可漏报不误报的降级策略，不会阻塞 UI 或弹出错误。
- **自定义词与仓库/外部词典只是白名单**，并未注入 `SpellChecker` 的词频表，因此这些词不会被判错，但也不会出现在纠错候选里；候选只能来自内置 en/ru。
- **`spellcheck_distance` 只影响候选生成，不影响是否标红**：`known()` 是纯查表，编辑距离只用于 `candidates()`。
- 候选取自 `set` 的前 5 个，顺序不代表相关性排序。
- 结果按词缓存，任何改变判定的来源（新词库、配置变化）都必须走上述失效路径，否则旧结果会残留。
- 配置是全局程序配置，不写入项目 JSON；headless 流水线不涉及此功能。

## 扩展点

- 新增语言支持：在 `DICTIONARY_URLS` 增加 URL（文件名即持久化 key），或通过外部词典路径接入；两者都只扩展白名单。
- 若需要让外部词进入候选，必须把词条注入 `SpellChecker` 的词频表，属于明确的行为变更，不要只在 `external_words` 加词后假定候选会变化。
- 扩展可检查文本范围需同时调整 `_SPELLCHECK_WORD_PATTERN` 与 `iter_spellcheck_words()`，并保持 UTF-16 偏移契约与相应测试。

## 验证

本次为只读代码梳理，未改动源码。运行：

```bash
ballontrans_pylibs_win\python.exe -m unittest discover -s tests -p "test_spellcheck.py" -v
```

5 项测试通过，覆盖：CJK 分隔与 UTF-16 偏移、高亮器只检查非 CJK 片段、禁用时零扫描、源文本守卫与译文保持启用、异步建议返回时重查配置。

未覆盖：真实 `pyspellchecker` 环境下的实际标红效果与建议浮窗交互、词典下载的网络路径、后台加载与配置变更的线程竞态；这些需要带 GUI 的人工验证。遵循 [仓库验证约定](../../AGENTS.md#verification)。
