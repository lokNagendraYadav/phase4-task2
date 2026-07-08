"""FastAPI web UI for the multi-agent research pipeline.

Two-pane layout:
  * LEFT  — the conversation: your question and the final briefing (rendered markdown).
  * RIGHT — the live orchestration flow: which sub-agent the orchestrator is
            running, what tools it called, and each delegation, streamed over SSE.

Run with:  python -m uvicorn src.app:app --reload
"""
from __future__ import annotations

import json
from typing import Iterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from .config import settings
from .graph import stream_events

app = FastAPI(title="Multi-Agent Research Pipeline", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "google_api_key": settings.has_google,
        "tavily_api_key": settings.has_tavily,
        "supervisor_model": settings.supervisor_model,
        "worker_model": settings.worker_model,
    }


@app.get("/agents")
def agents_roster() -> dict:
    """Describe the orchestrator and its sub-agents for the UI 'Agents' tab."""
    web_tools = (
        ["tavily_search"] if settings.has_tavily
        else ["(disabled — set TAVILY_API_KEY)"]
    )
    return {
        "orchestrator": {
            "name": "supervisor",
            "label": "🧭 Orchestrator",
            "model": settings.supervisor_model,
            "role": "Plans the research, delegates to one sub-agent at a time, "
                    "and compiles the final cited briefing.",
            "tools": ["transfer_to_… (delegation)"],
        },
        "workers": [
            {
                "name": "web_search_agent",
                "label": "🌐 Web Search",
                "model": settings.worker_model,
                "role": "Searches the public web and returns facts with source URLs.",
                "tools": web_tools,
            },
            {
                "name": "doc_summary_agent",
                "label": "📄 Doc Summary",
                "model": settings.worker_model,
                "role": "Reads and summarises the internal knowledge base (docs/).",
                "tools": ["list_documents", "read_document"],
            },
            {
                "name": "citation_validator_agent",
                "label": "✅ Citation Validator",
                "model": settings.worker_model,
                "role": "Verifies every cited URL is reachable and supports its claim.",
                "tools": ["validate_url", "fetch_url_excerpt"],
            },
        ],
    }


def _sse(question: str) -> Iterator[str]:
    """Yield SSE-formatted events for a research question."""
    try:
        for event in stream_events(question):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as exc:  # noqa: BLE001 - surface any runtime error to the UI
        err = {"agent": "error", "text": f"{type(exc).__name__}: {exc}",
               "tools": [], "handoffs": []}
        yield f"data: {json.dumps(err)}\n\n"


