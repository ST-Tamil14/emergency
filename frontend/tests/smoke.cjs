const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'), path=require('path');
const root=path.resolve(__dirname,'../..');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const procs=[];
async function waitFor(url){for(let i=0;i<120;i++){try{const r=await fetch(url);if(r.ok)return;}catch{}await delay(250)}throw Error('Service did not become ready: '+url)}
(async()=>{
 let browser;
 fs.mkdirSync(path.join(root,'.qa'),{recursive:true});
 const log=fs.openSync(path.join(root,'.qa','browser-services.log'),'w');
 const report={pageErrors:[],mobileOverflow:null,checks:[]};
 try{
 const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const api=spawn(python,['-m','uvicorn','app:app','--host','127.0.0.1','--port','8000'],{cwd:path.join(root,'research-service'),env:{...process.env,SIMULATION_MODE:'sumo',AGENT_MODE:'process',DATABASE_URL:'sqlite:///'+path.join(root,'.qa','browser.db')},stdio:['ignore',log,log]});procs.push(api);
 await waitFor('http://127.0.0.1:8000/api/health');
 const java=spawn('java',['-jar',path.join(root,'backend/target/corridor-backend-0.1.0.jar')],{cwd:root,env:{...process.env,RESEARCH_URL:'http://127.0.0.1:8000'},stdio:['ignore',log,log]});procs.push(java);java.on('error',()=>{});
 await waitFor('http://127.0.0.1:8080/actuator/health');
 const gateway=await fetch('http://127.0.0.1:8080/api/state').then(r=>r.json());if(!gateway.controllers)throw Error('Gateway state response invalid');report.checks.push('Spring Boot gateway');
 browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{}),args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage({viewport:{width:1512,height:1080},deviceScaleFactor:1});
 page.on('pageerror',e=>report.pageErrors.push(e.stack));
 await page.goto('http://127.0.0.1:8000');await page.getByText('Service connected').waitFor();await delay(1600);report.checks.push('Packaged UI and SUMO websocket');
 await page.screenshot({path:path.join(root,'docs/dashboard-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Start simulation',exact:true}).click();await delay(1400);
 await page.getByRole('button',{name:'Incident control',exact:true}).click();await page.getByRole('dialog').getByLabel('Incident type',{exact:true}).selectOption('readback');await page.getByRole('dialog').getByRole('button',{name:'Inject incident',exact:true}).click();
 await page.getByText('Generation E2 released',{exact:true}).waitFor({timeout:25000});report.checks.push('Fault injection and state-coupled recovery');
 await page.getByRole('button',{name:'Replay stale command'}).click();await page.getByText(/old command rejected/).waitFor();report.checks.push('Stale-command rejection');
 await page.getByRole('button',{name:'Pause',exact:true}).click();await page.evaluate(()=>window.scrollTo(0,0));await delay(300);
 await page.screenshot({path:path.join(root,'docs/dashboard-recovered.png'),fullPage:true});
 await page.getByRole('button',{name:/Inspect transfer certificates/}).click();await page.getByRole('dialog').waitFor();await page.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();report.checks.push('Certificate inspector');
 const exported=await fetch('http://127.0.0.1:8000/api/export').then(r=>r.json());fs.writeFileSync(path.join(root,'experiments/sample-run.json'),JSON.stringify(exported,null,2));
 await page.getByRole('button',{name:'Scenarios',exact:true}).click();await page.getByLabel('Scenario name').fill('Reproducible scenario');await page.getByRole('button',{name:'Save preset'}).click();await page.getByText('Scenario saved',{exact:true}).waitFor();report.checks.push('Scenario persistence');
 await page.getByRole('button',{name:'Experiments',exact:true}).click();await page.getByLabel('Seeds',{exact:true}).fill('1');await page.getByRole('button',{name:'Run comparison'}).click();
 let result;
 for(let i=0;i<160;i++){const jobs=await fetch('http://127.0.0.1:8000/api/experiments').then(r=>r.json());result=jobs.find(j=>j.mode==='sumo'&&j.status==='COMPLETE');if(result)break;await delay(500)}
 if(!result||result.results.length!==2)throw Error('SUMO comparison did not complete');report.checks.push('SUMO batch experiment');
 await delay(1700);await page.screenshot({path:path.join(root,'docs/experiments.png'),fullPage:true});
 await page.getByRole('button',{name:'Run history',exact:true}).click();await page.getByRole('button',{name:'Save current run'}).click();await page.getByRole('button',{name:'Replay',exact:true}).first().click();await page.getByText('Return to live').waitFor();await page.getByRole('button',{name:'Return to live'}).click();report.checks.push('Run persistence and recorded playback');
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));await delay(3800);await page.screenshot({path:path.join(root,'docs/dashboard-mobile.png'),fullPage:true});
 report.mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
 if(report.pageErrors.length||report.mobileOverflow)throw Error('Browser errors or horizontal overflow detected');
 report.checks.push('Responsive layout');report.passed=true;
 }catch(e){report.passed=false;report.failure=String(e);throw e;}
 finally{fs.writeFileSync(path.join(root,'experiments/browser-validation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(browser)await browser.close();for(const p of procs)p.kill('SIGTERM');fs.closeSync(log);}
})().catch(e=>{console.error(e);process.exitCode=1});
