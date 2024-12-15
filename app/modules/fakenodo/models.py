from app import db


class Fakenodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)


class Deposition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deposition_metadata = db.Column(db.JSON, nullable=False)
    is_published = db.Column(db.Boolean, default=False)
    doi = db.Column(db.String(100), unique=True, nullable=True)
