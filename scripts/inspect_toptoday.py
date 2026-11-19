#!/usr/bin/env python3
"""Inspect the exact public TopToday manifest and first catalog to establish
which source identifiers and poster routes are actually supported.
Read-only diagnostic, never prints credentials or untrusted response bodies.
"""
import json
import urllib.parse
import urllib.request
import urllib.error

BASE = ("https://toptoday.llamayu.com/"
        "backdropTags=false%7CbackdropLogos=false%7CbackdropRanked=false%7C"
        "backdropLanguage=null%7CbackdropTextlessArtwork=false%7C"
        "posterTags=true%7CposterLogos=true%7CposterRanked=true%7C"
        "posterLanguage=en%7CtextlessArtwork=true%7CposterShape=portrait%7C"
        "digitalOnly=false%7ClistLang=en")
def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={'User-Agent':'NuvioN1/1.0'}), timeout=15) as res:
        if res.geturl().split('/')[2].lower() != "toptoday.llamayu.com":
            raise ValueError("Redirect outside TopToday is not allowed")
        return json.loads(res.read(600000))

try:
    manifest=fetch(BASE+"/manifest.json")
    print("SOURCE_MANIFEST",json.dumps({
      k:manifest.get(k) for k in ("id","name","version","types","resources","catalogs")
    },ensure_ascii=False))
    for cat in manifest.get("catalogs", [])[:4]:
        t, id = cat["type"],cat["id"]
        url=BASE+"/catalog/"+urllib.parse.quote(t,safe="")+"/"+urllib.parse.quote(id,safe="")+".json"
        try:
            data=fetch(url)
            metas=data.get("metas", [])
            samples=[{k:meta.get(k) for k in ("id","type","name","poster","background")}
                    for meta in metas[:3]]
            print("CATALOG",json.dumps({"id":id,"type":t,"count":len(metas),"samples":samples},ensure_ascii=False))
            for meta in metas[:2]:
                sample_url = meta.get("poster", "")
                if sample_url.startswith("https://toptoday.llamayu.com/poster/"):
                    try:
                        request = urllib.request.Request(sample_url,headers={'User-Agent':'NuvioN1/1.0'})
                        with urllib.request.urlopen(request,timeout=20) as response:
                            head = response.read(16)
                            print("ACTUAL_POSTER",json.dumps({"url":sample_url,"status":response.status,"image":head.startswith(b'\xff\xd8\xff'),"location":response.geturl(),"content_type":response.headers.get('Content-Type')}))
                    except Exception as e:
                        print("ACTUAL_POSTER_ERROR",type(e).__name__,str(e)[:120])
        except Exception as e:
            print("CATALOG_ERROR",id,type(e).__name__,str(e)[:120])
except Exception as e:
    print("SOURCE_ERROR",type(e).__name__,str(e)[:180])

# Verify the exact renderer also accepts arbitrary metadata IDs without a
# TopToday worldwide-ranking entry and without a fabricated title badge.
for kind,tmdb_id in (("series",84773),("movie",1368337)):
    url=("https://toptoday.llamayu.com/poster/"+str(tmdb_id)+".jpg"+
         "?type="+kind+"&tag=none&rank=none&lang=en&logos=1")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url,headers={'User-Agent':'NuvioN1/1.0'}),timeout=20) as response:
            head=response.read(16)
            print("ARTWORK_SOURCE",json.dumps({
                "tmdb_id":tmdb_id,"media_type":kind,"status":response.status,
                "content_type":response.headers.get("Content-Type"),
                "jpeg_signature":head.startswith(b'\xff\xd8\xff'),
                "response_host":urllib.parse.urlsplit(response.geturl()).hostname,
            }))
    except Exception as e:
        print("ARTWORK_SOURCE_ERROR",tmdb_id,type(e).__name__,str(e)[:140])
