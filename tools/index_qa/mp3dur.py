#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مدّةُ ملفّ MP3 بعدّ إطاراته — بايثونَ خالصاً بلا `ffprobe`.

    python tools/index_qa/mp3dur.py work/024.mp3

**لماذا؟** لأنّ «صوتٌ معطوب» حكمٌ **يُقاس ولا يُكتب من الذاكرة**، ولا `ffmpeg`
ولا `ffprobe` على جهاز المالك. وقع مقيساً 2026-09-06: كُتب أن صوت
`akri_qalun/107` معطوب، فإذا هو **23.41ث · 896 إطاراً · 192ك.ب/ث** سليمٌ تامّ،
والعطبُ في الفهرس لا في الصوت (‏مدخلان مضلِّلان من سبعة).

⛔ **وللبترِ المصدريّ مقياسٌ أرخصُ من هذا:** `HEAD` على الملفّ وجارتيه وقسمةُ
الحجم على معدّل البِتّ — فرقُ الضعف يظهر بلا تنزيل بايتٍ واحد. وهذا العدّاد
لِما يلزم فيه الدقّة (‏الملفّات القصيرة، حيث ترويسةُ ID3 تُفسد التقدير).
"""
import sys, struct
BR = {1:[0,32,64,96,128,160,192,224,256,288,320,352,384,416,448],
      2:[0,32,48,56,64,80,96,112,128,160,192,224,256,320,384],
      3:[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]}
BR2= {1:[0,32,48,56,64,80,96,112,128,144,160,176,192,224,256],
      2:[0,8,16,24,32,40,48,56,64,80,96,112,128,144,160]}
SR = {3:[44100,48000,32000], 2:[22050,24000,16000], 0:[11025,12000,8000]}
def dur(path):
    d = open(path,'rb').read()
    i = 0
    if d[:3]==b'ID3':
        sz = (d[6]&0x7f)<<21 | (d[7]&0x7f)<<14 | (d[8]&0x7f)<<7 | (d[9]&0x7f)
        i = 10+sz
    total=0.0; frames=0; info=None
    while i < len(d)-4:
        if d[i]==0xFF and (d[i+1]&0xE0)==0xE0:
            ver=(d[i+1]>>3)&3; layer=(d[i+1]>>1)&3; bri=(d[i+2]>>4)&0xF; sri=(d[i+2]>>2)&3; pad=(d[i+2]>>1)&1
            if ver==1 or layer==0 or bri in (0,15) or sri==3: i+=1; continue
            lay = 4-layer
            br = (BR if ver==3 else BR2)[lay if ver==3 else (1 if lay==1 else 2)][bri]*1000
            sr = SR[ver][sri]
            if lay==1: flen = (12*br//sr + pad)*4; spf=384
            else:
                spf = 1152 if (lay==2 or ver==3) else 576
                flen = (spf//8*br)//sr + pad
            if flen<=0: i+=1; continue
            total += spf/sr; frames+=1
            if info is None: info=(ver,lay,br//1000,sr)
            i += flen
        else: i+=1
    return total, frames, info, len(d)
# ⛔ الحارسُ الوحيدُ في هذا الملفّ: **الحلقةُ تحت `__main__` لا في متنه**.
#    كانت في المتن فكان `import mp3dur` من أداةٍ أخرى **يقرأ `sys.argv` تلك
#    الأداة ويحاول فتحَ خياراتها ملفّاتٍ** — سقط مقيساً 2026-09-08:
#    `probe_new_reciter --self-test` انهار بـ`FileNotFoundError: '--self-test'`.
#    والسلوكُ سطرَ أمرٍ لم يتغيّر حرفاً.
if __name__ == "__main__":
    for p in sys.argv[1:]:
        t,f,inf,n = dur(p)
        print(f"{p}: {t:.2f}s frames={f} info={inf} bytes={n}")
