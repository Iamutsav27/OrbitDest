from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from storage import create_superadmin_if_missing, authenticate_user, create_client, list_clients, set_client_channels, get_client_channels, register_client_user, find_user_by_token
from storage import set_client_credential, get_client_credential, list_client_credentials

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    return response


def require_superadmin(fn):
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth.split(None, 1)[1]
            user = find_user_by_token(token)
            if user and getattr(user, 'role', None) == 'superadmin':
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
    user = create_superadmin_if_missing(username, password)
    return jsonify(id=user.id, token=user.token)


@app.route('/login', methods=['POST'])
def login():
    body = request.get_json(silent=True) or {}
    username = body.get('username')
    password = body.get('password')
    auth = authenticate_user(username, password)
    if auth:
        return jsonify(token=auth['token'], role=auth['role'])
    return jsonify(error='invalid credentials'), 401


@app.route('/clients', methods=['POST'])
@require_superadmin
def create_client_endpoint():
    body = request.get_json(silent=True) or {}
    name = body.get('name')
    if not name:
        return jsonify(error='name required'), 400
    client = create_client(name)
    return jsonify(client)


@app.route('/clients', methods=['GET'])
@require_superadmin
def list_clients_endpoint():
    clients = list_clients()
    return jsonify(clients=clients)


@app.route('/clients/<client_id>/channels', methods=['POST'])
@require_superadmin
def set_client_channels_endpoint(client_id):
    body = request.get_json(silent=True) or {}
    channels = body.get('channels')
    if channels is None or not isinstance(channels, list):
        return jsonify(error='channels must be a list'), 400
    client = set_client_channels(client_id, channels)
    if client is None:
        return jsonify(error='client not found'), 404
    return jsonify(client=client)


@app.route('/clients/<client_id>/channels', methods=['GET'])
@require_superadmin
def get_client_channels_endpoint(client_id):
    channels = get_client_channels(client_id)
    if channels is None:
        return jsonify(error='client not found'), 404
    return jsonify(channels=channels)


@app.route('/clients/<client_id>/register', methods=['POST'])
def client_register(client_id):
    body = request.get_json(silent=True) or {}
    username = body.get('username')
    password = body.get('password')
    if not username or not password:
        return jsonify(error='username and password required'), 400
    res = register_client_user(client_id, username, password)
    if res is None:
        return jsonify(error='client not found'), 404
    if res == 'taken':
        return jsonify(error='username taken'), 400
    return jsonify(id=res['id'], token=res['token'])


@app.route('/clients/<client_id>/credentials', methods=['GET'])
def list_credentials(client_id):
    # allow superadmin or client owner
    auth = request.headers.get('Authorization', '')
    user = None
    if auth.startswith('Bearer '):
        token = auth.split(None, 1)[1]
        user = find_user_by_token(token)
    if not user:
        return jsonify(error='unauthorized'), 401
    if user.role != 'superadmin' and user.client_id != client_id:
        return jsonify(error='forbidden'), 403
    creds = list_client_credentials(client_id)
    if creds is None:
        return jsonify(error='client not found'), 404
    return jsonify(credentials=creds)


@app.route('/clients/<client_id>/credentials/<channel>', methods=['GET'])
def get_credential(client_id, channel):
    auth = request.headers.get('Authorization', '')
    user = None
    if auth.startswith('Bearer '):
        token = auth.split(None, 1)[1]
        user = find_user_by_token(token)
    if not user:
        return jsonify(error='unauthorized'), 401
    if user.role != 'superadmin' and user.client_id != client_id:
        return jsonify(error='forbidden'), 403
    cred = get_client_credential(client_id, channel)
    if cred is None:
        return jsonify(error='not found'), 404
    return jsonify(credential=cred)


@app.route('/clients/<client_id>/credentials', methods=['POST'])
def set_credential(client_id):
    auth = request.headers.get('Authorization', '')
    user = None
    if auth.startswith('Bearer '):
        token = auth.split(None, 1)[1]
        user = find_user_by_token(token)
    if not user:
        return jsonify(error='unauthorized'), 401
    if user.role != 'superadmin' and user.client_id != client_id:
        return jsonify(error='forbidden'), 403
    body = request.get_json(silent=True) or {}
    channel = body.get('channel')
    config = body.get('config')
    if not channel or not isinstance(config, dict):
        return jsonify(error='channel and config(dict) required'), 400
    saved = set_client_credential(client_id, channel, config)
    if saved is None:
        return jsonify(error='client not found'), 404
    return jsonify(credential=saved)


@app.route('/me', methods=['GET'])
def me():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify(error='unauthorized'), 401
    token = auth.split(None, 1)[1]
    user = find_user_by_token(token)
    if not user:
        return jsonify(error='unauthorized'), 401
    return jsonify(id=user.id, username=user.username, role=user.role, client_id=user.client_id)


@app.route('/clients/<client_id>/info', methods=['GET'])
def client_info(client_id):
    # allow superadmin or the client owner
    auth = request.headers.get('Authorization', '')
    user = None
    if auth.startswith('Bearer '):
        token = auth.split(None, 1)[1]
        user = find_user_by_token(token)
    if not user:
        return jsonify(error='unauthorized'), 401
    if user.role != 'superadmin' and user.client_id != client_id:
        return jsonify(error='forbidden'), 403
    # fetch client
    from storage import get_client_channels
    channels = get_client_channels(client_id)
    if channels is None:
        return jsonify(error='client not found'), 404
    return jsonify(client_id=client_id, channels=channels)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
