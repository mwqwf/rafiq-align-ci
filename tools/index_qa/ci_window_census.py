"""شاهدٌ مستقلٌّ لنوافذ الإحصاء «غير الحاسمة» — سورةً كاملةً، بنموذجَي CTC مثبَّتَين بدقّة float32.

⭐ تعميمُ `ci_tail_census.py` (‏85:22) و`ci_spoken_census.py` (‏20:1) على كلّ صفٍّ «غير حاسم» في
سورةٍ محصاة: لكلّ صفّ نافذتُه من المرشّح نفسِه (‏السابقة → اللاحقة)، ويُقاس فيها نصُّ الآية بسياقها
بالنموذجين على PCM الأصليّ ببصمته. صفُّ Tiny الأصليُّ يُحفظ في `originalTinyRow`؛ ولا يُمسّ صفٌّ
جسيمٌ أو طفيفٌ أو متعذّر. التقريرُ الأصليُّ يُؤرشف في `state-census-original/` ويُكتب الجديدُ
بشرط ETag فلا يُكتب فوق تقريرٍ تغيّر في الأثناء.

⛔ لا يُشترط هنا صفاءُ `census_gate` كاملاً — فحارسُ «>50% غير حاسم» فيه هو **سببُ** هذا الشاهد.
يُشترط ما قبله: البصمةُ نفسُها · كلُّ حاضرٍ مسموع · لا تعذّر · لا جسيم فوق 5%.
و`--dry-run` يقيس ويكتب التشخيصَ ولا يكتب في الدلو — للضبط السالب (‏المرشّح المكبوس).
"""
import argparse
import copy
import gc
import gzip
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'alignment_v3'))
import ci_spoken_census as W            # noqa: E402  (‏configure_generic · C · Q)
import promote as P                     # noqa: E402
import run as R                         # noqa: E402
import window_census_witness as X       # noqa: E402

INCONCLUSIVE = 'الإحصاءُ لم يحكم'


