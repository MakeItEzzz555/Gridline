"""Detached Ed25519 approval verification. Private keys are never accepted here."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from component_spec import encode


def crypto(command):
    executable=shutil.which('openssl')
    if not executable:raise ValueError('OpenSSL 3 with Ed25519 support is required for signed source approval')
    env={k:v for k,v in os.environ.items() if not k.startswith('OPENSSL_')}
    try:
        return subprocess.run([executable,*command],env=env,capture_output=True,timeout=10,check=True).stdout
    except (subprocess.SubprocessError,OSError) as exc:
        raise ValueError('OpenSSL key/signature verification failed') from exc


def public_key_fingerprint(pem):
    if not isinstance(pem,bytes) or len(pem)>4096 or b'PRIVATE KEY' in pem:
        raise ValueError('only a bounded Ed25519 public key is accepted')
    with tempfile.TemporaryDirectory(prefix='gridline-public-key-') as temporary:
        key=Path(temporary)/'public.pem';key.write_bytes(pem)
        der=crypto(['pkey','-pubin','-in',str(key),'-outform','DER'])
    # RFC 8410 Ed25519 SubjectPublicKeyInfo: OID 1.3.101.112 and a 32-byte key.
    if len(der)!=44 or not der.startswith(bytes.fromhex('302a300506032b6570032100')):
        raise ValueError('approval key must be Ed25519')
    return hashlib.sha256(der).hexdigest()


def payload(action, project, target, key_fingerprint, owner):
    if action not in ('INITIALIZE','APPROVE','REJECT'):raise ValueError('unknown approval action')
    return encode({'protocol':'gridline-source-approval.v1','action':action,'project_id':project,
                   'target_sha256':target,'owner_key_sha256':key_fingerprint,'owner_label':owner})


def verify(pem, signature, message):
    fingerprint=public_key_fingerprint(pem)
    if not isinstance(signature,bytes) or len(signature)!=64:raise ValueError('Ed25519 signature must contain exactly 64 bytes')
    with tempfile.TemporaryDirectory(prefix='gridline-signature-') as temporary:
        folder=Path(temporary)
        for name,data in (('public.pem',pem),('signature.bin',signature),('payload.json',message)):(folder/name).write_bytes(data)
        crypto(['pkeyutl','-verify','-pubin','-inkey',str(folder/'public.pem'),'-rawin',
                '-in',str(folder/'payload.json'),'-sigfile',str(folder/'signature.bin')])
    return fingerprint
