# -*- coding: utf-8 -*-
"""شاهدٌ مستقلٌّ لصفوف الإحصاء «غير الحاسمة» — نافذةَ نافذة، بنموذجَي CTC مثبَّتَي البصمة.

⭐ **سببُه مقيسٌ (‏عاصم س38 · asim.48b0baaa · 2026-10-02):** الإحصاءُ الشامل «مقبول» بصفر جسيم
و74/88 نافذةً «غير حاسم» لأنّ whisper-tiny لا يقرأ تسجيلَ التراويح، لا لأنّ شاهداً خالف.
والدرسُ في CLAUDE.md: «حين تتناقض أداتان فالحَكَمُ قياسٌ ثالث». فهذا تعميمٌ لسابقتَي
`spoken_census_witness` (‏20:1) و`tail_census_witness` (‏85:22) على أيّ صفٍّ غير حاسم.

## ما يُثبته (‏كلُّه مقيسٌ من PCM الأصليّ لا من الفهرس)
نموذجان مختلفان مثبَّتا البصمة — العامُّ `jonatasgrosman` **والقرآنيُّ** `rabah2026` (‏لم تستعمله
`ctc_heard_map`) — يحاذيان **نصَّ الآية القانونيَّ بسياقها** (‏السابقةُ · الآيةُ · اللاحقة؛ أو البسملةُ
للآية الأولى) داخل **نافذة المرشّح نفسِها** (‏من بدء السابقة إلى نهاية اللاحقة)، فيجب:
  - ثقةُ الآية ≥ `TARGET_CONF` في كلا النموذجين، وثقةُ كلّ سياقٍ ≥ `ANCHOR_CONF`؛
  - مدّةُ الآية بين 0.5× و2× المتوقَّع بمعدّل الفهرس نفسِه (‏م.ث/حرف · وسيطُ السورة)؛
  - حدُّ الآية المقيسُ لا يبعد عن حدّ المرشّح أكثرَ من `START_TOL`/`END_TOL`؛
  - والنموذجان يتّفقان في الحدّ ضمن التسامح نفسِه.
⇒ **نافذةٌ منزاحةٌ بآيةٍ** (‏كالمرشّح المكبوس 9643cf98) تُردّ: نصُّ الآية لا يقع حيث يقول المرشّح.

## ما لا يفعله (‏حدودٌ لا تُكسر)
- لا يحوّل صفّاً **جسيماً** أو **طفيفاً** أو **تعذّر** إلى بريء — المؤهَّلُ «غير حاسم» فقط، ويُحفظ صفُّ
  Tiny الأصليُّ في `originalTinyRow` كما هو.
- لا يغيّر حدَّ «>50% غير حاسم» في `promote.py` ولا عتبةَ 5%؛ إنما يُضيف حكماً مستقلّاً **يُقرأ معه**.
- ⛔ شاهدٌ بلا نسب CI مراجَع (‏أداةٌ ببصمتها · تشغيلة) يُردّ في `report_error`.
"""
import hashlib
import math
import pathlib
import statistics

from dual_ctc_model import GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS
from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256

FIELD = 'independentWindowCtc'
TARGET_CONF = 0.60       # ثقةُ الآية المعنيّة في كلّ نموذج
ANCHOR_CONF = 0.45       # ثقةُ آيات السياق
START_TOL = 500          # م.ث — بُعدُ بدء الآية المقيس عن بدء المرشّح
END_TOL = 800            # م.ث — بُعدُ نهايتها
DUR_LO, DUR_HI = 0.5, 2.0
OPENER_PAD_MS = 8000     # نافذةُ الآية الأولى: قبلها بهذا القدر (‏تحوي البسملة)
TAIL_PAD_MS = 3000       # نافذةُ الآية الأخيرة: بعدها بهذا القدر
RUNTIME = {'precision': 'float32', 'threads': 2}
MODELS = [('generic', GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS),
          ('quran', MODEL_ID, REVISION, WEIGHTS_SHA256)]
BASMALA = 'بسم الله الرحمن الرحيم'


def _entry(idx, aid):
    return next((e for e in idx['entries'] if e['ayahId'] == aid), None)


def plan(idx, aid, total_ms):
    """نافذةُ الشاهد ونصوصُه القانونيّة لصفٍّ بعينه — دالّةٌ واحدةٌ للمنتج والمتحقّق.
    يُرجع (‏contextAyahIds، windowMs، alignmentInput) أو يرفع ValueError."""
    from common import load_index, load_text, surah_slice
    from spoken_letters import alignment_text
    s, k = (int(x) for x in aid.split(':'))
    target = _entry(idx, aid)
    if target is None or target.get('startMs') is None:
        raise ValueError('target has no entry')
    begin, stop, _ = surah_slice(load_index(), s)
    n = stop - begin
    refs = load_text(idx['riwaya'])[begin:stop]
    ids, texts = [], []
    prev = _entry(idx, f'{s}:{k - 1}') if k > 1 else None
    nxt = _entry(idx, f'{s}:{k + 1}') if k < n else None
    if k == 1:
        if s not in (1, 9):
            ids.append(f'{s}:basmala'); texts.append(BASMALA)
        start = max(0, target['startMs'] - OPENER_PAD_MS)
    else:
        if prev is None or prev.get('startMs') is None:
            raise ValueError('previous ayah has no entry')
        ids.append(f'{s}:{k - 1}'); texts.append(alignment_text(s, k - 1, refs[k - 2]))
        start = prev['startMs']
    ids.append(aid); texts.append(alignment_text(s, k, refs[k - 1]))
    if nxt is not None and nxt.get('startMs') is not None:
        ids.append(f'{s}:{k + 1}'); texts.append(alignment_text(s, k + 1, refs[k]))
        end = nxt['endMs']
    elif k == n:
        end = min(total_ms, target['endMs'] + TAIL_PAD_MS)
    else:
        raise ValueError('next ayah has no entry')
    if not 0 <= start < end <= total_ms:
        raise ValueError('window outside file')
    return ids, [start, end], texts


