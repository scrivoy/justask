from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, session, abort
from models import db
from models.models import Form, Feedback, Question
from utils import get_questions, t, validate_csrf, send_notification
from extensions import limiter
import os

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('/form/<token>')
def form(token):
    form = Form.query.filter_by(token=token).first()
    if not form:
        return render_template('customer/form.html', error=True, error_title=t('error_invalid'), token=token)
    if form.completed:
        return render_template('customer/form.html', error=True, error_title=t('error_used'), error_contact=True, token=token)

    offer = form.offer
    questions = get_questions()
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'de'))

    questions_translated = []
    for q in questions:
        questions_translated.append({
            'id': q['id'],
            'text': q['text'].get(lang, q['text'].get('de'))
        })

    return render_template('customer/form.html',
        offer=offer, form=form,
        questions=questions_translated, token=token)

@customer_bp.route('/form/<token>/submit', methods=['POST'])
@limiter.limit("5 per minute")
def submit(token):
    validate_csrf()
    form = Form.query.filter_by(token=token).first()
    if not form:
        abort(404)

    # Atomic check-and-set to prevent race condition (double submission).
    updated = db.session.query(Form).filter(
        Form.id == form.id,
        Form.completed == False
    ).update({"completed": True, "completed_at": datetime.now(timezone.utc)})
    if not updated:
        abort(400)

    questions = get_questions()

    for q in questions:
        rating_str = request.form.get(f'question_{q["id"]}', '')
        if not rating_str:
            continue
        try:
            rating = int(rating_str)
        except ValueError:
            abort(400)
        if rating < 1 or rating > 5:
            abort(400)

        feedback = Feedback(
            form_id=form.id,
            question_id=q['id'],
            rating=rating
        )
        db.session.add(feedback)

    comment = request.form.get('comment', '').strip()
    if comment:
        form.comment = comment[:2000]

    db.session.commit()

    send_notification(form)

    return render_template('customer/success.html', token=token)

@customer_bp.route('/language/<token>/<lang>')
def set_language(token, lang):
    if lang in ('de', 'en'):
        session['lang'] = lang
    return redirect(url_for('customer.form', token=token))
