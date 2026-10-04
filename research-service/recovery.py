"""Repeated incident lifecycle and constrained, measured-cost suffix planning."""
import copy
import uuid
import networkx as nx
from incidents import IncidentRequest, directed_edges


class IncidentRecovery:
    def init_incidents(self):
        self.incidents=[]
        self.recovery_history=[]
        self.alternatives=[]
        self.decision={'reason':'Original corridor active', 'eta_change':None}
        self.next_generation=2
        self.incident_revision=0
        self.eta=None
        self.minimum_benefit=3.0
        self.plan_deferred=False

    def fault(self,j,kind):
        return self.add_incident({'kind':kind,'controller':j})

    def add_incident(self,data):
        request=IncidentRequest.model_validate(data).model_dump()
        if self.status in ('COMPLETE','TIMEOUT','ERROR'):
            raise ValueError('Reset this finished run before adding incidents')
        if request['trigger']=='time' and request['at']<self.time:
            raise ValueError('Scheduled time must not be in the past')
        incident={**request,'id':uuid.uuid4().hex[:12],'status':'SCHEDULED','created_at':self.time,'activated_at':None,'resolved_at':None}
        self.incidents.append(incident)
        self.event('INCIDENT','Incident scheduled',f"{incident['kind']} / {incident['controller'] or ' → '.join(incident['edge'])} / {incident['trigger']}")
        self.process_incidents()
        return incident

    def active_incidents(self):
        return [i for i in self.incidents if i['status']=='ACTIVE']

    def process_incidents(self):
        changed=False
        for i in self.incidents:
            if i['status']=='SCHEDULED':
                distance=self.traffic.distance_to(i['junction']) if i['trigger']=='approach' else None
                due=i['trigger']=='now' or (i['trigger']=='time' and self.time>=i['at']) or (distance is not None and distance<=i['distance'])
                if due:
                    i['status']='ACTIVE'; i['activated_at']=self.time; changed=True
                    if i['kind']=='configuration':self.controllers[i['controller']].config+=1
                    self.faults.append({'id':i['id'],'at':self.time,'controller':i['controller'],'kind':i['kind'],'edge':i['edge']})
                    self.event('FAULT',f"{i['kind']} activated",i['controller'] or ' → '.join(i['edge']),i['controller'])
            if i['status']=='ACTIVE' and i['duration'] is not None and self.time>=i['activated_at']+i['duration']:
                i['status']='RESOLVED';i['resolved_at']=self.time;changed=True
                self.event('RESTORE','Incident duration elapsed',i['id'])
        if changed:self.incidents_changed()

    def resolve_incident(self,id):
        if self.status in ('COMPLETE','TIMEOUT','ERROR'):raise ValueError('Finished runs cannot be changed; reset to begin a new run')
        incident=next((i for i in self.incidents if i['id']==id),None)
        if incident is None:raise ValueError('Unknown incident')
        if incident['status'] not in ('ACTIVE','SCHEDULED'):raise ValueError('Incident already resolved')
        active=incident['status']=='ACTIVE'
        incident['status']='RESOLVED' if active else 'CANCELLED';incident['resolved_at']=self.time
        self.event('RESTORE','Incident resolved' if active else 'Scheduled incident cancelled',id)
        if active:self.incidents_changed()

    def restore(self,controller=None):
        if self.status in ('COMPLETE','TIMEOUT','ERROR'):raise ValueError('Finished runs cannot be changed; reset to begin a new run')
        if controller not in self.controllers:raise ValueError('Select a controller or resolve a specific incident')
        selected=[i for i in self.active_incidents() if i['controller']==controller]
        if not selected:raise ValueError('Selected controller has no active incidents')
        for i in selected:i['status']='RESOLVED';i['resolved_at']=self.time
        self.event('RESTORE',f'{controller} incidents resolved','Other incidents remain active',controller)
        self.incidents_changed()

    def incidents_changed(self):
        self.incident_revision+=1
        active=self.active_incidents()
        for j,c in self.controllers.items():
            local=[i for i in active if i['controller']==j]
            c.online=not any(i['kind']=='partition' for i in local)
            c.readback=not any(i['kind']=='readback' for i in local)
            c.writable=not any(i['kind']=='write' for i in local)
            c.pedestrian_until=max((i['activated_at']+i['duration'] for i in local if i['kind']=='pedestrian'),default=0)
        self.traffic.apply_incidents(active)
        self.failed=next((i['controller'] for i in active if i['controller']),None)
        self.plan_recovery()
        self.update_eta()

    def blocked_controllers(self):
        return {i['controller'] for i in self.active_incidents() if i['kind'] in ('readback','write','partition','configuration')}

    def path_cost(self,path):
        costs=[self.traffic.travel_cost(a,b) for a,b in zip(path,path[1:])]
        signal_delay=sum(max(0,self.controllers[n].pedestrian_until-self.time) for n in path if n in self.controllers)
        return sum(c['seconds'] for c in costs)+signal_delay, sum(c['distance'] for c in costs)

    def route_options(self):
        index=self.traffic.segment+1
        target=self.traffic.current_target()
        prefix=self.route[:index]
        excluded=self.blocked_controllers()|set(prefix)
        closed={tuple(i['edge']) for i in self.active_incidents() if i['kind'] in ('accident','closure')}
        graph=nx.DiGraph()
        graph.add_node('E')
        for a,b in directed_edges():
            if a not in excluded and b not in excluded and (a,b) not in closed:
                graph.add_edge(a,b,weight=self.traffic.travel_cost(a,b)['seconds'])
        options=[]
        if target not in graph or 'E' not in graph:return options
        try:
            for count,suffix in enumerate(nx.shortest_simple_paths(graph,target,'E',weight='weight')):
                if count>=100:break
                route=prefix+suffix
                if not all(self.traffic.legal_turn(a,b,c) for a,b,c in zip(route[index-1:],route[index:],route[index+1:])):continue
                seconds,distance=self.path_cost(suffix)
                edge=self.route[index-1:index+1]
                current=self.traffic.travel_cost(*edge)
                seconds+=current['seconds']*(1-self.traffic.progress)
                distance+=current['distance']*(1-self.traffic.progress)
                scope=sorted(n for n in set(self.route[index:]+suffix) if n in self.controllers)
                if self.strategy=='whole':scope=sorted(self.controllers)
                changed=route!=self.route
                options.append({'route':route,'eta':round(seconds+3.4,2),'distance':round(distance,1),'reconfigured':len(scope),'scope':scope,'score':round(seconds+3.4+(2 if changed else 0),2),'labels':[]})
        except nx.NetworkXNoPath:pass
        if options:
            min(options,key=lambda o:o['eta'])['labels'].append('Fastest estimated')
            min(options,key=lambda o:(o['reconfigured'],o['eta']))['labels'].append('Least reconfiguration')
        return sorted(options,key=lambda o:o['score'])

    def invalidate_pending(self):
        if self.recovery and self.recovery['stage']=='CLEARANCE':
            self.recovery['stage']='SUPERSEDED';self.recovery['ended']=self.time
            for n in self.recovery['scope']:self.freeze_clear(n)
            self.event('SUPERSEDE',f"Generation E{self.recovery['generation']} superseded",'Incident set changed; prior prepared authority revoked')

    def hold(self,reason):
        self.status='FALLBACK';self.metrics['fallbacks']+=1
        self.eta=None
        self.decision={'reason':reason,'eta_change':None,'next_action':'Resolve the blocking incident, or wait for its duration to expire.'}
        for n in self.route[self.traffic.segment+1:]:
            if n in self.controllers:self.freeze_clear(n)
        self.event('FALLBACK','No feasible verified route',reason)

    def plan_recovery(self):
        was_pending=self.status in ('RECOVERING','FALLBACK')
        self.invalidate_pending()
        self.alternatives=[]
        if self.traffic.done:return
        if not self.traffic.can_reroute():
            self.plan_deferred=True
            self.status='RECOVERING'
            self.decision={'reason':'Ambulance is clearing an entered junction; replanning will preserve its committed exit road.','eta_change':None}
            return
        self.plan_deferred=False
        blocked=self.traffic.current_blockage()
        if blocked:
            self.hold(f"{blocked['kind']} blocks the ambulance's entered lane ({' → '.join(blocked['edge'])}); movement withheld.")
            return
        target=self.traffic.current_target(); index=self.traffic.segment+1
        if target in self.blocked_controllers():
            self.hold(f'{target} cannot verify the already-entered movement. The current edge must be preserved.')
            return
        options=self.route_options()
        if not options:
            self.hold('Every legal downstream route is blocked or requires an unavailable controller.')
            return
        best=options[0];current=next((o for o in options if o['route']==self.route),None)
        # Hysteresis applies only when continuing the current route remains feasible.
        if current and current['score']-best['score']<self.minimum_benefit:best=current
        selected=[best]+[o for o in options if o is not best]
        self.alternatives=copy.deepcopy(selected[:3]);self.alternatives[0]['labels'].append('Selected')
        affected={i['controller'] for i in self.active_incidents()}&set(self.route[index:])
        needs_verification=any(self.controllers[n].mode not in ('ACTIVE','COMMITTED') for n in self.route[index:] if n in self.controllers)
        if best['route']==self.route and not affected and not was_pending and not needs_verification:
            self.decision={'reason':f'Current route remains feasible; no alternative improves the objective by {self.minimum_benefit:g}s.','eta_change':0}
            return
        self.prefix=self.route[:index]
        for obligation in self.obligations:obligation['completed']=obligation['controller'] in self.prefix
        scope=best['scope']
        for n in scope:self.freeze_clear(n)
        generation=self.next_generation;self.next_generation+=1
        candidates=[n for n in best['route'][index:] if n in self.controllers]
        self.recovery={'generation':generation,'revision':self.incident_revision,'frontier':target,'old':self.route[:],'successor':best['route'],'candidates':candidates,'scope':scope,'started':self.time,'stage':'CLEARANCE','kind':'incident','eta':best['eta']}
        self.recovery_history.append(self.recovery)
        self.metrics['reconfigured_total']+=len(scope)
        self.metrics['reconfigured']=len(scope);self.metrics['prefix_mutations']+=len(set(self.prefix)&set(scope))
        self.status='RECOVERING'
        active=', '.join(f"{i['kind']} at {i['controller'] or ' → '.join(i['edge'])}" for i in self.active_incidents()) or 'incident cleared'
        self.decision={'reason':f"{active}. Selected {' → '.join(best['route'][index:])} using estimated travel time, clearance and a route-change penalty; entered road retained.",'eta_change':round(best['eta']-self.eta,2) if self.eta is not None else None,'excluded_controllers':sorted(self.blocked_controllers())}
        self.recovery['decision']=copy.deepcopy(self.decision)
        self.event('FREEZE','Affected scope isolated',self.decision['reason'])
        for n in candidates:
            c=self.controllers[n]
            capsule={'run':self.id,'controller':n,'generation':generation,'revision':self.incident_revision,'capability':c.capability(),'suffix':best['route'],'frontier':target,'entry':'RED_CLEAR','commands':['GREEN','RED'],'native_commands':[c.native('GREEN'),c.native('RED')]}
            if not c.prepare(capsule):c.fallback('Preparation rejected')
        self.event('PREPARE',f'Generation E{generation} prepared','Movement waits for all successor verifications')

    def update_eta(self):
        if self.traffic.done:self.eta=0;return
        if self.status=='FALLBACK':self.eta=None;return
        route=self.recovery['successor'] if self.status=='RECOVERING' and self.recovery and not self.plan_deferred else self.route
        seconds,_=self.path_cost(route[self.traffic.segment+1:])
        seconds+=self.traffic.travel_cost(*self.route[self.traffic.segment:self.traffic.segment+2])['seconds']*(1-self.traffic.progress)
        if self.status=='RECOVERING' and self.recovery and not self.plan_deferred:seconds+=max(0,3.4-(self.time-self.recovery['started']))
        self.eta=round(seconds,1)
