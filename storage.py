import os
import json
import uuid
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get('OMNI_DB', os.path.join(os.path.dirname(__file__), 'omnichannel.db'))
DB_URL = f'sqlite:///{DB_PATH}'

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    token = Column(String, unique=True, nullable=True)
    client_id = Column(String, nullable=True)


class Client(Base):
    __tablename__ = 'clients'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    channels = Column(Text, nullable=True)  # JSON string


engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    # migrate data.json if present
    data_file = os.path.join(os.path.dirname(__file__), 'data.json')
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                txt = f.read()
                obj = json.loads(txt)
        except Exception:
            # try to decode first JSON document
            with open(data_file, 'r') as f:
                txt = f.read()
                from json import JSONDecoder
                dec = JSONDecoder()
                obj, _ = dec.raw_decode(txt)
        s = SessionLocal()
        # users
        for u in obj.get('users', []):
            if not s.query(User).filter_by(username=u.get('username')).first():
                pwd_hash = u.get('password_hash') or generate_password_hash(u.get('password', ''), method='pbkdf2:sha256')
                token = u.get('token') or str(uuid.uuid4())
                user = User(id=u.get('id') or str(uuid.uuid4()), username=u.get('username'), password_hash=pwd_hash, role=u.get('role','client'), token=token, client_id=u.get('client_id'))
                s.add(user)
        # clients
        for c in obj.get('clients', []):
            if not s.query(Client).filter_by(id=c.get('id')).first():
                client = Client(id=c.get('id') or str(uuid.uuid4()), name=c.get('name'), channels=json.dumps(c.get('channels', [])))
                s.add(client)
        s.commit()
        s.close()


def get_session():
    return SessionLocal()


def find_user_by_token(token):
    s = get_session()
    u = s.query(User).filter_by(token=token).first()
    s.close()
    return u


def create_superadmin_if_missing(username, password):
    s = get_session()
    existing = s.query(User).filter_by(role='superadmin').first()
    if existing:
        if existing.token is None:
            existing.token = str(uuid.uuid4())
            s.commit()
        s.close()
        return existing
    user = User(id=str(uuid.uuid4()), username=username, password_hash=generate_password_hash(password, method='pbkdf2:sha256'), role='superadmin', token=str(uuid.uuid4()))
    s.add(user)
    s.commit()
    s.refresh(user)
    s.close()
    return user


def authenticate_user(username, password):
    s = get_session()
    u = s.query(User).filter_by(username=username).first()
    if not u:
        s.close()
        return None
    if check_password_hash(u.password_hash, password):
        if not u.token:
            u.token = str(uuid.uuid4())
            s.commit()
        token = u.token
        role = u.role
        s.close()
        return {'token': token, 'role': role}
    s.close()
    return None


def create_client(name, channels=None):
    s = get_session()
    client = Client(id=str(uuid.uuid4()), name=name, channels=json.dumps(channels or []))
    s.add(client)
    s.commit()
    s.refresh(client)
    d = {'id': client.id, 'name': client.name, 'channels': json.loads(client.channels or '[]')}
    s.close()
    return d


def list_clients():
    s = get_session()
    rows = s.query(Client).all()
    out = []
    for c in rows:
        out.append({'id': c.id, 'name': c.name, 'channels': json.loads(c.channels or '[]')})
    s.close()
    return out


def set_client_channels(client_id, channels):
    s = get_session()
    c = s.query(Client).filter_by(id=client_id).first()
    if not c:
        s.close()
        return None
    c.channels = json.dumps(channels)
    s.commit()
    out = {'id': c.id, 'name': c.name, 'channels': json.loads(c.channels or '[]')}
    s.close()
    return out


def get_client_channels(client_id):
    s = get_session()
    c = s.query(Client).filter_by(id=client_id).first()
    if not c:
        s.close()
        return None
    channels = json.loads(c.channels or '[]')
    s.close()
    return channels


def register_client_user(client_id, username, password):
    s = get_session()
    c = s.query(Client).filter_by(id=client_id).first()
    if not c:
        s.close()
        return None
    if s.query(User).filter_by(username=username).first():
        s.close()
        return 'taken'
    user = User(id=str(uuid.uuid4()), username=username, password_hash=generate_password_hash(password, method='pbkdf2:sha256'), role='client', client_id=client_id, token=str(uuid.uuid4()))
    s.add(user)
    s.commit()
    s.refresh(user)
    token = user.token
    s.close()
    return {'id': user.id, 'token': token}


# initialize DB on import
init_db()
