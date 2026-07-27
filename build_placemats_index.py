#!/usr/bin/env python3
"""Regenerate placemats.html — the index of the three carry-in documents per partner.

Reads the live briefing-data block plus FLAGDEF/RAIL_PENDING out of command-brief.html,
so partner names, regions and flag bands cannot drift from the brief. Re-run this
whenever partners are added or their leadership/calendar depth changes:

    python3 build_placemats_index.py && python3 checks.py
"""
import re, json, html, pathlib

DIR = pathlib.Path('/Users/secondmind/claudecodetest/public/partnerships')
src = (DIR / 'command-brief.html').read_text(encoding='utf-8')
BD = json.loads(re.search(r'id="briefing-data"[^>]*>(.*?)</script>', src, re.S).group(1))
P = BD['partners']
as_at = BD['meta']['as_at']

# --- pull display names / regions / flag bands straight out of the brief's JS ---
flagblk = re.search(r'var FLAGDEF\s*=\s*\{(.*?)\n\};', src, re.S).group(1)
FLAGDEF = {}
for k, nm, reg, band in re.findall(
        r'(\w+)\s*:\s*\{name:"([^"]*)",\s*reg:"([^"]*)",\s*band:"([^"]*)"\}', flagblk):
    FLAGDEF[k] = {'name': nm, 'reg': reg, 'band': band}

railblk = re.search(r'var RAIL_PENDING\s*=\s*\[(.*?)\];', src, re.S).group(1)
RAIL = dict(re.findall(r'\["(\w+)","([^"]*)"\]', railblk))

MULTI_BAND = 'linear-gradient(120deg,#c89b5a,#8d6a35 55%,#2b3d57)'

ANALYSIS_DEPTH = {'quad', 'aukus', 'cspo', 'pacific', 'multilateral'}


def staffed(k, v):
    """Every partner now carries leadership + calendar; the multilateral groupings
    remain analysis-depth on scoring, which is what the chip marks."""
    if k in ANALYSIS_DEPTH:
        return False
    return bool((v.get('leadership') or {}).get('profiles')) and bool((v.get('calendar') or {}).get('events'))

def disp(k, v):
    if k in FLAGDEF:
        return FLAGDEF[k]['name']
    if k in RAIL:
        return RAIL[k]
    return v.get('name', k)

def region(k, v):
    if k in FLAGDEF:
        return FLAGDEF[k]['reg']
    return v.get('region', '') or 'Multilateral grouping'

def band(k):
    return FLAGDEF[k]['band'] if k in FLAGDEF else MULTI_BAND

order = list(P.keys())
MULTIS = ('quad', 'aukus', 'cspo', 'pacific', 'multilateral')
groups = [
    ('Nations', [k for k in order if k not in MULTIS and k != 'domestic']),
    ('Australia’s own base', [k for k in order if k == 'domestic']),
    ('Multilateral groupings', [k for k in order if k in MULTIS]),
]
seen = {k for _, ks in groups for k in ks}
leftover = [k for k in order if k not in seen]
if leftover:
    groups.append(('Other', leftover))

e = html.escape
cards = []
for title, keys in groups:
    if not keys:
        continue
    cards.append(f'<h2 class="grp">{e(title)}</h2>\n<div class="grid">')
    for k in keys:
        v = P[k]
        one = ' '.join((v.get('one_line') or '').split())
        if len(one) > 124:
            one = one[:121].rsplit(' ', 1)[0] + '…'
        depth = '' if staffed(k, v) else '<span class="depth" title="Carried at analysis depth on scoring">analysis depth</span>'
        cards.append(f'''  <div class="card">
    <span class="flag" style="background:{band(k)}" aria-hidden="true"></span>
    <div class="ch"><span class="nm">{e(disp(k, v))}</span>{depth}</div>
    <div class="reg">{e(region(k, v))}</div>
    <p class="one">{e(one)}</p>
    <div class="docs">
      <a href="command-brief.html?p={e(k)}&amp;doc=placemat#placemat">Placemat</a>
      <a href="command-brief.html?p={e(k)}&amp;doc=minute#generate">Minute</a>
      <a href="command-brief.html?p={e(k)}&amp;doc=brief#generate">In-brief</a>
    </div>
  </div>''')
    cards.append('</div>')

body = '\n'.join(cards)
n = len(P)

