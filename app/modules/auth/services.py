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

    def create_with_profile(self, email: str, **kwargs):
        try:
            # Aquí puedes incluir más validaciones si lo deseas
            if not email:
                raise ValueError("Email is necessary.")

            # Solo creamos el usuario después de que haya sido verificado
            user_data = {
                "email": email,
                # Aquí puedes pasar otros datos del formulario, si se quieren incluir
            }

            # Crear el usuario en la base de datos
            user = self.create(commit=False, email=email, **kwargs)

            # Asociar perfil al usuario
            profile_data = kwargs.get("profile_data", {})
            profile_data["user_id"] = user.id
            self.user_profile_repository.create(**profile_data)

            # Guardamos los cambios en la base de datos
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
    def generate_verification_token(self, email):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(email, salt="email-verification-salt")

    def verify_token(self, token, expiration=3600):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = serializer.loads(token, salt="email-verification-salt", max_age=expiration)
        except Exception:
            return None
        return email
    def send_verification_email(self, user_email):
        # geneacion token
        token = self.generate_verification_token(user_email)
        verification_link = url_for('auth.verify_email', token=token, _external=True)

        # configuración correo que envia la verificacion
        sender_email = "respuestaus@gmail.com"
        sender_password = "RespuestaUS237500"
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