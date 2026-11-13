"""Chinese proofreading of translated text with ChineseErrorCorrector4-4B.

The weights come from ``twnlp/ChineseErrorCorrector4-4B`` (CSRP, ACL 2026), a
Qwen3-4B fine-tune that solves Chinese grammatical error correction and spelling
check. It answers with a ``<think>错误类型/修改原因</think>`` block followed by the
corrected sentence, so every result is parsed and the reasoning block dropped
before it can reach a translation.

Prompt text and output parsing mirror the reference implementation in
``TW-NLP/ChineseErrorCorrector`` (``llm/infer/openai_infer.py``), which is only a
client for an OpenAI-compatible server. This module loads the same weights
in-process instead, because that server (vLLM) has no Windows build.
"""

import os
import os.path as osp
import re
from typing import List, Optional, Sequence, Tuple

from ballontranslator.utils import shared
from ballontranslator.utils.download_util import download_and_check_files
from ballontranslator.utils.logger import logger as LOGGER

MODEL_REPO_ID = 'twnlp/ChineseErrorCorrector4-4B'
MODEL_DIR_NAME = 'ChineseErrorCorrector4-4B'
MODEL_BASE_URL = f'https://huggingface.co/{MODEL_REPO_ID}/resolve/main/'

# Instruction used by the v4 model's SFT stage; the sentence goes on its own line.
PROMPT_V4 = (
    '假如你是一名专业的纠错专家，请分析输入句子的语法错误类型和修改原因，'
    '并只输出纠正后的语句，错误类型如下：错别字、词语搭配错误、词性错误、'
    '语序错误、成分残缺、成分赘余、关联词使用错误、指代不明、语义逻辑不通、无误。'
)

MODEL_FILES = (
    'config.json',
    'generation_config.json',
    'model.safetensors.index.json',
    'model-00001-of-00002.safetensors',
    'model-00002-of-00002.safetensors',
    'tokenizer.json',
    'tokenizer_config.json',
    'special_tokens_map.json',
    'added_tokens.json',
    'vocab.json',
    'merges.txt',
    'chat_template.jinja',
)

# Files that must exist before the directory counts as a usable local copy.
_REQUIRED_FILES = (
    'config.json',
    'tokenizer.json',
    'tokenizer_config.json',
    'model.safetensors.index.json',
    'model-00001-of-00002.safetensors',
    'model-00002-of-00002.safetensors',
)

CHINESE_TARGET_LANGS = ('简体中文', '繁體中文')

_THINK_BLOCK_RE = re.compile(r'<think>(.*?)</think>', re.DOTALL | re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r'<think>.*\Z', re.DOTALL | re.IGNORECASE)
_CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')


def strip_reasoning(text: str) -> str:
    """Return the corrected sentence without the chain-of-thought block.

    >>> strip_reasoning('<think>\\n错误类型：错别字\\n</think>\\n我跟我朋友去。')
    '我跟我朋友去。'
    >>> strip_reasoning('<think>被截断的思考')
    ''
    """

    if not text:
        return ''
    cleaned = _THINK_BLOCK_RE.sub('', text)
    if '<think>' in cleaned.lower():
        cleaned = _UNCLOSED_THINK_RE.sub('', cleaned)
    return cleaned.strip()


def default_prompt() -> str:
    """Return the instruction the model was fine-tuned with."""

    return PROMPT_V4


def looks_correctable(text: str) -> bool:
    """Skip blocks that carry no Chinese sentence to proofread.

    >>> looks_correctable('SFX!!')
    False
    >>> looks_correctable('我跟你讲')
    True
    """

    return bool(text and _CHINESE_RE.search(text))


def is_acceptable(source: str, corrected: str) -> bool:
    """Reject runaway rewrites so a bad generation cannot replace a translation.

    A proofread result must stay a sentence-sized edit of the original: bounded
    length ratio, no reasoning leftovers, and some shared body.

    >>> is_acceptable('我跟我朋友去.', '我跟我朋友去。')
    True
    >>> is_acceptable('我跟我朋友去。', '')
    False
    """

    if not corrected or not source:
        return False
    if '<think>' in corrected.lower():
        return False
    if len(corrected) > max(len(source) * 2.0, len(source) + 20):
        return False
    if len(corrected) < len(source) * 0.4:
        return False
    return True


