import copy, uuid, time, math, os
from agents import ControllerAgent
from recovery import IncidentRecovery
import networkx as nx
from protocol import Controller, Authority, digest
from traffic import NODES, PAIRS, BASE, KinematicTraffic, SumoTraffic

class Engine(IncidentRecovery):
    def __init__(self, seed=42, density=12, mode='sumo', strategy='partial', durable_dir=None):
        self.id=uuid.uuid4().hex[:12]; self.seed=seed; self.density=density; self.strategy=strategy
        self.authority=Authority(); self.time=0.; self.status='READY'; self.running=False
        factory=ControllerAgent if os.getenv('AGENT_MODE','inprocess')=='process' else Controller
        self.controllers={j:factory(id=j,profile=['Full readback','Limited adapter','Gateway adapter'][i%3],run=self.id,durable_dir=durable_dir) for i,j in enumerate(n for n in NODES if n.startswith('J'))}
        self.obligations=[{'id':f'movement-{j}','controller':j,'requires':['readback','write','configuration','clearance'],'completed':False} for j in BASE if j.startswith('J')]
        try:
            self.traffic=SumoTraffic(seed,density) if mode=='sumo' else KinematicTraffic(seed,density)
        except Exception:
            for c in self.controllers.values():
                if isinstance(c,ControllerAgent):c.close()
            raise
        self.events=[]; self.frames=[]; self.certificates=[]; self.route=BASE[:]; self.prefix=[]
        self.recovery=None; self.failed=None; self.clearance={}; self.faults=[]; self.wall_started=time.perf_counter()
        self.init_incidents()
        self.metrics={'reconfigured':0,'recovery_seconds':None,'stale_rejected':0,'unsafe_acceptances':0,'fallbacks':0,'prefix_mutations':0}
        self.metrics.update(recovery_count=0,reconfigured_total=0,total_recovery_seconds=0)
        self.event('SYSTEM','Corridor initialized',f'{self.traffic.name} · seed {seed} · local verification enabled')
    def event(self,kind,title,detail='',controller=None):
        self.events.append({'id':len(self.events)+1,'time':round(self.time,2),'kind':kind,'title':title,'detail':detail,'controller':controller})
    def start(self):
        if self.status in ['COMPLETE','TIMEOUT','ERROR']: raise ValueError('Reset before starting this run')
        self.running=True
        if self.status=='READY': self.status='ACTIVE'; self.event('START','Emergency corridor activated','Generation E1')
    def freeze_clear(self,j):
        c=self.controllers[j]; c.freeze()
        if c.phase=='GREEN': c.phase='YELLOW'; self.clearance[j]=self.time+3
        elif c.phase=='YELLOW': self.clearance.setdefault(j,self.time+3)
        else: self.clearance.setdefault(j,self.time+.4)
    def replay_stale(self):
        cs=[c for c in self.controllers.values() if c.generation>1]
        if not cs: raise ValueError('Complete a generation transfer before replaying an old command')
        c=cs[0]; ok=c.execute({'run':self.id,'generation':c.generation-1,'sequence':999,'action':'GREEN'},self.time,True)
        self.metrics['stale_rejected']+=int(not ok); self.metrics['unsafe_acceptances']+=int(ok)
        self.event('REJECT' if not ok else 'ERROR',f'{c.id} · old command '+('rejected' if not ok else 'accepted'),c.last_reason,c.id)
    def tick(self,dt=.2):
        if not self.running:return
        self.time=round(self.time+dt,6)
        self.process_incidents()
        if self.plan_deferred and self.traffic.can_reroute():self.plan_recovery()
        for j,c in self.controllers.items():
            if j in self.clearance:
                end=self.clearance[j]
                if self.time>=end: c.phase='RED'
                if self.time>=end+.4: del self.clearance[j]
            c.observe(self.time,self.traffic.observed_phase(j,c.phase),self.traffic.occupancy(j))
        if self.recovery and self.recovery['stage']=='CLEARANCE' and self.status=='RECOVERING' and not self.plan_deferred:
            r=self.recovery
            for n in r['candidates']:
                c=self.controllers[n]
                if c.mode=='COMMITTED' and c.generation==r['generation']: continue
                ready,reason=c.ready(self.time); c.last_reason=reason
                if ready and n not in self.clearance:
                    body={'run':self.id,'controller':n,'generation':r['generation'],'capsule':digest(c.prepared),'capability':c.capability(), 'frontier':r['frontier'],'suffix':r['successor'],'issued':self.time,'expires':self.time+1,'evidence':c.evidence(self.time),'vehicle_before_frontier':self.traffic.current_target()==r['frontier']}
                    token=self.authority.issue(body)
                    if c.commit(token,self.authority,self.time):
                        self.certificates.append(token); self.event('VERIFY',f'{n} · state transfer verified','Generation persisted; waiting for dependent controllers',n)
            if r['revision']==self.incident_revision and self.traffic.can_reroute() and all(self.controllers[n].mode=='COMMITTED' and self.controllers[n].generation==r['generation'] for n in r['candidates']):
                self.traffic.set_route(r['successor']); self.route=r['successor']; self.status='ACTIVE'
                self.metrics['recovery_seconds']=round(self.time-r['started'],3)
                self.metrics['recovery_count']+=1
                self.metrics['total_recovery_seconds']=round(self.metrics['total_recovery_seconds']+self.metrics['recovery_seconds'],3)
                r['stage']='COMMITTED'; r['ended']=self.time; self.event('COMMIT',f'Generation E{r["generation"]} released','All required successor controllers have locally committed')
            elif self.time>max(r['started']+15,max((self.controllers[n].pedestrian_until+5 for n in r['candidates']),default=0)):
                self.status='FALLBACK';self.metrics['fallbacks']+=1;r['stage']='FALLBACK'
                for n in r['candidates']: self.controllers[n].fallback('Recovery timeout; successor movement withheld')
                self.decision={'reason':'Verification deadline exceeded: '+ '; '.join(f'{n}: {self.controllers[n].last_reason}' for n in r['candidates']),'eta_change':None,'next_action':'Resolve unavailable controllers or reset this scenario; successor movement remains withheld.'}
                self.event('FALLBACK','Recovery deadline exceeded','Successor actuation withheld')
        # Local signal model. Only the route's next intersection receives emergency green.
        target=self.traffic.current_target()
        if self.status=='ACTIVE':
            for j,c in self.controllers.items():
                if j==target and j not in self.clearance:
                    c.execute({'run':self.id,'generation':c.generation,'sequence':c.sequence+1,'action':'GREEN','native':c.native('GREEN'),'capsule':c.committed_capsule},self.time,True)
                elif c.phase=='GREEN' and j!=target:
                    c.phase='YELLOW'; self.clearance[j]=self.time+3
        self.traffic.step(dt,self.status in ['RECOVERING','FALLBACK'] or bool(self.traffic.current_blockage()),self.controllers)
        if self.traffic.done:
            self.status='COMPLETE';self.running=False; self.event('COMPLETE','Ambulance reached destination',f'{self.time:.1f} simulated seconds')
        if self.time>=600:
            self.running=False;self.status='TIMEOUT';self.event('TIMEOUT','Scenario time limit reached')
        if self.traffic.done:
            for incident in self.incidents:
                if incident['status']=='SCHEDULED':incident['status']='MISSED'
        if int(round(self.time*5))%5==0:
            self.update_eta()
            if len(self.frames)<601:self.frames.append(self.snapshot(include_history=False))
    def snapshot(self,include_history=True):
        out={'id':self.id,'time':round(self.time,1),'status':self.status,'running':self.running,'mode':self.traffic.name,'seed':self.seed,'density':self.density,'strategy':self.strategy,'nodes':NODES,'pairs':PAIRS,'route':self.route,'prefix':self.prefix,'failed':self.failed,'recovery':self.recovery,'controllers':[c.snapshot(self.time) for c in self.controllers.values()],'vehicles':self.traffic.vehicles(),'ambulance_speed':round(self.traffic.speed*3.6,1),'metrics':self.metrics,'certificates':self.certificates,'faults':self.faults,'collisions':getattr(self.traffic,'collision_count',None),'obligations':self.obligations,'agent_mode':os.getenv('AGENT_MODE','inprocess')}
        out.update(incidents=self.incidents,recovery_history=self.recovery_history,alternatives=self.alternatives,decision=self.decision,eta=self.eta,segment=self.traffic.segment,progress=self.traffic.progress,incident_revision=self.incident_revision)
        if include_history:out['events']=self.events[-150:]
        return copy.deepcopy(out)
    def export(self):return {'schema_version':2,'algorithm_version':'0.2.0','verification_public_key':self.authority.public_hex(),'snapshot':self.snapshot(),'events':self.events,'frames':self.frames,'assumptions':['Simulated physical evidence; no roadside validation','Single emergency vehicle; corridor release waits for all successor commitments','Pedestrian clearance fault is modelled as an explicit timer, not SUMO pedestrian demand','Authority key is ephemeral per experiment; signed records remain inspectable but replay uses stored states'],'wall_elapsed_seconds':time.perf_counter()-self.wall_started}
    def close(self):
        self.traffic.close()
        for c in self.controllers.values():
            if isinstance(c,ControllerAgent):c.close()
