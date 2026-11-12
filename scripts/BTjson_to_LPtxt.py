"""BallonsTranslator project JSON -> LabelPlus txt.

The export logic lives in ``ballontranslator.utils.lptxt_export``; this file is
only a thin entry point. Run without arguments for the tkinter window, or pass
a JSON path for headless use::

    python scripts/BTjson_to_LPtxt.py <imgtrans_*.json> [--font-info]
                                      [--groups 对白,旁白]
                                      [--width 1080 --height 1920] [-o out.txt]

The group order given by ``--groups`` decides both the header labels and the
group number written into every block's coordinate triple.
"""

import argparse
import os.path as osp
import sys

APP_ROOT = osp.dirname(osp.dirname(osp.abspath(__file__)))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from ballontranslator.utils.lptxt_export import LPTxtPageSizeError, export_lptxt


def _parse_groups(raw):
    """Split a comma separated group list into an ordered name list."""
    if raw is None:
        return None
    return [name.strip() for name in raw.split(",") if name.strip()]


def _run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把 BallonsTranslator 项目 JSON 导出为 LabelPlus txt")
    parser.add_argument("json_path", help="项目 JSON 路径（imgtrans_*.json）")
    parser.add_argument("--font-info", action="store_true", help="译文前附加识别到的字体/字号信息")
    parser.add_argument("--groups", default=None,
                        help="Photoshop 动作分组名称，逗号分隔（顺序即分组序号），默认使用脚本内置分组")
    parser.add_argument("--width", type=int, default=None, help="无法自动读取尺寸时使用的图片宽度")
    parser.add_argument("--height", type=int, default=None, help="无法自动读取尺寸时使用的图片高度")
    parser.add_argument("-o", "--output", default=None, help="输出 txt 路径，默认与 JSON 同目录")
    args = parser.parse_args(argv)

    text_labels = _parse_groups(args.groups)
    if args.groups is not None and not text_labels:
        parser.error("--groups 需要至少一个分组名称")

    fallback_page_size = None
    if args.width is not None or args.height is not None:
        if args.width is None or args.height is None or args.width <= 0 or args.height <= 0:
            parser.error("--width 与 --height 必须同时提供且为正整数")
        fallback_page_size = (args.width, args.height)

    try:
        out = export_lptxt(
            args.json_path,
            args.output,
            include_font_info=args.font_info,
            fallback_page_size=fallback_page_size,
            text_labels=text_labels,
        )
    except (OSError, ValueError) as e:
        print(f"导出失败：{e}", file=sys.stderr)
        return 1
    print(f"翻译文本已保存到: {out}")
    return 0


def _ask_page_size(page_name, simpledialog, messagebox):
    """Ask for a size that will be used for every page lacking a real size."""
    width = simpledialog.askinteger(
        "输入图片宽度", f"无法读取图片 {page_name} 的尺寸，请输入宽度：", minvalue=1)
    height = simpledialog.askinteger(
        "输入图片高度", f"无法读取图片 {page_name} 的尺寸，请输入高度：", minvalue=1)
    if not width or not height:
        messagebox.showwarning("警告", "未输入有效尺寸，已取消导出")
        return None
    return width, height


def _run_gui() -> None:
    # tkinter stays a GUI-only dependency; CLI/headless runs never import it.
    import tkinter as tk
    from tkinter import filedialog, simpledialog, messagebox

    root = tk.Tk()
    root.title("气泡翻译器翻译转lptxt")
    root.geometry("460x240")

    font_info_var = tk.BooleanVar()
    tk.Checkbutton(root, text="导出时包含字体字号信息", variable=font_info_var).pack(pady=12)

    # The group order defines the group number written into each block.
    groups_var = tk.StringVar(value="框内,框外")
    tk.Label(root, text="Photoshop 动作分组（逗号分隔，顺序即分组序号）").pack()
    tk.Entry(root, textvariable=groups_var).pack(pady=6)

    def process_json():
        json_file = filedialog.askopenfilename(
            title="选择 JSON 文件", filetypes=[("JSON Files", "*.json")])
        if not json_file:
            messagebox.showwarning("警告", "未选择文件")
            return
        text_labels = _parse_groups(groups_var.get())
        # Each JSON starts fresh, so a size entered for one project never leaks
        # into the next one handled by this window.
        fallback_page_size = None
        try:
            while True:
                try:
                    out = export_lptxt(
                        json_file,
                        include_font_info=font_info_var.get(),
                        fallback_page_size=fallback_page_size,
                        text_labels=text_labels,
                    )
                except LPTxtPageSizeError as e:
                    if fallback_page_size is not None:
                        raise
                    fallback_page_size = _ask_page_size(e.page_name, simpledialog, messagebox)
                    if fallback_page_size is None:
                        return
                    continue
                break
        except Exception as e:
            messagebox.showerror("错误", f"处理文件时出错：{e}")
            return
        messagebox.showinfo("输出完成", f"翻译文本已成功输出到：\n{out}")

    tk.Button(root, text="选择JSON文件并处理", command=process_json).pack(pady=10)
    tk.Button(root, text="退出", command=root.destroy).pack(pady=10)
    root.mainloop()


def main() -> int:
    if len(sys.argv) > 1:
        return _run_cli()
    _run_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
