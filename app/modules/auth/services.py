import os
from flask_login import login_user
from flask_login import current_user

from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService

from itsdangerous import URLSafeTimedSerializer
from flask import current_app
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import url_for

class AuthenticationService(BaseService):
    def __init__(self):
        super().__init__(UserRepository())
        self.user_profile_repository = UserProfileRepository()

    def login(self, email, password, remember=True):
        user = self.repository.get_by_email(email)
        if user is not None and user.check_password(password):
            login_user(user, remember=remember)
            return True
        return False

    def is_email_available(self, email: str) -> bool:
        return self.repository.get_by_email(email) is None

    def create_with_profile(self, **kwargs):
        try:
            email = kwargs.pop("email", None)
            password = kwargs.pop("password", None)
            name = kwargs.pop("name", None)
            surname = kwargs.pop("surname", None)
            if not self.is_email_available(email):
                return None
            if not email:
                raise ValueError("Email is required.")
            if not password:
                raise ValueError("Password is required.")
            if not name:
                raise ValueError("Name is required.")
            if not surname:
                raise ValueError("Surname is required.")

            user_data = {
                "email": email,
                "password": password
            }

            profile_data = {
                "name": name,
                "surname": surname,
            }

            user = self.create(commit=False, **user_data)
            profile_data["user_id"] = user.id
            self.user_profile_repository.create(**profile_data)
            self.repository.session.commit()
        except Exception as exc:
            self.repository.session.rollback()
            raise exc
        return user


    def update_profile(self, user_profile_id, form):
        if form.validate():
            updated_instance = self.update(user_profile_id, **form.data)
            return updated_instance, None

        return None, form.errors

    def get_authenticated_user(self) -> User | None:
        if current_user.is_authenticated:
            return current_user
        return None

    def get_authenticated_user_profile(self) -> UserProfile | None:
        if current_user.is_authenticated:
            return current_user.profile
        return None

    def temp_folder_by_user(self, user: User) -> str:
        return os.path.join(uploads_folder_name(), "temp", str(user.id))
    
    def generate_verification_token(self, user_data):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(user_data, salt="user-registration-salt")

    def verify_token(self, token):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            user_data = serializer.loads(token, salt="user-registration-salt", max_age=3600)
        except Exception as e:
            print(f"Error verifying token: {e}")
            return None
        
        user=self.create_with_profile(**user_data)
        return user
    def send_verification_email(self, user_data):
        # geneacion token
        user_email=user_data.get("email")
        if not self.is_email_available(user_email):
            return
        token = self.generate_verification_token(user_data)
        verification_link = url_for('auth.verify_email', token=token, _external=True)
        # configuración correo que envia la verificacion
        sender_email = os.getenv('VERIFICATION_EMAIL')
        sender_password = os.getenv('VERIFICATION_EMAIL_PASSWORD')
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = user_email
        msg['Subject'] = "[UvlHub] Email verify"
        body = f"Hi, please verify your email with this link: {verification_link}"
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, user_email, msg.as_string())
            server.quit()
            print("Verification email sent successfully")
        except Exception as e:
            print(f"Failed sending email: {e}")