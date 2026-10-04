import asyncio, threading, uuid, os, traceback
from contextlib import asynccontextmanager, suppress
from typing import Literal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, Field
from engine import Engine
from store import Store
from incidents import IncidentRequest

lock=threading.RLock(); engine=None; store=Store(); jobs={}
class Scenario(BaseModel):
    name:str=Field(default='Downtown emergency corridor',max_length=100)
    seed:int=Field(default=42,ge=0,le=100000)
    density:int=Field(default=12,ge=0,le=60)
    mode:Literal['sumo','kinematic']='sumo'
    strategy:Literal['partial','whole']='partial'
    incidents:list[IncidentRequest]=Field(default_factory=list,max_length=100)
class Fault(BaseModel):
    controller:Literal['J1','J2','J3','J4','J5','J6','J7','J8']='J3'
    kind:Literal['readback','write','configuration','partition','pedestrian']='readback'
class Batch(BaseModel):
    seeds:int=Field(default=3,ge=1,le=20)
    mode:Literal['sumo','kinematic']='sumo'
    density:int=Field(default=12,ge=0,le=60)
    scenario:Literal['single','repeated']='single'

async def ticker():
    while True:
        await asyncio.sleep(.2)
        try:
            with lock:
                if engine:
                    was=engine.running; revision=engine.incident_revision; engine.tick()
                    if (was and not engine.running) or revision!=engine.incident_revision or (engine.running and round(engine.time*5)%25==0):store.save(engine.id,'run',engine.export())
        except Exception as e:
            traceback.print_exc()
            with lock:
                engine.running=False; engine.status='ERROR';engine.event('ERROR','Simulation stopped',str(e))

@asynccontextmanager
async def lifespan(app):
    global engine
    engine=Engine(mode=os.getenv('SIMULATION_MODE','sumo'),durable_dir='./state')
    for job in store.list('batch'):
        if job.get('status')=='RUNNING':
            job['status']='INTERRUPTED';job['error']='Service restarted; partial results retained. Start a new comparison.'
            store.save(job['id'],'batch',job)
    task=asyncio.create_task(ticker())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):await task
    store.save(engine.id,'run',engine.export())
    engine.close()

app=FastAPI(title='Corridor Research Service',lifespan=lifespan)
@app.get('/api/health')
def health():return {'status':'ok','version':'0.2.0'}
@app.get('/api/state')
def state():
    with lock:return engine.snapshot()
@app.post('/api/reset')
def reset(s:Scenario):
    global engine
    with lock:
        try:new=Engine(s.seed,s.density,s.mode,s.strategy,durable_dir='./state')
        except Exception as e:raise HTTPException(400,f'Could not initialize {s.mode}: {e}')
        if engine:
            store.save(engine.id,'run',engine.export());engine.close()
        engine=new
        for incident in s.incidents:engine.add_incident(incident.model_dump())
        return engine.snapshot()
@app.post('/api/control/{action}')
def control(action:str):
    with lock:
        try:
            if action=='start':engine.start()
            elif action=='pause':engine.running=False
            elif action=='step':
                if engine.status in ['COMPLETE','TIMEOUT','ERROR']:raise ValueError('Reset this completed run')
                engine.start();engine.tick();engine.running=False
            elif action=='restore':raise ValueError('Resolve an incident or select /api/controllers/{controller}/restore')
            elif action=='replay-stale':engine.replay_stale()
            elif action=='save':store.save(engine.id,'run',engine.export())
            else:raise ValueError('Unknown action')
            return engine.snapshot()
        except ValueError as e:raise HTTPException(409,str(e))
@app.post('/api/fault')
def fault(f:Fault):
    with lock:
        try:engine.fault(f.controller,f.kind);store.save(engine.id,'run',engine.export());return engine.snapshot()
        except ValueError as e:raise HTTPException(409,str(e))
@app.post('/api/incidents')
def incident(request:IncidentRequest):
    with lock:
        try:
            engine.add_incident(request.model_dump());store.save(engine.id,'run',engine.export());return engine.snapshot()
        except ValueError as e:raise HTTPException(409,str(e))