def _download(url, expected_sha, cache):
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and hashlib.sha256(cache.read_bytes()).hexdigest() == expected_sha:
        return cache
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=300) as audio:
        raw = audio.read()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('Indexed source audio changed (sha256 differs from audioSha256)')
    cache.write_bytes(raw)
    return cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', required=True)
    ap.add_argument('--surah', type=int, required=True)
    ap.add_argument('--dry-run', action='store_true', help='يقيس ويشخّص ولا يكتب في الدلو')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    if (not a.key.startswith('timings-staging/') or a.key.count('/') != 2 or not a.key.endswith('.jz')
            or os.environ.get('CTC_INT8') != '0' or os.environ.get('CTC_THREADS') != '2'):
        raise ValueError('Explicit staging key and bounded float32 runtime required')
    s = a.surah
    cl, bucket = P.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)['Body'].read()
    idx = json.loads(gzip.decompress(body)); sha = hashlib.sha256(body).hexdigest()
    state = 'state-census/' + a.key.replace('/', '_') + '.json'
    response = cl.get_object(Bucket=bucket, Key=state)
    original = response['Body'].read(); report = json.loads(original)
    if report.get('sha256') != sha:
        raise ValueError('Census report is for another sha256')
    if str(s) not in {str(x) for x in (report.get('census') or {}).get('surahs') or []}:
        raise ValueError('Surah is not part of the census')
    gate = P.census_gate(cl, bucket, a.key, sha, idx)
    if gate and not gate.startswith(INCONCLUSIVE):
        raise ValueError('Census is rejected for a reason other than inconclusiveness: ' + gate)
    rows = [r for r in report['sample']['rows'] if r['aid'].split(':')[0] == str(s)]
    todo = [r for r in rows if r.get('kind') == 'غير حاسم' and X.FIELD not in r]
    refs = {e['fileRef'] for e in idx['entries'] if e['ayahId'].startswith(f'{s}:') and e.get('startMs') is not None}
    if len(refs) != 1:
        raise ValueError('Surah entries must share one indexed source file')
    source = refs.pop(); source_sha = idx['audioSha256'][s - 1]
    out = ROOT / (a.out or f'ops/out/window-census-witness-{sha[:8]}-s{s:03d}.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    diagnostic = {'key': a.key, 'sha256': sha, 'surah': s, 'dryRun': a.dry_run, 'rows': len(rows),
                  'inconclusive': len(todo), 'accepted': [], 'rejected': {}, 'productionChanged': False}
    if not todo:
        out.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(diagnostic, ensure_ascii=False)); return
    path = _download(source, source_sha, ROOT / 'scratch' / 'window-census' / (source_sha + pathlib.Path(source).suffix))
    pcm_all = R._full_decode_pcm(path)
    total = len(pcm_all) // 16
    proofs = {}
    for r in todo:
        try:
            ids, window, texts = X.plan(idx, r['aid'], total)
        except ValueError as exc:
            diagnostic['rejected'][r['aid']] = 'plan: ' + str(exc); continue
        proofs[r['aid']] = {'target': r['aid'], 'sourceSha256': source_sha, 'canonicalTextChanged': False,
                            'contextAyahIds': ids, 'windowMs': window, 'totalMs': total, 'models': {},
                            'runtime': dict(X.RUNTIME), '_texts': texts}
    # ⛔ النموذجُ خارجَ الحلقة: `Q.configure()` يشترط `C._M` فارغاً، فيُحمَّل كلُّ نموذجٍ مرّةً
    #    وتُقاس به كلُّ النوافذ ثمّ يُفرَّغ.
    for name in ['generic', 'quran']:
        model = W.configure_generic() if name == 'generic' else W.Q.configure()
        model = {k: model[k] for k in ('id', 'revision', 'weightsSha256', 'license')}
        for aid, proof in proofs.items():
            start, end = proof['windowMs']
            texts = proof['_texts']
            actual = texts if name == 'generic' else [W.Q.reference_text(t) for t in texts]
            pcm = pcm_all[start * 16:end * 16]
            try:
                raw = W.C._segment(W.C._emissions(pcm), len(pcm), actual)
            except Exception as exc:                       # noqa: BLE001 — نافذةٌ واحدةٌ لا تُسقط السورة
                proof['models'][name] = {'alignmentModel': model, 'alignmentInput': actual,
                                         'entries': [], 'error': str(exc)[:200]}
                continue
            entries = [{'ayahId': cid, 'startMs': start + int(st * 1000),
                        'endMs': start + int(en * 1000), 'conf': W.C._conf(score)}
                       for cid, (st, en, score) in zip(proof['contextAyahIds'], raw)]
            for i in range(len(entries) - 1):
                entries[i]['endMs'] = entries[i + 1]['startMs']
            proof['models'][name] = {'alignmentModel': model, 'alignmentInput': actual, 'entries': entries}
            print(name, aid, [(e['startMs'], e['endMs'], round(e['conf'], 3)) for e in entries], flush=True)
        W.C._M.clear(); gc.collect()
    tool_sha = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
    provenance = {'kind': 'audio', 'source': 'ci', 'run_id': os.environ.get('GITHUB_RUN_ID', ''),
                  'run_sha': os.environ.get('GITHUB_SHA', ''), 'tool': 'tools/index_qa/ci_window_census.py',
                  'tool_sha': tool_sha}
    by_aid = {r['aid']: r for r in todo}
    changed = []
    for aid, proof in proofs.items():
        proof.pop('_texts')
        error = X.witness_error(proof, idx, aid)
        if error:
            diagnostic['rejected'][aid] = error; continue
        proof['provenance'] = dict(provenance)
        diagnostic['accepted'].append({'aid': aid, 'windowMs': proof['windowMs'],
                                       'measured': {n: proof['models'][n]['entries'][proof['contextAyahIds'].index(aid)]
                                                    for n in ('generic', 'quran')}})
        changed.append((by_aid[aid], proof))
    diagnostic['proofs'] = {aid: p for aid, p in proofs.items()}
    out.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in diagnostic.items() if k != 'proofs'}, ensure_ascii=False), flush=True)
    if a.dry_run or not changed:
        return
    original_sha = hashlib.sha256(original).hexdigest()
    archive = 'state-census-original/' + a.key.replace('/', '_') + '/' + original_sha + '.json'
    try:
        archived = cl.get_object(Bucket=bucket, Key=archive)['Body'].read()
    except cl.exceptions.NoSuchKey:
        cl.put_object(Bucket=bucket, Key=archive, Body=original, ContentType='application/json', IfNoneMatch='*')
    else:
        if hashlib.sha256(archived).hexdigest() != original_sha:
            raise ValueError('Original census archive does not match unchanged bytes')
    for row, proof in changed:
        row['originalTinyRow'] = copy.deepcopy(row)
        row[X.FIELD] = proof
        row['kind'] = row['verdict'] = 'بريء'
        row['why'] = ('بريئة بشاهدٍ مستقلّ: نموذجا CTC مثبَّتان (عامٌّ وقرآنيّ) يحاذيان نصَّ الآية بسياقها'
                      ' داخل نافذة المرشّح على الصوت الأصليّ ببصمته، بثقةٍ ومدّةٍ وحدودٍ مطابقة؛'
                      ' وصفُّ Tiny غيرُ الحاسم محفوظٌ كاملاً')
    report.setdefault('independentWindowOriginal', []).append({'key': archive, 'sha256': original_sha,
                                                               'surah': s, 'rows': [r['aid'] for r, _ in changed]})
    report['ts'] = time.time()
    cl.put_object(Bucket=bucket, Key=state, Body=json.dumps(report, ensure_ascii=False).encode(),
                  ContentType='application/json', IfMatch=response['ETag'])
    diagnostic['productionChanged'] = True; diagnostic['originalReport'] = archive
    out.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'productionChanged': True, 'accepted': len(changed), 'rejected': len(diagnostic['rejected'])},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
