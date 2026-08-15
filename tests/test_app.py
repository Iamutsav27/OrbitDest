import json
import os
import sys

# Ensure project root is on sys.path so tests can import app.py
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app


def test_health():
    client = app.test_client()
    r = client.get('/health')
    assert r.status_code == 200
    assert r.get_json()['status'] == 'ok'


def test_echo():
    client = app.test_client()
    r = client.post('/echo', json={'msg': 'hello'})
    assert r.status_code == 200
    assert r.get_json()['msg'] == 'hello'


def test_sum():
    client = app.test_client()
    r = client.post('/sum', json={'numbers': [1, 2, 3]})
    assert r.status_code == 200
    assert r.get_json()['sum'] == 6.0
