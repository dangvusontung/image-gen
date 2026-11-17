import json
import subprocess

from app.routes import connection


def test_configured_backend_origin_does_not_call_tailscale(client, monkeypatch):
    monkeypatch.setenv('MOBILE_BACKEND_URL', 'https://backend.example.test/')
    monkeypatch.setattr(connection.shutil, 'which', lambda _: None)
    assert client.get('/api/connection-info').json() == {'origin': 'https://backend.example.test', 'transport': 'configured'}


def test_tailscale_origin_requires_existing_backend_forwarder(client, monkeypatch):
    monkeypatch.delenv('MOBILE_BACKEND_URL', raising=False)
    monkeypatch.setattr(connection.shutil, 'which', lambda _: '/fake/tailscale')
    forwarded = {'TCP': {'8000': {'TCPForward': '127.0.0.1:8000'}}}

    def run(args, **kwargs):
        data = forwarded if 'serve' in args else {'BackendState': 'Running', 'Self': {'TailscaleIPs': ['fd7a::1', '100.72.216.79']}}
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(data))

    monkeypatch.setattr(connection.subprocess, 'run', run)
    assert client.get('/api/connection-info').json()['origin'] == 'http://100.72.216.79:8000'
    forwarded.clear()
    assert client.get('/api/connection-info').json()['origin'] is None


def test_tailscale_failure_does_not_advertise_localhost(client, monkeypatch):
    monkeypatch.setenv('MOBILE_BACKEND_URL', 'https://user:password@example.test/path')
    monkeypatch.setattr(connection.shutil, 'which', lambda _: None)
    assert client.get('/api/connection-info').json() == {'origin': None, 'transport': None}
