import os
import re
import base64
from pathlib import Path
import yaml


SENSITIVE_PATTERNS = [
    r'PASSWORD', r'SECRET', r'TOKEN', r'KEY', r'CREDENTIAL',
    r'REDIS_PASSWORD', r'POSTGRES_PASSWORD'
]

ALL_IN_SECRET_SERVICES = ['ocr']

SERVICE_PREFIXES = {
    'postgres': ['POSTGRES_'],
    'redis': ['REDIS_'],
    'kafka': ['KAFKA_'],
    'spark': ['SPARK_'],
    'ocr': ['OCR_'],
    'detector': ['DETECTOR_'],
    'app': ['APP_', 'LOG_LEVEL', 'SCAN_', 'POSTGRES_', 'REDIS_', 'KAFKA_', 'SPARK_', 'OCR_', 'DETECTOR_'],
}


def is_sensitive(key: str) -> bool:
    return any(re.search(pattern, key, re.I) for pattern in SENSITIVE_PATTERNS)


def parse_env_file(env_path: str) -> dict[str, str]:
    env_vars = {}

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def generate_configmap(env_vars: dict, service: str, namespace: str) -> dict:
    prefixes = SERVICE_PREFIXES.get(service, [])
    
    if service == 'app':
        data = {
            k: v for k, v in env_vars.items()
            if any(k.startswith(p) for p in prefixes)
        }
    else:
        data = {
            k: v for k, v in env_vars.items()
            if any(k.startswith(p) for p in prefixes) and not is_sensitive(k)
        }
    
    if not data:
        return None
    
    return {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': f'pd-{service}-config',
            'namespace': namespace,
            'labels': {'app': f'pd-{service}'}
        },
        'data': data
    }


def generate_secret(env_vars: dict, service: str, namespace: str) -> dict:
    prefixes = SERVICE_PREFIXES.get(service, [])
    
    if service in ALL_IN_SECRET_SERVICES:
        data = {
            k: base64.b64encode(v.encode()).decode() for k, v in env_vars.items()
            if any(k.startswith(p) for p in prefixes)
        }
    else:
        data = {
            k: base64.b64encode(v.encode()).decode() for k, v in env_vars.items()
            if any(k.startswith(p) for p in prefixes) and is_sensitive(k)
        }
    
    if not data:
        return None
    
    return {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': f'pd-{service}-secret',
            'namespace': namespace,
            'labels': {'app': f'pd-{service}'}
        },
        'type': 'Opaque',
        'data': data
    }


def main():
    import sys
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    
    if '--env-file' in sys.argv:
        idx = sys.argv.index('--env-file')
        if idx + 1 < len(sys.argv):
            env_path = Path(sys.argv[idx + 1])
    
    output_dir = Path(__file__).parent.parent / 'base'
    
    if not env_path.exists():
        print(f".env not found at {env_path}")
        return
    
    env_vars = parse_env_file(str(env_path))
    namespace = 'pd-scanner'
    
    for service in SERVICE_PREFIXES.keys():
        cm = generate_configmap(env_vars, service, namespace)
        secret = generate_secret(env_vars, service, namespace)
        
        if cm:
            cm_path = output_dir / service / 'configmap.yaml'
            cm_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cm_path, 'w', encoding='utf-8') as f:
                yaml.dump(cm, f, default_flow_style=False, allow_unicode=True)
            print(f"Generated {cm_path}")
        
        if secret:
            secret_path = output_dir / service / 'secret.yaml'
            with open(secret_path, 'w', encoding='utf-8') as f:
                yaml.dump(secret, f, default_flow_style=False, allow_unicode=True)
            print(f"Generated {secret_path}")
    
    ns_manifest = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {
            'name': namespace,
            'labels': {'name': namespace}
        }
    }
    ns_path = output_dir / 'namespace.yaml'
    with open(ns_path, 'w', encoding='utf-8') as f:
        yaml.dump(ns_manifest, f, default_flow_style=False, allow_unicode=True)
    print(f"Generated {ns_path}")


if __name__ == '__main__':
    main()