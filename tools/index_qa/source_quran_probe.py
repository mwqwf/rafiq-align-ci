#!/usr/bin/env python3
"""Read-only investigation of two independently archived Janaini Qalun surahs.
Never stages, uploads audio, alters source registration or promotes an index.
"""
import argparse, gzip, hashlib, json, subprocess, sys, tempfile, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"tools/alignment"), str(ROOT/"tools/alignment_v3"),
               str(ROOT/"tools/tasmi_bench"), str(ROOT/"tools/index_qa")]
from common import ffprobe_duration_ms, load_index, load_text, surah_slice
from basmala_local import cut
FILES = {
33: ("033-mp-3_20240313", "محمد عمر الجنايني رواية قالون سورة 033  الأحزاب  mp3.mp3",
     "27d494142182ead16578eb1bc2ca3a12"),
55: ("055-mp-3_20240313", "محمد عمر الجنايني رواية قالون سورة 055  الرحمن  mp3.mp3",
     "fa197638cfcfbc4828bf2f8cc25af4ce")}
def download(url, dst):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=300) as r:
        data=r.read()
    dst.write_bytes(data)
    return data
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ctc", action="store_true")
    ap.add_argument("--kurdi-neighborhood", action="store_true")
    ap.add_argument("--omit-basmala", nargs="*", type=int, default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True)
    a=ap.parse_args()
    out=ROOT/a.out
    if out.parent!=ROOT/"ops/out" or out.suffix!=".json":
        ap.error("output must be in ops/out")
    from pywhispercpp.model import Model
    model=Model(a.model,n_threads=2,language="ar",print_progress=False,print_realtime=False)
    result={"readOnly":True,"productionChanged":False,"canonicalTextChanged":False,
            "tinyModelSha256":hashlib.sha256(Path(a.model).read_bytes()).hexdigest(),"surahs":[]}
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)
        if a.kurdi_neighborhood:
            url="https://server6.mp3quran.net/kurdi/016.mp3"
            src=work/"kurdi016.mp3"
            raw=download(url,src)
            sha=hashlib.sha256(raw).hexdigest()
            if sha!="185935fe61b370176c417ab580dd9db86b45651d1b12656c81ec520233bb87a7":
                raise ValueError("Kurdi source changed")
            index_raw=download("https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/timings-staging/hafs/kurdi.e7f53af3.jz",work/"index.jz")
            if hashlib.sha256(index_raw).hexdigest()!="e7f53af3fe655404b0735b67da381355d74d334e8eddafcc4ac9c3678cb9d627":
                raise ValueError("Kurdi staged index changed")
            idx=json.loads(gzip.decompress(index_raw))
            neighborhood=[e for e in idx["entries"] if e["ayahId"] in [f"16:{i}" for i in range(81,86)]]
            row={"surah":16,"url":url,"sourceSha256":sha,"native":[],"timings":neighborhood}
            result["surahs"].append(row)
            left=next(e for e in neighborhood if e["ayahId"]=="16:81")
            right=next(e for e in neighborhood if e["ayahId"]=="16:85")
            windows=[(left["startMs"],right["endMs"]-left["startMs"]),
                     (max(left["startMs"],left["endMs"]-15000),45000)]
            for st,dt in windows:
                wav=str(work/"native.wav")
                cut(str(src),st,dt,wav)
                heard=" ".join(seg.text for seg in model.transcribe(wav))
                row["native"].append({"startMs":st,"durationMs":dt,"heard":heard})
                print(json.dumps(row["native"][-1],ensure_ascii=False),flush=True)
            out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            return
        for s,(ident,name,expected_md5) in FILES.items():
            metadata=json.loads(download("https://archive.org/metadata/"+ident,work/"meta.json"))
            src=work/(str(s)+".mp3")
            url="https://archive.org/download/"+ident+"/"+urllib.parse.quote(name)
            raw=download(url,src)
            md5=hashlib.md5(raw).hexdigest()
            if md5!=expected_md5:
                raise ValueError("source differs from measured publisher MD5")
            duration=ffprobe_duration_ms(str(src))
            row={"surah":s,"url":url,"item":ident,"publisherMetadata":metadata["metadata"],
                 "sourceBytes":len(raw),"sourceMd5":md5,
                 "sourceSha256":hashlib.sha256(raw).hexdigest(),"totalMs":duration,"native":[]}
            result["surahs"].append(row)
            windows=[(0,6000),(0,15000),(max(0,duration-80000),80000)]
            for st,dt in windows:
                wav=str(work/"native.wav")
                cut(str(src),st,dt,wav)
                heard=" ".join(seg.text for seg in model.transcribe(wav))
                row["native"].append({"startMs":st,"durationMs":dt,"heard":heard})
                print(json.dumps({"surah":s,"startMs":st,"durationMs":dt,"heard":heard},ensure_ascii=False),flush=True)
            out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            if a.ctc:
                import ctc_seg as C
                aligned=C.run_surah(str(src),s,"qalun",quran_model=True,
                                    omit_basmala=s in a.omit_basmala)
                row["alignment"]=aligned
                low=[e["ayahIdx"]+1 for e in aligned["entries"]
                     if e["startMs"] is None or e["conf"]<.45]
                row["lowOrMissing"]=low
                row["strictComplete"]=not low and not aligned["issues"]
                for ai in ([42,68,73] if s==33 else [64,78]):
                    e=aligned["entries"][ai-1]
                    if e["startMs"] is not None:
                        dt=min(30000,max(6000,e["endMs"]-e["startMs"]+2500))
                        wav=str(work/"native.wav")
                        cut(str(src),e["startMs"],dt,wav)
                        heard=" ".join(seg.text for seg in model.transcribe(wav))
                        row["native"].append({"ayahId":f"{s}:{ai}","startMs":e["startMs"],
                                              "durationMs":dt,"heard":heard})
                out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
                print(json.dumps({"surah":s,"lowOrMissing":low,"issues":aligned["issues"],
                                  "strictComplete":row["strictComplete"]},ensure_ascii=False),flush=True)
if __name__=="__main__":
    main()
