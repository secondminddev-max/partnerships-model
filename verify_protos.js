/* Execute each prototype's <script> in a stubbed DOM-less env, call renderArchSvg,
   then verify: tag balance, NaN/undefined in output, duplicate ids, attr quoting. */
const fs = require("fs");
const vm = require("vm");
const path = "/private/tmp/claude-501/-Users-secondmind-claudecodetest/d1ea2501-e749-4b4d-90cc-6c626e2c5d62/scratchpad/";

const VOID = new Set(["br","hr","img","input","meta","link","area","base","col","embed","source","track","wbr"]);

function checkString(name, out){
  const report = {name, len: out.length, errors: [], warns: []};
  // NaN / undefined leakage
  if(/NaN/.test(out)) report.errors.push("NaN in output at idx "+out.indexOf("NaN"));
  if(/undefined/.test(out)) report.errors.push("'undefined' in output: ..."+out.slice(Math.max(0,out.indexOf("undefined")-60), out.indexOf("undefined")+30));
  // tag balance
  const stack = [];
  const re = /<(\/?)([a-zA-Z][a-zA-Z0-9-]*)((?:"[^"]*"|'[^']*'|[^>"'])*?)(\/?)>/g;
  let m, count = 0;
  while((m = re.exec(out))){
    count++;
    const [ , close, tag, attrs, selfclose] = m;
    if(close){
      if(!stack.length) { report.errors.push("close </"+tag+"> with empty stack @"+m.index); continue; }
      const top = stack.pop();
      if(top !== tag.toLowerCase()) report.errors.push("mismatch: open <"+top+"> closed by </"+tag+"> @"+m.index+" ctx: "+out.slice(Math.max(0,m.index-80), m.index+20));
    } else if(!selfclose && !VOID.has(tag.toLowerCase())){
      stack.push(tag.toLowerCase());
    }
    // attr sanity: unquoted attr values with spaces would already break regex; check for stray quotes
    if(/=\s*"[^"]*$/.test(attrs)) report.errors.push("unterminated attr in <"+tag+"> @"+m.index);
  }
  if(stack.length) report.errors.push("unclosed tags: "+stack.join(","));
  report.tagCount = count;
  // duplicate ids
  const ids = {};
  let im, ire = /\sid="([^"]+)"/g;
  while((im = ire.exec(out))){ ids[im[1]] = (ids[im[1]]||0)+1; }
  const dups = Object.entries(ids).filter(([k,v])=>v>1);
  if(dups.length) report.errors.push("duplicate ids: "+dups.map(d=>d[0]+"x"+d[1]).join(", "));
  report.idCount = Object.keys(ids).length;
  // archnode contract
  const nodes = out.match(/class="[^"]*archnode[^"]*"/g)||[];
  report.archnodes = nodes.length;
  const dataK = out.match(/data-k="([^"]+)"/g)||[];
  report.dataK = dataK.map(s=>s.slice(8,-1));
  const tab = (out.match(/tabindex="0"/g)||[]).length;
  const roleBtn = (out.match(/role="button"/g)||[]).length;
  const aria = (out.match(/aria-label="/g)||[]).length;
  report.tabindex = tab; report.roleButton = roleBtn; report.ariaLabels = aria;
  return report;
}

function extractScript(file){
  const html = fs.readFileSync(path+file,"utf8");
  const ms = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)];
  return ms.map(m=>m[1]).join("\n");
}

function makeSandbox(reduced){
  const noop = ()=>{};
  const fakeEl = { innerHTML:"", querySelectorAll:()=>[], querySelector:()=>null, addEventListener:noop, getAttribute:()=>null, setAttribute:noop, classList:{add:noop,remove:noop,toggle:noop}, style:{} };
  const sandbox = {
    console,
    window: {},
    document: {
      getElementById: ()=>({...fakeEl}),
      querySelectorAll: ()=>[],
      querySelector: ()=>null,
      addEventListener: noop,
      createElement: ()=>({...fakeEl}),
    },
    matchMedia: (q)=>({matches: reduced}),
    requestAnimationFrame: noop,
    setTimeout: noop,
  };
  sandbox.window.matchMedia = sandbox.matchMedia;
  sandbox.window.__ARCH_CTX = undefined;
  sandbox.globalThis = sandbox;
  return sandbox;
}

for(const [file, label] of [["arch-proto-a.html","A"],["arch-proto-b.html","B"],["arch-proto-c.html","C"]]){
  for(const reduced of [false,true]){
    const sb = makeSandbox(reduced);
    vm.createContext(sb);
    try{
      vm.runInContext(extractScript(file), sb, {timeout:5000});
    }catch(e){
      console.log(label+(reduced?" [reduced]":" [motion]")+" SCRIPT ERROR: "+e.message);
      continue;
    }
    let out;
    try{
      // A: renderArchSvg(arch); B: (arch,ctx); C: (arch,ctx)
      const arch = {satellite:3,launch:2,ground:4,sda:2,user:3,delta:{satellite:1,launch:-1,ground:0,user:2}};
      if(label==="A") out = sb.renderArchSvg(arch);
      else if(label==="B") out = sb.renderArchSvg(arch, sb.CTX);
      else out = sb.renderArchSvg(arch, sb.MOCK_CTX);
    }catch(e){ console.log(label+" RENDER ERROR: "+e.message); continue; }
    const r = checkString(label+(reduced?" [reduced-motion]":" [motion]"), out);
    console.log(JSON.stringify(r,null,1));
  }
}

// Edge cases: empty arch, missing keys, no ctx, hostile strings
console.log("\n--- EDGE CASES ---");
for(const [file,label] of [["arch-proto-a.html","A"],["arch-proto-b.html","B"],["arch-proto-c.html","C"]]){
  const sb = makeSandbox(false);
  vm.createContext(sb);
  try{ vm.runInContext(extractScript(file), sb, {timeout:5000}); }catch(e){}
  for(const [cn, arch, ctx] of [
      ["empty-arch", {}, null],
      ["no-ctx", {satellite:5,launch:0,ground:2.5,sda:2,user:1}, null],
      ["fractional+oob", {satellite:7,launch:-2,ground:2.5,sda:"3",user:null}, null],
    ]){
    try{
      const out = label==="A" ? sb.renderArchSvg(arch) : sb.renderArchSvg(arch, ctx);
      const r = checkString(label+" "+cn, out);
      const errs = r.errors.length? r.errors.join(" | ") : "clean";
      console.log(label+" "+cn+": len="+r.len+" archnodes="+r.archnodes+" -> "+errs);
    }catch(e){ console.log(label+" "+cn+" THROWS: "+e.message); }
  }
}
