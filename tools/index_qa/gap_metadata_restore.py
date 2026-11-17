#!/usr/bin/env python3
"""تحقق مغلق لاستعادة دليل حجب ضائع عبر سلسلة آباء مثبتة،بلا شبكة أو كتابة."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
import re
from pathlib import Path
import promote
from declarations import prior_declarations
SHA = re.compile(r'[0-9a-f]{64}')

def require(ok, why):
    if not ok:
        raise ValueError('استعادة دليل الحجب: ' + why)

def verify(parent, candidate, parent_sha, plan, read_blob):
    """يربط الأدلة ببصمات fromSha256 الموروثة في الحي،لا ببصمات يدعيها الملف وحده."""
    require(SHA.fullmatch(str(parent_sha)) is not None, 'بصمة الحي كاملة إلزامية')
    require(isinstance(plan, dict) and set(plan) == {'version', 'parentSha256', 'nodes', 'restore'}, 'صيغة الخطة غير صالحة')
    require(type(plan['version']) is int and plan['version'] == 1 and plan['parentSha256'] == parent_sha, 'الخطة لا تصف الحي الحالي')
    require(isinstance(plan['nodes'], list) and 0 < len(plan['nodes']) <= 64, 'سلسلة الآباء فارغة أو طويلة')
    require(isinstance(plan['restore'], list) and bool(plan['restore']), 'لا سور للاستعادة')
    require({k:v for k,v in candidate.items() if k != 'transform'} ==
            {k:v for k,v in parent.items() if k != 'transform'}, 'تغير حقل خارج transform')
    identity = (parent.get('riwaya'), parent.get('reciterId'))
    live_key = f'timings/{identity[0]}/{identity[1]}.jz'
    nodes = {}
    for node in plan['nodes']:
        require(isinstance(node, dict) and set(node) == {'key', 'sha256', 'file'}, 'وصف أب غير صالح')
        sha = node['sha256']
        require(SHA.fullmatch(str(sha)) is not None and sha not in nodes, 'بصمة أب ناقصة أو مكررة')
        require(node['key'] in (live_key, f'timings-staging/{identity[0]}/{identity[1]}.{sha[:8]}.jz'), 'مفتاح أب لقارئ آخر أو بصمة أخرى')
        raw = read_blob(node['file'])
        require(hashlib.sha256(raw).hexdigest() == sha, 'بايتات الأب لا تطابق بصمته')
        doc = json.loads(gzip.decompress(raw))
        require((doc.get('riwaya'), doc.get('reciterId')) == identity, 'هوية الأب تختلف')
        nodes[sha] = (doc, node['key'])
    targets = {}
    for row in plan['restore']:
        require(isinstance(row, dict) and set(row) == {'surah', 'sourceSha256'}, 'صف استعادة غير صالح')
        s, sha = row['surah'], row['sourceSha256']
        require(type(s) is int and 1 <= s <= 114 and s not in targets and sha in nodes, 'سورة أو مصدر مكرر/غير صالح')
        targets[s] = sha
    # كل عقدة بين الحي ومصدر الدليل يجب أن تكون متصلة ببصمتها الكاملة.
    chain, seen, cur, reference_keys = [], set(), parent, {}
    while not set(targets.values()) <= seen:
        tr = cur.get('transform') or {}
        sha, key = tr.get('fromSha256'), tr.get('fromKey')
        require(sha in nodes and sha not in seen, 'سلسلة الأصل منقطعة أو دائرية')
        doc, _archive_key = nodes[sha]
        require(key in (live_key, f'timings-staging/{identity[0]}/{identity[1]}.{sha[:8]}.jz'), 'رابط الأب لا يطابق بصمته وهويته')
        reference_keys[sha] = key
        chain.append((sha, doc));seen.add(sha);cur=doc
    require(seen == set(nodes), 'عقدة غير مرتبطة أو غير لازمة في الخطة')
    expected = copy.deepcopy(parent)
    tr = expected.get('transform')
    require(isinstance(tr, dict), 'تحويل الحي غير صالح')
    tr['declarations'] = copy.deepcopy(prior_declarations(parent))
    proofs = []
    for s, source_sha in sorted(targets.items()):
        source = nodes[source_sha][0]
        ok, why = promote.declared_truncated_gaps(source, s)
        require(ok, why)
        require(str(s) not in tr.get('truncatedGaps', {}) and str(s) not in tr['declarations'], 'لا يجوز استبدال إعلان قائم')
        # لا يكفي تطابق الطرفين: لم تتغير فجوة الآية أو صوتها في أي خطوة وسيطة.
        docs = [parent] + [d for _,d in chain[:next(i for i,(sha,_) in enumerate(chain) if sha == source_sha)+1]]
        source_missing = {a for a in source.get('missing', {}).get('ids', []) if str(a).startswith(str(s)+':')}
        source_audio = source.get('audioSha256', [])[s-1]
        require(SHA.fullmatch(str(source_audio)) is not None, 'بصمة صوت المصدر ناقصة')
        for doc in docs:
            require(len(doc.get('audioSha256', [])) >= s and doc['audioSha256'][s-1] == source_audio, 'الصوت تبدل في سلسلة الأصل')
            missing = {a for a in doc.get('missing', {}).get('ids', []) if str(a).startswith(str(s)+':')}
            have = {int(e['ayahId'].split(':')[1]) for e in doc.get('entries', []) if e['ayahId'].split(':')[0] == str(s)}
            actual = {f'{s}:{a}' for a in range(1, promote._AYAH_COUNTS[s-1]+1) if a not in have}
            require(missing == source_missing == actual, 'الغياب تبدل أو لا يطابق المداخل في سلسلة الأصل')
        src_tr = source['transform'];record=src_tr['truncatedGaps'][str(s)]
        tr.setdefault('truncatedGaps', {})[str(s)] = copy.deepcopy(record)
        tr['declarations'][str(s)] = copy.deepcopy(prior_declarations(source)[str(s)])
        tr['op'] += '|declare_gap:' + str(s)
        claims = (src_tr.get('witnessedAbsent') or {}).get(str(s))
        if claims is not None:
            existing = (tr.get('witnessedAbsent') or {}).get(str(s))
            require(existing is None or existing == claims, 'لا يجوز استبدال شاهد حي مختلف بدليل أقدم')
            require(isinstance(claims, dict) and {int(a) for a in claims} <= set(record['absent']), 'شاهد خارج الغياب المعلن')
            version = src_tr.get('witnessedAbsentVersion') or 'ctc-absent-witnessed-1'
            require(not tr.get('witnessedAbsentVersion') or tr['witnessedAbsentVersion'] == version, 'نسخة شاهد الغياب تختلف')
            tr.setdefault('witnessedAbsent', {})[str(s)] = copy.deepcopy(claims)
            tr['witnessedAbsentVersion'] = version
        proofs.append({'surah':s,'sourceKey':reference_keys[source_sha],
                       'archiveKey':nodes[source_sha][1],'sourceSha256':source_sha})
    require(candidate == expected, 'المنتج ليس نسخاً حرفياً للإعلانات المسموح بها وحدها')
    for s in tr['truncatedGaps']:
        ok, why = promote.declared_truncated_gaps(candidate, s)
        require(ok, why)
    return {'version':1, 'parentSha256':parent_sha, 'sources':proofs,
            'chainSha256':[sha for sha,_ in chain], 'entriesUnchanged':True, 'audioUnchanged':True}

def from_file(parent, candidate, parent_sha, path):
    p = Path(path)
    plan = json.loads(p.read_text(encoding='utf-8'))
    def read(name):
        require(isinstance(name, str), 'اسم ملف الأب غير صالح')
        file = Path(name)
        return (file if file.is_absolute() else p.parent/file).read_bytes()
    return verify(parent, candidate, parent_sha, plan, read)
