"""Proofreading stage wiring: progress marking and finish-code compatibility.

The stage runs on stored translations, so these tests stay model-free: they pin
the state machine and the legacy-project behaviour instead of inference quality.
"""

import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from ballontranslator.utils.config import (
    ModuleConfig,
    ProgramConfig,
    RunStatus,
    json_dump_program_config,
    pcfg,
)
from ballontranslator.utils.proj_imgtrans import ProjImgTrans
from ballontranslator.utils.textblock import TextBlock
from ballontranslator.ui.module_manager import proofread_page_translations
from ballontranslator.modules import text_correction


class FakeProject:
    def __init__(self, blocks):
        self.pages = {'p1': blocks}
        self.marked = []

    def update_page_progress(self, page_key, code):
        self.marked.append((page_key, code))


class ProofreadStageTests(unittest.TestCase):

    def test_page_without_translations_is_marked_without_a_model(self):
        project = FakeProject([TextBlock(text=['あ'], translation='')])

        self.assertTrue(proofread_page_translations(project, 'p1'))
        self.assertEqual(project.marked, [('p1', RunStatus.FIN_PROOFREAD)])
        self.assertEqual(project.pages['p1'][0].proofread, '')

    def test_page_without_blocks_is_marked_without_a_model(self):
        project = FakeProject([])

        self.assertTrue(proofread_page_translations(project, 'p1'))
        self.assertEqual(project.marked, [('p1', RunStatus.FIN_PROOFREAD)])

    def test_finish_code_tracks_the_proofread_stage(self):
        config = ModuleConfig()
        config.enable_proofread = False
        config.update_finish_code()
        without = config.finish_code
        config.enable_proofread = True
        config.update_finish_code()

        self.assertEqual(config.finish_code, without | RunStatus.FIN_PROOFREAD)
        self.assertEqual(RunStatus.FIN_ALL, 31)
        self.assertTrue(config.stage_enabled(4))
        config.set_stage_enabled(4, False)
        self.assertFalse(config.enable_proofread)
        self.assertEqual(config.finish_code, without)

    def test_proofread_can_be_the_only_enabled_stage(self):
        config = ModuleConfig()
        for index in range(4):
            config.set_stage_enabled(index, False)
        config.set_stage_enabled(4, True)

        self.assertFalse(config.all_stages_disabled())
        self.assertEqual(config.finish_code, RunStatus.FIN_PROOFREAD)

    def test_legacy_page_needs_proofreading_only_when_enabled(self):
        project = ProjImgTrans()
        project._image_info = {'p': {'finish_code': 15}}
        backup = pcfg.module.enable_proofread
        self.addCleanup(setattr, pcfg.module, 'enable_proofread', backup)
        self.addCleanup(pcfg.module.update_finish_code)

        pcfg.module.enable_proofread = False
        pcfg.module.update_finish_code()
        self.assertTrue(project.get_page_progress('p'))

        pcfg.module.enable_proofread = True
        pcfg.module.update_finish_code()
        self.assertFalse(project.get_page_progress('p'))

        project.update_page_progress('p', RunStatus.FIN_PROOFREAD)
        self.assertTrue(project.get_page_progress('p'))


class ProofreadModelSettingsTests(unittest.TestCase):
    """The prompt and generation settings configured in the settings panel."""

    def test_empty_prompt_falls_back_to_the_shipped_instruction(self):
        corrector = text_correction.ChineseTextCorrector(prompt='   ')

        self.assertEqual(corrector.prompt, text_correction.default_prompt())
        self.assertEqual(
            corrector._build_prompt('我跟我朋友去。'),
            text_correction.default_prompt() + '\n我跟我朋友去。',
        )

    def test_custom_prompt_is_used_verbatim(self):
        corrector = text_correction.ChineseTextCorrector(
            prompt='只输出纠正后的句子。', max_new_tokens=512
        )

        self.assertEqual(
            corrector._build_prompt('我跟我朋友去。'), '只输出纠正后的句子。\n我跟我朋友去。'
        )
        self.assertEqual(corrector.max_new_tokens, 512)

    def test_corrector_is_rebuilt_only_when_settings_change(self):
        self.addCleanup(text_correction.release_corrector)
        first = text_correction.get_corrector(model_dir='m', prompt='a')
        same = text_correction.get_corrector(model_dir='m', prompt='a')
        changed = text_correction.get_corrector(model_dir='m', prompt='b')
        retuned = text_correction.get_corrector(model_dir='m', prompt='b', max_new_tokens=256)

        self.assertIs(first, same)
        self.assertIsNot(first, changed)
        self.assertEqual(changed.prompt, 'b')
        self.assertIsNot(changed, retuned)
        self.assertEqual(retuned.max_new_tokens, 256)

    def test_settings_survive_a_config_round_trip(self):
        config = ProgramConfig()
        config.text_correction_prompt = '只输出纠正后的句子。'
        config.text_correction_max_new_tokens = 512
        config.text_correction_batch_size = 3
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'config.json')
            with open(path, 'w', encoding='utf8') as f:
                f.write(json_dump_program_config(config))
            loaded = ProgramConfig.load(path)

        self.assertEqual(loaded.text_correction_prompt, '只输出纠正后的句子。')
        self.assertEqual(loaded.text_correction_max_new_tokens, 512)
        self.assertEqual(loaded.text_correction_batch_size, 3)


if __name__ == '__main__':
    unittest.main()
