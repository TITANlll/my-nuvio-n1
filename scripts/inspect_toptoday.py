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
        "posterLanguage=en%7CtextlessArtwork=false%7CposterShape=portrait%7C"
        "digitalOnly=true%7ClistLang=en")
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
        except Exception as e:
            print("CATALOG_ERROR",id,type(e).__name__,str(e)[:120])
except Exception as e:
    print("SOURCE_ERROR",type(e).__name__,str(e)[:180])
