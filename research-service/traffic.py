"""SUMO is authoritative when available. Kinematic mode is explicitly labelled."""
import os, math, random, subprocess, shutil
from pathlib import Path

NODES={'W':(-80,0),'J1':(0,0),'J2':(80,0),'J3':(160,0),'J4':(0,80),'J5':(80,80),'J6':(160,80),'J7':(80,-80),'J8':(240,-80),'E':(240,80)}
PAIRS=[('W','J1'),('J1','J2'),('J2','J3'),('J1','J4'),('J2','J5'),('J3','J6'),('J4','J5'),('J5','J6'),('J6','E'),('J2','J7'),('J7','J8'),('J3','J8'),('J8','E')]
BASE=['W','J1','J2','J3','J6','E']
def route_edges(route): return [f'{a}_{b}' for a,b in zip(route,route[1:])]

class KinematicTraffic:
    name='Kinematic model'
    def __init__(self,seed=42,density=12):
        self.route=BASE[:]; self.segment=0; self.progress=0.; self.speed=0.; self.done=False; self.t=0
        self.rng=random.Random(seed); self.density=density
        self.incidents=[]
        self.cars=[{'id':f'car-{i}','segment':i%len(PAIRS),'progress':self.rng.random(), 'speed':4+self.rng.random()*3} for i in range(density)]
    def step(self,dt,hold,controllers):
        self.t+=dt
        if not self.done:
            target=self.route[self.segment+1]; allowed=hold is False
            if target in controllers and self.progress>.62 and controllers[target].phase!='GREEN': allowed=False
            edge=self.route[self.segment:self.segment+2]
            self.speed=self.edge_speed(*edge) if allowed else 0
            a=NODES[self.route[self.segment]]; b=NODES[target]; length=math.dist(a,b)
            self.progress+=self.speed*dt/length
            if self.progress>=1:
                self.progress-=1; self.segment+=1
                if self.segment>=len(self.route)-1: self.done=True; self.progress=0; self.speed=0
        for c in self.cars:
            a,b=PAIRS[c['segment']]; phase=controllers[b].phase if b in controllers else 'GREEN'
            if any(i['edge']==[a,b] and i['kind'] in ('closure','accident') for i in self.incidents):continue
            if phase=='GREEN' or c['progress']<.7:
                c['progress']+=dt*min(c['speed'],self.edge_speed(a,b))/math.dist(NODES[a],NODES[b])
            if c['progress']>=1: c['progress']=0
    def position(self):
        if self.done: return list(NODES[self.route[-1]])
        a=NODES[self.route[self.segment]]; b=NODES[self.route[self.segment+1]]
        return [a[j]+(b[j]-a[j])*self.progress for j in [0,1]]
    def current_target(self): return self.route[min(self.segment+1,len(self.route)-1)]
    def edge_length(self,a,b): return math.dist(NODES[a],NODES[b])
    def edge_speed(self,a,b):
        reductions=[1-i['intensity'] for i in self.incidents if i['kind']=='congestion' and i['edge']==[a,b]]
        return 11*min(reductions,default=1)
    def travel_cost(self,a,b):
        return {'seconds':self.edge_length(a,b)/self.edge_speed(a,b),'distance':self.edge_length(a,b),'queue':0,'source':'model speed'}
    def legal_turn(self,a,b,c): return a!=c
    def can_reroute(self): return not self.done
    def distance_to(self,j):
        remaining=self.route[self.segment+1:]
        if j not in remaining:return None
        distance=self.edge_length(*self.route[self.segment:self.segment+2])*(1-self.progress)
        for a,b in zip(remaining,remaining[1:]):
            if a==j:break
            distance+=self.edge_length(a,b)
        return distance
    def apply_incidents(self,incidents): self.incidents=incidents
    def current_blockage(self):
        edge=self.route[self.segment:self.segment+2]
        return next((i for i in self.incidents if i['edge']==edge and (i['kind']=='closure' or (i['kind']=='accident' and self.progress<=i['position']))),None)
    def set_route(self,route):
        # Route must retain the current edge; never teleport or reverse the vehicle.
        if route[:self.segment+2]!=self.route[:self.segment+2]: raise ValueError('Replacement changes already entered edge')
        self.route=route
    def observed_phase(self,j,requested): return requested
    def occupancy(self,j): return False
    def signals(self,controllers): pass
    def vehicles(self):
        out=[]
        for c in self.cars:
            a,b=PAIRS[c['segment']]; p=c['progress']; aa=NODES[a]; bb=NODES[b]
            out.append({'id':c['id'],'x':aa[0]+(bb[0]-aa[0])*p,'y':aa[1]+(bb[1]-aa[1])*p,'angle':math.atan2(bb[1]-aa[1],bb[0]-aa[0])})
        p=self.position(); target=self.current_target(); a=NODES[self.route[min(self.segment,len(self.route)-2)]]; b=NODES[target]
        out.append({'id':'ambulance','x':p[0],'y':p[1],'angle':math.atan2(b[1]-a[1],b[0]-a[0])})
        return out
    def close(self): pass