def _rate(idx, s):
    from common import load_index, load_text, norm, surah_slice
    begin, stop, _ = surah_slice(load_index(), s)
    refs = load_text(idx['riwaya'])[begin:stop]
    chars = {f'{s}:{i + 1}': len(norm(t).replace(' ', '')) for i, t in enumerate(refs)}
    rates = [(e['endMs'] - e['startMs']) / chars[e['ayahId']] for e in idx['entries']
             if e['ayahId'].startswith(f'{s}:') and e.get('startMs') is not None and chars.get(e['ayahId'])]
    if not rates:
        raise ValueError('no indexed entries to derive a rate')
    return statistics.median(rates), chars


def witness_error(proof, idx, aid):
    """None إن صحّ الشاهدُ للصفّ `aid`، وإلا نصُّ الردّ."""
    try:
        s = int(aid.split(':')[0])
        shas = idx['audioSha256']
        if (proof['target'] != aid or proof['canonicalTextChanged'] is not False
                or proof['sourceSha256'] != shas[s - 1] or proof['runtime'] != RUNTIME):
            raise ValueError('wrong target, source, canonical text or runtime')
        total = proof['totalMs']
        ids, window, texts = plan(idx, aid, total)
        if proof['contextAyahIds'] != ids or proof['windowMs'] != window:
            raise ValueError('context or window differs from the candidate plan')
        target = _entry(idx, aid)
        rate, chars = _rate(idx, s)
        pos = ids.index(aid)
        measured = []
        for name, ident, revision, weights in MODELS:
            result = proof['models'][name]
            model = result['alignmentModel']
            if (model['id'], model['revision'], model['weightsSha256'], model['license']) != (
                    ident, revision, weights, 'Apache-2.0'):
                raise ValueError('unpinned independent model')
            if name == 'generic' and result['alignmentInput'] != texts:
                raise ValueError('generic alignment input differs from canonical reference')
            if name == 'quran' and len(result['alignmentInput']) != len(texts):
                raise ValueError('quran alignment input differs from canonical reference')
            entries = result['entries']
            if len(entries) != len(ids) or [e['ayahId'] for e in entries] != ids:
                raise ValueError('incomplete witness context')
            last = window[0]
            for i, e in enumerate(entries):
                c = e['conf']
                if not math.isfinite(c) or not 0 <= c <= 1:
                    raise ValueError('invalid confidence')
                if not last <= e['startMs'] < e['endMs'] <= window[1]:
                    raise ValueError('invalid context interval')
                last = e['endMs']
                if (c < ANCHOR_CONF) if i != pos else (c < TARGET_CONF):
                    raise ValueError('weak target or anchor confidence')
            t = entries[pos]
            dur, exp = t['endMs'] - t['startMs'], rate * chars[aid]
            if not DUR_LO * exp <= dur <= DUR_HI * exp:
                raise ValueError('target duration outside bounds')
            if abs(t['startMs'] - target['startMs']) > START_TOL or abs(t['endMs'] - target['endMs']) > END_TOL:
                raise ValueError('witness differs from candidate boundary')
            measured.append(t)
        if (abs(measured[0]['startMs'] - measured[1]['startMs']) > START_TOL
                or abs(measured[0]['endMs'] - measured[1]['endMs']) > END_TOL):
            raise ValueError('independent models disagree')
    except (KeyError, ValueError, TypeError, IndexError, StopIteration, ZeroDivisionError) as exc:
        return 'Window census witness rejected: ' + str(exc)
    return None


def report_error(report, idx):
    """يُقرأ في `promote.py` مع الإحصاء: صفٌّ يحمل هذا الشاهدَ يجب أن يكون أصلُه «غير حاسم»
    وحكمُه الآن «بريء» وشاهدُه صحيحاً بنسب CI — وإلا يُردّ الإحصاءُ كلُّه."""
    tool = pathlib.Path(__file__).parents[1] / 'index_qa' / 'ci_window_census.py'
    tool_sha = hashlib.sha256(tool.read_bytes()).hexdigest() if tool.exists() else None
    for row in report.get('sample', {}).get('rows', []):
        proof = row.get(FIELD)
        if proof is None:
            continue
        original = row.get('originalTinyRow') or {}
        if (row.get('kind') != 'بريء' or original.get('aid') != row.get('aid')
                or original.get('kind') != 'غير حاسم'):
            return 'Window witness cannot override an adverse verdict or a different row'
        provenance = proof.get('provenance') or {}
        if (provenance.get('kind') != 'audio' or provenance.get('source') != 'ci'
                or not str(provenance.get('run_id') or '').isdigit()
                or provenance.get('tool') != 'tools/index_qa/ci_window_census.py'
                or provenance.get('tool_sha') != tool_sha):
            return 'Window witness lacks reviewed CI producer provenance'
        error = witness_error(proof, idx, row['aid'])
        if error:
            return error
    return None
