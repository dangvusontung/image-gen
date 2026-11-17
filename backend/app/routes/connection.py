"""Advertise an existing mobile-reachable backend address without changing networking."""
import ipaddress
import json
import os
import shutil
import subprocess
from urllib.parse import urlsplit

from fastapi import APIRouter

router = APIRouter(tags=["connection"])


def mobile_origin():
    configured = os.getenv('MOBILE_BACKEND_URL', '').strip().rstrip('/')
    if configured:
        url = urlsplit(configured)
        if (url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
                and not url.path and not url.query and not url.fragment):
            return {'origin': configured, 'transport': 'configured'}
    executable = shutil.which('tailscale')
    if executable:
        try:
            status = json.loads(subprocess.run([executable, 'status', '--json'], capture_output=True, text=True, check=True, timeout=3).stdout)
            serve = json.loads(subprocess.run([executable, 'serve', 'status', '--json'], capture_output=True, text=True, check=True, timeout=3).stdout)
            forwarding = serve.get('TCP', {}).get('8000', {}).get('TCPForward')
            if status.get('BackendState') == 'Running' and forwarding in ('127.0.0.1:8000', 'localhost:8000'):
                for value in status.get('Self', {}).get('TailscaleIPs', []):
                    address = ipaddress.ip_address(value)
                    if address.version == 4:
                        return {'origin': f'http://{address}:8000', 'transport': 'tailscale'}
        except (subprocess.SubprocessError, OSError, ValueError, TypeError):
            pass
    return {'origin': None, 'transport': None}


@router.get('/api/connection-info')
def connection_info():
    return mobile_origin()
