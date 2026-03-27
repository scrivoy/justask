import re
import uuid
import os
import json
from collections import defaultdict
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
import bcrypt
from models import db
from models.models import Offer, Form, ProjectLeader, Feedback, Question
from utils import (t, validate_csrf, require_staff, get_questions,
                   get_customer_link, generate_qr_base64)
from extensions import limiter

intranet_bp = Blueprint('intranet', __name__)

OFFER_NUMBER_PATTERN = re.compile(os.environ.get('OFFER_NUMBER_PATTERN', r'^\d{3}/\d{2}$'))
PROJECT_NUMBER_PATTERN = re.compile(
    os.environ.get('PROJECT_NUMBER_PATTERN') or os.environ.get('OFFER_NUMBER_PATTERN', r'^\d{3}/\d{2}$')
)

@intranet_bp.route('/')
def index():
    return redirect(url_for('intranet.login'))

@intranet_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if session.get('staff_logged_in') or session.get('admin_logged_in'):
        return redirect(url_for('intranet.dashboard'))

    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        staff_hash = os.environ.get('STAFF_PASSWORD_HASH', '')
        admin_hash = os.environ.get('ADMIN_PASSWORD_HASH', '')

        # Check admin password first (grants both staff + admin access)
        try:
            if admin_hash and bcrypt.checkpw(password.encode('utf-8'), admin_hash.encode('utf-8')):
                session['staff_logged_in'] = True
                session['admin_logged_in'] = True
                session.permanent = True
                return redirect(url_for('admin.dashboard'))
        except (ValueError, TypeError):
            pass

        # Check staff password
        try:
            if staff_hash and bcrypt.checkpw(password.encode('utf-8'), staff_hash.encode('utf-8')):
                session['staff_logged_in'] = True
                session.permanent = True
                return redirect(url_for('intranet.dashboard'))
        except (ValueError, TypeError):
            pass

        error = t('error_invalid_password')

    return render_template('intranet/login.html', error=error)

@intranet_bp.route('/logout', methods=['POST'])
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for('intranet.login'))

@intranet_bp.route('/dashboard')
@require_staff
def dashboard():
    questions = get_questions()
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'de'))
    question_ids = [q['id'] for q in questions]

    # Per-question averages
    feedback_query = db.session.query(
        Feedback.question_id,
        db.func.avg(Feedback.rating).label('avg'),
        db.func.count(Feedback.id).label('count')
    ).filter(Feedback.question_id.in_(question_ids)).group_by(Feedback.question_id).all()

    question_stats = {}
    for f in feedback_query:
        question_stats[f.question_id] = {'avg': round(f.avg, 2), 'count': f.count}

    total_avg = db.session.query(db.func.avg(Feedback.rating)).scalar()
    total_count = Form.query.filter_by(completed=True).count()

    questions_with_stats = []
    for q in questions:
        stats = question_stats.get(q['id'], {'avg': None, 'count': 0})
        questions_with_stats.append({
            'id': q['id'],
            'text': q['text'].get(lang, q['text'].get('de')),
            'avg': stats['avg'],
            'count': stats['count']
        })

    # Monthly averages for chart
    month_labels = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mai', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Dez'
    }
    monthly = defaultdict(list)
    completed_forms = (
        Form.query
        .filter_by(completed=True)
        .filter(Form.completed_at.isnot(None))
        .all()
    )
    for form in completed_forms:
        avg = db.session.query(db.func.avg(Feedback.rating)).filter_by(form_id=form.id).scalar()
        if avg is not None:
            key = (form.completed_at.year, form.completed_at.month)
            monthly[key].append(float(avg))

    sorted_months = sorted(monthly.keys())
    chart_labels = [f"{month_labels[m]} {str(y)[2:]}" for y, m in sorted_months]
    chart_data = [round(sum(monthly[k]) / len(monthly[k]), 2) for k in sorted_months]

    return render_template('intranet/dashboard.html',
        questions=questions_with_stats,
        total_rating=round(total_avg, 2) if total_avg else 0,
        total_responses=total_count,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data))

@intranet_bp.route('/create', methods=['GET', 'POST'])
@require_staff
def create():
    leaders = ProjectLeader.query.order_by(ProjectLeader.name).all()
    today = datetime.now().strftime('%Y-%m-%d')

    if request.method == 'POST':
        validate_csrf()

        offer_number = request.form.get('offer_number', '').strip()
        offer_title = request.form.get('offer_title', '').strip()
        project_number = request.form.get('project_number', '').strip()
        leader_name = request.form.get('leader_name', '').strip()
        date = request.form.get('date', '')

        # Validate offer number format
        if not OFFER_NUMBER_PATTERN.match(offer_number):
            flash(t('error_offer_number_format'), 'error')
            return render_template('intranet/create.html', leaders=leaders, today=today)

        # Validate project number format (optional, but must match if provided)
        if project_number and not PROJECT_NUMBER_PATTERN.match(project_number):
            flash(t('error_project_number_format'), 'error')
            return render_template('intranet/create.html', leaders=leaders, today=today)

        # Check if offer number already exists
        existing_offer = Offer.query.filter_by(offer_number=offer_number).first()

        if existing_offer:
            # Add new form to existing offer
            offer = existing_offer
        else:
            # New offer: require all fields
            if not all([offer_title, leader_name, date]):
                flash(t('error_required'), 'error')
                return render_template('intranet/create.html', leaders=leaders, today=today)

            # Create Offer
            offer = Offer(
                offer_number=offer_number,
                title=offer_title,
                project_number=project_number or None,
                leader_name=leader_name,
                date=datetime.strptime(date, '%Y-%m-%d').date()
            )
            db.session.add(offer)
            db.session.flush()

        # Create Form with token
        token = str(uuid.uuid4())
        form = Form(
            offer_id=offer.id,
            token=token
        )
        db.session.add(form)
        db.session.commit()

        generated_link = get_customer_link(token)
        qr_code = generate_qr_base64(generated_link)

        return render_template('intranet/create.html',
            leaders=leaders, today=today,
            generated_link=generated_link, qr_code=qr_code,
            created_offer=offer)

    return render_template('intranet/create.html',
        leaders=leaders, today=today)

@intranet_bp.route('/language/<lang>')
def set_language(lang):
    if lang in ('de', 'en'):
        session['lang'] = lang
    return redirect(url_for('intranet.dashboard'))
