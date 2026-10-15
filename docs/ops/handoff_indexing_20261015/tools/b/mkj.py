import json,sys
print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":sys.argv[1],"url_template":"https://archive.org/download/Kamal-Almaroush-Qalon/{s:03d}.mp3","riwaya":"qalun","surahs":sys.argv[2],"mode":"dualfix","base_key":"timings-staging/qalun/maroush_qalun.3d4e8af3.jz","reason":"pC3: استكشاف س"+sys.argv[2]+" فوق الحيّ d7c9b443"}},ensure_ascii=False))
