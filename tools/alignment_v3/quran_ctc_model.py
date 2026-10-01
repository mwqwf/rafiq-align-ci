"""Pinned, Apache-2.0 Quran CTC model; alignment input only, never shipped text."""
import hashlib
import unicodedata

MODEL_ID = 'rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final'
REVISION = 'b03a268c6ba1a693752307325ab376c86c3b12da'
WEIGHTS_SHA256 = 'bf65674a26eb4ef7042cedade96c3c8f8cbd04f3a7d1a68eadceec8ed0f99ecb'
ENGINE = 'ctc-quran-window-1'
_VOCAB = None


def configure():
    global _VOCAB
    import ctc_seg as C
    evidence = {'id': MODEL_ID, 'revision': REVISION, 'weightsSha256': WEIGHTS_SHA256,
                'license': 'Apache-2.0', 'canonicalTextChanged': False}
    if _VOCAB is not None and C._M.get('alignmentModelId') == MODEL_ID:
        return evidence
    if C._M:
        raise ValueError('A model is already loaded; use a fresh process for this engine')
    from huggingface_hub import snapshot_download
    from pathlib import Path
    snapshot = Path(snapshot_download(MODEL_ID, revision=REVISION,
                         allow_patterns=['*.json', 'model.safetensors', 'README.md']))
    digest = hashlib.sha256()
    with (snapshot/'model.safetensors').open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != WEIGHTS_SHA256:
        raise ValueError('Quran CTC model weights differ from the pinned source')
    C.MODEL_ID = str(snapshot)
    _VOCAB = C._model()['proc'].tokenizer.get_vocab()
    C._M['alignmentModelId'] = MODEL_ID
    return evidence


def reference_text(text):
    if _VOCAB is None:
        raise ValueError('Configure the pinned model before preparing alignment input')
    aliases = {'ے': 'ي', 'ۓ': 'ئ', 'ک': 'ك', 'ی': 'ي'}
    out = []
    for ch in text:
        ch = aliases.get(ch, ch)
        if ch in _VOCAB or ch == ' ':
            out.append(ch)
        elif ch in ('۞', '۩') or unicodedata.category(ch).startswith(('M', 'P')) or ch.isspace():
            continue
        else:
            raise ValueError(f'Unsupported canonical character in alignment input: {ch!r}')
    return ''.join(out)


def records_error(idx):
    models = idx.get('alignmentModelBySurah') or {}
    for surah, engine in (idx.get('engineBySurah') or {}).items():
        if engine not in (ENGINE, 'ctc-quran-surah-1'):
            continue
        ev = models.get(str(surah), {}) if isinstance(models, dict) else {}
        if (ev.get('id') != MODEL_ID or ev.get('revision') != REVISION
                or ev.get('weightsSha256') != WEIGHTS_SHA256
                or ev.get('license') != 'Apache-2.0' or ev.get('canonicalTextChanged') is not False):
            return f'س{surah}: محرك التلاوة بلا نسب نموذج ثابت صحيح'
    from dual_ctc_model import records_error as dual_records_error
    return dual_records_error(idx)
