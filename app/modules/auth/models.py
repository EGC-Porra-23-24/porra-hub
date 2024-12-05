from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    data_sets = db.relationship('DataSet', backref='user', lazy=True)
    profile = db.relationship('UserProfile', backref='user', uselist=False)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if 'password' in kwargs:
            self.set_password(kwargs['password'])

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def temp_folder(self) -> str:
        from app.modules.auth.services import AuthenticationService
        return AuthenticationService().temp_folder_by_user(self)


community_owners = db.Table(
    'community_owners',
    db.metadata,
    db.Column('community_id', db.Integer, db.ForeignKey('community.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

community_members = db.Table(
    'community_members',
    db.metadata,
    db.Column('community_id', db.Integer, db.ForeignKey('community.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

community_request = db.Table(
    'community_request',
    db.metadata,
    db.Column('community_id', db.Integer, db.ForeignKey('community.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


class Community(db.Model):
    __tablename__ = 'community'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    owners = db.relationship(
        'User',
        secondary=community_owners,
        backref=db.backref('owned_communities', lazy='dynamic'),
        lazy='dynamic'
    )

    members = db.relationship(
        'User',
        secondary=community_members,
        backref=db.backref('joined_communities', lazy='dynamic'),
        lazy='dynamic'
    )

    requests = db.relationship(
        'User',
        secondary=community_request,
        backref=db.backref('requested_communities', lazy='dynamic'),
        lazy='dynamic'
    )