@app.get("/research")
def research(q: str) -> StreamingResponse:
    return StreamingResponse(
        _sse(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Multi-Agent Research Pipeline</title>
<style>
  :root{
    color-scheme: dark;
    --bg:#0b0d13; --panel:#141824; --panel2:#0f131d; --border:#242a3a;
    --fg:#e8ebf2; --muted:#8b93a7; --accent:#6ea8fe; --accent2:#a78bfa;
    --ok:#4ade80; --warn:#fbbf24; --err:#f87171;
  }
  *{box-sizing:border-box;}
  html,body{height:100%;}
  body{margin:0; font:15px/1.55 system-ui,"Segoe UI",Roboto,sans-serif;
       background:var(--bg); color:var(--fg); display:flex; flex-direction:column;}
  header{padding:14px 22px; border-bottom:1px solid var(--border);
         display:flex; align-items:center; gap:12px; flex-shrink:0;}
  header h1{margin:0; font-size:16px; font-weight:650;}
  header .sub{color:var(--muted); font-size:12.5px;}
  .layout{flex:1; display:grid; grid-template-columns: 1.15fr 0.85fr; min-height:0;}
  .col{display:flex; flex-direction:column; min-height:0;}
  .col.left{border-right:1px solid var(--border);}
  .col-head{padding:10px 18px; font-size:12px; letter-spacing:.06em;
            text-transform:uppercase; color:var(--muted);
            border-bottom:1px solid var(--border); flex-shrink:0;
            display:flex; align-items:center; gap:8px;}
  .scroll{flex:1; overflow-y:auto; padding:18px;}

  /* ---- left: conversation ---- */
  .msg{margin-bottom:16px;}
  .msg .role{font-size:12px; color:var(--muted); margin-bottom:6px;}
  .bubble.user{background:var(--panel); border:1px solid var(--border);
        border-radius:12px; padding:10px 14px; display:inline-block; max-width:100%;}
  .bubble.answer{background:linear-gradient(180deg,#141a2b,#10151f);
        border:1px solid #2b3450; border-radius:14px; padding:4px 20px;}
  .answer h2{font-size:16px; margin:18px 0 8px; color:var(--accent);
        border-bottom:1px solid var(--border); padding-bottom:5px;}
  .answer h3{font-size:14px; margin:14px 0 6px; color:var(--accent2);}
  .answer h1{font-size:18px; margin:14px 0 8px;}
  .answer p{margin:8px 0;}
  .answer ul,.answer ol{margin:8px 0; padding-left:22px;}
  .answer li{margin:4px 0;}
  .answer a{color:var(--accent); word-break:break-all;}
  .answer code{background:#0b0f18; border:1px solid var(--border);
        border-radius:5px; padding:1px 5px; font-size:13px;}
  .answer strong{color:#fff;}
  .placeholder{color:var(--muted); font-size:14px; text-align:center; margin-top:60px;}

  /* ---- right: orchestration flow ---- */
  .flow{position:relative; padding-left:26px;}
  .flow::before{content:""; position:absolute; left:9px; top:4px; bottom:4px;
        width:2px; background:var(--border);}
  .node{position:relative; margin-bottom:14px;}
  .node .dot{position:absolute; left:-22px; top:3px; width:14px; height:14px;
        border-radius:50%; background:var(--panel); border:2px solid var(--accent);}
  .node.active .dot{border-color:var(--warn); box-shadow:0 0 0 4px rgba(251,191,36,.15);}
  .node.done .dot{background:var(--ok); border-color:var(--ok);}
  .node.sup .dot{border-color:var(--accent2);}
  .node.err .dot{border-color:var(--err); background:var(--err);}
  .card{background:var(--panel); border:1px solid var(--border);
        border-radius:10px; padding:9px 12px;}
  .card .who{font-weight:650; font-size:13.5px; display:flex;
        align-items:center; gap:8px; flex-wrap:wrap;}
  .tag{font-size:10.5px; padding:2px 7px; border-radius:999px;
        background:#22304d; color:var(--accent);}
  .tag.sup{background:#2b2450; color:var(--accent2);}
  .tag.tool{background:#3a3320; color:var(--warn);}
  .tag.route{background:#1f3a2a; color:var(--ok);}
  .card .detail{font-size:12.5px; color:var(--muted); margin-top:5px;
        white-space:pre-wrap; word-wrap:break-word;}
  .card .detail.snippet{max-height:120px; overflow:hidden;
        -webkit-mask-image:linear-gradient(#000 70%,transparent);}
  .spinner{width:13px;height:13px;border:2px solid var(--border);
        border-top-color:var(--warn); border-radius:50%;
        animation:spin .8s linear infinite; display:inline-block;}
  @keyframes spin{to{transform:rotate(360deg);}}

  /* ---- tabs + agents roster ---- */
  .col-head.tabs{gap:6px; text-transform:none; letter-spacing:0; padding:6px 12px;}
  .tab{background:transparent; border:1px solid var(--border); color:var(--muted);
       padding:6px 12px; border-radius:8px; font-size:12.5px; cursor:pointer; min-width:0;}
  .tab.active{background:var(--panel); color:var(--fg); border-color:#3a4360;}
  #status{margin-left:auto; color:var(--muted); font-size:12px;}
  .agent-card{background:var(--panel); border:1px solid var(--border);
       border-radius:11px; padding:12px 14px; margin-bottom:12px;}
  .agent-card.orch{border-color:#3a3163; background:linear-gradient(180deg,#191633,#12101f);}
  .agent-card .name{font-weight:650; font-size:14px;}
  .agent-card .model{font-size:11px; color:var(--muted); float:right;
       background:var(--bg); border:1px solid var(--border); padding:1px 8px; border-radius:999px;}
  .agent-card .role{font-size:12.5px; color:var(--muted); margin:6px 0 8px;}
  .agent-card .tools{display:flex; flex-wrap:wrap; gap:6px;}
  .agent-card .tools .tag{background:#22304d; color:var(--accent);}
  .roster-arrow{color:var(--muted); text-align:center; font-size:12px; margin:-4px 0 8px;}

  /* ---- form ---- */
  form{display:flex; gap:10px; padding:14px 18px; border-top:1px solid var(--border);
       background:var(--panel2); flex-shrink:0;}
  input[type=text]{flex:1; padding:11px 14px; border-radius:10px;
       border:1px solid var(--border); background:var(--bg); color:var(--fg); font-size:15px;}
  button{padding:11px 20px; border:0; border-radius:10px; background:var(--accent);
       color:#08132b; font-weight:650; cursor:pointer; min-width:110px;}
  button:disabled{opacity:.55; cursor:not-allowed;}
  .examples{padding:0 18px 12px; font-size:12.5px; color:var(--muted); background:var(--panel2);}
  .examples a{color:var(--accent); cursor:pointer; margin-right:16px; text-decoration:none;}
  @media (max-width:820px){ .layout{grid-template-columns:1fr; grid-template-rows:1fr 1fr;}
       .col.left{border-right:0; border-bottom:1px solid var(--border);} }
</style>
</head>
<body>
<header>
  <h1>🔎 Multi-Agent Research Pipeline</h1>
  <span class="sub">LangGraph supervisor · Gemini · web-search + doc-summary + citation-validator</span>
</header>

<div class="layout">
  <section class="col left">
    <div class="col-head">💬 Conversation</div>
    <div class="scroll" id="chat">
      <div class="placeholder" id="ph">Ask a research question below to begin.</div>
    </div>
  </section>

  <section class="col right">
    <div class="col-head tabs">
      <button class="tab active" data-tab="flow" type="button">⚙️ Flow</button>
      <button class="tab" data-tab="agents" type="button">🤖 Agents</button>
      <span id="status"></span>
    </div>
    <div class="scroll" id="pane-flow"><div class="flow" id="flow">
      <div class="placeholder">The orchestration timeline will appear here while a query runs.</div>
    </div></div>
    <div class="scroll" id="pane-agents" style="display:none"><div id="roster"></div></div>
  </section>
</div>

<div class="examples">
  Try:
  <a data-q="Research the company Anthropic: products, funding, and leadership. Cross-check with our internal notes.">Client research</a>
  <a data-q="Summarise what we know internally about Project Atlas and find any recent public news about it.">Internal knowledge</a>
</div>
<form id="f">
  <input id="q" type="text" autocomplete="off" required
         placeholder="e.g. Research Acme Corp: products, recent news, and cross-check with our internal notes" />
  <button id="go" type="submit">Research</button>
</form>

<script>
const AGENTS = {
  supervisor:{label:"🧭 Orchestrator", cls:"sup"},
  web_search_agent:{label:"🌐 Web Search", cls:""},
  doc_summary_agent:{label:"📄 Doc Summary", cls:""},
  citation_validator_agent:{label:"✅ Citation Validator", cls:""},
  error:{label:"❌ Error", cls:"err"},
};
const chat = document.getElementById('chat');
const flow = document.getElementById('flow');
const statusEl = document.getElementById('status');
const form = document.getElementById('f'), qEl = document.getElementById('q'), go = document.getElementById('go');

document.querySelectorAll('.examples a').forEach(a =>
  a.addEventListener('click', () => { qEl.value = a.dataset.q; qEl.focus(); }));

/* ---------- tabs (Flow | Agents) ---------- */
const paneFlow=document.getElementById('pane-flow'), paneAgents=document.getElementById('pane-agents');
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  t.classList.add('active');
  const isFlow = t.dataset.tab==='flow';
  paneFlow.style.display  = isFlow ? '' : 'none';
  paneAgents.style.display= isFlow ? 'none' : '';
}));

/* ---------- load agent roster ---------- */
function agentCardHtml(a, orch){
  const tools=(a.tools||[]).map(t=>'<span class="tag">'+t.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))+'</span>').join('');
  return '<div class="agent-card'+(orch?' orch':'')+'">'+
    '<span class="model">'+a.model+'</span>'+
    '<div class="name">'+a.label+'</div>'+
    '<div class="role">'+a.role+'</div>'+
    '<div class="tools">'+tools+'</div></div>';
}
fetch('/agents').then(r=>r.json()).then(d=>{
  const roster=document.getElementById('roster');
  let html=agentCardHtml(d.orchestrator, true);
  html+='<div class="roster-arrow">▼ delegates to ▼</div>';
  html+=(d.workers||[]).map(w=>agentCardHtml(w,false)).join('');
  roster.innerHTML=html;
}).catch(()=>{ document.getElementById('roster').textContent='Could not load agents.'; });

/* ---------- tiny markdown renderer (headings, bold, italic, code, lists, links) ---------- */
function esc(s){ return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function inline(s){
  s = esc(s);
  s = s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s = s.replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>');
  s = s.replace(/(^|[^*])\\*([^*\\n]+)\\*/g,'$1<em>$2</em>');
  s = s.replace(/\\[([^\\]]+)\\]\\((https?:[^)\\s]+)\\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/(^|[\\s(])(https?:\\/\\/[^\\s)]+)/g,'$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  return s;
}
function mdToHtml(md){
  if(!md) return '';
  const lines = md.replace(/\\r\\n/g,'\\n').split('\\n');
  let html='', list=null, para=[];
  const flushP=()=>{ if(para.length){ html+='<p>'+inline(para.join(' '))+'</p>'; para=[]; } };
  const closeL=()=>{ if(list){ html+='</'+list+'>'; list=null; } };
  for(const raw of lines){
    const line = raw.replace(/\\s+$/,'');
    if(!line.trim()){ flushP(); closeL(); continue; }
    let m;
    if(m=line.match(/^(#{1,6})\\s+(.*)$/)){ flushP(); closeL();
      const l=m[1].length; html+='<h'+l+'>'+inline(m[2])+'</h'+l+'>'; continue; }
    if(m=line.match(/^\\s*[-*+]\\s+(.*)$/)){ flushP();
      if(list!=='ul'){ closeL(); html+='<ul>'; list='ul'; } html+='<li>'+inline(m[1])+'</li>'; continue; }
    if(m=line.match(/^\\s*\\d+[.)]\\s+(.*)$/)){ flushP();
      if(list!=='ol'){ closeL(); html+='<ol>'; list='ol'; } html+='<li>'+inline(m[1])+'</li>'; continue; }
    closeL(); para.push(line.trim());
  }
  flushP(); closeL();
  return html;
}

/* ---------- rendering ---------- */
function addUser(q){
  document.getElementById('ph')?.remove();
  const d=document.createElement('div'); d.className='msg';
  d.innerHTML='<div class="role">You</div><div class="bubble user">'+esc(q)+'</div>';
  chat.appendChild(d);
}
function addAnswer(md){
  const d=document.createElement('div'); d.className='msg';
  d.innerHTML='<div class="role">Research briefing</div><div class="bubble answer">'+mdToHtml(md)+'</div>';
  chat.appendChild(d); chat.scrollTop=chat.scrollHeight;
}
let activeNode=null;
function markPrevDone(){ if(activeNode){ activeNode.classList.remove('active'); activeNode.classList.add('done'); } }
function addFlow(ev){
  const meta = AGENTS[ev.agent] || {label:ev.agent, cls:""};
  markPrevDone();
  const node=document.createElement('div');
  node.className='node '+(meta.cls||'')+' active';
  const tags=[];
  (ev.handoffs||[]).forEach(h=>{
    const t=AGENTS[h]?AGENTS[h].label:h;
    tags.push('<span class="tag route">→ '+esc(t)+'</span>');
  });
  (ev.tools||[]).forEach(t=> tags.push('<span class="tag tool">🛠 '+esc(t)+'</span>'));
  let detail='';
  if(ev.handoffs && ev.handoffs.length){
    detail='<div class="detail">Delegating to '+ev.handoffs.map(h=>AGENTS[h]?AGENTS[h].label:h).join(', ')+'</div>';
  } else if(ev.text){
    detail='<div class="detail snippet">'+esc(ev.text.slice(0,400))+'</div>';
  } else {
    detail='<div class="detail"><span class="spinner"></span> working…</div>';
  }
  node.innerHTML='<div class="dot"></div><div class="card">'+
    '<div class="who"><span class="tag '+(meta.cls||'')+'">'+meta.label+'</span>'+tags.join('')+'</div>'+
    detail+'</div>';
  flow.appendChild(node); activeNode=node;
  flow.parentElement.scrollTop=flow.parentElement.scrollHeight;
}

/* ---------- run ---------- */
form.addEventListener('submit', e=>{
  e.preventDefault();
  const q=qEl.value.trim(); if(!q) return;
  qEl.value='';                         // clear the typing area after submit
  chat.innerHTML=''; flow.innerHTML=''; activeNode=null;
  document.querySelector('.tab[data-tab="flow"]').click();  // show Flow while running
  addUser(q);
  go.disabled=true; go.innerHTML='<span class="spinner"></span>';
  statusEl.textContent='running…';

  const es=new EventSource('/research?q='+encodeURIComponent(q));
  es.onmessage=m=>{
    const ev=JSON.parse(m.data);
    if(ev.agent==='final'){
      markPrevDone();
      addAnswer(ev.text || '(no answer produced)');
      statusEl.textContent='done ✓';
      es.close(); go.disabled=false; go.textContent='Research';
      return;
    }
    if(ev.agent==='error'){
      addFlow(ev);
      addAnswer('**Error:** '+ (ev.text||'unknown error'));
      statusEl.textContent='error';
      es.close(); go.disabled=false; go.textContent='Research';
      return;
    }
    addFlow(ev);
  };
  es.onerror=()=>{ es.close(); go.disabled=false; go.textContent='Research';
    if(statusEl.textContent==='running…') statusEl.textContent='connection closed'; };
});
</script>
</body>
</html>
"""
