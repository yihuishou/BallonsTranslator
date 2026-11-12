"""Background jobs for Chinese proofreading of translated text."""

from typing import Sequence

from qtpy.QtCore import Signal

from ballontranslator.utils.config import pcfg
from ballontranslator.utils.logger import logger as LOGGER
from .io_thread import ThreadBase


class ProofreadThread(ThreadBase):
    """Proofread translated blocks off the UI thread.

    The worker only produces text. Blocks are updated on the UI thread after
    ``proofread_done`` so the project list is never mutated from a worker.
    """

    proofread_done = Signal(object)

    _thread_error_msg = 'Proofreading failed.'

    def __init__(self, texts: Sequence[str], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.texts = list(texts)
        self.job = self._proofread

    def _proofread(self) -> None:
        from ballontranslator.modules.text_correction import proofread_translations

        corrected = proofread_translations(
            self.texts,
            model_dir=pcfg.text_correction_model_path,
            device=pcfg.text_correction_device,
            batch_size=pcfg.text_correction_batch_size,
            # A manual page check is one-off, so it hands the VRAM back.
            release_after=True,
        )
        self.proofread_done.emit(corrected)


class ProofreadModelThread(ThreadBase):
    """Fetch the proofreading weights before the first run.

    ``done_ok`` carries the resolved model directory, or an empty string when
    the download failed and proofreading stays unavailable.
    """

    done_ok = Signal(str)

    _thread_error_msg = 'Failed to download the proofreading model.'

    def __init__(self, model_dir: str = '', *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.model_dir = model_dir
        self.job = self._download

    def _download(self) -> None:
        from ballontranslator.modules.text_correction import ensure_model_files

        LOGGER.info('Preparing the Chinese proofreading model.')
        ok, path = ensure_model_files(self.model_dir)
        self.done_ok.emit(path if ok else '')
