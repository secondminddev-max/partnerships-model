#!/usr/bin/env python3
"""Integrity checks for the Defence Space Partnership Model.

Run from public/partnerships/:  python3 checks.py
Every fidelity defect found in this product to date would have been caught by
one of these checks. Run it after ANY edit, before committing.
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
fails = []

def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    if not ok:
        fails.append(name)

def js_blocks(html):
    return re.findall(r"<script(?![^>]*application/json)[^>]*>(.*?)</script>", html, re.S)

def json_block(html, bid):
    m = re.search(r'id="%s">(.*?)</script>' % bid, html, re.S)
    return json.loads(m.group(1)) if m else None

def node_ok(src):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(src); path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()[:200]
    finally:
        os.unlink(path)

print("== syntax ==")
pages = {}
for f in ("command-brief.html", "model.html", "index.html", "placemats.html", "briefing-pack.html"):
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        check(f + " exists", False); continue
    pages[f] = open(p, encoding="utf-8").read()
    ok, err = node_ok("\n;\n".join(js_blocks(pages[f]))) if js_blocks(pages[f]) else (True, "")
    check(f + " JS", ok, err)

cb = pages["command-brief.html"]

print("== data ==")
BD = json_block(cb, "briefing-data"); check("briefing-data parses", BD is not None)
VEH = json_block(cb, "cb-vehicles");  check("cb-vehicles parses", VEH is not None)
for bid in ("model-data", "vehicles-data", "evidence-data"):
    check("model.html " + bid + " parses", json_block(pages["model.html"], bid) is not None)

print("== photos ==")
bad = []
for k, p in BD["partners"].items():
    for x in (p.get("leadership") or {}).get("profiles", []):
        if x.get("photo") and not os.path.exists(os.path.join(ROOT, x["photo"])):
            bad.append(x["photo"])
check("all photo refs resolve", not bad, ",".join(bad))

print("== cross-structure dates (the SoI class of bug) ==")
def dates(s): return set(re.findall(r"\b20\d{2}-\d{2}(?:-\d{2})?\b", str(s)))
mismatch = []
for pk, p in BD["partners"].items():
    reg = {v["name"]: v for v in VEH.get(pk, [])}
    for e in (p.get("calendar") or {}).get("events", []):
        for key in ("Statement of Intent", "SouthPAN", "Catalyst", "GBSI"):
            if key in e["title"]:
                for rn, rv in reg.items():
                    if key in rn:
                        # same-instrument test: require real name overlap, not a shared
                        # stock phrase — "Statement of Intent" alone matches four
                        # different US instruments
                        tok = lambda s: {w for w in re.findall(r"[A-Za-z]{4,}", s.lower())}                                         - {"statement","intent","joint","space","australia","australian","united","states","zealand","cooperation"}
                        if len(tok(e["title"]) & tok(rn)) < 2:
                            continue
                        cd = dates(e.get("when", "")) | dates(e.get("note", ""))
                        rd = dates(rv.get("signed", ""))
                        same = any(r in c or c in r for r in rd for c in cd)
                        if rd and cd and not same:
                            mismatch.append(f"{pk}:{key}")
check("no calendar/register date splits on shared instruments", not mismatch, ",".join(mismatch))

print("== renders: placemat/minute/brief x all partners ==")
js = js_blocks(cb)[0]
def fn(name):
    i = js.index("function " + name); d = 0; k = js.index("{", i)
    for x in range(k, len(js)):
        if js[x] == "{": d += 1
        elif js[x] == "}":
            d -= 1
            if d == 0: return js[i:x + 1]
harness = (
    "const BD=" + re.search(r'id="briefing-data">(.*?)</script>', cb, re.S).group(1) + ";"
    "const VEH=" + re.search(r'id="cb-vehicles">(.*?)</script>', cb, re.S).group(1) + ";"
    + re.search(r"var PARTNER_SIDE=\{.*?\};", cb, re.S).group(0)
    + re.search(r"var FLAGDEF\s*=\s*\{.*?\n\};?", cb, re.S).group(0) + ";"
    + js[js.index("function calWindow"):js.index("function initials")]
    + 'let CURKEY="nz";function partnerVehicles(k){return (VEH[k]||[]).slice();}'
    + 'const esc=s=>String(s==null?"":s);function today(){return "run";}'
    + 'function scrubEv(s){return String(s==null?"":s);}function cls(l){return String(l||"");}'
    + 'function selectedOpps(){const p=BD.partners[CURKEY];return (p.opportunities||[]).map(o=>({id:o.id,title:o.title}));}'
    + js[js.index("var CB_LAYERS"):js.index("function cbMarks")]
    + fn("nzFern")
    + fn("buildPlacemat") + fn("buildMinute") + fn("buildBrief")
    + '''
let bad=0;
for(const k of Object.keys(BD.partners)){ CURKEY=k; const p=BD.partners[k];
  for(const f of [buildPlacemat,buildMinute,buildBrief]){
    try{ const o=f(p);
      if(/undefined/.test(o)) {bad++; console.error("UNDEF "+k);}
      const a=(o.match(/<div/g)||[]).length,b=(o.match(/<\\/div>/g)||[]).length;
      if(a!==b){bad++; console.error("DIVS "+k);}
    }catch(e){ bad++; console.error("THREW "+k+" "+e.message); } } }
console.log("BAD="+bad);
''')
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(harness); hp = f.name
r = subprocess.run(["node", hp], capture_output=True, text=True); os.unlink(hp)
check("all partner documents render clean", "BAD=0" in r.stdout, (r.stdout + r.stderr).strip()[:200])

print("== NZ verdict invariant ==")
nz_reg = VEH.get("nz", [])
nz_bilat_space = [v for v in nz_reg if v.get("channel") == "bilateral_def"
                  and v.get("status") == "In force" and v.get("space_relevance") == "Direct"]
check("NZ holds zero in-force bilateral-defence space instruments (matches BLUF)",
      len(nz_bilat_space) == 0, str([v["name"][:40] for v in nz_bilat_space]))


print("== worked-partner completeness ==")
inc = []
for k, p in BD["partners"].items():
    # 'domestic' is Australia's own Defence x Industry view, not a bilateral
    # partner — the minute/LOE pattern deliberately does not apply to it
    if p.get("bluf") and k != "domestic":
        if not (p.get("current_state") and p.get("future_state")
                and len(p.get("opportunities") or []) >= 3
                and len((p.get("loe") or {}).get("lines", [])) == 3
                and p.get("minute_defaults")):
            inc.append(k)
check("every partner with a BLUF is fully staffed", not inc, ",".join(inc))

print("== calendar url hygiene ==")
bad_u = [f"{k}:{e['title'][:30]}" for k, p in BD["partners"].items()
         for e in (p.get("calendar") or {}).get("events", [])
         if e.get("url") and not str(e["url"]).startswith("https://")]
check("all calendar source urls are https", not bad_u, ",".join(bad_u[:4]))

print("== cover consistency ==")
cov = pages.get("index.html", "")
nveh = sum(len(v) for v in VEH.values())
check("cover artefact figure matches register", f"<b>{nveh}</b>" in cov, f"register={nveh}")
check("cover partner figure matches data", f"<b>{len(BD['partners'])}</b>" in cov, f"partners={len(BD['partners'])}")
# cover verdict strip was removed from the landing page by design; only
# validate it against the data if it is still present
mv = re.search(r'data-verdicts="([^"]+)"', cov)
if mv:
    claimed = dict(x.split(":") for x in mv.group(1).split(";"))
    derived = {}
    for k in claimed:
        vs = VEH.get(k, [])
        full = any(v.get("channel") == "bilateral_def" and v.get("status") == "In force"
                   and v.get("space_relevance") == "Direct" for v in vs)
        derived[k] = "full" if full else "none"
    wrong = [k for k in claimed if claimed[k] != derived[k]]
    check("cover verdict strip matches derived verdicts", not wrong, ",".join(wrong))


print("== css structure (catches floating declarations) ==")
def css_lint(css):
    import re as _re
    css=_re.sub(r"/\*.*?\*/","",css,flags=_re.S)
    depth=0; buf=""; orphans=0
    for ch in css:
        if ch=="{": depth+=1; buf=""
        elif ch=="}": depth-=1; buf=""
        elif ch==";" and depth==0:
            frag=buf.strip()
            if ":" in frag and not frag.startswith("@"): orphans+=1
            buf=""
        else: buf+=ch
    return orphans
css_bad=[]
for fn, content in pages.items():
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", content, re.S):
        n=css_lint(m.group(1))
        if n: css_bad.append(f"{fn}:{n}")
check("no floating CSS declarations (root-wrapper bug class)", not css_bad, ",".join(css_bad))


print("== register source-url well-formedness ==")
malformed = []
for pk, vs in VEH.items():
    for v in vs:
        u = str(v.get("source_ref", "")).strip()
        if not u: continue
        for part in re.split(r"[;\s]+", u):
            if part.startswith("http") and not re.match(r"https?://[\w.-]+\.[a-z]{2,}(/|$)", part):
                malformed.append(v.get("vehicle_id", "?"))
check("all register source urls are well-formed", not malformed, ",".join(malformed[:5]))

print("== industry & supply-chain render (the promoted domestic tab) ==")
# The supply-chain model is the domestic partner's headline. Render it in full
# through a permissive fake-DOM so the whole script bootstraps, then assert every
# supply-chain partner produces balanced, complete output — this is the render the
# hand-picked placemat/minute/brief harness above does NOT exercise.
_blocks = {m.group(1): m.group(2) for m in
           re.finditer(r'<script[^>]*application/json[^>]*id="([^"]+)">(.*?)</script>', cb, re.S)}
_stub = ('var JB=' + json.dumps(_blocks) + ';'
    'function mk(id){return new Proxy(function(){},{get:(t,k)=>{'
    'if(k==="textContent"||k==="innerHTML")return (id&&JB[id])||"";'
    'if(k==="classList")return {add(){},remove(){},toggle(){},contains(){return false;}};'
    'if(k==="style")return new Proxy({},{get:()=>"",set:()=>true});'
    'if(k==="getContext")return ()=>mk();if(k==="dataset")return {};'
    'if(k==="children"||k==="childNodes")return [];if(k==="getAttribute")return ()=>null;'
    'return (typeof k==="symbol")?undefined:mk();},apply:()=>mk(),set:()=>true});}'
    'globalThis.document=new Proxy({},{get:(t,k)=>{'
    'if(k==="getElementById")return (id)=>mk(id);'
    'if(k==="querySelector")return (s)=>{var m=/#([\\w-]+)/.exec(s||"");return mk(m&&m[1]);};'
    'if(k==="createElement"||k==="createElementNS")return ()=>mk();'
    'if(k==="querySelectorAll"||k==="getElementsByClassName")return ()=>[];'
    'if(k==="addEventListener"||k==="removeEventListener")return ()=>{};return mk();}});'
    'var W={};'   # real store: the page exposes IIFE functions via window.x= — keep and re-expose them
    'globalThis.window=new Proxy(W,{set:(t,k,v)=>{t[k]=v;return true;},get:(t,k)=>{'
    'if(k in t)return t[k];'
    'if(k==="matchMedia")return ()=>({matches:false,addEventListener(){},removeEventListener(){}});'
    'if(k==="addEventListener"||k==="removeEventListener"||k==="requestAnimationFrame")return ()=>{};'
    'if(k==="location")return {hash:"",search:"",href:""};'
    'return undefined;}});'   # browser semantics: unset window props are undefined, never fake elements
    'globalThis.location={hash:"",search:"",href:""};globalThis.navigator={userAgent:"node"};'
    'globalThis.L=undefined;globalThis.requestAnimationFrame=()=>{};globalThis.setTimeout=()=>{};'
    'globalThis.getComputedStyle=()=>({getPropertyValue:()=>""});')
_render = ('\nObject.keys(W).forEach(function(k){ if(!(k in globalThis)) globalThis[k]=W[k]; });'
    'var BD2=' + _blocks["briefing-data"] + ';var bad=0;'
    'Object.keys(BD2.partners).forEach(function(k){var p=BD2.partners[k];'
    'var f=p.factsheet||{};if(!(f.supply_chain&&f.supply_chain.length))return;'
    'try{var o=renderIndustryTab(p);'
    'var a=(o.match(/<div/g)||[]).length,b=(o.match(/<\\/div>/g)||[]).length;'
    'if(a!==b){bad++;console.error("DIVS "+k+" "+a+"/"+b);}'
    'if(/undefined/.test(o)){bad++;console.error("UNDEF "+k);}'
    'if(!/ind-hero-title/.test(o)){bad++;console.error("NOHERO "+k);}'
    'var comp=(p.components||{});var n=(comp.satellite||[]).length+(comp.ground||[]).length;'
    'if(n&&(o.match(/class="subrow"/g)||[]).length!==n){bad++;console.error("SUBS "+k);}'
    'if(p.arch&&!/ORBITAL DOMAIN/.test(o)){bad++;console.error("NOORB "+k);}'
    'if(n&&!/Component capability/.test(o)){bad++;console.error("NOCOMP "+k);}'
    'if(n&&!/class="ex-part"/.test(o)){bad++;console.error("NOPARTS "+k);}'
    'var fs=renderFactsheet(p);if(!/openTab\\(.industry.\\)/.test(fs)){bad++;console.error("NOJUMP "+k);}'
    '}catch(e){bad++;console.error("THREW "+k+" "+e.message);}});'
    'console.log("IBAD="+bad);')
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(_stub + js_blocks(cb)[0] + _render); ip = f.name
ir = subprocess.run(["node", ip], capture_output=True, text=True); os.unlink(ip)
check("industry & supply-chain tab renders complete for every supply-chain partner",
      "IBAD=0" in ir.stdout, (ir.stdout + ir.stderr).strip()[:200])

print()
if fails:
    print("FAILURES:", ", ".join(fails)); sys.exit(1)
print("ALL CHECKS PASSED")
