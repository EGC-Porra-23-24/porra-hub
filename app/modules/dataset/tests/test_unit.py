import pytest
from io import BytesIO
from zipfile import ZipFile


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    """
    with test_client.application.app_context():
        # Add HERE new elements to the database that you want to exist in the test context.
        # DO NOT FORGET to use db.session.add(<element>) and db.session.commit() to save the data.
        pass

    yield test_client


@pytest.fixture
def login(test_client):
    """
    Realiza el login y devuelve el token JWT para su uso en las pruebas.
    """
    response = test_client.post(
        "/login", data=dict(email="test@example.com", password="test1234"), follow_redirects=True
    )
    assert response.status_code == 200 and response.request.path == "/"

    cookies = response.headers.getlist('Set-Cookie')

    remember_token = None
    session = None

    for cookie in cookies:
        if 'remember_token' in cookie:
            remember_token = cookie.split(';')[0].split('=')[1]
        elif 'session' in cookie:
            session = cookie.split(';')[0].split('=')[1]

    return remember_token, session


def test_upload_valid_zip(test_client, login):
    """
    Prueba para cargar un archivo ZIP válido.
    """
    remember_token, session = login

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('testfile.uvl', 'contenido del archivo UVL')

    zip_buffer.seek(0)
    data = {
        'file': (zip_buffer, 'test.zip')
    }

    headers = {
        'Cookie': f'remember_token={remember_token}; session={session}'
    }

    response = test_client.post('/dataset/file/upload/zip',
                                data=data, headers=headers, content_type='multipart/form-data')

    assert response.status_code == 200


def test_upload_zip_without_uvl(test_client, login):
    """
    Verifica que no se encuentran archivos .uvl en el zip.
    """
    remember_token, session = login

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('testfile.txt', 'contenido del archivo de texto')

    zip_buffer.seek(0)
    data = {
        'file': (zip_buffer, 'test.zip')
    }

    headers = {'Cookie': f'remember_token={remember_token}; session={session}'}

    response = test_client.post('/dataset/file/upload/zip',
                                data=data, headers=headers, content_type='multipart/form-data')

    assert response.status_code == 400


def test_upload_invalid_zip(test_client, login):
    """
    Verifica que un archivo que no es un ZIP da un error.
    """
    remember_token, session = login

    data = {
        'file': (BytesIO(b"Not a zip file"), 'invalid.zip')
    }

    headers = {'Cookie': f'remember_token={remember_token}; session={session}'}

    response = test_client.post('/dataset/file/upload/zip',
                                data=data, headers=headers, content_type='multipart/form-data')

    assert response.status_code == 400


def test_upload_no_file(test_client, login):
    """
    Verifica que no se envía archivo en la solicitud.
    """
    remember_token, session = login

    data = {}

    headers = {'Cookie': f'remember_token={remember_token}; session={session}'}

    response = test_client.post('/dataset/file/upload/zip',
                                data=data, headers=headers, content_type='multipart/form-data')

    assert response.status_code == 400
