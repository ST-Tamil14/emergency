// Exercise the running local stack. Adds a measured batch and a saved demo preset.
const {chromium}=require('playwright');
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..'),base='http://127.0.0.1:8088';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const report={checks:[],pageErrors:[]};
async function api(p,body){const r=await fetch(base+'/api'+p,body===undefined?{}:{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});assert.equal(r.status,200,await r.clone().text());return r.json()}
(async()=>{
 let browser;
 try{
  assert.equal((await api('/health')).version,'0.2.0');
  const state=await api('/state');assert.equal(state.controllers.length,8);assert.equal(state.agent_mode,'process');
  report.checks.push('Nginx → Spring gateway → research API, eight controller processes');
  const job=await api('/experiments',{seeds:1,mode:'sumo',density:0,scenario:'repeated'});
  let result;
  for(let i=0;i<180;i++){result=(await api('/experiments')).find(j=>j.id===job.id);if(result.status!=='RUNNING')break;await delay(1000)}
  assert.equal(result.status,'COMPLETE',JSON.stringify(result));assert.equal(result.results.length,2);
  for(const r of result.results){assert.equal(r.status,'COMPLETE');assert.ok(r.recovery_count>=2);assert.equal(r.unsafe_acceptances,0);assert.equal(r.collisions,0)}
  report.experiment=result;report.checks.push('Repeated SUMO experiment: both strategies arrive, multiple transfers, zero observed collisions or stale acceptances');
  const demo={name:'Accident near J3 — advanced demo',seed:42,density:12,mode:'sumo',strategy:'partial',incidents:[{kind:'accident',edge:['J3','J6'],trigger:'approach',junction:'J3',distance:30,duration:30}]};
  const preset=await api('/scenarios',demo);report.preset=preset.id;
  const current=await api('/state');
  if(current.status==='READY'&&!current.running&&current.time===0){await api('/reset',demo);report.checks.push('Approaching-J3 accident demo staged, ready to start')}
  assert.ok((await api('/scenarios')).some(s=>s.id===preset.id));
  assert.ok((await api('/runs')).length);report.checks.push('PostgreSQL run and scenario persistence');
  browser=await chromium.launch({channel:'msedge',headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1512,height:1080}});page.on('pageerror',e=>report.pageErrors.push(String(e)));
  await page.goto(base);await page.getByText('Service connected',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Incident control',exact:true}).waitFor();
  await page.screenshot({path:path.join(root,'.qa','docker-ready.png'),fullPage:true});
  assert.deepEqual(report.pageErrors,[]);report.checks.push('Deployed frontend and WebSocket telemetry');report.passed=true;
 }catch(e){report.passed=false;report.failure=String(e);throw e}
 finally{if(browser)await browser.close();fs.mkdirSync(path.join(root,'.qa'),{recursive:true});fs.writeFileSync(path.join(root,'.qa','docker-smoke-report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2))}
})().catch(e=>{console.error(e);process.exitCode=1});
