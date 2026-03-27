from datetime import datetime, timezone
from models import db


class Question(db.Model):
    """Question definitions loaded from locales/questions.json."""
    __tablename__ = "questions"

    id = db.Column(db.String(16), primary_key=True)  # e.g. "q1"
    sort_order = db.Column(db.Integer, nullable=False)

    feedback = db.relationship(
        "Feedback",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class ProjectLeader(db.Model):
    """Project manager - managed by admin."""
    __tablename__ = "project_leaders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )



class Offer(db.Model):
    __tablename__ = "offers"

    id = db.Column(db.Integer, primary_key=True)
    offer_number = db.Column(db.String(32), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    project_number = db.Column(db.Text, nullable=True)
    leader_name = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )

    forms = db.relationship(
        "Form",
        back_populates="offer",
        cascade="all, delete-orphan",
    )


class Form(db.Model):
    """Feedback form - one UUID token per recipient/stakeholder."""
    __tablename__ = "forms"

    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(
        db.Integer,
        db.ForeignKey("offers.id"),
        nullable=False,
    )
    # UUID-v4, generated in application code.
    token = db.Column(db.String(36), nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )
    completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    # Optional free-text comment submitted by the customer.
    comment = db.Column(db.Text, nullable=True)

    offer = db.relationship("Offer", back_populates="forms")
    feedback = db.relationship(
        "Feedback",
        back_populates="form",
        cascade="all, delete-orphan",
    )


class Feedback(db.Model):
    """Single rating answer for one question inside a form."""
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(
        db.Integer,
        db.ForeignKey("forms.id"),
        nullable=False,
    )
    question_id = db.Column(
        db.String(16),
        db.ForeignKey("questions.id"),
        nullable=False,
    )
    # Rating 1-5, validated server-side before insert.
    rating = db.Column(db.Integer, nullable=False)
    submitted_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
    )

    form = db.relationship("Form", back_populates="feedback")
    question = db.relationship("Question", back_populates="feedback")
