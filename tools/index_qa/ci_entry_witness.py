"""شاهدُ نوافذ مداخلَ بعينها بنموذجَي CTC (عامّ وقرآنيّ) — قراءةٌ محضةٌ بلا كتابةٍ في الدلو (2026-11-07).

لكلّ آيةٍ مسمّاة: نافذتُها من المرشّح نفسِه (السابقة→الآية→اللاحقة كما `window_census_witness.plan`)،
ثمّ لكلّ نموذجٍ (1) محاذاةٌ قسريّةٌ لنصوص السياق فتُقارَن حدودُها بحدود المرشّح، و(2) فكٌّ جشعٌ للنافذة
يُبيّن **النصَّ المسموعَ** ويُقاس تشابهُه مع الآية وجاراتِها ±2. المعتبرُ النصُّ لا البدء (النافذةُ مقطوعةٌ من
بدء المرشّح فبدؤها ملتصقٌ بالنافذة). لا يحكم ولا يرقّي ولا يمسّ حارساً؛ التفريغُ مرشّحٌ للحكم لا نصٌّ يُنشر.
"""
import argparse, difflib, gc, gzip, hashlib, json, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'alignment_v3'))
sys.path.insert(0, str(ROOT / 'tools' / 'alignment'))
import ci_spoken_census as W            # noqa: E402
import promote as P                     # noqa: E402
import run as R                         # noqa: E402
import window_census_witness as X       # noqa: E402
import ci_window_census as K            # noqa: E402  (_download)
import ctc_heard_map as H               # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', required=True)
    ap.add_argument('--surah', type=int, required=True)
    ap.add_argument('--ayahs', required=True)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    if (not a.key.startswith('timings-staging/') or a.key.count('/') != 2
            or os.environ.get('CTC_INT8') != '0' or os.environ.get('CTC_THREADS') != '2'):
        raise ValueError('staging key + float32 + two threads required')
    from common import load_index, load_text, norm, surah_slice
    s = a.surah
    cl, bucket = P.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)['Body'].read()
    idx = json.loads(gzip.decompress(body)); sha = hashlib.sha256(body).hexdigest()
    refs_f = {e['fileRef'] for e in idx['entries'] if e['ayahId'].startswith(f'{s}:') and e.get('startMs') is not None}
    assert len(refs_f) == 1
    source = refs_f.pop(); source_sha = idx['audioSha256'][s - 1]
    path = K._download(source, source_sha, ROOT / 'scratch' / 'ew' / (source_sha + pathlib.Path(source).suffix))
    pcm_all = R._full_decode_pcm(path); total = len(pcm_all) // 16
    b0, b1, _ = surah_slice(load_index(), s)
    texts_all = [norm(t) for t in load_text(idx['riwaya'])[b0:b1]]
    ayahs = [int(x) for x in a.ayahs.replace(',', ' ').split()]
    plans = {k: X.plan(idx, f'{s}:{k}', total) for k in ayahs}
    entry = {e['ayahId']: e for e in idx['entries']}
    out = {'key': a.key, 'sha256': sha, 'surah': s, 'ayahs': {}}
    for name in ('generic', 'quran'):
        model = W.configure_generic() if name == 'generic' else W.Q.configure()
        cl_, blank, delim = H._char_list()
        for k, (ids, window, texts) in plans.items():
            st, en = window
            pcm = pcm_all[st * 16:en * 16]
            actual = texts if name == 'generic' else [W.Q.reference_text(t) for t in texts]
            rec = out['ayahs'].setdefault(str(k), {'windowMs': window, 'candidate': {i: [entry[i]['startMs'], entry[i]['endMs']] for i in ids if i in entry}})
            lpz = W.C._emissions(pcm)
            frame = len(pcm) / 16 / lpz.shape[0]
            heard = ''.join(c for c, _ in H.greedy_decode(lpz, frame, cl_, blank, delim))
            hn = norm(heard)
            sims = {str(j): round(difflib.SequenceMatcher(None, hn, texts_all[j - 1]).ratio(), 3)
                    for j in range(max(1, k - 2), min(len(texts_all), k + 2) + 1)}
            r = {'heardText': heard, 'similarityByAyah': sims,
                 'nearest': max(sims, key=sims.get), 'ownSimilarity': sims[str(k)]}
            try:
                raw = W.C._segment(lpz, len(pcm), actual)
                r['aligned'] = {cid: [st + int(b * 1000), st + int(e * 1000), round(W.C._conf(sc), 3)]
                                for cid, (b, e, sc) in zip(ids, raw)}
            except Exception as exc:  # noqa: BLE001
                r['alignError'] = str(exc)[:200]
            rec[name] = r
            print(name, s, k, 'heard=', heard, 'sims', sims, 'aligned', r.get('aligned'), flush=True)
        W.C._M.clear(); gc.collect()
    p = ROOT / (a.out or f'ops/out/entry-witness-{sha[:8]}-s{s:03d}.json')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
