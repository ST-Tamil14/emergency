"""Run from project root: .venv/Scripts/python.exe experiments/validate.py"""
import sys, json, time, os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'research-service'))
from engine import Engine

def run(mode,seed,strategy,kind):
    e=Engine(seed=seed,density=8,mode=mode,strategy=strategy)
    start=time.perf_counter()
    try:
        e.start()
        for step in range(900):
            if step==20:e.fault('J3',kind)
            e.tick()
            if not e.running:break
        if any(c.generation>1 for c in e.controllers.values()):e.replay_stale()
        return {'engine':mode,'seed':seed,'strategy':strategy,'fault':kind,'outcome':e.status,'simulated_seconds':e.time,'wall_seconds':round(time.perf_counter()-start,3),'collisions':getattr(e.traffic,'collision_count',None),**e.metrics}
    finally:e.close()

if __name__=='__main__':
    results=[]
    for mode in ['kinematic','sumo']:
        for seed in [11,42,73]:
            for strategy in ['whole','partial']:
                r=run(mode,seed,strategy,'readback');results.append(r)
                print(mode,seed,strategy,r['outcome'],r['simulated_seconds'])
    for kind in ['write','configuration','partition','pedestrian']:
        r=run('sumo',42,'partial',kind);results.append(r);print('sumo',kind,r['outcome'])
    out=root/'experiments'/'validation-results.json';out.write_text(json.dumps({'algorithm_version':'0.1.0','agent_mode':os.getenv('AGENT_MODE','inprocess'),'scope':'Bounded six-junction simulation; not field validation','results':results},indent=2))
    assert all(r['outcome']=='COMPLETE' for r in results)
    assert all(r['stale_rejected']==1 and r['unsafe_acceptances']==0 for r in results)
    assert all(r['collisions'] in [None,0] for r in results)
