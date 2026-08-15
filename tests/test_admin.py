import os
import sys
import json
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# remove existing SQLite DB before importing app to ensure fresh DB
import os as _os
_os.environ['OMNI_DB'] = ':memory:'

from app import app


def test_superadmin_and_client_flow():
    client = app.test_client()

    # setup superadmin
    r = client.post('/setup-superadmin', json={'username': 'admin', 'password': 'secret'})
    assert r.status_code == 200
    body = r.get_json()
    assert 'token' in body
    token = body['token']

    # use token to create a client
    headers = {'Authorization': f'Bearer {token}'}
    r = client.post('/clients', json={'name': 'Acme Corp'}, headers=headers)
    assert r.status_code == 200
    client_body = r.get_json()
    client_id = client_body['id']

    # set channels
    r = client.post(f'/clients/{client_id}/channels', json={'channels': ['whatsapp', 'email']}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()['client']['channels'] == ['whatsapp', 'email']

    # get channels
    r = client.get(f'/clients/{client_id}/channels', headers=headers)
    assert r.status_code == 200
    assert r.get_json()['channels'] == ['whatsapp', 'email']
