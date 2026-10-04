import os
from engine import Engine

def test_process_agents_recover(monkeypatch):
    monkeypatch.setenv('AGENT_MODE','process')
    e=Engine(mode='kinematic')
    try:
        e.start()
        for _ in range(20):e.tick()
        e.fault('J3','readback')
        for _ in range(30):e.tick()
        assert e.recovery['stage']=='COMMITTED'
        e.replay_stale();assert e.metrics['stale_rejected']==1
        assert len({c._process.pid for c in e.controllers.values()})==8
    finally:e.close()
