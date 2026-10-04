import os, json
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

class Store:
    def __init__(self):
        self.engine=create_engine(os.getenv('DATABASE_URL','sqlite:///./corridor.db'))
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE IF NOT EXISTS records (id VARCHAR(100) PRIMARY KEY, kind VARCHAR(30) NOT NULL, created VARCHAR(60) NOT NULL, payload TEXT NOT NULL)'))
    def save(self,id,kind,payload):
        with self.engine.begin() as c:
            c.execute(text('INSERT INTO records (id,kind,created,payload) VALUES (:id,:kind,:created,:payload) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload'),{'id':id,'kind':kind,'created':datetime.now(timezone.utc).isoformat(),'payload':json.dumps(payload)})
    def list(self,kind):
        with self.engine.connect() as c:
            return [{'id':r[0],'created':r[1],**json.loads(r[2])} for r in c.execute(text('SELECT id,created,payload FROM records WHERE kind=:kind ORDER BY created DESC'),{'kind':kind})]
    def get(self,id):
        with self.engine.connect() as c:
            r=c.execute(text('SELECT payload FROM records WHERE id=:id'),{'id':id}).first()
            return json.loads(r[0]) if r else None
