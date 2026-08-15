from flask import Flask, request, jsonify
import os
import json
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    return response


# Simple file-backed storage
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            txt = f.read()
            try:
                # try normal load first
                return json.loads(txt)
            except Exception:
                # if file contains multiple JSON documents (e.g., tests appended),
                # decode the first JSON object found
                decoder = json.JSONDecoder()
                obj, idx = decoder.raw_decode(txt)
                return obj
    return {'users': [], 'clients': []}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


data = load_data()

# Normalize legacy/plain fields: convert plain 'password' to 'password_hash' and
# ensure users have tokens.
def normalize_data():
    changed = False
    for u in data.get('users', []):
        if 'password' in u and not u.get('password_hash'):
            u['password_hash'] = generate_password_hash(u.pop('password'), method='pbkdf2:sha256')
            changed = True
        if u.get('token') is None:
            u['token'] = str(uuid.uuid4())
            changed = True
    if changed:
        save_data(data)

normalize_data()


def find_user_by_token(token):
    for u in data.get('users', []):
        if u.get('token') == token:
            return u
    return None


def require_superadmin(fn):
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth.split(None, 1)[1]
            user = find_user_by_token(token)
            if user and user.get('role') == 'superadmin':
                request.user = user
                return fn(*args, **kwargs)
        return jsonify(error='unauthorized'), 401
    wrapper.__name__ = fn.__name__
    return wrapper


@app.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok')


@app.route('/echo', methods=['POST'])
def echo():
    data_in = request.get_json(silent=True)
    return jsonify(data_in or {})


@app.route('/sum', methods=['POST'])
def sum_numbers():
    payload = request.get_json(silent=True)
    numbers = []
    if payload and isinstance(payload, dict):
        numbers = payload.get('numbers', [])
    try:
        total = sum(float(x) for x in numbers)
    except Exception:
        return jsonify(error='invalid numbers'), 400
    return jsonify(sum=total)


# --- Admin & client endpoints ---
@app.route('/setup-superadmin', methods=['POST'])
def setup_superadmin():
    body = request.get_json(silent=True) or {}
    username = body.get('username')
    password = body.get('password')
    if not username or not password:
        return jsonify(error='username and password required'), 400
    # disallow if already exists
    for u in data['users']:
        if u.get('role') == 'superadmin':
            # return existing superadmin id and token instead of failing
            return jsonify(id=u.get('id'), token=u.get('token'))
    user = {
        'id': str(uuid.uuid4()),
        'username': username,
        'password_hash': generate_password_hash(password, method='pbkdf2:sha256'),
        'role': 'superadmin',
        'token': str(uuid.uuid4())
    }
    data['users'].append(user)
    save_data(data)
    return jsonify(id=user['id'], token=user['token'])


@app.route('/login', methods=['POST'])
def login():
    body = request.get_json(silent=True) or {}
    username = body.get('username')
    password = body.get('password')
    for u in data.get('users', []):
        if u.get('username') == username and check_password_hash(u.get('password_hash', ''), password):
            # ensure token exists
            if not u.get('token'):
                u['token'] = str(uuid.uuid4())
                save_data(data)
            return jsonify(token=u['token'], role=u.get('role'))
    return jsonify(error='invalid credentials'), 401


@app.route('/clients', methods=['POST'])
@require_superadmin
def create_client():
    body = request.get_json(silent=True) or {}
    name = body.get('name')
    if not name:
        return jsonify(error='name required'), 400
    client = {
        'id': str(uuid.uuid4()),
        'name': name,
        'channels': body.get('channels', [])
    }
    data['clients'].append(client)
    save_data(data)
    return jsonify(client)


@app.route('/clients', methods=['GET'])
@require_superadmin
def list_clients():
    return jsonify(clients=data.get('clients', []))


@app.route('/clients/<client_id>/channels', methods=['POST'])
@require_superadmin
def set_client_channels(client_id):
    body = request.get_json(silent=True) or {}
    channels = body.get('channels')
    if channels is None or not isinstance(channels, list):
        return jsonify(error='channels must be a list'), 400
    for c in data.get('clients', []):
        if c['id'] == client_id:
            c['channels'] = channels
            save_data(data)
            return jsonify(client=c)
    return jsonify(error='client not found'), 404


@app.route('/clients/<client_id>/channels', methods=['GET'])
@require_superadmin
def get_client_channels(client_id):
    for c in data.get('clients', []):
        if c['id'] == client_id:
            return jsonify(channels=c.get('channels', []))
    return jsonify(error='client not found'), 404


@app.route('/clients/<client_id>/register', methods=['POST'])
def client_register(client_id):
    # Allow a user to register for a specific client.
    body = request.get_json(silent=True) or {}
    username = body.get('username')
    password = body.get('password')
    if not username or not password:
        return jsonify(error='username and password required'), 400
    # check client exists
    client_exists = any(c['id'] == client_id for c in data.get('clients', []))
    if not client_exists:
        return jsonify(error='client not found'), 404
    # ensure username unique
    for u in data.get('users', []):
        if u.get('username') == username:
            return jsonify(error='username taken'), 400
    user = {
        'id': str(uuid.uuid4()),
        'username': username,
        'password_hash': generate_password_hash(password, method='pbkdf2:sha256'),
        'role': 'client',
        'client_id': client_id,
        'token': str(uuid.uuid4())
    }
    data['users'].append(user)
    save_data(data)
    return jsonify(id=user['id'], token=user['token'])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
