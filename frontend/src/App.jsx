import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, AlertCircle, ArrowUpRight, Bug, Check, ChevronDown, CircleHelp, Clock3, Code2, Database, FileSearch, FlaskConical, FolderKanban, Gauge, GitCompareArrows, Layers3, Plus, RefreshCw, Search, ShieldCheck, Sparkles, X } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const FAILURE_TYPES = new Set(["javascript_error","unhandled_promise_rejection","http_error","network_error"]);
const pretty = value => value ? new Date(value).toLocaleString() : "—";
const short = value => String(value || "").replaceAll("_"," ");
async function request(path, options={}) {
  const response = await fetch(`${API}${path}`, { ...options, headers: { "Content-Type":"application/json", ...(options.headers||{}) }});
  const data = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
function App(){
  const [projects,setProjects]=useState([]), [sessions,setSessions]=useState([]), [events,setEvents]=useState([]);
  const [projectId,setProjectId]=useState(
  () => localStorage.getItem("traceforge_project_id") || ""
);

const [sessionId,setSessionId]=useState(
  () => localStorage.getItem("traceforge_session_id") || ""
);

const [failureId,setFailureId]=useState("");
  const [evidence,setEvidence]=useState(null), [plans,setPlans]=useState([]), [attempts,setAttempts]=useState([]);
  const [confidence,setConfidence]=useState(null), [recommendations,setRecommendations]=useState([]);
  const [loading,setLoading]=useState(false), [error,setError]=useState(""), [notice,setNotice]=useState("");
  const [projectName,setProjectName]=useState(""), [sessionName,setSessionName]=useState("");
  const [showProject,setShowProject]=useState(false), [showSession,setShowSession]=useState(false), [showAttempt,setShowAttempt]=useState(false);
  const [attemptForm,setAttemptForm]=useState({outcome:"reproduced",notes:"",conditions:'{"browser":"Chrome","network":"Wi-Fi"}',plan_id:""});
  const [query,setQuery]=useState("");
  const loadProjects=useCallback(async()=>{const d=await request("/projects");setProjects(d.projects||[]);},[]);
  const loadSessionData=useCallback(async(sid)=>{
    if(!sid)return;
    const [ev,pl,at]=await Promise.all([
      request(`/sessions/${sid}/events`), request(`/sessions/${sid}/reproduction-plans`), request(`/sessions/${sid}/reproduction-attempts`)
    ]);
    setEvents(ev.events||[]);setPlans(pl.plans||[]);setAttempts(at.attempts||[]);
  },[]);
  useEffect(()=>{loadProjects().catch(e=>setError(e.message));},[loadProjects]);
  useEffect(()=>{if(!projectId)return;request(`/projects/${projectId}/sessions`).then(d=>setSessions(d.sessions||[])).catch(e=>setError(e.message));},[projectId]);
  useEffect(() => {
  if (projectId) {
    localStorage.setItem("traceforge_project_id", projectId);
  } else {
    localStorage.removeItem("traceforge_project_id");
  }
}, [projectId]);

useEffect(() => {
  if (sessionId) {
    localStorage.setItem("traceforge_session_id", sessionId);
  } else {
    localStorage.removeItem("traceforge_session_id");
  }
}, [sessionId]);
  useEffect(()=>{if(sessionId)loadSessionData(sessionId).catch(e=>setError(e.message));},[sessionId,loadSessionData]);
  const failures=useMemo(()=>events.filter(e=>FAILURE_TYPES.has(e.event_type)),[events]);
  const selectedFailure=failures.find(e=>e.id===failureId)||failures[0]||null;
  useEffect(()=>{if(selectedFailure && selectedFailure.id!==failureId)setFailureId(selectedFailure.id);},[selectedFailure,failureId]);
  const loadInvestigation=useCallback(async(fid)=>{
    if(!sessionId||!fid)return;
    setLoading(true);setError("");
    try{
      const [ev,conf,rec]=await Promise.all([
        request(`/sessions/${sessionId}/evidence`),
        request(`/sessions/${sessionId}/failures/${fid}/confidence`),
        request(`/sessions/${sessionId}/failures/${fid}/experiment-recommendations`)
      ]);
      setEvidence(ev);setConfidence(conf.confidence);setRecommendations(rec.recommendations||[]);
    }catch(e){setError(e.message);}finally{setLoading(false);}
  },[sessionId]);
  useEffect(()=>{if(selectedFailure)loadInvestigation(selectedFailure.id);else{setConfidence(null);setRecommendations([]);setEvidence(null);}},[selectedFailure,loadInvestigation]);
  async function createProject(e){e.preventDefault();try{const d=await request("/projects",{method:"POST",body:JSON.stringify({name:projectName})});setProjectName("");setShowProject(false);await loadProjects();setProjectId(d.project_id);setNotice("Project created.");}catch(e){setError(e.message);}}
  async function createSession(e){e.preventDefault();try{const d=await request(`/projects/${projectId}/sessions`,{method:"POST",body:JSON.stringify({name:sessionName})});setSessionName("");setShowSession(false);const s=await request(`/projects/${projectId}/sessions`);setSessions(s.sessions||[]);setSessionId(d.session_id);setNotice("Session created.");}catch(e){setError(e.message);}}
  async function generatePlan(){if(!selectedFailure)return;try{await request(`/sessions/${sessionId}/failures/${selectedFailure.id}/reproduction-plan`);await loadSessionData(sessionId);setNotice("Reproduction plan generated.");}catch(e){setError(e.message);}}
  async function addAttempt(e){e.preventDefault();try{const conditions=JSON.parse(attemptForm.conditions||"{}");await request(`/sessions/${sessionId}/reproduction-attempts`,{method:"POST",body:JSON.stringify({failure_event_id:selectedFailure.id,outcome:attemptForm.outcome,notes:attemptForm.notes,conditions,plan_id:attemptForm.plan_id||null})});setShowAttempt(false);await loadSessionData(sessionId);await loadInvestigation(selectedFailure.id);setNotice("Attempt saved.");}catch(e){setError(e.message);}}
  async function makeRecommendation(){try{await request(`/sessions/${sessionId}/failures/${selectedFailure.id}/experiment-recommendations`,{method:"POST"});await loadInvestigation(selectedFailure.id);setNotice("Recommendation generated and saved.");}catch(e){setError(e.message);}}
  async function updateRecommendation(id,status){try{await request(`/sessions/${sessionId}/experiment-recommendations/${id}`,{method:"PATCH",body:JSON.stringify({status})});await loadInvestigation(selectedFailure.id);setNotice(`Recommendation marked ${status}.`);}catch(e){setError(e.message);}}
  const filteredEvents=events.filter(e=>!query||`${e.event_type} ${JSON.stringify(e.event_data)}`.toLowerCase().includes(query.toLowerCase()));
  const score=confidence?.confidence_score;
  const scoreLevel=confidence?.confidence_level||"not assessed";
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Activity size={21}/></div><div><b>TraceForge</b><small>INVESTIGATION WORKSPACE</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <button className="side-item active"><Layers3 size={17}/> Investigation overview</button>
      <button className="side-item" onClick={()=>document.getElementById("events")?.scrollIntoView({behavior:"smooth"})}><Activity size={17}/> Event timeline</button>
      <button className="side-item" onClick={()=>document.getElementById("reproduction")?.scrollIntoView({behavior:"smooth"})}><FlaskConical size={17}/> Reproduction lab</button>
      <div className="side-bottom"><ShieldCheck size={17}/><span>Local-first workspace</span><i/></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="crumb">Workspace <span>/</span> <b>Failure investigation</b></div><div className="top-actions"><span className="api-status"><i/> API endpoint configured</span><button className="icon-btn" title="Refresh" onClick={()=>{loadProjects();if(sessionId)loadSessionData(sessionId);}}><RefreshCw size={16}/></button></div></header>
      <section className="welcome"><div><div className="eyebrow"><Sparkles size={14}/> EVIDENCE-DRIVEN DEBUGGING</div><h1>Investigation <em>workspace</em></h1><p>Turn browser failures into structured, reviewable investigations.</p></div><div className="welcome-chip"><span className="pulse"/> LOCAL DEVELOPMENT</div></section>
      {error&&<div className="alert error"><AlertCircle size={17}/>{error}<button onClick={()=>setError("")}><X size={15}/></button></div>}
      {notice&&<div className="alert success"><Check size={17}/>{notice}<button onClick={()=>setNotice("")}><X size={15}/></button></div>}
      <section className="selector-grid">
        <div className="selector-card"><div className="selector-icon purple"><FolderKanban size={18}/></div><div className="selector-content"><label>ACTIVE PROJECT</label><select value={projectId} onChange={e=>{setProjectId(e.target.value);setSessionId("");setEvents([]);setFailureId("");}}><option value="">Select a project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></div><button className="tiny-add" onClick={()=>setShowProject(!showProject)}><Plus size={16}/></button></div>
        <div className="selector-card"><div className="selector-icon blue"><Database size={18}/></div><div className="selector-content"><label>ACTIVE SESSION</label><select value={sessionId} disabled={!projectId} onChange={e=>{setSessionId(e.target.value);setFailureId("");}}><option value="">Select a session</option>{sessions.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></div><button className="tiny-add" disabled={!projectId} onClick={()=>setShowSession(!showSession)}><Plus size={16}/></button></div>
      </section>
      {showProject&&<form className="inline-form" onSubmit={createProject}><input required maxLength="100" placeholder="Project name" value={projectName} onChange={e=>setProjectName(e.target.value)}/><button className="primary">Create project</button><button type="button" className="ghost" onClick={()=>setShowProject(false)}>Cancel</button></form>}
      {showSession&&<form className="inline-form" onSubmit={createSession}><input required maxLength="100" placeholder="Session name" value={sessionName} onChange={e=>setSessionName(e.target.value)}/><button className="primary">Create session</button><button type="button" className="ghost" onClick={()=>setShowSession(false)}>Cancel</button></form>}
      {!sessionId?<div className="empty-state"><div className="empty-icon"><FileSearch size={27}/></div><h2>Choose an investigation session</h2><p>Select a project and session to inspect recorded events, failures, evidence and reproduction activity. You can create them using the + controls above.</p></div>:<>
        <section className="metrics">
          <Metric icon={<Activity/>} label="RECORDED EVENTS" value={events.length} detail="Events in selected session" color="blue"/>
          <Metric icon={<Bug/>} label="DETECTED FAILURES" value={failures.length} detail="Recognized failure events" color="red"/>
          <Metric icon={<FlaskConical/>} label="REPRODUCTION ATTEMPTS" value={attempts.length} detail="Recorded investigation runs" color="purple"/>
          <Metric icon={<Gauge/>} label="CONFIDENCE" value={score==null?"—":`${score}/100`} detail={short(scoreLevel)} color="green"/>
        </section>
        <section className="content-grid">
          <div className="panel failure-panel"><div className="panel-head"><div><div className="eyebrow">INVESTIGATION TARGET</div><h2>Failure explorer</h2></div><span className="count">{failures.length} failures</span></div>
            {failures.length===0?<div className="empty-small"><Bug size={22}/><b>No failure events yet</b><span>Start the TraceForge browser recorder, then reproduce a browser issue.</span></div>:<div className="failure-list">{failures.map(f=><button key={f.id} className={`failure-row ${selectedFailure?.id===f.id?"chosen":""}`} onClick={()=>setFailureId(f.id)}><span className={`failure-symbol ${f.event_type}`}><AlertCircle size={17}/></span><span className="failure-main"><b>{short(f.event_type)}</b><small>{f.event_data?.message||f.event_data?.statusText||f.event_data?.requestUrl||"Failure event captured"}</small><time>{pretty(f.created_at)}</time></span><ArrowUpRight size={16}/></button>)}</div>}
          </div>
          <div className="panel confidence-panel"><div className="panel-head"><div><div className="eyebrow">EVIDENCE ASSESSMENT</div><h2>Confidence overview</h2></div><CircleHelp size={17} className="muted"/></div>
            {selectedFailure?<><div className="score-wrap"><div className={`score-ring ${score==null?"neutral":score>=80?"high":score>=50?"medium":"low"}`}><div><strong>{score??"—"}</strong><small>{score==null?"N/A":"/ 100"}</small></div></div><div className="score-copy"><span className={`level level-${scoreLevel.replaceAll(" ","-")}`}>{short(scoreLevel)}</span><h3>{score==null?"Not assessed yet":score>=80?"Strong supporting evidence":score>=50?"Some supporting evidence":"Limited supporting evidence"}</h3><p>{score==null?"Record informative reproduction attempts to assess investigation confidence.":"A heuristic summary of recorded repeatability, context, plan quality and outcome consistency."}</p></div></div>
              <div className="score-note"><ShieldCheck size={16}/><span>This score is a heuristic indicator, not a calibrated probability or proof of root cause.</span></div>
              {confidence?.confidence_reasons?.length>0&&<div className="reason-list">{confidence.confidence_reasons.slice(0,3).map((r,i)=><div key={i}><Check size={14}/>{r}</div>)}</div>}
            </>:<div className="empty-small">Select a failure to inspect its evidence assessment.</div>}
          </div>
        </section>
        <section className="panel" id="events"><div className="panel-head"><div><div className="eyebrow">SESSION ACTIVITY</div><h2>Event timeline</h2></div><div className="search-box"><Search size={15}/><input placeholder="Filter events..." value={query} onChange={e=>setQuery(e.target.value)}/></div></div>
          <div className="timeline">{filteredEvents.slice().reverse().slice(0,30).map((ev,i)=><div className="timeline-row" key={ev.id}><div className={`timeline-dot ${FAILURE_TYPES.has(ev.event_type)?"danger":""}`}/><div className="timeline-body"><div className="timeline-title"><b>{short(ev.event_type)}</b>{FAILURE_TYPES.has(ev.event_type)&&<span className="tag red">FAILURE</span>}<time>{pretty(ev.created_at)}</time></div><p>{ev.event_data?.message||ev.event_data?.title||ev.event_data?.url||ev.event_data?.requestUrl||JSON.stringify(ev.event_data).slice(0,180)}</p></div></div>)}{filteredEvents.length===0&&<div className="empty-small">No events match this filter.</div>}</div>
        </section>
        <section className="panel" id="reproduction"><div className="panel-head"><div><div className="eyebrow">REPRODUCIBILITY WORKFLOW</div><h2>Reproduction lab</h2></div><div className="button-row"><button className="secondary" disabled={!selectedFailure} onClick={generatePlan}><FileSearch size={15}/> Generate plan</button><button className="primary" disabled={!selectedFailure} onClick={()=>setShowAttempt(true)}><Plus size={15}/> Add attempt</button></div></div>
          {showAttempt&&<form className="attempt-form" onSubmit={addAttempt}><div className="form-grid"><label>Outcome<select value={attemptForm.outcome} onChange={e=>setAttemptForm({...attemptForm,outcome:e.target.value})}><option value="reproduced">Reproduced</option><option value="not_reproduced">Not reproduced</option><option value="inconclusive">Inconclusive</option></select></label><label>Linked plan (optional)<select value={attemptForm.plan_id} onChange={e=>setAttemptForm({...attemptForm,plan_id:e.target.value})}><option value="">No plan linked</option>{plans.map(p=><option value={p.id} key={p.id}>{p.id.slice(0,18)} · {p.status}</option>)}</select></label></div><label>Conditions (JSON object)<textarea rows="3" value={attemptForm.conditions} onChange={e=>setAttemptForm({...attemptForm,conditions:e.target.value})}/></label><label>Notes<textarea rows="2" maxLength="1000" value={attemptForm.notes} onChange={e=>setAttemptForm({...attemptForm,notes:e.target.value})}/></label><div className="button-row"><button className="primary">Save attempt</button><button type="button" className="ghost" onClick={()=>setShowAttempt(false)}>Cancel</button></div></form>}
          <div className="subsection"><div className="subhead"><b>Reproduction plans</b><span>{plans.length} saved</span></div>{plans.length===0?<p className="muted-text">No plans generated for this session yet.</p>:plans.map(p=><div className="data-row" key={p.id}><div className="data-icon"><FileSearch size={17}/></div><div className="data-main"><b>Plan {p.id.slice(0,12)}</b><small>{p.step_count??p.plan_data?.steps?.length??"—"} steps · {pretty(p.created_at)}</small></div><span className={`tag ${p.status==="passed"?"green":p.status==="failed"?"red":"neutral"}`}>{p.status}</span></div>)}</div>
          <div className="subsection"><div className="subhead"><b>Recorded attempts</b><span>{attempts.length} total</span></div>{attempts.length===0?<p className="muted-text">No reproduction attempts recorded yet.</p>:attempts.slice().reverse().map(a=><div className="data-row" key={a.id}><div className="data-icon"><FlaskConical size={17}/></div><div className="data-main"><b>{short(a.outcome)}</b><small>{pretty(a.created_at)} · {Object.keys(a.conditions||{}).length} conditions</small></div><span className="tag neutral">{a.id.slice(0,12)}</span></div>)}</div>
        </section>
        <section className="panel"><div className="panel-head"><div><div className="eyebrow">CONTROLLED COMPARISON</div><h2>Next experiment</h2></div><button className="secondary" disabled={!selectedFailure} onClick={makeRecommendation}><Sparkles size={15}/> Generate recommendation</button></div>
          {recommendations.length===0?<div className="empty-small">Generate a recommendation after recording at least two informative attempts with comparable conditions.</div>:recommendations.slice().reverse().map(r=><div className="recommendation" key={r.id}><div className="rec-top"><b>Experiment recommendation</b><span className={`tag ${r.status==="completed"?"green":"neutral"}`}>{r.status}</span></div><p>{r.recommendation?.reason||r.recommendation_data?.reason||r.message||"Review the stored recommendation details."}</p><div className="rec-actions">{r.status==="proposed"&&<><button className="secondary" onClick={()=>updateRecommendation(r.id,"accepted")}>Accept</button><button className="ghost" onClick={()=>updateRecommendation(r.id,"skipped")}>Skip</button></>}{r.status==="accepted"&&<button className="secondary" onClick={()=>updateRecommendation(r.id,"completed")}>Mark completed</button>}</div></div>)}
        </section>
      </>}
      <footer><span>TRACEFORGE · LOCAL-FIRST INVESTIGATION</span><span>Evidence informs decisions. It does not replace verification.</span></footer>
    </main>
  </div>
}
function Metric({icon,label,value,detail,color}){return <div className="metric-card"><div className={`metric-icon ${color}`}>{icon}</div><div><label>{label}</label><strong>{value}</strong><small>{detail}</small></div></div>}
export default App;
