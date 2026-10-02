"""Read-only source copy: exact public stream bytes, no production index edits."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
PUBLISHER = 'https://soundcloud.com/mustafa-el-nwihy/1441-2020'
SHA = 'c82dee8759a803dbe1364e9745880856ca5a5eb98b8473a70f689b4905e27e3a'
SIZE = 44566568
FRAMES_MS = 2785410.612241291
NATIVE_MS = 2785349.6875
DEST = ROOT / 'ops/source-repair/audio-fixtures/kurdi-nahl-c82dee87.mp3'
EVIDENCE = ROOT / 'ops/source-repair/kurdi-soundcloud-original-source-evidence-20261002.json'

def verify_bytes(path):
    data = Path(path).read_bytes()
    if len(data) != SIZE or hashlib.sha256(data).hexdigest() != SHA:
        raise ValueError('Public original stream bytes changed; no fixture or index write')

def main():
    import run as R
    with tempfile.TemporaryDirectory() as td:
        original = Path(td) / 'original.mp3'
        proc = subprocess.run(['python','-m','yt_dlp','--no-playlist','--no-progress',
                               '--format','http_mp3_0_1','--output',str(original),PUBLISHER],
                              capture_output=True,text=True,timeout=180)
        if proc.returncode:
            raise ValueError('Original public publisher download failed; no source substitution')
        verify_bytes(original)
        frames = R._file_duration_ms(original)
        pcm = R._full_decode_pcm(original)
        native = len(pcm)*1000.0/16000
        if abs(frames-FRAMES_MS)>2 or abs(native-NATIVE_MS)>2:
            raise ValueError('Complete original physical source duration changed')
        proof={'kind':'byte-exact-original-public-source-qa-fixture','publisherPage':PUBLISHER,
               'title':'سورة النحل كاملة بترتيل متنوع من اجمل تلاوات للشيخ رعد الكردي من رمضان1441 -2020',
               'reciterId':'kurdi','riwaya':'hafs','surah':16,'sourceSha256':SHA,'bytes':SIZE,
               'containerMs':frames,'nativeMs':native,'wholeDecodeStrict':True,
               'sourceBytesChanged':False,'locallyTranscoded':False,'canonicalTextChanged':False,
               'productionChanged':False,'completeAlignmentNotYetAccepted':True,
               'fixturePath':str(DEST.relative_to(ROOT)),
               'storage':'regular Git in verified public repository; no LFS/cache/artifacts/R2 audio write',
               'ts':time.time()}
        DEST.parent.mkdir(parents=True,exist_ok=True)
        if DEST.exists():
            verify_bytes(DEST)
        else:
            DEST.write_bytes(original.read_bytes())
        EVIDENCE.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
        print('KURDI_ORIGINAL_SOURCE_RESULT='+json.dumps(proof,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
