import pytest
from flask import url_for
from app import create_app, db
from app.modules.auth.models import User, Community
from flask_login import login_user


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def setup_data(app):
    """ Create initial data for tests """
    user1 = User(email="owner1@example.com", password="password123")
    user2 = User(email="member1@example.com", password="password123")
    user3 = User(email="requester1@example.com", password="password123")

    community1 = Community(name="Scientific Community")
    community2 = Community(name="Data Community")

    community1.owners.append(user1)
    community1.members.append(user1)
    community1.members.append(user2)
    community1.requests.append(user3)

    db.session.add_all([user1, user2, user3, community1, community2])
    db.session.commit()


def test_list_communities_authenticated(client, app, setup_data):
    """ Test access to the communities view with an authenticated user """
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for('community.list_communities'))

        assert response.status_code == 200
        # Decode the bytes to string
        response_data = response.data.decode('utf-8')

        assert "Scientific Community" in response_data
        assert "Data Community" in response_data


def test_list_communities_not_authenticated(client):
    """ Test access without authentication """
    response = client.get('/communities')
    assert response.status_code == 302  # Redirect to login


def test_search_communities_valid_query(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(
            url_for('community.search_communities', query='Scientific'),
            follow_redirects=True
        )

        assert response.status_code == 200
        assert 'Search Results' in response.data.decode('utf-8')
        assert 'Scientific Community' in response.data.decode('utf-8')


def test_search_communities_empty_query(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(
            url_for('community.search_communities', query=''),
            follow_redirects=True
        )

        assert response.status_code == 200
        assert 'Search Results' in response.data.decode('utf-8')
        assert 'No communities found' in response.data.decode('utf-8')


def test_search_communities_no_results(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(
            url_for('community.search_communities', query='Nonexistent'),
            follow_redirects=True
        )

        assert response.status_code == 200
        assert 'Search Results' in response.data.decode('utf-8')
        assert 'No communities found' in response.data.decode('utf-8')