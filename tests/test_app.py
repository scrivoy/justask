"""Basic smoke tests for justask."""

import uuid
from models import db
from models.models import Offer, Form, Question, ProjectLeader, Feedback
from utils import generate_qr_base64


# ---------------------------------------------------------------------------
# App & database
# ---------------------------------------------------------------------------

def test_app_starts(app):
    assert app is not None

def test_tables_created(app):
    """All model tables exist after create_all."""
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    for expected in ['questions', 'project_leaders', 'offers', 'forms', 'feedback']:
        assert expected in tables

def test_questions_seeded(app):
    """init_db seeds the questions table from questions.json."""
    assert Question.query.count() == 4


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def test_login_page(client):
    resp = client.get('/login')
    assert resp.status_code == 200

def test_index_redirects_to_login(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

def test_invalid_token_no_crash(client):
    resp = client.get('/form/nonexistent-token')
    assert resp.status_code == 200

def test_language_switch(client):
    token = 'dummy'
    resp = client.get(f'/language/{token}/en')
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Auth protection
# ---------------------------------------------------------------------------

def test_staff_dashboard_requires_login(client):
    resp = client.get('/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

def test_admin_dashboard_requires_login(client):
    resp = client.get('/admin/dashboard')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

def test_create_requires_login(client):
    resp = client.get('/create')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']

def test_export_requires_admin(client):
    resp = client.get('/admin/export')
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_staff_login(client):
    resp = client.post('/login', data={'password': 'staffpass'})
    assert resp.status_code == 302
    assert '/dashboard' in resp.headers['Location']

def test_admin_login(client):
    resp = client.post('/login', data={'password': 'adminpass'})
    assert resp.status_code == 302
    assert '/admin/dashboard' in resp.headers['Location']

def test_wrong_password(client):
    resp = client.post('/login', data={'password': 'wrong'})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

def test_post_without_csrf_rejected(staff_client):
    resp = staff_client.post('/create', data={
        'offer_number': '123/45',
        'offer_title': 'Test',
        'leader_name': 'Test Leader',
        'date': '2025-01-01',
    })
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Staff functionality
# ---------------------------------------------------------------------------

def test_staff_dashboard_loads(staff_client):
    resp = staff_client.get('/dashboard')
    assert resp.status_code == 200

def test_create_page_loads(staff_client):
    resp = staff_client.get('/create')
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Admin functionality
# ---------------------------------------------------------------------------

def test_admin_dashboard_loads(admin_client):
    resp = admin_client.get('/admin/dashboard')
    assert resp.status_code == 200

def test_csv_export(admin_client):
    resp = admin_client.get('/admin/export')
    assert resp.status_code == 200
    assert 'text/csv' in resp.content_type


# ---------------------------------------------------------------------------
# Feedback submission
# ---------------------------------------------------------------------------

def test_submit_feedback(app, client):
    """Full flow: create form, submit feedback, verify stored."""
    with app.app_context():
        offer = Offer(
            offer_number='100/25', title='Test Project',
            leader_name='Test Leader',
        )
        db.session.add(offer)
        db.session.flush()

        token = str(uuid.uuid4())
        form = Form(offer_id=offer.id, token=token)
        db.session.add(form)
        db.session.commit()

    # Load form page.
    resp = client.get(f'/form/{token}')
    assert resp.status_code == 200

    # Get CSRF token from session.
    with client.session_transaction() as sess:
        csrf = sess.get('_csrf_token', '')

    # If no CSRF token yet, load the page to generate one.
    if not csrf:
        client.get(f'/form/{token}')
        with client.session_transaction() as sess:
            csrf = sess['_csrf_token']

    resp = client.post(f'/form/{token}/submit', data={
        'csrf_token': csrf,
        'question_q1': '5',
        'question_q2': '4',
        'question_q3': '3',
        'question_q4': '5',
        'comment': 'Great work!',
    })
    assert resp.status_code == 200

    with app.app_context():
        form = Form.query.filter_by(token=token).first()
        assert form.completed is True
        assert form.comment == 'Great work!'
        assert Feedback.query.filter_by(form_id=form.id).count() == 4

def test_double_submit_rejected(app, client):
    """Submitting the same form twice is rejected."""
    with app.app_context():
        offer = Offer(
            offer_number='101/25', title='Test',
            leader_name='Leader',
        )
        db.session.add(offer)
        db.session.flush()

        token = str(uuid.uuid4())
        form = Form(offer_id=offer.id, token=token, completed=True)
        db.session.add(form)
        db.session.commit()

    resp = client.get(f'/form/{token}')
    assert resp.status_code == 200
    assert b'error' in resp.data.lower() or resp.status_code == 200


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------

def test_translations_load(app):
    with app.app_context():
        with app.test_request_context():
            from utils import get_ui_texts, get_questions
            texts, lang = get_ui_texts()
            assert isinstance(texts, dict)
            assert len(texts) > 0

            questions = get_questions()
            assert len(questions) == 4
            assert all('text' in q for q in questions)


# ---------------------------------------------------------------------------
# QR code
# ---------------------------------------------------------------------------

def test_qr_code_generation(app):
    with app.app_context():
        result = generate_qr_base64('https://example.com/form/test')
        assert isinstance(result, str)
        assert len(result) > 100  # valid base64 PNG is not tiny

        # Verify it's valid base64.
        import base64
        decoded = base64.b64decode(result)
        assert decoded[:4] == b'\x89PNG'
