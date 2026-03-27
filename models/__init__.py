from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.models import Question, ProjectLeader, Offer, Form, Feedback
