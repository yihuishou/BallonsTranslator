import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from qtpy.QtCore import QPoint
from qtpy.QtWidgets import QApplication, QLabel

from ballontranslator.ui import shared_widget as SW
from ballontranslator.ui.canvas import Canvas
from ballontranslator.ui.text_engine.item import TextBlkItem
from ballontranslator.ui.text_engine.formatting.panel import FontFormatPanel
from ballontranslator.utils import config as C
from ballontranslator.utils import shared
from ballontranslator.utils.fontformat import FontFormat
from ballontranslator.utils.textblock import TextBlock


GROUPS = [
    {'name': '框内', 'font': ''},
    {'name': '旁白', 'font': 'GroupFontA'},
    {'name': '框外', 'font': ''},
]


def _patch_groups(testcase, groups=None):
    patcher = patch.object(
        C.pcfg, 'lptxt_text_labels', list(GROUPS if groups is None else groups)
    )
    patcher.start()
    testcase.addCleanup(patcher.stop)


class LptxtGroupConfigTests(unittest.TestCase):
    """Group lookup helpers used by both the block model and the UI."""

    def setUp(self):
        _patch_groups(self)

    def test_first_group_name(self):
        self.assertEqual(C.first_lptxt_group_name(), '框内')

    def test_first_group_name_without_groups(self):
        with patch.object(C.pcfg, 'lptxt_text_labels', []):
            self.assertEqual(C.first_lptxt_group_name(), '')

    def test_resolve_known_group(self):
        self.assertEqual(C.resolve_lptxt_group_name('旁白'), '旁白')

    def test_resolve_unknown_group_falls_back_to_first(self):
        self.assertEqual(C.resolve_lptxt_group_name('不存在的组'), '框内')

    def test_resolve_empty_group_falls_back_to_first(self):
        self.assertEqual(C.resolve_lptxt_group_name(''), '框内')

    def test_get_group_font(self):
        self.assertEqual(C.get_lptxt_group_font('旁白'), 'GroupFontA')
        self.assertEqual(C.get_lptxt_group_font('框内'), '')
        self.assertEqual(C.get_lptxt_group_font('不存在的组'), '')
        self.assertEqual(C.get_lptxt_group_font(''), '')


class TextBlockGroupTests(unittest.TestCase):
    """The group identifier lives on the block and drives the font override."""

    def setUp(self):
        _patch_groups(self)

    def test_group_defaults_to_empty(self):
        self.assertEqual(TextBlock([0, 0, 10, 10]).group, '')

    def test_group_is_serialized(self):
        block = TextBlock([0, 0, 10, 10])
        block.group = '旁白'
        self.assertEqual(block.to_dict()['group'], '旁白')

    def test_group_round_trips_through_dict(self):
        block = TextBlock([0, 0, 10, 10])
        block.group = '框外'
        restored = TextBlock(**block.to_dict())
        self.assertEqual(restored.group, '框外')

    def test_unassigned_group_resolves_to_first_group(self):
        block = TextBlock([0, 0, 10, 10])
        # '框内' is the first group and has no font.
        self.assertEqual(block.group_font_override, '')
        block.fontformat.font_family = 'OwnFontB'
        self.assertEqual(block.effective_font_family, 'OwnFontB')

    def test_group_font_overrides_own_font(self):
        block = TextBlock([0, 0, 10, 10])
        block.group = '旁白'
        block.fontformat.font_family = 'OwnFontB'
        self.assertEqual(block.group_font_override, 'GroupFontA')
        self.assertEqual(block.effective_font_family, 'GroupFontA')

    def test_group_without_font_keeps_own_font(self):
        block = TextBlock([0, 0, 10, 10])
        block.group = '框外'
        block.fontformat.font_family = 'OwnFontB'
        self.assertEqual(block.group_font_override, '')
        self.assertEqual(block.effective_font_family, 'OwnFontB')

    def test_unknown_group_falls_back_to_first_group(self):
        block = TextBlock([0, 0, 10, 10])
        block.group = '已删除的组'
        block.fontformat.font_family = 'OwnFontB'
        # Falls back to the first group ('框内'), which has no font.
        self.assertEqual(block.group_font_override, '')
        self.assertEqual(block.effective_font_family, 'OwnFontB')


