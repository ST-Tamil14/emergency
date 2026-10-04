from engine import Engine

def test_recovery_preserves_entered_edge_and_fences():
    e=Engine(mode='kinematic');e.start()
    for _ in range(20):e.tick()
    old=e.route[:e.traffic.segment+2];e.fault('J3','readback')
    for _ in range(30):e.tick()
    assert e.recovery['stage']=='COMMITTED';assert e.route[:len(old)]==old
    assert 'J3' not in e.route;assert 'J5' in e.route
    e.replay_stale();assert e.metrics['stale_rejected']==1
    assert e.metrics['unsafe_acceptances']==0

def test_failed_current_target_falls_back():
    e=Engine(mode='kinematic');e.start();e.fault('J1','readback');e.tick()
    assert e.status=='FALLBACK';assert e.traffic.speed==0

def test_pedestrian_delays_commit():
    e=Engine(mode='kinematic');e.start();e.fault('J1','pedestrian')
    for _ in range(20):e.tick()
    assert e.status=='RECOVERING';assert e.traffic.speed==0
    for _ in range(25):e.tick()
    assert e.recovery['stage']=='COMMITTED'

def test_committed_prefix_is_not_reconfigured():
    e=Engine(mode='kinematic');e.start()
    for _ in range(60):e.tick()
    assert e.traffic.segment>=1
    generation=e.controllers['J1'].generation
    e.fault('J3','readback')
    assert 'J1' in e.prefix;assert 'J1' not in e.recovery['scope']
    for _ in range(30):e.tick()
    assert e.controllers['J1'].generation==generation
    assert e.metrics['prefix_mutations']==0
