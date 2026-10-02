"""إلغاء خمس نسخ مكررة بعينها؛ تحفظ الفحوص الأصلية وأدلتها دون تعديل."""
import gzip, hashlib, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'index_qa'))
import promote as P
from qa_recover_stalled import gh

KEY = 'timings-staging/hafs/a_klb.f033e3fe.jz'
SHA = 'f033e3fe75f9ae484688e01745f94846c204b32f8c4ed276610fdf5dc8cd41e1'
DUPLICATES = {36955080830: 'k1', 36955083137: 'k2', 36955085502: 'k3',
              36955087563: 'k4', 36955078120: 'openers'}

def eligible(run):
    salt = DUPLICATES.get(run.get('id'))
    if salt is None: return False
    path = '.github/workflows/' + ('openers.yml' if salt == 'openers' else 'audio_qa.yml')
    title = (f'openers {KEY} · n=1' if salt == 'openers'
             else f'qa {KEY} · salt={salt} · n=20')
    return (run.get('path') == path and run.get('display_title') == title
            and run.get('event') == 'workflow_dispatch'
            and run.get('status') in ('queued', 'in_progress', 'pending')
            and run.get('repository', {}).get('full_name') == 'mwqwf/rafiq-align-ci'
            and run.get('repository', {}).get('private') is False)

def main():
    cl, bucket = P.s3()
    if P.object_sha(cl, bucket, KEY)[0] != SHA: raise ValueError('تغير المرشح')
    flat = KEY.replace('/', '_')
    for salt in ('rs1', 'rs3', 'rs4'):
        r = json.loads(cl.get_object(Bucket=bucket, Key=f'state/{flat}.audio-{salt}.json')['Body'].read())
        sm = r.get('sample') or {}
        if (r.get('sha256') != SHA or r.get('fatal') or sm.get('errors')
                or sm.get('seedSalt') != salt or len(sm.get('rows') or []) != 200):
            raise ValueError('الفحص الأصلي الفعلي غير مكتمل: ' + salt)
    original = gh('actions/runs/36953326331')
    if (original.get('display_title') != f'qa {KEY} · salt=rs2 · n=1'
            or original.get('status') not in ('queued', 'in_progress', 'completed')
            or (original.get('status') == 'completed' and original.get('conclusion') != 'success')):
        raise ValueError('الفحص الأصلي الرابع غير جار أو ناجح')
    opener = json.loads(cl.get_object(Bucket=bucket, Key=f'state/{flat}.openers.json')['Body'].read())
    if (opener.get('sha256') != SHA or opener.get('scope') != 'full'
            or opener.get('errors') or opener.get('swallowed') or opener.get('lateConfirmed')):
        raise ValueError('المطالع الأصلية ليست كاملة ومتحققة')
    for ident in DUPLICATES:
        run = gh(f'actions/runs/{ident}')
        ok = eligible(run)
        print(json.dumps({'run': ident, 'duplicateEligible': ok, 'status': run.get('status')}, ensure_ascii=False), flush=True)
        if ok:
            gh(f'actions/runs/{ident}/cancel', {})
            print('أُلغي الفحص المكرر فقط:', ident, flush=True)
        elif run.get('status') != 'completed':
            raise ValueError('هوية النسخة المكررة تغيرت؛ لا إلغاء')

if __name__ == '__main__': main()