class TextBlkItemGroupOverrideTests(unittest.TestCase):
    """The group font overrides rendering but never overwrites storage."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        _patch_groups(self)
        bounds = [0, 0, 300, 180]
        self.block = TextBlock(bounds)
        self.block._bounding_rect = list(bounds)
        self.block.translation = 'Group override test'
        self.block.fontformat.font_family = 'OwnFontB'
        self.block.fontformat.font_size = 20
        self.item = TextBlkItem(self.block, 0)

    def test_group_font_is_used_for_rendering(self):
        self.block.group = '旁白'
        self.item.set_fontformat(self.block.fontformat)
        self.assertEqual(
            self.item.document().defaultFont().family(), 'GroupFontA'
        )

    def test_own_font_is_used_without_group_font(self):
        self.block.group = '框外'
        self.item.set_fontformat(self.block.fontformat)
        self.assertEqual(
            self.item.document().defaultFont().family(), 'OwnFontB'
        )

    def test_get_fontformat_preserves_own_font_family(self):
        self.block.group = '旁白'
        self.item.set_fontformat(self.block.fontformat)
        # Rendering uses the group font, but the block keeps its own family.
        self.assertEqual(self.item.get_fontformat().font_family, 'OwnFontB')
        self.assertEqual(self.block.fontformat.font_family, 'OwnFontB')

    def test_removing_group_font_restores_own_font(self):
        self.block.group = '旁白'
        self.item.set_fontformat(self.block.fontformat)
        self.assertEqual(
            self.item.document().defaultFont().family(), 'GroupFontA'
        )
        self.block.group = '框外'
        self.item.set_fontformat(self.block.fontformat)
        self.assertEqual(
            self.item.document().defaultFont().family(), 'OwnFontB'
        )


class FontFormatPanelGroupTests(unittest.TestCase):
    """The text modify panel exposes the group assignment of the selection."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        _patch_groups(self)
        self.canvas = Canvas()
        self.canvas.editor_index = 1
        canvas_patcher = patch.object(SW, 'canvas', self.canvas)
        canvas_patcher.start()
        self.addCleanup(canvas_patcher.stop)
        previous = C.active_format
        self.addCleanup(setattr, C, 'active_format', previous)
        with patch.object(
            shared, 'register_view_widget', lambda *_: None, create=True
        ):
            self.panel = FontFormatPanel(self.app)
        self.panel.global_format = FontFormat()
        bounds = [0, 0, 300, 180]
        self.block = TextBlock(bounds)
        self.block._bounding_rect = list(bounds)
        self.block.translation = 'Panel group test'
        self.block.fontformat.font_family = 'OwnFontB'
        self.block.fontformat.font_size = 20
        self.item = TextBlkItem(self.block, 0)
        self.item.setParentItem(self.canvas.textLayer)
        self.addCleanup(self.canvas.gv.deleteLater)
        self.addCleanup(self.panel.deleteLater)

    def _group_names(self):
        return [b.text() for b in self.panel.group_buttons]

    def _click_group(self, name):
        """Click the group button with the given name."""
        for button in self.panel.group_buttons:
            if button.text() == name:
                button.click()
                return
        raise AssertionError(f'group button not found: {name}')

    def test_group_buttons_list_configured_groups(self):
        self.assertEqual(self._group_names(), ['框内', '旁白', '框外'])

    def test_group_buttons_default_to_first_group(self):
        self.panel.set_textblk_item(self.item)
        self.assertEqual(self.panel.current_group_name(), '框内')

    def test_group_buttons_show_the_block_group(self):
        self.block.group = '旁白'
        self.panel.set_textblk_item(self.item)
        self.assertEqual(self.panel.current_group_name(), '旁白')

    def test_clicking_group_writes_to_the_block(self):
        self.panel.set_textblk_item(self.item)
        self._click_group('旁白')
        self.assertEqual(self.block.group, '旁白')
        # The group font now drives the rendering.
        self.assertEqual(
            self.item.document().defaultFont().family(), 'GroupFontA'
        )
        # ...without overwriting the block's own font family.
        self.assertEqual(self.block.fontformat.font_family, 'OwnFontB')

    def test_clicking_group_highlights_it(self):
        self.panel.set_textblk_item(self.item)
        self._click_group('框外')
        self.assertEqual(self.panel.current_group_name(), '框外')
        checked = self.panel.group_button_group.checkedButton()
        self.assertIsNotNone(checked)
        self.assertTrue(checked.isChecked())

    def test_refresh_group_options_repopulates(self):
        with patch.object(
            C.pcfg, 'lptxt_text_labels', [{'name': '新组', 'font': ''}]
        ):
            self.panel.refresh_group_options()
        self.assertEqual(self._group_names(), ['新组'])

    def test_group_change_emits_signal(self):
        self.panel.set_textblk_item(self.item)
        seen = []
        self.panel.group_changed.connect(lambda: seen.append(True))
        self._click_group('框外')
        self.assertTrue(seen)

    def test_family_box_shows_effective_group_font(self):
        self.panel.set_textblk_item(self.item)
        self._click_group('旁白')
        # The box must show the font the canvas actually renders with.
        self.assertEqual(self.panel.familybox.currentText(), 'GroupFontA')
        self.assertEqual(
            self.item.document().defaultFont().family(), 'GroupFontA'
        )

    def test_family_box_shows_own_font_without_group_font(self):
        self.block.group = '框外'
        self.panel.set_textblk_item(self.item)
        self.assertEqual(self.panel.familybox.currentText(), 'OwnFontB')

    def test_no_group_text_label_is_shown(self):
        # The group row shows the group chips only; no "分组" caption.
        self.assertFalse(hasattr(self.panel, 'group_label'))
        labels = [
            child.text()
            for child in self.panel.findChildren(QLabel)
            if child.objectName() == 'LptxtGroupLabel'
        ]
        self.assertEqual(labels, [])

    def test_group_buttons_are_centered_in_the_row(self):
        self.panel.resize(380, 620)
        self.panel.show()
        self.app.processEvents()
        row = self.panel.group_button_row
        first = self.panel.group_buttons[0]
        last = self.panel.group_buttons[-1]
        left_gap = first.mapTo(row, QPoint(0, 0)).x()
        right_gap = row.width() - (
            last.mapTo(row, QPoint(0, 0)).x() + last.width()
        )
        self.assertAlmostEqual(left_gap, right_gap, delta=1)
        self.assertGreater(left_gap, 0)

    def test_group_row_is_close_to_the_row_below(self):
        self.panel.resize(380, 620)
        self.panel.show()
        self.app.processEvents()

        def top(widget):
            return widget.mapTo(self.panel, QPoint(0, 0)).y()

        gap = top(self.panel.foldTextBtn) - (
            top(self.panel.group_button_row)
            + self.panel.group_button_row.height()
        )
        self.assertLessEqual(gap, 8)
        self.assertGreaterEqual(gap, 0)


if __name__ == '__main__':
    unittest.main()
