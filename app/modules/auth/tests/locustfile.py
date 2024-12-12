from locust import HttpUser, TaskSet, task
from core.locust.common import get_csrf_token, fake
from core.environment.host import get_host_for_locust_testing
from app.modules.auth.services import AuthenticationService
from app import app_context


class SignupBehavior(TaskSet):
    def on_start(self):
        self.signup()

    @task
    def signup(self):
        response = self.client.get("/signup")
        csrf_token = get_csrf_token(response)

        name = fake.name()
        surname = fake.name()

        email = fake.email()
        password = fake.password()
        response = self.client.post("/signup", data={
            "email": email,
            "password": password,
            "name": name,
            "surname": surname,
            "csrf_token": csrf_token
        })

        if response.status_code != 200:
            print(f"Signup failed: {response.status_code}")

        self.verify_email(email, password, name, surname)

    def verify_email(self, email, password, name, surname):
        user_data = {
            "email": email,
            "password": password,
            "name": name,
            "surname": surname,
        }
        token = 0

        with app_context():
            token = AuthenticationService().generate_verification_token(user_data)

        response = self.client.post(f"/verify/{token}", data={})

        if response.status_code != 200:
            print(f"Verification failed: {response.status_code}")


class LoginBehavior(TaskSet):
    def on_start(self):
        self.ensure_logged_out()
        self.login()

    @task
    def ensure_logged_out(self):
        response = self.client.get("/logout")
        if response.status_code != 200:
            print(f"Logout failed or no active session: {response.status_code}")

    @task
    def login(self):
        response = self.client.get("/login")
        if response.status_code != 200 or "Login" not in response.text:
            print("Already logged in or unexpected response, redirecting to logout")
            self.ensure_logged_out()
            response = self.client.get("/login")

        csrf_token = get_csrf_token(response)

        response = self.client.post("/login", data={
            "email": 'user1@example.com',
            "password": '1234',
            "csrf_token": csrf_token
        })
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")


class AuthUser(HttpUser):
    tasks = [SignupBehavior, LoginBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
