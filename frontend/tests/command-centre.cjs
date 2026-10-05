const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),base='http://127.0.0.1:8019',out=path.join(root,'.qa','ui-tour');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const report={pages:[],checks:[],pageErrors:[]};
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const log=fs.openSync(path.join(out,'service.log'),'w');
 const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const service=spawn(python,['-m','uvicorn','app:app','--host','127.0.0.1','--port','8019'],{cwd:path.join(root,'research-service'),windowsHide:true,env:{...process.env,SIMULATION_MODE:'sumo',AGENT_MODE:'inprocess',DATABASE_URL:'sqlite:///'+path.join(out,'ui.db')},stdio:['ignore',log,log]});
 let browser,context,page,video,holdTelemetry=false;
 const api=async(p,body)=>{const r=await fetch(base+'/api'+p,body===undefined?{}:{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});assert.equal(r.status,200,await r.clone().text());return r.json()};
 try{
  let ready=false;for(let i=0;i<120;i++){try{if((await fetch(base+'/api/health')).ok){ready=true;break}}catch{}await sleep(250)}assert.ok(ready,'isolated test service started');
  await api('/reset',{mode:'sumo',density:4});
  browser=await chromium.launch({channel:process.env.BROWSER_CHANNEL||'msedge',headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  context=await browser.newContext({viewport:{width:1600,height:1000},recordVideo:{dir:out,size:{width:1280,height:800}}});
  page=await context.newPage();video=page.video();page.on('pageerror',e=>report.pageErrors.push(String(e)));
  await page.routeWebSocket('**/ws',route=>{const server=route.connectToServer();server.onMessage(message=>{if(!holdTelemetry)route.send(message)})});
  await page.goto(base);await page.getByText('Service connected',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Start simulation',exact:true}).click();await sleep(1800);
  await page.getByRole('button',{name:'Incident control',exact:true}).click();
  await page.getByRole('dialog').getByLabel('Incident type',{exact:true}).selectOption('readback');
  await page.getByRole('dialog').getByRole('button',{name:'Inject incident',exact:true}).click();
  await page.getByText('Generation E2 released',{exact:true}).waitFor({timeout:30000});
  await sleep(1600);await page.getByRole('button',{name:'Pause',exact:true}).click();
  await page.getByRole('button',{name:'Replay stale command'}).click();
  await page.getByText(/old command rejected/).waitFor();
  report.checks.push('Actual SUMO motion, incident injection, verified E2 recovery and stale-command rejection');
  await api('/control/save',{});
  const pages=['Command Centre','Missions','Route Planner','Incident Centre','Controllers','Hospitals','Scenarios','Experiments','Analytics','Run history'];
  for(const [i,label] of pages.entries()){
   await page.getByRole('navigation').getByRole('button',{name:label,exact:true}).click();await sleep(1000);
   assert.ok(await page.locator('h1').innerText());
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,label+' desktop overflow');
   await page.screenshot({path:path.join(out,`${String(i+1).padStart(2,'0')}-${label.toLowerCase().replaceAll(' ','-')}.png`),fullPage:true});
   report.pages.push(label);
   if(label==='Route Planner'){
    await page.locator('.candidate-card').first().click();await page.getByText('Alternative preview · not activated',{exact:true}).waitFor();
    report.checks.push('Alternative route preview is labeled and does not activate a plan');
   }
   if(label==='Controllers'){
    await page.locator('.controller-card').filter({hasText:'J5'}).click();await page.getByText('Selected junction · J5',{exact:true}).waitFor();
    report.checks.push('Controller selection updates the evidence inspector');
   }
  }
  await page.getByRole('button',{name:'Replay',exact:true}).first().click();
  await page.getByRole('button',{name:'Play replay',exact:true}).click();await sleep(1200);
  assert.ok(Number(await page.getByLabel('Replay time').inputValue())>0,'replay advances by recorded timestamps');
  await page.getByRole('button',{name:'Pause replay',exact:true}).click();
  assert.ok(await page.getByRole('button',{name:'Start simulation',exact:true}).isDisabled());
  await page.getByRole('button',{name:'Return to live',exact:true}).click();report.checks.push('Animated recorded replay and disabled mutations during replay');
  await page.getByRole('button',{name:'Follow ambulance',exact:true}).click();await sleep(700);
  await page.getByRole('button',{name:'Reset camera',exact:true}).click();
  await page.getByRole('button',{name:'Top-down view',exact:true}).click();await sleep(700);
  await page.getByRole('button',{name:'Reset camera',exact:true}).click();
  await page.getByRole('button',{name:'Reduce animation',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'Reduce animation',exact:true}).getAttribute('aria-pressed'),'true');
  holdTelemetry=true;await page.getByText(/Telemetry is stale/).waitFor({timeout:12000});
  assert.ok(await page.getByRole('button',{name:'Start simulation',exact:true}).isDisabled());
  holdTelemetry=false;await page.getByText(/Telemetry is stale/).waitFor({state:'hidden'});
  report.checks.push('Camera controls, reduced motion, stale telemetry interlock and reconnection');
  await page.setViewportSize({width:390,height:844});
  for(const label of pages){await page.getByRole('navigation').getByRole('button',{name:label,exact:true}).click();await sleep(350);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,label+' mobile overflow')}
  await page.getByRole('navigation').getByRole('button',{name:'Command Centre',exact:true}).click();
  await page.screenshot({path:path.join(out,'mobile-command-centre.png'),fullPage:true});
  await page.getByRole('button',{name:'Incident control',exact:true}).click();await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);
  assert.deepEqual(report.pageErrors,[]);report.checks.push('All ten pages fit mobile, modal Escape dismissal, no browser exceptions');report.passed=true;
 }catch(e){report.passed=false;report.failure=String(e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw e}
 finally{if(context)await context.close();if(video)await video.saveAs(path.join(out,'command-centre-tour.webm'));if(browser)await browser.close();service.kill();fs.closeSync(log);fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2))}
})().catch(e=>{console.error(e);process.exitCode=1});
