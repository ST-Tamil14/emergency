"""Offline signature verification: python experiments/verify_export.py run.json"""
import sys,json,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research-service'))
from protocol import canonical_bytes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
if __name__=='__main__':
    data=json.load(open(sys.argv[1],encoding='utf-8'))
    key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(data['verification_public_key']))
    tokens=data['snapshot']['certificates']
    for token in tokens:
        raw=canonical_bytes(token['body'])
        key.verify(base64.b64decode(token['signature']),raw)
    print(f'{len(tokens)} archived certificate signatures verified. This verifies integrity, not real-world safety.')
