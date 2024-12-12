import pytest
from flask import url_for
from app import create_app, db
from app.modules.auth.models import User, Community
from flask_login import login_user, logout_user

from app.modules.profile.models import UserProfile


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

    # Crear usuarios
    user1 = User(id=111, email="owner1@example.com", password="password123")
    user2 = User(id=222, email="member1@example.com", password="password123")
    user3 = User(id=333, email="requester1@example.com", password="password123")

    # Crear perfiles
    profile1 = UserProfile(
        user_id=user1.id,
        name="Owner 1",
        surname="Surname 1",
        orcid="0000-0000-0000-0001",
        affiliation="University of Example"
    )
    profile2 = UserProfile(
        user_id=user2.id,
        name="Member 1",
        surname="Surname 2",
        orcid="0000-0000-0000-0002",
        affiliation="Institute of Example"
    )
    profile3 = UserProfile(
        user_id=user3.id,
        name="Requester 1",
        surname="Surname 3",
        orcid="0000-0000-0000-0003",
        affiliation="Research Center Example"
    )

    # Crear comunidades
    community1 = Community(id=111, name="Scientific Community")
    community2 = Community(id=222, name="Data Community")

    # Asociar usuarios a las comunidades
    community1.owners.append(user1)
    community1.members.append(user1)
    community1.members.append(user2)
    community1.requests.append(user3)

    # Añadir todos los datos a la base de datos
    db.session.add_all([user1, user2, user3, community1, community2, profile1, profile2, profile3])
    db.session.commit()

    return user1, user2, user3, community1, community2


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


def test_view_community_existing(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(
            url_for('community.view_community', community_id=community.id),
            follow_redirects=True
        )

        assert response.status_code == 200
        assert 'Scientific Community' in response.data.decode('utf-8')
        assert user.profile.name in response.data.decode('utf-8')


def test_view_community_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(
            url_for('community.view_community', community_id=9999),
            follow_redirects=True
        )

        assert response.status_code == 404
        assert 'Community not found' in response.data.decode('utf-8')


def test_view_community_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(
            url_for('community.view_community', community_id=community.id),
            follow_redirects=True
        )

        assert response.status_code == 200
        assert 'Scientific Community' in response.data.decode('utf-8')
        assert 'Requests' in response.data.decode('utf-8')


def test_create_community_page_access(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for('community.create_community_page'))

        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        assert "Create a New Community" in response_data

        logout_user()


def test_create_community_page_unauthenticated_access(client, app, setup_data):
    response = client.get('/community/create')

    assert response.status_code == 302


def test_create_community_success(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.post(
            url_for('community.create_community'),
            data={'name': 'New Community test'},
            follow_redirects=True
        )

        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        assert "New Community test" in response_data


def test_create_community_missing_name(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.post(
            url_for('community.create_community'),
            data={'name': ''},
            follow_redirects=True
        )

        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        print(response_data)
        assert 'Create a New Community' in response_data


def test_edit_community_page_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(
            url_for('community.edit_community_page', community_id=community.id)
        )

        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        assert 'Edit Community' in response_data
        assert community.name in response_data


def test_edit_community_page_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(
            url_for('community.edit_community_page', community_id=community.id)
        )

        assert response.status_code == 403
        response_data = response.data.decode('utf-8')
        assert 'Forbidden' in response_data


def test_edit_community_page_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        response = client.get(url_for('community.edit_community_page', community_id=9999))

        assert response.status_code == 404
        response_data = response.data.decode('utf-8')
        assert 'Community not found' in response_data


def test_edit_community_page_unauthenticated(client, app, setup_data):
    community = Community.query.filter_by(name="Scientific Community").first()
    url = '/community/' + str(community.id) + '/edit'

    response = client.get(url, follow_redirects=True)

    assert response.status_code == 200
    response_data = response.data.decode('utf-8')
    assert 'Login' in response_data


def test_edit_community_post_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        new_name = "Updated Community Name"

        response = client.post(
            url_for('community.edit_community', community_id=community.id),
            data={'name': new_name},
            follow_redirects=True
        )

        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        assert 'Updated Community Name' in response_data

        updated_community = Community.query.filter_by(id=community.id).first()
        assert updated_community.name == new_name


def test_edit_community_post_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(
            url_for('community.edit_community', community_id=community.id),
            data={'name': 'New Name'},
            follow_redirects=True
        )

        assert response.status_code == 403
        response_data = response.data.decode('utf-8')
        assert 'Forbidden' in response_data


def test_edit_community_post_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        response = client.post(
            url_for('community.edit_community', community_id=9999),
            data={'name': 'New Name'},
            follow_redirects=True
        )

        assert response.status_code == 404
        response_data = response.data.decode('utf-8')
        assert 'Community not found' in response_data


def test_delete_community_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(
            url_for('community.delete_community', community_id=community.id),
            follow_redirects=True
        )

        assert response.status_code == 200
        response_data = response.data.decode('utf-8')
        assert 'My Communities' in response_data

        deleted_community = Community.query.filter_by(id=community.id).first()
        assert deleted_community is None


def test_delete_community_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(
            url_for('community.delete_community', community_id=community.id),
            follow_redirects=True
        )

        assert response.status_code == 403
        response_data = response.data.decode('utf-8')
        assert 'Forbidden' in response_data


def test_delete_community_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        response = client.post(
            url_for('community.delete_community', community_id=9999),
            follow_redirects=True
        )

        assert response.status_code == 404
        response_data = response.data.decode('utf-8')
        assert 'Community not found' in response_data


def test_delete_community_unauthenticated(client, app, setup_data):
    community = Community.query.filter_by(name="Scientific Community").first()
    url = '/community/' + str(community.id) + '/delete'

    response = client.post(url, follow_redirects=True)

    assert response.status_code == 200
    response_data = response.data.decode('utf-8')
    assert 'Login' in response_data
