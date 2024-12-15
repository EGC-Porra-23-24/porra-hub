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
from unittest.mock import patch
import pytest

from app.modules.auth.models import User
from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import Author, DSMetaData, DSMetrics, DataSet
from app.modules.dataset.services import DataSetService
from app.modules.featuremodel.models import FMMetaData, FeatureModel
from app.modules.hubfile.models import Hubfile
from app.modules.profile.models import UserProfile


@pytest.fixture()
def dataset_service():
    dataset_service = DataSetService()
    with patch.object(dataset_service.dsmetadata_repository, 'create', return_value=DSMetaData(id=1)), \
         patch.object(dataset_service.author_repository, 'create', return_value=Author(id=1)), \
         patch.object(dataset_service.repository, 'create', return_value=DataSet(id=1)), \
         patch.object(dataset_service.fmmetadata_repository, 'create', return_value=FMMetaData(id=1)), \
         patch.object(dataset_service.feature_model_repository, 'create', return_value=FeatureModel(id=1)), \
         patch.object(dataset_service.hubfilerepository, 'create', return_value=Hubfile(id=1)):

        yield dataset_service


@pytest.fixture()
def current_user(dataset_service):
    profile = UserProfile(name="Jane", surname="Doe")
    current_user = User(email='test@example.com', password='test1234', profile=profile)
    yield current_user


def test_dsmetrics_with_whitespaces(dataset_service, current_user, test_app):

    with test_app.app_context():
        form = DataSetForm()
        form.feature_models[0].uvl_filename.data = 'file_that_uses_whitespaces.uvl'

    with patch.object(current_user, 'temp_folder', return_value='app/modules/dataset/uvl_examples'), \
         patch.object(dataset_service.dsmetrics_repository, 'create') as mock_create_dsmetrics:
        mock_create_dsmetrics.return_value = DSMetrics(id=1)

        dataset_service.create_from_form(form=form, current_user=current_user)
        mock_create_dsmetrics.assert_called_once_with(number_of_models=1,
                                                      number_of_features=10)


def test_dsmetrics_with_tabs(dataset_service, current_user, test_app):

    with test_app.app_context():
        form = DataSetForm()
        form.feature_models[0].uvl_filename.data = 'file_that_uses_tabs.uvl'

    with patch.object(current_user, 'temp_folder', return_value='app/modules/dataset/uvl_examples'), \
         patch.object(dataset_service.dsmetrics_repository, 'create') as mock_create_dsmetrics:
        mock_create_dsmetrics.return_value = DSMetrics(id=1)

        dataset_service.create_from_form(form=form, current_user=current_user)
        mock_create_dsmetrics.assert_called_once_with(number_of_models=1,
                                                      number_of_features=24)


def test_dsmetrics_both(dataset_service, current_user, test_app):

    with test_app.app_context():
        form = DataSetForm()
        form.feature_models[0].uvl_filename.data = 'file_that_uses_whitespaces.uvl'
        form.feature_models.append_entry(data={'uvl_filename': 'file_that_uses_tabs.uvl'})

    with patch.object(current_user, 'temp_folder', return_value='app/modules/dataset/uvl_examples'), \
         patch.object(dataset_service.dsmetrics_repository, 'create') as mock_create_dsmetrics:
        mock_create_dsmetrics.return_value = DSMetrics(id=1)

        dataset_service.create_from_form(form=form, current_user=current_user)
        mock_create_dsmetrics.assert_called_once_with(number_of_models=2,
                                                      number_of_features=34)
