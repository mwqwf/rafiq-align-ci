import json,sys
base,bsha,donor,dsha,surahs,tag=sys.argv[1:7]
print(json.dumps({"action":"tool","tool":"index_qa/graft_surahs.py","args":["--base",base,"--base-sha",bsha,"--donor",donor,"--donor-sha",dsha,"--surahs",surahs,"--reason","pC3 heal "+tag+": زرع سور اجتازت السماع من وضع heard","--yes"]},ensure_ascii=False))
