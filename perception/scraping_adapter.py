#!/usr/bin/env python3
from __future__ import annotations
from typing import List,Dict,Optional,Any
from dataclasses import dataclass,field
import time as _t
_sl=None
def _ck():
    global _sl
    if _sl is None:
        try:
            from scrapling.fetchers import Fetcher;_sl=True
        except: _sl=False
    return _sl
@dataclass
class ScrapedPage:
    url:str;title:str="";text:str="";html:str="";mode:str="http"
    css_selectors:Dict=field(default_factory=dict);links:List=field(default_factory=list)
    metadata:Dict=field(default_factory=dict);error:Optional[str]=None;elapsed_ms:float=0.0
@dataclass
class SpiderItem:
    url:str;data:Dict;depth:int;scraped_at:str
def _pws(s):
    p=s.split(",");return(p[0].strip(),p[1].strip() if len(p)>1 else "visible")
def _pp(page,url,mode,sel,start):
    title=""
    try: title=page.css("title::text").get() or ""
    except: pass
    rt=page.css((sel+"::text") if sel else "body ::text").getall()
    text=" ".join(t.strip() for t in rt if t.strip())
    links=[]
    try: links=[l for l in page.css("a::attr(href)").getall() if l and l.startswith("http")]
    except: pass
    return ScrapedPage(url=url,title=title,text=text,mode=mode,links=links,elapsed_ms=(_t.time()-start)*1000)
def scrape_url(url,mode="http",css_selector=None,impersonate="chrome",
               wait_selector=None,solve_cloudflare=False,timeout_ms=30000,
               disable_resources=False,network_idle=False,proxy=None):
    start=_t.time()
    if not _ck(): return ScrapedPage(url=url,mode=mode,error="scrapling not installed: pip install scrapling[all]")
    try:
        if mode=="http":
            from scrapling.fetchers import Fetcher as F
            kw={"timeout":timeout_ms//1000}
            if proxy: kw["proxy"]=proxy
            if impersonate: kw["impersonate"]=impersonate
            return _pp(F.get(url,**kw),url,mode,css_selector,start)
        elif mode=="dynamic":
            from scrapling.fetchers import DynamicFetcher as DF
            kw={"headless":True,"timeout":timeout_ms}
            if css_selector: kw["css_selector"]=css_selector
            if impersonate: kw["impersonate"]=impersonate
            if wait_selector: kw["wait_selector"]=_pws(wait_selector)
            if disable_resources: kw["disable_resources"]=True
            if network_idle: kw["network_idle"]=True
            if proxy: kw["proxy"]=proxy
            return _pp(DF.fetch(url,**kw),url,mode,css_selector,start)
        elif mode=="stealth":
            from scrapling.fetchers import StealthyFetcher as SF
            kw={"headless":True,"timeout":timeout_ms}
            if css_selector: kw["css_selector"]=css_selector
            if impersonate: kw["impersonate"]=impersonate
            if wait_selector: kw["wait_selector"]=_pws(wait_selector)
            if solve_cloudflare: kw["solve_cloudflare"]=True
            kw["block_webrtc"]=True;kw["hide_canvas"]=True
            if disable_resources: kw["disable_resources"]=True
            if network_idle: kw["network_idle"]=True
            if proxy: kw["proxy"]=proxy
            return _pp(SF.fetch(url,**kw),url,mode,css_selector,start)
        else: return ScrapedPage(url=url,mode=mode,error="Unknown mode:"+mode)
    except Exception as e:
        return ScrapedPage(url=url,mode=mode,error=str(e),elapsed_ms=(_t.time()-start)*1000)
def scrape(url,mode="http",**kw): return scrape_url(url,mode=mode,**kw)
def spider_crawl(start_urls,max_pages=50,max_depth=3,delay=1.0,output_file=None,css_selector=None):
    if not _ck(): return []
    from scrapling.fetchers import FetcherSession as FS;import json
    visited,results,queue=set(),[],[(u,0) for u in start_urls]
    with FS(impersonate="chrome") as s:
        while queue and len(results)<max_pages:
            url,depth=queue.pop(0)
            if url in visited or depth>max_depth: continue
            visited.add(url)
            try:
                page=s.get(url);_t.sleep(delay)
                if css_selector:
                    for el in page.css(css_selector).getall():
                        results.append(SpiderItem(url=url,data={"html":el,"text":page.css(css_selector+"::text").get()},depth=depth,scraped_at=_t.strftime("%Y-%m-%d %H:%M:%S")))
                else:
                    txt=" ".join(p.strip() for p in page.css("p::text,h1::text,h2::text").getall() if p.strip())
                    results.append(SpiderItem(url=url,data={"text":txt},depth=depth,scraped_at=_t.strftime("%Y-%m-%d %H:%M:%S")))
                for link in [l for l in page.css("a::attr(href)").getall() if l and l.startswith("http") and l not in visited][:5]:
                    queue.append((link,depth+1))
            except Exception as e: print("[Spider] "+url+": "+str(e))
    if output_file:
        with open(output_file,"w",encoding="utf-8") as f:
            json.dump([{"url":i.url,"data":i.data,"depth":i.depth} for i in results],f,ensure_ascii=False,indent=2)
        print("[Spider] Saved "+str(len(results))+" to "+output_file)
    return results
def save_to_intents(topic,content,url="",source="scraping",priority=3):
    try:
        from judgment.user_model import save_perception_result
        return save_perception_result(source=source,topic=topic,content=content[:2000],url=url,priority=priority)
    except: return None
__all__=["ScrapedPage","SpiderItem","scrape_url","scrape","spider_crawl","save_to_intents"]