def default_model_dir() -> str:
    return osp.join(shared.PROGRAM_PATH, 'data', 'models', MODEL_DIR_NAME)


def model_is_complete(model_dir: str) -> bool:
    """Check that a directory holds every file needed to load the model.

    >>> model_is_complete('definitely/missing')
    False
    """

    if not model_dir or not osp.isdir(model_dir):
        return False
    return all(osp.isfile(osp.join(model_dir, name)) for name in _REQUIRED_FILES)


def resolve_model_dir(configured: str = '') -> str:
    """Pick the first usable local copy, else the directory downloads target.

    The explicit setting wins, then the environment variable, then the folder
    downloads go to. No fixed path is probed: a copy kept elsewhere has to be
    named by one of the first two, so a missing drive cannot silently shadow
    the copy this installation downloaded.

    >>> resolve_model_dir().endswith('ChineseErrorCorrector4-4B')
    True
    """

    candidates = []
    if configured:
        candidates.append(configured)
    env_dir = os.environ.get('BALLOONTS_CEC_MODEL', '')
    if env_dir:
        candidates.append(env_dir)
    candidates.append(default_model_dir())
    for candidate in candidates:
        if model_is_complete(candidate):
            return candidate
    return default_model_dir()


def ensure_model_files(
    model_dir: str = '',
    progress_callback=None,
    cancel_event=None,
) -> Tuple[bool, str]:
    """Download the weights into ``model_dir`` when no local copy is usable.

    Returns ``(ok, path)``. A cancelled or failed download leaves any partial
    files retryable and reports ``ok=False`` instead of raising, so a proofread
    pass can degrade to "no result" without touching translations.
    """

    target = model_dir or resolve_model_dir()
    if model_is_complete(target):
        return True, target
    if not target:
        target = default_model_dir()
    try:
        os.makedirs(target, exist_ok=True)
        LOGGER.info(f'Downloading {MODEL_REPO_ID} to {target}')
        ok = download_and_check_files(
            url=MODEL_BASE_URL,
            files=list(MODEL_FILES),
            sha256_pre_calculated=[None] * len(MODEL_FILES),
            save_dir=target,
            concatenate_url_filename=1,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )
    except Exception as e:
        LOGGER.error(f'Failed to download {MODEL_REPO_ID}: {e}')
        return False, target
    if not ok:
        LOGGER.error(
            f'Incomplete {MODEL_REPO_ID} files in {target}; proofreading stays disabled.'
        )
        return False, target
    return True, target


