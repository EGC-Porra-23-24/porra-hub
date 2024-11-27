from flask import render_template, redirect, url_for, request
from flask_login import current_user, login_user, logout_user

from app.modules.auth import auth_bp
from app.modules.auth.forms import SignupForm, LoginForm
from app.modules.auth.services import AuthenticationService
from app.modules.profile.services import UserProfileService


authentication_service = AuthenticationService()
user_profile_service = UserProfileService()


@auth_bp.route("/signup/", methods=["GET", "POST"])
@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        if not authentication_service.is_email_available(email):
            return render_template("auth/signup_form.html", form=form, error=f'Email {email} in use')

        # Generamos un token de verificación
        try:
            # Generamos un token para la verificación
            authentication_service.send_verification_email(email)  # Envía el correo con el token
        except Exception as exc:
            return render_template("auth/signup_form.html", form=form, error=f'Error sending verification email: {exc}')

        return render_template("auth/signup_success.html", message="Revisa tu correo para verificar tu cuenta.")

    return render_template("auth/signup_form.html", form=form)

@auth_bp.route('/verify/<token>')
def verify_email(token):
    # Verifica el token y obtiene el correo electrónico asociado
    email = authentication_service.verify_token(token)
    
    if email is None:
        return render_template("auth/verification_failed.html", message="El enlace de verificación es inválido o ha expirado.")
    
    # Si el token es válido, creamos al usuario
    try:
        # Aquí creamos el usuario una vez que se verifica el correo
        # Llamamos al método `create_with_profile` para crear el usuario
        user = authentication_service.create_with_profile(email=email)  # Puedes pasar otros datos si es necesario
        return render_template("auth/verification_success.html", message="Correo verificado y cuenta creada con éxito.")
    except Exception as exc:
        return render_template("auth/verification_failed.html", message=f"Error al crear el usuario: {exc}")
    
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        if authentication_service.login(form.email.data, form.password.data):
            return redirect(url_for('public.index'))

        return render_template("auth/login_form.html", form=form, error='Invalid credentials')

    return render_template('auth/login_form.html', form=form)


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('public.index'))
