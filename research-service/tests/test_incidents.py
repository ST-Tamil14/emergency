import pytest
from engine import Engine
from incidents import IncidentRequest


@pytest.fixture
def engine():
    e=Engine(mode='kinematic',density=0)
    e.start()
    yield e
    e.close()


def advance(e,seconds=5):
    for _ in range(round(seconds/.2)):e.tick()


def test_repeated_disruptions_preserve_entered_road(engine):
    e=engine
    e.fault('J3','readback');advance(e)
    assert e.recovery['stage']=='COMMITTED'
    original=e.route[:e.traffic.segment+2]
    e.fault('J5','partition');advance(e)
    assert e.recovery['stage']=='COMMITTED'
    assert e.recovery['generation']==3
    assert e.route[:len(original)]==original
    assert not {'J3','J5'}&set(e.route)
    assert 'J7' in e.route
    e.replay_stale()
    assert e.metrics['unsafe_acceptances']==0
    assert e.metrics['stale_rejected']==1


def test_pending_generation_is_superseded(engine):
    e=engine;e.fault('J3','readback')
    e.fault('J5','write');advance(e)
    assert e.recovery_history[0]['stage']=='SUPERSEDED'
    assert e.recovery['generation']==3
    assert e.recovery['stage']=='COMMITTED'
    assert all(t['body']['generation']==3 for t in e.certificates)
    assert not {'J3','J5'}&set(e.route)


def test_partially_committed_generation_cannot_release(engine):
    e=engine
    e.fault('J1','pedestrian');advance(e,1)
    assert any(c.generation==2 for c in e.controllers.values())
    assert e.status=='RECOVERING'
    e.fault('J3','write');advance(e,10)
    assert e.recovery_history[0]['stage']=='SUPERSEDED'
    assert not any(x['kind']=='COMMIT' and 'E2' in x['title'] for x in e.events)
    assert e.status=='ACTIVE'
    assert 'J3' not in e.route


def test_overlapping_failures_resolve_individually(engine):
    e=engine
    a=e.add_incident({'kind':'readback','controller':'J3'})
    b=e.add_incident({'kind':'partition','controller':'J3'})
    e.resolve_incident(a['id'])
    assert e.controllers['J3'].readback
    assert not e.controllers['J3'].online
    assert b['status']=='ACTIVE'
    assert 'J3' not in e.recovery['successor']


def test_current_lane_blockage_holds_then_reverifies(engine):
    e=engine;before=e.traffic.position()
    i=e.add_incident({'kind':'accident','edge':['W','J1'],'position':.7,'duration':2})
    assert e.status=='FALLBACK';advance(e,1)
    assert e.traffic.position()==before
    advance(e,5)
    assert i['status']=='RESOLVED'
    assert e.status=='ACTIVE'
    assert e.traffic.position()!=before


def test_accident_behind_vehicle_does_not_hold(engine):
    e=engine;advance(e,3)
    e.add_incident({'kind':'accident','edge':['W','J1'],'position':.1})
    assert e.status=='ACTIVE'


def test_timed_trigger_and_cancellation(engine):
    e=engine
    first=e.add_incident({'kind':'closure','edge':['J3','J6'],'trigger':'time','at':2})
    second=e.add_incident({'kind':'readback','controller':'J1','trigger':'time','at':2})
    e.resolve_incident(second['id']);advance(e,1)
    assert first['status']=='SCHEDULED';advance(e,1)
    assert first['activated_at']==2
    assert second['status']=='CANCELLED'
    assert e.controllers['J1'].readback


def test_approach_trigger_blocks_outgoing_road_without_teleport(engine):
    e=engine
    i=e.add_incident({'kind':'closure','edge':['J3','J6'],'trigger':'approach','junction':'J3','distance':30})
    for _ in range(200):
        before=e.traffic.position();prefix=e.route[:e.traffic.segment+2]
        e.tick()
        if i['status']=='ACTIVE':break
    assert i['status']=='ACTIVE'
    assert e.traffic.current_target()=='J3'
    assert e.traffic.position()==before
    advance(e)
    assert e.route[:len(prefix)]==prefix
    assert e.recovery['stage']=='COMMITTED'
    assert ('J3','J6') not in list(zip(e.route,e.route[1:]))


def test_no_feasible_route_explains_hold(engine):
    e=engine
    e.add_incident({'kind':'closure','edge':['J6','E']})
    e.add_incident({'kind':'closure','edge':['J8','E']})
    assert e.status=='FALLBACK'
    assert 'Every legal' in e.decision['reason']
    advance(e,1);assert e.traffic.speed==0


def test_congestion_uses_time_not_hops(engine):
    e=engine
    e.add_incident({'kind':'congestion','edge':['J2','J3'],'intensity':.9})
    assert 'J3' not in e.recovery['successor']
    assert e.alternatives[0]['eta']<next(o['eta'] for o in e.route_options() if o['route']==e.route)
    assert len(e.alternatives)<=3


def test_directed_closure_does_not_block_reverse(engine):
    e=engine;e.add_incident({'kind':'closure','edge':['J3','J2']})
    assert e.status=='ACTIVE'
    assert e.recovery is None


def test_hysteresis_retains_similar_route(engine):
    e=engine;e.add_incident({'kind':'congestion','edge':['J2','J3'],'intensity':.1})
    assert e.status=='ACTIVE'
    assert e.recovery is None


def test_invalid_input_does_not_mutate(engine):
    e=engine
    for data in ({'kind':'bad'},{'kind':'closure','edge':['W','E']},{'kind':'readback','controller':'J99'},{'kind':'accident','edge':['J3','J6'],'lane':1},{'kind':'readback','controller':'J3','trigger':'time'}):
        with pytest.raises(ValueError):e.add_incident(data)
    assert not e.incidents


def test_export_contains_incident_and_generation_history(engine):
    e=engine;e.fault('J3','readback');advance(e)
    snapshot=e.export()['snapshot']
    assert snapshot['incidents'][0]['status']=='ACTIVE'
    assert snapshot['recovery_history'][0]['stage']=='COMMITTED'
    assert snapshot['eta'] is not None
    assert e.export()['schema_version']==2


def test_unrelated_failures_do_not_hold_final_entered_road(engine):
    e=engine
    while e.traffic.current_target()!='E':e.tick()
    for j in e.controllers:e.fault(j,'readback')
    assert e.status=='ACTIVE'
    assert e.route_options()[0]['route']==e.route