class ChineseTextCorrector:
    """Lazy in-process wrapper around the 4B proofreading model."""

    def __init__(
        self,
        model_dir: str = '',
        device: str = '',
        batch_size: int = 8,
        max_new_tokens: int = 1024,
        prompt: str = '',
    ) -> None:
        self.model_dir = model_dir
        self.device = device
        self.batch_size = max(1, int(batch_size))
        self.max_new_tokens = max(64, int(max_new_tokens))
        self.prompt = (prompt or '').strip() or PROMPT_V4
        self._tokenizer = None
        self._model = None

    def loaded(self) -> bool:
        return self._model is not None

    def _resolve_device(self) -> str:
        import torch

        if self.device:
            return self.device
        return 'cuda' if torch.cuda.is_available() else 'cpu'

    def load(self) -> bool:
        """Import and place the model; returns False when weights are missing."""

        if self._model is not None:
            return True
        model_dir = self.model_dir or resolve_model_dir()
        if not model_is_complete(model_dir):
            LOGGER.warning(f'Proofreading model not found in {model_dir}.')
            return False
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = self._resolve_device()
        dtype = torch.bfloat16 if device.startswith(('cuda', 'xpu')) else torch.float32
        LOGGER.info(f'Loading {MODEL_DIR_NAME} from {model_dir} on {device}')
        tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
        tokenizer.padding_side = 'left'
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            dtype=dtype,
            trust_remote_code=True,
        )
        model.to(device)
        model.eval()
        self.model_dir = model_dir
        self.device = device
        self._tokenizer = tokenizer
        self._model = model
        return True

    def release(self) -> None:
        """Drop the weights so the GPU stays available for OCR or translation."""

        self._model = None
        self._tokenizer = None
        try:
            import gc

            import torch

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _build_prompt(self, sentence: str) -> str:
        """Compose the user message: instruction first, sentence on its own line."""

        return f'{self.prompt}\n{sentence}'

    def _generate(self, sentences: Sequence[str]) -> List[str]:
        import torch

        tokenizer = self._tokenizer
        prompts = [
            tokenizer.apply_chat_template(
                [{'role': 'user', 'content': self._build_prompt(sentence)}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for sentence in sentences
        ]
        inputs = tokenizer(prompts, return_tensors='pt', padding=True)
        inputs = {key: value.to(self._model.device) for key, value in inputs.items()}
        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                repetition_penalty=1.1,
            )
        new_tokens = output[:, inputs['input_ids'].shape[1]:]
        decoded = tokenizer.batch_decode(new_tokens, skip_special_tokens=True)
        return [strip_reasoning(text) for text in decoded]

    def correct(self, texts: Sequence[str]) -> List[str]:
        """Proofread every sentence, keeping the original when a result is unusable."""

        results = list(texts)
        if not texts:
            return results
        if not self.load():
            return results
        for start in range(0, len(texts), self.batch_size):
            chunk = list(texts[start:start + self.batch_size])
            try:
                generated = self._generate(chunk)
            except Exception as e:
                LOGGER.warning(f'Proofreading batch failed, keeping translations: {e}')
                continue
            for offset, (source, corrected) in enumerate(zip(chunk, generated)):
                if is_acceptable(source, corrected):
                    results[start + offset] = corrected
        return results


_CORRECTOR: Optional[ChineseTextCorrector] = None


def get_corrector(
    model_dir: str = '',
    device: str = '',
    batch_size: int = 8,
    prompt: str = '',
    max_new_tokens: int = 1024,
) -> ChineseTextCorrector:
    """Return the process-wide corrector, rebuilding it when settings change."""

    global _CORRECTOR
    prompt = (prompt or '').strip() or PROMPT_V4
    max_new_tokens = max(64, int(max_new_tokens))
    if (
        _CORRECTOR is None
        or _CORRECTOR.model_dir != model_dir
        or _CORRECTOR.device != device
        or _CORRECTOR.batch_size != max(1, int(batch_size))
        or _CORRECTOR.prompt != prompt
        or _CORRECTOR.max_new_tokens != max_new_tokens
    ):
        if _CORRECTOR is not None:
            _CORRECTOR.release()
        _CORRECTOR = ChineseTextCorrector(
            model_dir=model_dir,
            device=device,
            batch_size=batch_size,
            max_new_tokens=max_new_tokens,
            prompt=prompt,
        )
    return _CORRECTOR


def release_corrector() -> None:
    global _CORRECTOR
    if _CORRECTOR is not None:
        _CORRECTOR.release()
        _CORRECTOR = None


def proofread_translations(
    texts: Sequence[str],
    *,
    model_dir: str = '',
    device: str = '',
    batch_size: int = 8,
    prompt: str = '',
    max_new_tokens: int = 1024,
    release_after: bool = False,
) -> List[str]:
    """Proofread translated blocks and return one result per input.

    Unchanged, non-Chinese, and failed inputs come back verbatim, so callers can
    compare against the translation and store only real differences.
    """

    results = list(texts)
    targets = [
        index for index, text in enumerate(results) if looks_correctable(text)
    ]
    if not targets:
        return results
    ready, resolved_dir = ensure_model_files(model_dir)
    if not ready:
        return results
    corrector = get_corrector(
        model_dir=resolved_dir,
        device=device,
        batch_size=batch_size,
        prompt=prompt,
        max_new_tokens=max_new_tokens,
    )
    try:
        corrected = corrector.correct([results[index] for index in targets])
    except Exception as e:
        LOGGER.warning(f'Proofreading skipped: {e}')
        return results
    for index, value in zip(targets, corrected):
        results[index] = value
    if release_after:
        release_corrector()
    return results
