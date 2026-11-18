"use client";
import { useState } from "react";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Draft = { id: string; channel: string; content: string; status: string };
export default function Home() {
  const [name,setName] = useState("Qopanza");
  const [description,setDescription] = useState("Developer security and cryptographic discovery");
  const [audience,setAudience] = useState("Software startups and technical founders");
  const [projectId,setProjectId] = useState("");
  const [strategy,setStrategy] = useState<string[]>([]);
  const [drafts,setDrafts] = useState<Draft[]>([]);
  const [analytics,setAnalytics] = useState<Record<string,number>|null>(null);
  const [error,setError] = useState("");
  async function request(path:string,options?:RequestInit) {
    const response = await fetch(API+path,options);
    if(!response.ok) throw new Error(await response.text());
    return response.json();
  }
  const post = (path:string,data?:unknown) => request(path,{method:"POST",headers:{"Content-Type":"application/json"},...(data===undefined?{}:{body:JSON.stringify(data)})});
  async function run(action:()=>Promise<void>) {try{setError("");await action()}catch(e){setError(String(e))}}
  async function create() {const p=await post("/projects",{product_name:name,description,audience,goal_customers:10});setProjectId(p.id);setStrategy([]);setDrafts([]);setAnalytics(null)}
  async function plan(){const result=await post("/projects/"+projectId+"/strategy");setStrategy(result.steps)}
  async function generate(){const result=await post("/projects/"+projectId+"/drafts");setDrafts(result.drafts)}
  async function review(id:string,decision:"approved"|"rejected"){const d=await post("/drafts/"+id+"/review?decision="+decision);setDrafts(old=>old.map(x=>x.id===id?d:x))}
  async function record(){await post("/projects/"+projectId+"/metrics",{channel:"manual",impressions:100,leads:10,signups:3,paying_customers:1});await refresh()}
  async function refresh(){const r=await request("/projects/"+projectId+"/analytics");setAnalytics(r.totals)}
  return <main>
    <div className="tag">FounderOS · MVP v0.1</div><h1>Your AI Growth Employee</h1>
    <p>You build the product. FounderOS helps you find your first customers.</p>
    <section className="panel"><h2>1. Understand your product</h2>
      <label>Product name<input value={name} onChange={e=>setName(e.target.value)}/></label>
      <label>What does it do?<textarea value={description} onChange={e=>setDescription(e.target.value)}/></label>
      <label>Who is it for?<input value={audience} onChange={e=>setAudience(e.target.value)}/></label>
      <button onClick={()=>run(create)}>Create growth project</button>
      {projectId&&<small> Project created: {projectId}</small>}
    </section>
    {projectId&&<><section className="panel"><h2>2. Growth Strategist</h2><button onClick={()=>run(plan)}>Generate growth plan</button>
      <ol>{strategy.map((s,i)=><li key={i}>{s}</li>)}</ol></section>
      <section className="panel"><h2>3. Growth Executor</h2><button onClick={()=>run(generate)}>Prepare campaign drafts</button>
        {drafts.map(d=><div key={d.id} className="panel"><strong>{d.channel.toUpperCase()} · {d.status}</strong><p>{d.content}</p>
          {d.status==="pending"&&<><button onClick={()=>run(()=>review(d.id,"approved"))}>Approve</button><button onClick={()=>run(()=>review(d.id,"rejected"))}>Reject</button></>}
        </div>)}
        <small>Approved drafts are not automatically published or sent.</small>
      </section>
      <section className="panel"><h2>4. Growth Analyst</h2><p>Use the sample metric button to test the analytics workflow.</p>
        <button onClick={()=>run(record)}>Record sample results</button><button onClick={()=>run(refresh)}>Refresh analytics</button>
        {analytics&&<pre>{JSON.stringify(analytics,null,2)}</pre>}</section></>}
    {error&&<p className="error">{error}</p>}
  </main>;
}