out = f'''<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Partner placemats, minutes and visit in-briefs — one print-ready set per partner. UNOFFICIAL, open-source only.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Crect width=%2732%27 height=%2732%27 rx=%276%27 fill=%27%230e1826%27/%3E%3Ctext x=%2716%27 y=%2721%27 font-family=%27Georgia%27 font-size=%2713%27 font-weight=%27600%27 fill=%27%23c89b5a%27 text-anchor=%27middle%27%3EDS%3C/text%3E%3C/svg%3E">
<title>Partner placemats, minutes &amp; in-briefs — UNOFFICIAL</title>
<style>
:root{{
  --bg:#0e1826; --panel:#152336; --hair:rgba(214,222,235,.14);
  --ink:#e8ecf3; --ink2:#aab6c6; --muted:#768699;
  --accent:#c89b5a; --accent-ink:#e6c896;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
::selection{{background:rgba(200,155,90,.3);color:var(--ink)}}
html{{color-scheme:dark}}
body{{font-family:var(--sans);background:radial-gradient(1100px 500px at 50% -10%, #16283f 0%, transparent 60%),var(--bg);
  color:var(--ink);line-height:1.55;min-height:100vh;display:flex;flex-direction:column}}
.banner{{background:#fff;color:#000;text-align:center;font-size:11px;font-weight:700;
  letter-spacing:.16em;padding:6px 10px;text-transform:uppercase;border-bottom:2px solid #000}}
main{{width:100%;max-width:1120px;margin:0 auto;padding:clamp(36px,6vh,64px) 28px 56px;flex:1}}
.back{{display:inline-block;font-size:12px;color:var(--muted);text-decoration:none;margin-bottom:20px}}
.back:hover{{color:var(--ink2)}}
.kicker{{font-size:11px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-bottom:12px}}
h1{{font-family:var(--serif);font-weight:600;font-size:clamp(28px,4.4vw,40px);line-height:1.1}}
.stand{{max-width:72ch;margin:14px 0 0;color:var(--ink2);font-size:14.5px;line-height:1.65}}
.legend{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;margin:26px 0 0;
  padding:16px 0;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}}
.legend div{{font-size:12.5px;color:var(--ink2)}}
.legend b{{display:block;font-family:var(--serif);font-size:15px;color:var(--accent-ink);font-weight:600;margin-bottom:3px}}
h2.grp{{font-family:var(--serif);font-size:14px;font-weight:600;color:var(--accent);letter-spacing:.07em;
  text-transform:uppercase;margin:36px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--hair)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;align-items:stretch}}
.card{{position:relative;display:flex;flex-direction:column;background:linear-gradient(180deg,#182a41,var(--panel));
  border:1px solid var(--hair);border-radius:10px;padding:16px 16px 13px;overflow:hidden;transition:border-color .18s}}
.card:hover{{border-color:rgba(200,155,90,.5)}}
.flag{{position:absolute;inset:0 0 auto 0;height:3px;opacity:.85}}
.ch{{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}}
.nm{{font-family:var(--serif);font-size:17.5px;font-weight:600;color:var(--ink);line-height:1.25}}
.depth{{font-size:9px;letter-spacing:.11em;text-transform:uppercase;color:var(--muted);white-space:nowrap;
  border:1px solid var(--hair);border-radius:99px;padding:2px 7px}}
.reg{{font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin-top:5px}}
.one{{font-size:12.5px;color:var(--ink2);margin:9px 0 14px;line-height:1.5}}
.docs{{display:flex;gap:7px;flex-wrap:wrap;margin-top:auto}}
.docs a{{flex:1;min-width:86px;text-align:center;text-decoration:none;font-size:12px;color:var(--ink2);
  border:1px solid var(--hair);border-radius:7px;padding:7px 8px;transition:border-color .15s,color .15s,background .15s}}
.docs a:hover{{border-color:var(--accent);color:var(--ink);background:rgba(200,155,90,.09)}}
.docs a:focus-visible,.back:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
footer{{border-top:1px solid var(--hair);padding:18px 28px 26px;text-align:center;
  font-size:11.5px;color:var(--muted);max-width:1120px;margin:0 auto;width:100%}}
footer .lock{{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;margin-top:6px;color:#5d6b80}}
@media(max-width:560px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="banner">Unofficial — open-source evidence only — draft, pending custodian validation</div>
<main>
  <a class="back" href="index.html">&#8592; Partnership model</a>
  <div class="kicker">Print · carry-in documents</div>
  <h1>Partner placemats, minutes &amp; in-briefs</h1>
  <p class="stand">Three print-ready documents are generated live for each of the {n} partners, current with the register as at {e(as_at)}.
  Open one and use <b>Print / PDF</b> on the page — the placemat is a single large-format carry-in sheet; the minute and in-brief follow the
  ADF Writing Manual (Ch&nbsp;10 Minutes, Ch&nbsp;12 Briefs). The Command Brief asks for its access code once per session.</p>
  <div class="legend">
    <div><b>Placemat</b>One-page decision sheet: key messages, capability radar, leadership, agreements, engagements and priority opportunities.</div>
    <div><b>Minute</b>ADF-format minute drafted from that partner’s confirmed content and any opportunities ticked on the Opportunities tab.</div>
    <div><b>In-brief</b>Visit in-brief for an engagement with that partner, under the same sourcing discipline.</div>
  </div>
{body}
</main>
<footer>
  Prepared from publicly available sources only. Contains no classified, caveated or partner-controlled information.
  Items held at TO_VERIFY render as pending confirmation and must not be asserted until sourced.
  <div class="lock">UNOFFICIAL · OPEN SOURCE · DRAFT · AS AT {e(as_at.upper())}</div>
</footer>
</body>
</html>
'''

(DIR / 'placemats.html').write_text(out, encoding='utf-8')
print(f'wrote placemats.html  {len(out):,} bytes  {n} partners  (FLAGDEF={len(FLAGDEF)}, RAIL={len(RAIL)})')
for t, ks in groups:
    if ks:
        print(f'  {t}: {len(ks)}')
missing = [k for k in P if k not in FLAGDEF and k not in RAIL]
print('  no display-name source (fell back to data name):', missing or 'none')
