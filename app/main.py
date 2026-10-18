"""旅游行程规划 Agent 服务入口。

链路：自然语言需求 → 意图解析 → 片区聚类编排 → 预算核算 → 行程单
所有环节均可降级：未配置模型 Key 时走规则引擎，接口照常可用。
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agents import intent as intent_agent
from app.agents import planner as planner_agent
from app.llm.client import LLMClient
from app.tools import attractions

app = FastAPI(title="Travel Plan Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = LLMClient()


class PlanRequest(BaseModel):
    text: str = Field(..., description="自然语言需求，例如：带父母去杭州玩三天，轻松一点，预算五千")
    city: str | None = None
    days: int | None = None
    budget: float | None = None
    people: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_available": llm.available,
        "mode": "llm" if llm.available else "rule-engine",
        "cities": attractions.list_cities(),
    }


@app.get("/cities")
def cities() -> dict:
    return {"cities": attractions.list_cities()}


@app.post("/plan")
def create_plan(req: PlanRequest) -> dict:
    try:
        parsed = intent_agent.parse(req.text, llm=llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"需求解析失败：{exc}") from exc

    # 显式传参优先级高于自然语言解析结果
    if req.city:
        parsed.city = req.city
    if req.days:
        parsed.days = req.days
    if req.budget is not None:
        parsed.budget = req.budget
    if req.people:
        parsed.people = req.people

    if not parsed.city:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "未识别到目的地，请补充城市",
                "supported_cities": attractions.list_cities(),
            },
        )

    try:
        result = planner_agent.plan(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "intent": parsed.to_dict(),
        "plan": result.to_dict(),
        "markdown": planner_agent.render_markdown(result),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


INDEX_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>旅游行程规划 Agent</title>
<style>
:root{--ink:#1a1a1a;--sub:#666;--line:#e6e6e6;--brand:#1f6feb;--bg:#fafafa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:24px;margin:0 0 6px}
.sub{color:var(--sub);font-size:13px;margin-bottom:24px}
.box{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}
textarea{width:100%;min-height:88px;border:1px solid var(--line);border-radius:8px;
  padding:12px;font:inherit;resize:vertical;outline:none}
textarea:focus{border-color:var(--brand)}
.row{display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap}
button{background:var(--brand);color:#fff;border:0;border-radius:8px;
  padding:10px 20px;font:inherit;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.chip{border:1px solid var(--line);background:#fff;border-radius:999px;
  padding:6px 12px;font-size:13px;cursor:pointer;color:var(--sub)}
.chip:hover{border-color:var(--brand);color:var(--brand)}
pre{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:16px;
  overflow:auto;font-size:12.5px;line-height:1.7}
.meta{font-size:12px;color:var(--sub);margin-bottom:8px}
</style></head>
<body><div class="wrap">
<h1>旅游行程规划 Agent</h1>
<div class="sub">输入一句需求，输出可直接发给客户的行程单 · 无模型 Key 时自动走规则引擎</div>

<div class="box">
  <textarea id="q" placeholder="例如：带父母去杭州玩三天，路线轻松一点，预算五千"></textarea>
  <div class="row">
    <button id="go">生成行程</button>
    <span class="chip" data-q="带孩子去成都玩四天，想看熊猫，预算八千">亲子·成都4天</span>
    <span class="chip" data-q="和女朋友去厦门三天，想拍照吃海鲜，预算四千">情侣·厦门3天</span>
    <span class="chip" data-q="去西安两天，看兵马俑和博物馆，节奏紧凑一点">独自·西安2天</span>
  </div>
</div>

<div class="box">
  <div class="meta" id="meta">等待输入…</div>
  <pre id="out">—</pre>
</div>
</div>
<script>
const $=s=>document.querySelector(s);
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{$('#q').value=c.dataset.q});
$('#go').onclick=async()=>{
  const text=$('#q').value.trim(); if(!text) return;
  $('#go').disabled=true; $('#meta').textContent='解析中…'; $('#out').textContent='…';
  try{
    const r=await fetch('/plan',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text})});
    const d=await r.json();
    if(!r.ok){
      const det=d.detail||{};
      const msg=det.message||(typeof det==='string'?det:'请求失败');
      const cities=(det.supported_cities||[]).join('、');
      $('#meta').textContent='无法规划';
      $('#out').textContent=msg+(cities?`\n\n当前支持的城市：${cities}\n试试上面那三个示例按钮。`:'');
      return;
    }
    $('#meta').textContent=`解析来源：${d.intent.source}　城市：${d.plan.city}　`
      +`${d.plan.days.length} 天　人均 ¥${d.plan.budget.per_person_estimate}`;
    $('#out').textContent=d.markdown;
  }catch(e){ $('#meta').textContent='网络错误'; $('#out').textContent=String(e); }
  finally{ $('#go').disabled=false; }
};
</script></body></html>"""
