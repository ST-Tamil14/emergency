import copy
from protocol import Controller, Authority, digest

def prepared(tmp_path=None):
    c=Controller('J1','test','run',str(tmp_path) if tmp_path else None);a=Authority();c.observe(1)
    cap={'run':'run','controller':'J1','generation':2,'capability':c.capability()}
    assert c.prepare(cap)
    b={'run':'run','controller':'J1','generation':2,'capsule':digest(cap),'capability':c.capability(),'issued':1,'expires':2,'evidence':c.evidence(1),'vehicle_before_frontier':True}
    return c,a,a.issue(b)

def cmd(c,g=2):return {'run':'run','generation':g,'sequence':0,'action':'GREEN','native':c.native('GREEN'),'capsule':c.committed_capsule}

def test_prepared_does_not_actuate():
    c,a,t=prepared();assert not c.execute(cmd(c),1,True);assert c.phase=='RED'
def test_valid_transfer_and_stale_rejection():
    c,a,t=prepared();assert c.commit(t,a,1);assert c.execute(cmd(c),1,True)
    assert not c.execute(cmd(c,1),1,True);assert not c.execute(cmd(c),1,True)
def test_tamper_rejected():
    c,a,t=prepared();t['body']['generation']=3;assert not c.commit(t,a,1)
def test_expired_certificate():
    c,a,t=prepared();c.observe(3);assert not c.commit(t,a,3)
def test_state_changes_after_signing():
    c,a,t=prepared();c.occupied=True;assert not c.commit(t,a,1)
def test_capability_drift_after_preparation():
    c,a,t=prepared();c.config+=1;assert not c.commit(t,a,1)
def test_dependencies_gate_actuation():
    c,a,t=prepared();assert c.commit(t,a,1);assert not c.execute(cmd(c),1,False)
def test_restart_preserves_fence_and_withholds():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        c,a,t=prepared(d);assert c.commit(t,a,1)
        restored=Controller('J1','test','run',d);assert restored.generation==2
        assert not restored.execute(cmd(restored,1),1,True)
        assert not restored.execute(cmd(restored,2),1,True)
def test_wrong_run_and_controller():
    c,a,t=prepared();b=t['body'];b['run']='other';assert not c.commit(a.issue(b),a,1)
def test_clearance_and_freshness():
    c,a,t=prepared();c.pedestrian_until=3;assert not c.commit(t,a,1)
    c.pedestrian_until=0;c.observed_at=-2;assert not c.commit(t,a,1)
def test_actuation_rechecks_evidence():
    c,a,t=prepared();assert c.commit(t,a,1);c.occupied=True;assert not c.execute(cmd(c),1,True)
def test_future_evidence_rejected():
    c,a,t=prepared();c.observed_at=5;assert not c.commit(t,a,1)

def test_capability_drift_after_commit_blocks_execution():
    c,a,t=prepared();assert c.commit(t,a,1);c.config+=1;assert not c.execute(cmd(c),1,True)

def test_stale_readback_blocks_new_actuation():
    c,a,t=prepared();assert c.commit(t,a,1);assert not c.execute(cmd(c),3,True)

def test_commanded_red_is_not_evidence_of_observed_red():
    c,a,t=prepared();c.phase='RED';c.observe(1,'YELLOW')
    assert not c.ready(1)[0]
    assert not c.commit(t,a,1)


def test_wrong_native_interface_is_rejected():
    c,a,t=prepared();assert c.commit(t,a,1)
    command=cmd(c);command['native']={'operation':'select_program','program':'priority'}
    assert not c.execute(command,1,True)

def test_browser_numeric_roundtrip_preserves_signature_and_binding():
    authority=Authority()
    token=authority.issue({'issued':1.0,'evidence':{'observed_at':0.0},'values':[2.0,0.2]})
    browser_body={'issued':1,'evidence':{'observed_at':0},'values':[2,0.2]}
    assert digest(token['body'])==digest(browser_body)
    token['body']=browser_body
    assert authority.valid(token)
    token['body']['issued']=2
    assert not authority.valid(token)
