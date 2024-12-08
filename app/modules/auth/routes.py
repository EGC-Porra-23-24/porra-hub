from flask import render_template, redirect, url_for, request
from flask_login import current_user, logout_user

from app.modules.auth import auth_bp
from app.modules.auth.forms import SignupForm, LoginForm
from app.modules.auth.services import AuthenticationService
from app.modules.profile.services import UserProfileService

authentication_service = AuthenticationService()
user_profile_service = UserProfileService()


@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        name = form.name.data
        surname = form.surname.data
        password = form.password.data

        if not authentication_service.is_email_available(email):
            return render_template(
                "auth/signup_form.html",
                form=form,
                error=f'Email {email} in use'
            )

        try:
            user_data = {
                'email': email,
                'name': name,
                'surname': surname,
                'password': password
            }

            authentication_service.send_verification_email(user_data)
        except Exception as exc:
            return render_template(
                "auth/signup_form.html",
                form=form,
                error=f'Error sending verification email: {exc}'
            )

        return render_template(
            "auth/signup_success.html",
            message="Check your inbox to verify your account."
        )

    return render_template("auth/signup_form.html", form=form)


@auth_bp.route('/verify/<token>', methods=["GET", "POST"])
def verify_email(token):
    try:
        user = authentication_service.verify_token(token)

        if user is None:
            return render_template(
                "auth/verification_failed.html",
                message="Email verification failed."
            )
        else:
            return render_template(
                "auth/verification_success.html",
                message="Email verified and user account created."
            )
    except Exception:
        return render_template(
            "auth/verification_failed.html",
            message="Email verification failed."
        )


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))

    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        if authentication_service.login(form.email.data, form.password.data):
            return redirect(url_for('public.index'))

        return render_template(
            "auth/login_form.html",
            form=form,
            error='Invalid credentials'
        )

    return render_template('auth/login_form.html', form=form)


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('public.index'))
