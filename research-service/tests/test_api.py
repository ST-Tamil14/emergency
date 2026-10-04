from fastapi.testclient import TestClient
import app
import pytest
from store import Store


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch,tmp_path):
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+str(tmp_path/'api-tests.db'))
    monkeypatch.setattr(app,'store',Store())

def test_api_lifecycle(monkeypatch):
    monkeypatch.setenv('SIMULATION_MODE','kinematic')
    with TestClient(app.app) as c:
        assert c.get('/api/health').status_code==200
        assert c.get('/api/state').json()['status']=='READY'
        assert c.post('/api/reset',json={'density':-1}).status_code==422
        assert c.post('/api/control/unknown').status_code==409
        assert c.post('/api/control/start',json={}).status_code==200
        for _ in range(20):c.post('/api/control/step',json={})
        assert c.post('/api/fault',json={'controller':'J3','kind':'readback'}).status_code==200
        for _ in range(30):c.post('/api/control/step',json={})
        assert c.get('/api/state').json()['recovery']['stage']=='COMMITTED'
        assert c.post('/api/control/replay-stale',json={}).json()['metrics']['stale_rejected']==1
        assert c.post('/api/control/save',json={}).status_code==200
        assert c.get('/api/runs').json()
        with c.websocket_connect('/ws') as ws:assert 'controllers' in ws.receive_json()


def test_incident_api_validation_and_individual_resolution(monkeypatch):
    monkeypatch.setenv('SIMULATION_MODE','kinematic')
    with TestClient(app.app) as c:
        assert c.post('/api/incidents',json={'kind':'closure','edge':['W','E']}).status_code==422
        assert c.post('/api/incidents',json={'kind':'closure','edge':['J3','J6'],'lane':1}).status_code==422
        s=c.post('/api/incidents',json={'kind':'readback','controller':'J3'}).json()
        first=s['incidents'][0]['id']
        s=c.post('/api/incidents',json={'kind':'partition','controller':'J5'}).json()
        assert len(s['incidents'])==2
        assert s['recovery_history'][0]['stage']=='SUPERSEDED'
        assert c.post('/api/incidents/unknown/resolve').status_code==409
        s=c.post(f'/api/incidents/{first}/resolve').json()
        assert s['incidents'][0]['status']=='RESOLVED'
        assert s['incidents'][1]['status']=='ACTIVE'
        assert c.post('/api/control/restore').status_code==409
        s=c.post('/api/controllers/J5/restore').json()
        assert all(i['status']=='RESOLVED' for i in s['incidents'])
        saved=c.get('/api/runs/'+s['id']).json()
        assert saved['snapshot']['incidents']==s['incidents']


def test_scenario_preserves_schedule(monkeypatch):
    monkeypatch.setenv('SIMULATION_MODE','kinematic')
    with TestClient(app.app) as c:
        config={'mode':'kinematic','incidents':[{'kind':'closure','edge':['J3','J6'],'trigger':'time','at':2}]}
        result=c.post('/api/scenarios',json=config)
        assert result.status_code==200
        assert c.get('/api/scenarios').json()[0]['incidents'][0]['at']==2
        s=c.post('/api/reset',json=config).json()
        assert s['incidents'][0]['status']=='SCHEDULED'
        for _ in range(10):s=c.post('/api/control/step').json()
        assert s['incidents'][0]['status']=='ACTIVE'


def test_repeated_experiment_runs_both_strategies(monkeypatch):
    job={'id':'repeated-validation','status':'RUNNING','cancel':False,'progress':0,'results':[],'scenario':'repeated'}
    monkeypatch.setattr(app,'jobs',{job['id']:job})
    app.batch_worker(job['id'],1,'kinematic',0,'repeated')
    assert job['status']=='COMPLETE'
    assert job['progress']==1
    assert {r['strategy'] for r in job['results']}=={'partial','whole'}
    for result in job['results']:
        assert result['status']=='COMPLETE'
        assert result['recovery_count']>=2
        assert result['reconfigured_total']>=result['reconfigured']
        assert result['unsafe_acceptances']==0
    assert app.store.get(job['id'])['results']==job['results']
