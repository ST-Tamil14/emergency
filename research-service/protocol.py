"""Local enforcement for a bounded simulation. No real-road safety certification.
All mutation and actuation checks must be serialized by the caller.
"""
from dataclasses import dataclass, field, asdict
from adapters import ControllerAdapter
import hashlib, json, base64, os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical_bytes(value):
    """Stable encoding for this protocol's JSON schema, including browser round trips.

    JSON has one number type: 1.0 and 1 carry identical protocol meaning.
    Non-finite values are disallowed. This is not a general RFC 8785 encoder.
    """
    def normalize(item):
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: normalize(val) for key, val in item.items()}
        if isinstance(item, list):
            return [normalize(val) for val in item]
        return item
    return json.dumps(normalize(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

class Authority:
    def __init__(self):
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key()
    def public_hex(self):
        return self.public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
    def issue(self, body):
        raw = canonical_bytes(body)
        return {'body':body, 'signature':base64.b64encode(self.key.sign(raw)).decode()}
    def valid(self, token):
        try:
            raw=canonical_bytes(token['body'])
            self.public.verify(base64.b64decode(token['signature']),raw)
            return True
        except Exception:
            return False

@dataclass
class Controller:
    id: str
    profile: str
    run: str
    durable_dir: str | None = None
    generation: int = 1
    mode: str = 'ACTIVE'
    config: int = 1
    readback: bool = True
    writable: bool = True
    online: bool = True
    phase: str = 'RED'
    observed_phase: str = 'RED'
    pedestrian_until: float = 0
    occupied: bool = False
    observed_at: float = 0
    sequence: int = -1
    rejected: int = 0
    prepared: dict | None = None
    committed_capsule: str | None = None
    last_reason: str = 'Ready'
    committed_state: dict | None = None

    def __post_init__(self):
        if self.durable_dir and self.path.exists():
            d=json.loads(self.path.read_text())
            self.generation=d['generation']; self.sequence=d['sequence']
            self.mode='RECOVERING'; self.last_reason='Restart: fresh verification required'
    @property
    def path(self):
        return Path(self.durable_dir)/f'{self.run}-{self.id}.json'
    def persist(self):
        if not self.durable_dir: return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        p=self.path.with_suffix('.tmp')
        with open(p,'w') as f:
            json.dump({'generation':self.generation,'sequence':self.sequence},f)
            f.flush(); os.fsync(f.fileno())
        os.replace(p,self.path)
    def native(self,action):
        return ControllerAdapter(self.profile).encode(action)
    def capability(self):
        return digest({'id':self.id,'profile':self.profile,'config':self.config,
                       'readback':self.readback,'writable':self.writable,'operations':ControllerAdapter(self.profile).operations()})
    def observe(self, now, phase='RED', occupied=False):
        if self.online and self.readback:
            self.observed_phase=phase; self.occupied=occupied; self.observed_at=now
    def evidence(self,now):
        return {'controller':self.id,'phase':self.observed_phase,'occupied':self.occupied,
                'pedestrian_clear':now>=self.pedestrian_until,'observed_at':self.observed_at,
                'capability':self.capability()}
    def ready(self,now):
        if not self.online: return False,'Controller disconnected'
        if not self.readback or not self.writable: return False,'Required capability unavailable'
        if now-self.observed_at>1 or self.observed_at>now: return False,'Evidence stale or from the future'
        if self.observed_phase!='RED': return False,'Observed signal clearance incomplete'
        if self.occupied: return False,'Conflict zone occupied'
        if now<self.pedestrian_until: return False,'Pedestrian clearance pending'
        return True,'State predicates satisfied'
    def prepare(self,capsule):
        if capsule['run']!=self.run or capsule['controller']!=self.id: return False
        if capsule['generation']<=self.generation or capsule['capability']!=self.capability(): return False
        if not self.online or not self.readback or not self.writable: return False
        self.prepared=capsule; self.mode='PREPARED'; self.last_reason='Commands stored; authority withheld'
        return True
    def commit(self,token,authority,now):
        def reject(reason):
            self.last_reason=reason; return False
        if not authority.valid(token): return reject('Invalid certificate signature')
        b=token['body']; p=self.prepared
        if not p: return reject('No prepared capsule')
        if b.get('run')!=self.run or b.get('controller')!=self.id: return reject('Certificate identity mismatch')
        if b.get('generation')!=p['generation'] or b['generation']<=self.generation: return reject('Generation mismatch')
        if b.get('capsule')!=digest(p): return reject('Capsule binding mismatch')
        if b.get('capability')!=self.capability(): return reject('Capability changed')
        if not b['issued']<=now<=b['expires']: return reject('Certificate expired')
        ok,reason=self.ready(now)
        if not ok: return reject(reason)
        old=b['evidence']; current=self.evidence(now)
        if old['observed_at']>now or now-old['observed_at']>1: return reject('Certified evidence stale')
        for k in ['controller','phase','occupied','pedestrian_clear','capability']:
            if old[k]!=current[k]: return reject('Local state differs from certified state')
        if not b.get('vehicle_before_frontier'): return reject('Vehicle has crossed recovery frontier')
        self.generation=b['generation']; self.sequence=-1
        self.committed_capsule=digest(p); self.committed_state=b
        self.persist() # durable fence before any actuation is possible
        self.mode='COMMITTED'; self.last_reason='Verified locally; waiting for corridor release'
        return True
    def execute(self,command,now,dependencies_ready):
        reason=None
        if command.get('run')!=self.run: reason='Wrong corridor run'
        elif command.get('generation')!=self.generation: reason='Superseded or uncommitted generation'
        elif not self.online or not self.writable or not self.readback: reason='Capability unavailable'
        elif self.mode not in ['ACTIVE','COMMITTED']: reason='Controller does not hold executable authority'
        elif now-self.observed_at>1 or self.observed_at>now: reason='Actuation evidence is not fresh'
        elif self.generation>1 and (not self.committed_state or self.committed_state['capability']!=self.capability()): reason='Committed capability binding invalidated'
        elif command.get('sequence',-1)<=self.sequence: reason='Duplicate or reordered command'
        elif not dependencies_ready: reason='Successor dependencies not committed'
        elif self.generation>1 and command.get('capsule')!=self.committed_capsule: reason='Command capsule mismatch'
        elif command.get('action') not in ['GREEN','RED']: reason='Unsupported action'
        elif command.get('native')!=self.native(command['action']): reason='Native command does not match controller interface'
        elif command.get('action')=='GREEN' and self.phase!='GREEN':
            ok,r=self.ready(now)
            if not ok: reason=r
        if reason:
            self.rejected+=1; self.last_reason=reason; return False
        self.sequence=command['sequence']; self.persist()
        self.phase=command['action']; self.mode='ACTIVE'; self.last_reason='Command accepted'
        return True
    def freeze(self):
        self.mode='FROZEN'; self.prepared=None; self.last_reason='Old actuation authority revoked locally'
    def fallback(self,reason):
        self.mode='FALLBACK'; self.last_reason=reason
    def snapshot(self,now):
        d=asdict(self); d.pop('durable_dir',None); d['capability_digest']=self.capability()
        d['evidence_age']=round(now-self.observed_at,2); d['ready']=self.ready(now)[0]
        return d
