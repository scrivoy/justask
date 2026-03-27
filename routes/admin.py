import csv
import io
import os
import json
from collections import defaultdict
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, Response
from models import db
from models.models import Offer, Form, Feedback, ProjectLeader, Question
from utils import t, validate_csrf, require_admin, get_questions, get_customer_link

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('intranet.login'))

@admin_bp.route('/dashboard')
@require_admin
def dashboard():
    lang = session.get('lang', os.environ.get('DEFAULT_LANGUAGE', 'de'))
    questions = get_questions()

    # --- Chart data: monthly averages ---
    month_labels_map = {
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
    chart_labels = [f"{month_labels_map[m]} {str(y)[2:]}" for y, m in sorted_months]
    chart_data = [round(sum(monthly[k]) / len(monthly[k]), 2) for k in sorted_months]

    # --- Table: last 10 completed forms ---
    latest_forms = (
        Form.query
        .join(Offer)
        .filter(Form.completed == True)
        .order_by(Form.created_at.desc())
        .limit(10)
        .all()
    )

    table_rows = []
    for form in latest_forms:
        offer = form.offer
        feedbacks = Feedback.query.filter_by(form_id=form.id).all()
        avg_rating = round(sum(fb.rating for fb in feedbacks) / len(feedbacks), 1) if feedbacks else None

        table_rows.append({
            'id': form.id,
            'offer_number': offer.offer_number,
            'offer_title': offer.title,
            'project_number': offer.project_number,
            'leader_name': offer.leader_name,
            'date': offer.date,
            'completed': form.completed,
            'completed_at': form.completed_at,
            'avg_rating': avg_rating,
            'comment': form.comment,
        })

    # --- Open links: all non-completed forms ---
    open_forms = (
        Form.query
        .join(Offer)
        .filter(Form.completed == False)
        .order_by(Form.created_at.desc())
        .all()
    )

    open_links = []
    for form in open_forms:
        offer = form.offer
        open_links.append({
            'id': form.id,
            'offer_number': offer.offer_number,
            'title': offer.title,
            'project_number': offer.project_number,
            'leader_name': offer.leader_name,
            'created_at': form.created_at,
            'link': get_customer_link(form.token)
        })

    # --- Leaders management ---
    leaders = ProjectLeader.query.order_by(ProjectLeader.name).all()
    leader_names = '\n'.join([l.name for l in leaders])

    return render_template('admin/dashboard.html',
        table_rows=table_rows,
        open_links=open_links,
        chart_labels=json.dumps(chart_labels),
        chart_data=json.dumps(chart_data),
        leaders=leaders,
        leader_names=leader_names)

@admin_bp.route('/delete/<int:id>', methods=['POST'])
@require_admin
def delete_form(id):
    validate_csrf()
    form = Form.query.get_or_404(id)

    if form.completed:
        flash(t('error_delete_completed'), 'error')
        return redirect(url_for('admin.dashboard'))

    offer = form.offer
    db.session.delete(form)
    db.session.flush()

    if not offer.forms:
        db.session.delete(offer)

    db.session.commit()
    flash(t('link_deleted'), 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete-open', methods=['POST'])
@require_admin
def delete_all_open():
    validate_csrf()
    open_forms = Form.query.filter_by(completed=False).all()
    for form in open_forms:
        offer = form.offer
        db.session.delete(form)
        db.session.flush()
        if not offer.forms:
            db.session.delete(offer)
    db.session.commit()
    flash(t('all_open_deleted'), 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/leaders/save', methods=['POST'])
@require_admin
def save_leaders():
    validate_csrf()
    leaders_text = request.form.get('leaders', '')
    new_names = set(n.strip() for n in leaders_text.split('\n') if n.strip())

    existing = ProjectLeader.query.all()
    existing_names = set(l.name for l in existing)
    existing_map = {l.name: l for l in existing}

    for name in (existing_names - new_names):
        leader = existing_map[name]
        db.session.delete(leader)

    for name in (new_names - existing_names):
        db.session.add(ProjectLeader(name=name))

    db.session.commit()
    flash(t('saved'), 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/export')
@require_admin
def export_csv():
    questions = get_questions()

    forms = (
        Form.query
        .join(Offer)
        .order_by(Form.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    # Header - always English
    header = ['Offer Number', 'Title', 'Project Number', 'Project Leader', 'Date', 'Status', 'Completed On']
    for q in questions:
        header.append(q['text'].get('en', q['text'].get('de'))[:50])
    header.extend(['Average', 'Comment'])
    writer.writerow(header)

    for form in forms:
        offer = form.offer
        feedbacks = {fb.question_id: fb.rating for fb in Feedback.query.filter_by(form_id=form.id).all()}

        row = [
            offer.offer_number,
            offer.title,
            offer.project_number or '',
            offer.leader_name,
            offer.date.strftime('%Y-%m-%d') if offer.date else '',
            'completed' if form.completed else 'open',
            form.completed_at.strftime('%Y-%m-%d') if form.completed_at else ''
        ]

        total = 0
        count = 0
        for q in questions:
            rating = feedbacks.get(q['id'])
            row.append(rating if rating else '')
            if rating:
                total += rating
                count += 1

        row.append(round(total / count, 2) if count > 0 else '')
        row.append(form.comment or '')
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=feedback_export_{datetime.now().strftime("%Y%m%d")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )

@admin_bp.route('/logout', methods=['POST'])
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for('intranet.login'))