class SumoTraffic(KinematicTraffic):
    name='SUMO microsimulation'
    def __init__(self,seed=42,density=12):
        super().__init__(seed,density)
        import traci, sumolib
        self.traci=traci
        import tempfile
        self.work=Path(tempfile.mkdtemp(prefix='corridor-sumo-'))
        nodes=['<nodes>']+[f'<node id="{n}" x="{p[0]}" y="{p[1]}" type="{"traffic_light" if n.startswith("J") else "priority"}"/>' for n,p in NODES.items()]+['</nodes>']
        edges=['<edges>']
        for a,b in PAIRS:
            for x,y in [(a,b),(b,a)]: edges.append(f'<edge id="{x}_{y}" from="{x}" to="{y}" numLanes="1" speed="11"/>')
        edges.append('</edges>')
        (self.work/'nodes.xml').write_text('\n'.join(nodes)); (self.work/'edges.xml').write_text('\n'.join(edges))
        subprocess.run([sumolib.checkBinary('netconvert'),'--node-files',str(self.work/'nodes.xml'),'--edge-files',str(self.work/'edges.xml'),'-o',str(self.work/'network.net.xml'),'--no-turnarounds','true','--offset.disable-normalization','true'],check=True,capture_output=True)
        self.network=sumolib.net.readNet(str(self.work/'network.net.xml'))
        label=str(self.work)
        traci.start([sumolib.checkBinary('sumo'),'-n',str(self.work/'network.net.xml'),'--step-length','0.2','--seed',str(seed),'--no-step-log','true','--no-warnings','true','--collision.action','warn','--time-to-teleport','-1'],label=label,doSwitch=False,stdout=subprocess.DEVNULL)
        self.conn=traci.getConnection(label)
        self.conn.vehicletype.copy('DEFAULT_VEHTYPE','emergency')
        self.conn.vehicletype.setVehicleClass('emergency','emergency')
        self.conn.vehicletype.setColor('emergency',(255,255,255,255))
        self.conn.route.add('emergency-route',route_edges(self.route))
        self.conn.vehicle.add('ambulance','emergency-route',typeID='emergency',depart='0')
        self.conn.vehicle.setSpeedFactor('ambulance',1.0)
        bg=['E','J6','J5','J4','J1','W']; self.conn.route.add('background',route_edges(bg))
        for i in range(density): self.conn.vehicle.add(f'car-{i}','background',depart=str(i*2))
        self.conn.simulationStep(); self.started=True; self.last_position=list(NODES['W']); self.collision_count=0
    def signals(self,controllers):
        for j,c in controllers.items():
            links=self.conn.trafficlight.getControlledLinks(j)
            chars=['r']*len(links)
            if c.phase=='YELLOW':
                previous=self.conn.trafficlight.getRedYellowGreenState(j)
                chars=['y' if k in 'GgyY' else 'r' for k in previous]
            elif c.phase=='GREEN':
                incoming=None
                if j in self.route:
                    i=self.route.index(j)
                    if i>0: incoming=self.route[i-1]+'_'+j
                if incoming is None: incoming=links[0][0][0].rsplit('_',1)[0] if links and links[0] else ''
                for i,group in enumerate(links):
                    if group and group[0][0].rsplit('_',1)[0]==incoming: chars[i]='G'
            self.conn.trafficlight.setRedYellowGreenState(j,''.join(chars))
    def step(self,dt,hold,controllers):
        self.signals(controllers)
        if 'ambulance' in self.conn.vehicle.getIDList():
            internal=self.conn.vehicle.getRoadID('ambulance').startswith(':')
            # Finish only the movement already entered; replan on its outgoing edge.
            self.conn.vehicle.setSpeed('ambulance',0 if hold and not internal else -1)
        self.conn.simulationStep(); self.t=self.conn.simulation.getTime()
        self.collision_count+=self.conn.simulation.getCollidingVehiclesNumber()
        if 'ambulance' in self.conn.vehicle.getIDList():
            self.last_position=list(self.conn.vehicle.getPosition('ambulance')); self.speed=self.conn.vehicle.getSpeed('ambulance')
            edge=self.conn.vehicle.getRoadID('ambulance')
            if not edge.startswith(':') and edge in route_edges(self.route):
                self.segment=route_edges(self.route).index(edge)
                self.progress=min(1,self.conn.vehicle.getLanePosition('ambulance')/self.conn.lane.getLength(edge+'_0'))
        elif 'ambulance' in self.conn.simulation.getArrivedIDList(): self.done=True; self.speed=0
    def position(self): return self.last_position
    def vehicles(self):
        return [{'id':v,'x':self.conn.vehicle.getPosition(v)[0],'y':self.conn.vehicle.getPosition(v)[1], 'angle':math.radians(90-self.conn.vehicle.getAngle(v))} for v in self.conn.vehicle.getIDList()]
    def observed_phase(self,j,requested):
        state=self.conn.trafficlight.getRedYellowGreenState(j)
        if any(x in 'Gg' for x in state):return 'GREEN'
        if any(x in 'Yy' for x in state):return 'YELLOW'
        return 'RED'
    def occupancy(self,j):
        return any(self.conn.vehicle.getRoadID(v).startswith(':'+j+'_') for v in self.conn.vehicle.getIDList())
    def set_route(self,route):
        if route[:self.segment+2]!=self.route[:self.segment+2]: raise ValueError('Replacement changes already entered edge')
        if not self.can_reroute(): raise ValueError('Wait until ambulance leaves the internal junction edge')
        self.conn.vehicle.setRoute('ambulance',route_edges(route)[self.segment:])
        self.route=route
    def can_reroute(self):
        return 'ambulance' in self.conn.vehicle.getIDList() and not self.conn.vehicle.getRoadID('ambulance').startswith(':')
    def edge_length(self,a,b): return self.network.getEdge(f'{a}_{b}').getLength()
    def legal_turn(self,a,b,c):
        return a!=c and bool(self.network.getEdge(f'{a}_{b}').getConnections(self.network.getEdge(f'{b}_{c}')))
    def travel_cost(self,a,b):
        edge=f'{a}_{b}'; length=self.edge_length(a,b)
        count=self.conn.edge.getLastStepVehicleNumber(edge)
        measured=self.conn.edge.getLastStepMeanSpeed(edge) if count else 11
        speed=max(1,min(self.edge_speed(a,b),measured))
        queue=self.conn.edge.getLastStepHaltingNumber(edge)
        return {'seconds':length/speed+queue*1.5,'distance':length,'queue':queue,'source':'SUMO measured speed and queue'}
    def apply_incidents(self,incidents):
        super().apply_incidents(incidents)
        for a,b in [(x,y) for a,b in PAIRS for x,y in ((a,b),(b,a))]:
            lane=f'{a}_{b}_0'
            blocked=any(i['edge']==[a,b] and i['kind'] in ('accident','closure') for i in incidents)
            self.conn.lane.setDisallowed(lane,['all'] if blocked else [])
            self.conn.lane.setMaxSpeed(lane,self.edge_speed(a,b))
    def close(self):
        if hasattr(self,'conn'): self.conn.close()
        shutil.rmtree(self.work,ignore_errors=True)
