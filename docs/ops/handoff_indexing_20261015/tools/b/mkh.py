import json,sys
par,url,riw,sur,rw,tag=sys.argv[1:7]
print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":par,"url_template":url,"riwaya":riw,"surahs":sur,"mode":"heard","rewindow":rw,"reason":"pC3 heal "+tag+": heard لسور بقايا مقيسة (heard_pub على الحيّ)"}},ensure_ascii=False))