@app.post('/api/incidents/{id}/resolve')
def resolve_incident(id:str):
    with lock:
        try:
            engine.resolve_incident(id);store.save(engine.id,'run',engine.export());return engine.snapshot()
        except ValueError as e:raise HTTPException(409,str(e))
@app.post('/api/controllers/{controller}/restore')
def restore_controller(controller:str):
    with lock:
        try:engine.restore(controller);store.save(engine.id,'run',engine.export());return engine.snapshot()
        except ValueError as e:raise HTTPException(409,str(e))
@app.get('/api/export')
def export():
    with lock:return engine.export()
@app.get('/api/runs')
def runs():return store.list('run')
@app.get('/api/runs/{id}')
def run(id:str):
    r=store.get(id)
    if not r:raise HTTPException(404,'Run not found')
    return r
@app.get('/api/scenarios')
def scenarios():return store.list('scenario')
@app.post('/api/scenarios')
def save_scenario(s:Scenario):
    id=uuid.uuid4().hex[:12];store.save(id,'scenario',s.model_dump());return {'id':id}
@app.websocket('/ws')
async def websocket(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            with lock:s=engine.snapshot()
            await ws.send_json(s);await asyncio.sleep(.2)
    except (WebSocketDisconnect,RuntimeError):pass

def batch_worker(id,seeds,mode,density,scenario):
    job=jobs[id]
    try:
        for seed in range(seeds):
            for strategy in ['whole','partial']:
                if job['cancel']:job['status']='CANCELLED';return
                e=Engine(seed=seed,density=density,mode=mode,strategy=strategy)
                try:
                    e.start()
                    schedule=[{'kind':'readback','controller':'J3','trigger':'time','at':4}]
                    if scenario=='repeated':schedule += [{'kind':'partition','controller':'J5','trigger':'time','at':8}, {'kind':'congestion','edge':['J8','E'],'intensity':.7,'duration':20,'trigger':'time','at':12}]
                    for incident in schedule:e.add_incident(incident)
                    for step in range(3000):
                        if job['cancel']:job['status']='CANCELLED';return
                        e.tick()
                        if not e.running:break
                    if any(c.generation>1 for c in e.controllers.values()):e.replay_stale()
                    result={'seed':seed,'strategy':strategy,'scenario':scenario,'mode':e.traffic.name,'elapsed':e.time,'status':e.status,'collisions':getattr(e.traffic,'collision_count',None),**e.metrics}
                    job['results'].append(result);job['progress']=len(job['results'])/(seeds*2)
                    store.save(id,'batch',job)
                    store.save(e.id,'run',e.export())
                finally:e.close()
        job['status']='COMPLETE'
    except Exception as exc:job['status']='ERROR';job['error']=str(exc)
    finally:store.save(id,'batch',job)
@app.post('/api/experiments')
def experiment(b:Batch):
    if any(j['status']=='RUNNING' for j in jobs.values()):raise HTTPException(409,'An experiment is already running')
    id=uuid.uuid4().hex[:12];jobs[id]={'id':id,'status':'RUNNING','cancel':False,'progress':0,'results':[],'mode':b.mode,'density':b.density,'scenario':b.scenario}
    store.save(id,'batch',jobs[id])
    threading.Thread(target=batch_worker,args=(id,b.seeds,b.mode,b.density,b.scenario),daemon=True).start();return jobs[id]
@app.get('/api/experiments')
def experiments():
    saved={x['id']:x for x in store.list('batch')};saved.update(jobs);return list(saved.values())
@app.post('/api/experiments/{id}/cancel')
def cancel(id:str):
    if id not in jobs:raise HTTPException(404,'Active job not found')
    jobs[id]['cancel']=True;return jobs[id]

# Packaged single-service mode: serve the already-built UI when present.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
_ui = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
if _ui.is_dir():
    app.mount('/', StaticFiles(directory=str(_ui), html=True), name='frontend')
