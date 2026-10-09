#!/bin/bash
# hb.sh name riw/id urltemplate surahs shards reason
echo "hb_$1" "$(python3 -c "
import json,sys
n,k,u,s,sh,r=sys.argv[1:]
riw=k.split('/')[0]
print(json.dumps({'action':'dispatch','workflow':'heard_batch.yml','inputs':{'parent':'timings/'+k+'.jz','url_template':u,'riwaya':riw,'surahs':s,'shards':sh,'reason':r}},ensure_ascii=False))" "$@")"
