"""Opt-in integration checks against the real SUMO binary."""
import os
import pytest
from engine import Engine

pytestmark=pytest.mark.skipif(os.getenv('RUN_SUMO_TESTS')!='1',reason='Set RUN_SUMO_TESTS=1 to exercise real SUMO')


@pytest.fixture
def engine():
    e=Engine(mode='sumo',density=0)
    e.start()
    yield e
    e.close()


def until(e,predicate,limit=500):
    for _ in range(limit):
        e.tick()
        if predicate():return
    raise AssertionError(f'Timed out: {e.status} / {e.decision} / {e.traffic.position()}')


def test_sumo_repeated_incidents_and_arrival(engine):
    e=engine
    first=e.add_incident({'kind':'closure','edge':['J3','J6']})
    until(e,lambda:e.status=='ACTIVE')
    e.fault('J5','readback')
    until(e,lambda:e.status=='ACTIVE')
    assert e.recovery['generation']==3
    assert 'J5' not in e.route
    assert ('J3','J6') not in list(zip(e.route,e.route[1:]))
    assert 'emergency' in e.traffic.conn.lane.getDisallowed('J3_J6_0')
    e.resolve_incident(first['id'])
    assert not e.traffic.conn.lane.getDisallowed('J3_J6_0')
    until(e,lambda:e.status=='COMPLETE',1000)
    assert e.traffic.collision_count==0


def test_sumo_approach_trigger_changes_exit(engine):
    e=engine
    i=e.add_incident({'kind':'accident','edge':['J3','J6'],'trigger':'approach','junction':'J3','distance':30})
    until(e,lambda:i['status']=='ACTIVE')
    prefix=e.route[:e.traffic.segment+2]
    assert e.traffic.current_target()=='J3'
    until(e,lambda:e.status=='ACTIVE')
    assert e.route[:len(prefix)]==prefix
    assert 'J8' in e.route
    until(e,lambda:e.status=='COMPLETE',1000)


def test_sumo_incident_inside_junction_defers_until_exit(engine):
    e=engine
    until(e,lambda:not e.traffic.can_reroute())
    e.fault('J3','readback')
    assert e.plan_deferred
    until(e,lambda:e.status=='ACTIVE')
    assert not e.plan_deferred
    assert 'J3' not in e.route
    until(e,lambda:e.status=='COMPLETE',1000)


def test_sumo_current_road_closure_recovers_after_expiry(engine):
    e=engine
    i=e.add_incident({'kind':'closure','edge':['W','J1'],'duration':3})
    assert e.status=='FALLBACK'
    until(e,lambda:i['status']=='RESOLVED')
    until(e,lambda:e.status=='ACTIVE')
    until(e,lambda:e.status=='COMPLETE',1000)
