import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QPlainTextEdit

from ballontranslator.modules import codex
from ballontranslator.ui import mainwindow as mw
from ballontranslator.ui.configpanel import ConfigPanel
from ballontranslator.utils.config import pcfg
from ballontranslator.utils.shared import CONFIG_FONTSIZE_CONTENT, LLM_PROMPT_EDITOR_WIDTH


class LabelTxtSettingsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        note_patch = patch.object(pcfg, 'lptxt_note', '默认备注')
        labels_patch = patch.object(pcfg, 'lptxt_text_labels', ['框内', '框外'])
        note_patch.start()
        labels_patch.start()
        self.addCleanup(note_patch.stop)
        self.addCleanup(labels_patch.stop)

        with patch.object(
            codex.account, '_load',
            side_effect=AssertionError('Unexpected credential IO'),
        ):
            self.panel = ConfigPanel()
        self.addCleanup(self.panel.deleteLater)
        self.saved = []
        self.panel.save_config.connect(lambda: self.saved.append(1))

    @staticmethod
    def _labels(panel) -> list:
        """Real group names stored in UserRole (the values that get exported)."""
        return [
            panel.lptxt_text_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(panel.lptxt_text_list.count())
        ]

    @staticmethod
    def _display_labels(panel) -> list:
        """What the user actually sees in the list, including the numbers."""
        return [
            panel.lptxt_text_list.item(row).text()
            for row in range(panel.lptxt_text_list.count())
        ]

    def test_section_is_registered_in_general_group(self):
        self.assertIn('lptxt', self.panel.configContent.section_index)
        self.assertEqual(
            self.panel.configTable.section_items['lptxt'].text(), 'Label TXT'
        )
        self.panel.showSection('lptxt')
        self.assertEqual(
            self.panel.configContent.currentIndex(),
            self.panel.configContent.section_index['lptxt'],
        )

    def test_note_editor_matches_codex_prompt_editor(self):
        edit = self.panel.lptxt_note_edit
        # QPlainTextEdit is what picks up the ConfigContentScrollContent QSS
        # used by the Codex translation-prompt editor; QTextEdit does not.
        self.assertIsInstance(edit, QPlainTextEdit)
        self.assertEqual(edit.objectName(), 'LabelTxtNoteEdit')
        self.assertEqual(
            edit.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.assertEqual(edit.minimumWidth(), LLM_PROMPT_EDITOR_WIDTH)
        self.assertEqual(edit.maximumWidth(), LLM_PROMPT_EDITOR_WIDTH)
        self.assertTrue(hasattr(edit, 'scrollbar_v'))
        self.assertTrue(hasattr(edit, 'scrollbar_h'))
        # Both controls stay aligned at the prompt-editor width.
        self.assertEqual(
            self.panel.lptxt_text_list.maximumWidth(), LLM_PROMPT_EDITOR_WIDTH
        )

    def test_hints_are_small_wrapped_text(self):
        for block in (
            self.panel.lptxt_note_block, self.panel.lptxt_group_block,
        ):
            title = block.name_label
            hint = block.description_label
            self.assertIsNotNone(title)
            self.assertIsNotNone(hint)
            self.assertTrue(hint.wordWrap())
            self.assertLess(hint.font().pointSizeF(), title.font().pointSizeF())
            self.assertAlmostEqual(
                hint.font().pointSizeF(), CONFIG_FONTSIZE_CONTENT - 4
            )
        # The Photoshop group hint is split into two explicit lines.
        group_hint = self.panel.lptxt_group_block.description_label.text()
        self.assertEqual(len(group_hint.split('\n')), 2)
        self.assertIn('双击列表项也可修改。\n左侧序号', group_hint)

    def test_setup_config_populates_widgets_without_saving(self):
        self.panel.setupConfig()
        self.assertEqual(self.panel.lptxt_note_edit.toPlainText(), '默认备注')
        self.assertEqual(self._labels(self.panel), ['框内', '框外'])
        self.assertEqual(self._display_labels(self.panel), ['1.  框内', '2.  框外'])
        self.assertEqual(self.saved, [])

    def test_note_edit_writes_config_without_per_keystroke_save(self):
        self.panel.setupConfig()
        self.panel.lptxt_note_edit.setPlainText('第一行\n第二行')
        self.assertEqual(pcfg.lptxt_note, '第一行\n第二行')
        # hideEvent emits save_config once for the whole settings window.
        self.assertEqual(self.saved, [])

    def test_add_edit_and_remove_text_labels(self):
        self.panel.setupConfig()

        with patch(
            'ballontranslator.ui.configpanel.QInputDialog.getText',
            return_value=('旁白', True),
        ):
            self.panel.on_lptxt_add_text()
        self.assertEqual(pcfg.lptxt_text_labels, ['框内', '框外', '旁白'])
        self.assertEqual(
            self._display_labels(self.panel),
            ['1.  框内', '2.  框外', '3.  旁白'],
        )

        self.panel.lptxt_text_list.setCurrentRow(1)
        with patch(
            'ballontranslator.ui.configpanel.QInputDialog.getText',
            return_value=('内心独白', True),
        ) as get_text:
            self.panel.on_lptxt_edit_text()
        # The edit dialog prefills the real name, not the numbered display text.
        self.assertEqual(get_text.call_args.kwargs.get('text'), '框外')
        self.assertEqual(pcfg.lptxt_text_labels, ['框内', '内心独白', '旁白'])

        # Removing a row renumbers the remaining items from 1 again.
        self.panel.lptxt_text_list.setCurrentRow(0)
        self.panel.on_lptxt_remove_text()
        self.assertEqual(pcfg.lptxt_text_labels, ['内心独白', '旁白'])
        self.assertEqual(self._labels(self.panel), ['内心独白', '旁白'])
        self.assertEqual(
            self._display_labels(self.panel), ['1.  内心独白', '2.  旁白']
        )
        self.assertTrue(self.saved)

    def test_cancelled_or_blank_input_does_not_change_labels(self):
        self.panel.setupConfig()

        with patch(
            'ballontranslator.ui.configpanel.QInputDialog.getText',
            return_value=('', False),
        ):
            self.panel.on_lptxt_add_text()
        self.assertEqual(pcfg.lptxt_text_labels, ['框内', '框外'])

        self.panel.lptxt_text_list.setCurrentRow(0)
        with patch(
            'ballontranslator.ui.configpanel.QInputDialog.getText',
            return_value=('   ', True),
        ):
            self.panel.on_lptxt_edit_text()
        self.assertEqual(pcfg.lptxt_text_labels, ['框内', '框外'])
        self.assertEqual(self.saved, [])

    def test_menu_export_uses_configured_header(self):
        self.panel.setupConfig()
        pcfg.lptxt_note = '嵌字备注\n第二行'

        # Configure the groups through the UI; the list displays numbers.
        self.panel.lptxt_text_list.setCurrentRow(1)
        self.panel.on_lptxt_remove_text()
        self.panel.lptxt_text_list.setCurrentRow(0)
        with patch(
            'ballontranslator.ui.configpanel.QInputDialog.getText',
            return_value=('对白', True),
        ):
            self.panel.on_lptxt_edit_text()
        with patch(
            'ballontranslator.ui.configpanel.QInputDialog.getText',
            return_value=('旁白', True),
        ):
            self.panel.on_lptxt_add_text()
        self.assertEqual(self._labels(self.panel), ['对白', '旁白'])
        self.assertEqual(
            self._display_labels(self.panel), ['1.  对白', '2.  旁白']
        )

        data = {
            'image_info': {'p.png': {'width': 1000, 'height': 1000}},
            'pages': {'p.png': [
                {'text': ['a'], 'translation': '译文',
                 'xyxy': [100, 200, 300, 400]},
            ]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / 'imgtrans_settings.json'
            proj.write_text('{}', encoding='utf-8')

            fake = SimpleNamespace(
                imgtrans_proj=SimpleNamespace(
                    proj_path=str(proj), to_dict=lambda: data,
                ),
                canvas=SimpleNamespace(text_change_unsaved=lambda: False),
                st_manager=SimpleNamespace(updateTextBlkList=lambda: None),
                titleBar=SimpleNamespace(),
            )
            info = []
            with patch.object(
                mw, 'create_info_dialog',
                lambda msg, *a, **k: info.append(msg),
            ), patch.object(
                mw, 'create_error_dialog',
                lambda e, *a, **k: info.append('ERROR ' + str(e)),
            ):
                mw.MainWindow.on_export_lptxt(fake)

            text = (root / 'imgtrans_settings_translations.txt').read_text(
                encoding='utf-8'
            )
        self.assertTrue(
            text.startswith('1,0\n-\n对白\n旁白\n-\n嵌字备注 第二行\n'), text
        )
        # Leading numbers are display-only: neither the names nor the note
        # carry them into the exported txt.
        self.assertNotIn('1.  对白', text)
        self.assertNotIn('2.  旁白', text)
        self.assertIn('\n译文\n', text)
        self.assertIn('[0.1, 0.2, 1]', text)
        self.assertTrue(info and not any('ERROR' in m for m in info), info)


if __name__ == '__main__':
    unittest.main()
