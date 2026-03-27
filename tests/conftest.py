import os
import json
import pytest
import bcrypt

# Set test environment before any app imports.
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['DEFAULT_LANGUAGE'] = 'de'
os.environ['BASE_URL'] = 'http://localhost:5000'
os.environ['STAFF_PASSWORD_HASH'] = bcrypt.hashpw(b'staffpass', bcrypt.gensalt()).decode()
os.environ['ADMIN_PASSWORD_HASH'] = bcrypt.hashpw(b'adminpass', bcrypt.gensalt()).decode()

from app import create_app
from models import db as _db
from models.models import Question


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        _db.create_all()

        # Seed questions like init_db does.
        base_dir = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base_dir, 'locales', 'questions.json'), encoding='utf-8') as f:
            data = json.load(f)
        for q in data.get('questions', []):
            _db.session.add(Question(id=q['id'], sort_order=q['sort_order']))
        _db.session.commit()

        yield app

        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def staff_client(app):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['staff_logged_in'] = True
    return client


@pytest.fixture
def admin_client(app):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['staff_logged_in'] = True
        sess['admin_logged_in'] = True
    return client
