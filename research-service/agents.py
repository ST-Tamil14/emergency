"""Optional process-isolated controller agents. Every RPC is serialized.
Local pipes emulate a trusted gateway transport; they are not a vendor protocol.
"""
import multiprocessing as mp
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from protocol import Controller, Authority

METHODS={'native','capability','observe','evidence','ready','prepare','commit','execute','freeze','fallback','snapshot','persist'}
def serve(connection,kwargs):
    controller=Controller(**kwargs)
    while True:
        try:
            message=connection.recv()
            op,name,args=message
            if op=='close':break
            if op=='get':result=getattr(controller,name)
            elif op=='set':setattr(controller,name,args);result=None
            else:
                if name=='commit':
                    token,public_bytes,now=args
                    verifier=Authority.__new__(Authority)
                    verifier.public=Ed25519PublicKey.from_public_bytes(public_bytes)
                    args=(token,verifier,now)
                result=getattr(controller,name)(*args)
            connection.send((True,result))
        except EOFError:break
        except Exception as exc:connection.send((False,str(exc)))
    connection.close()

class ControllerAgent:
    def __init__(self,**kwargs):
        ctx=mp.get_context('spawn');parent,child=ctx.Pipe()
        object.__setattr__(self,'_connection',parent)
        process=ctx.Process(target=serve,args=(child,kwargs),daemon=True,name=f"controller-{kwargs['id']}")
        object.__setattr__(self,'_process',process);process.start();child.close()
    def _rpc(self,op,name,args=None):
        self._connection.send((op,name,args))
        if not self._connection.poll(5):raise RuntimeError('Controller agent did not respond')
        ok,result=self._connection.recv()
        if not ok:raise RuntimeError(result)
        return result
    def __getattr__(self,name):
        if name in METHODS:
            def call(*args):
                if name=='commit':
                    token,authority,now=args
                    key=authority.public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
                    args=(token,key,now)
                return self._rpc('call',name,args)
            return call
        return self._rpc('get',name)
    def __setattr__(self,name,value):
        if name.startswith('_'):object.__setattr__(self,name,value)
        else:self._rpc('set',name,value)
    def close(self):
        if self._process.is_alive():
            self._connection.send(('close','',None));self._process.join(2)
            if self._process.is_alive():self._process.terminate();self._process.join()
        self._connection.close()
