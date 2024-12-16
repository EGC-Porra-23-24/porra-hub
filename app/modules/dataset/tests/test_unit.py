from datetime import datetime
import os
import tempfile
from unittest import mock
import pytest
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from app import create_app, db
from app.modules import hubfile
from app.modules.auth.models import User
from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import Author, DSMetaData, DSMetrics, DataSet, PublicationType
from app.modules.dataset.services import DataSetService
from app.modules.featuremodel.models import FMMetaData, FeatureModel
from app.modules.hubfile.models import Hubfile
from app.modules.profile.models import UserProfile
from flamapy.metamodels.fm_metamodel.transformations import UVLReader, GlencoeWriter, SPLOTWriter
from flamapy.metamodels.pysat_metamodel.transformations import FmToPysat, DimacsWriter



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


# Fixture de pytest
@pytest.fixture(scope="function")
def client():
    app = create_app('testing')  # Usamos el entorno de testing
    with app.test_client() as client:
        with app.app_context():
            # Configuración de la base de datos en modo de prueba
            db.drop_all()
            db.create_all()

            # Crear un usuario de prueba (user_33)
            user = User(id=33, email="user33@example.com", password="1234", created_at=datetime(2022, 3, 13))
            db.session.add(user)
            db.session.commit()

            # Crear metadata para el dataset (dataset_33)
            dsmetadata = DSMetaData(id=33, title="Sample Dataset 33", description="Description for dataset 33",
                                    publication_type=PublicationType.DATA_MANAGEMENT_PLAN.name)
            db.session.add(dsmetadata)
            db.session.commit()

            # Crear el dataset (dataset_33)
            dataset = DataSet(id=33, user_id=user.id, ds_meta_data_id=dsmetadata.id)
            db.session.add(dataset)
            db.session.commit()

            # Crear un feature_model y asociarlo al dataset
            feature_model = FeatureModel(id=1, data_set_id=dataset.id)
            db.session.add(feature_model)
            db.session.commit()

            # Crear un archivo Hubfile asociado al feature_model (sin 'path')
            hubfile = Hubfile(id=1, feature_model_id=feature_model.id, name="file33.uvl",
                              checksum="dummy_checksum", size=1234)
            db.session.add(hubfile)
            db.session.commit()

            yield client

            db.session.remove()
            db.drop_all()


# Test para la descarga de todos los datasets (esperando un archivo ZIP)
def test_download_all_dataset(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:
        # Mockear al usuario correcto (user_33)
        mock_user = User(id=33, email="user33@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Crear datasets mock (dataset_33)
        mock_datasets = [
            mock.Mock(id=33, user_id=33, files=lambda: [mock.Mock(name="file33.uvl", id=1)]),
        ]

        # Mock de Hubfile con un id y un path
        hubfile_mock = mock.Mock(id=1, get_path=lambda: f"uploads/user_{mock_user.id}/dataset_{33}/file33.uvl")

        # Mockear la llamada a HubfileService.get_or_404
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404', return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f'user_{mock_user.id}', f'dataset_{33}', 'file33.uvl')
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, 'w') as f:
                    f.write('features\n')
                    f.write('    Chat\n')
                    f.write('        mandatory\n')
                    f.write('            Connection\n')
                    f.write('                alternative\n')
                    f.write('                    "Peer 2 Peer"\n')
                    f.write('                    Server\n')
                    f.write('            Messages\n')
                    f.write('                or\n')
                    f.write('                    Text\n')
                    f.write('                    Video\n')
                    f.write('                    Audio\n')
                    f.write('        optional\n')
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write('\n')
                    f.write('constraints\n')
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # Aquí comenzamos a crear el archivo ZIP
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        for file in dataset.files():
                            # Hacer que file.name sea un string
                            file.name = "file33.uvl"  # No es un Mock, es un string
                            zipf.write(file_path, os.path.basename(file_path))
                try:
                    # Verificación de la existencia del archivo
                    print(f"ZIP file exists at: {zip_path}")
                    assert os.path.exists(zip_path)
                    assert os.path.getsize(zip_path) > 0

                    # Aquí va tu lógica de comprobación del contenido del ZIP
                    with ZipFile(zip_path, 'r') as zipf:
                        # Verifica el contenido
                        zipf.testzip()  # Esto puede levantar una excepción si el ZIP está dañado

                    response = client.get('/dataset/download/all')
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")


# Test para la descarga de todos los datasets
def test_download_all_dataset_splx(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:
        # Mockear al usuario correcto (user_33)
        mock_user = User(id=33, email="user33@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Crear datasets mock (dataset_33)
        mock_datasets = [
            mock.Mock(id=33, user_id=33, files=lambda: [mock.Mock(name="file33.uvl", id=1)]),
        ]

        # Mock de Hubfile con un id y un path
        hubfile_mock = mock.Mock(id=1, get_path=lambda: f"uploads/user_{mock_user.id}/dataset_{33}/file33.uvl")

        # Mockear la llamada a HubfileService.get_or_404
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404', return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f'user_{mock_user.id}', f'dataset_{33}', 'file33.uvl')
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, 'w') as f:
                    f.write('features\n')
                    f.write('    Chat\n')
                    f.write('        mandatory\n')
                    f.write('            Connection\n')
                    f.write('                alternative\n')
                    f.write('                    "Peer 2 Peer"\n')
                    f.write('                    Server\n')
                    f.write('            Messages\n')
                    f.write('                or\n')
                    f.write('                    Text\n')
                    f.write('                    Video\n')
                    f.write('                    Audio\n')
                    f.write('        optional\n')
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write('\n')
                    f.write('constraints\n')
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                # Crear el archivo ZIP de salida
                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # Crear un archivo ZIP para simular la descarga
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        dataset_folder = f"dataset_{dataset.id}/"

                        for file in dataset.files():
                            content = ""
                            # Convertir el archivo UVL a SPLX directamente aquí
                            temp_file = tempfile.NamedTemporaryFile(suffix='.splx', delete=False)
                            fm = UVLReader(hubfile_mock.get_path()).transform()
                            SPLOTWriter(temp_file.name, fm).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()

                            # Nombre del archivo SPLX dentro del ZIP
                            file_name_in_zip = f"{hubfile_mock.id}_splot.txt"
                            
                            # Agregar el archivo SPLX al archivo ZIP
                            zipf.writestr(os.path.join(dataset_folder, file_name_in_zip), content)

                            # Eliminar el archivo SPLX temporal después de agregarlo al ZIP
                            os.remove(temp_file.name)

                try:
                    # Verificación de la existencia del archivo ZIP
                    print(f"ZIP file exists at: {zip_path}")
                    assert os.path.exists(zip_path)
                    assert os.path.getsize(zip_path) > 0

                    # Abrir el ZIP y comprobar que contiene el archivo con el sufijo '_splot.txt'
                    with ZipFile(zip_path, 'r') as zipf:
                        # Obtener los nombres de los archivos dentro del ZIP
                        zip_file_names = zipf.namelist()
                        
                        # Verificar que al menos un archivo tenga el sufijo '_splot.txt'
                        assert any(name.endswith('_splot.txt') for name in zip_file_names)
                    # Simulamos una llamada a la descarga del archivo ZIP
                    response = client.get('/dataset/download/all')
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")

# Test para la descarga de todos los datasets
def test_download_all_dataset_glencoe(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:
        # Mockear al usuario correcto (user_33)
        mock_user = User(id=33, email="user33@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Crear datasets mock (dataset_33)
        mock_datasets = [
            mock.Mock(id=33, user_id=33, files=lambda: [mock.Mock(name="file33.uvl", id=1)]),
        ]

        # Mock de Hubfile con un id y un path
        hubfile_mock = mock.Mock(id=1, get_path=lambda: f"uploads/user_{mock_user.id}/dataset_{33}/file33.uvl")

        # Mockear la llamada a HubfileService.get_or_404
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404', return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f'user_{mock_user.id}', f'dataset_{33}', 'file33.uvl')
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, 'w') as f:
                    f.write('features\n')
                    f.write('    Chat\n')
                    f.write('        mandatory\n')
                    f.write('            Connection\n')
                    f.write('                alternative\n')
                    f.write('                    "Peer 2 Peer"\n')
                    f.write('                    Server\n')
                    f.write('            Messages\n')
                    f.write('                or\n')
                    f.write('                    Text\n')
                    f.write('                    Video\n')
                    f.write('                    Audio\n')
                    f.write('        optional\n')
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write('\n')
                    f.write('constraints\n')
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                # Crear el archivo ZIP de salida
                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # Crear un archivo ZIP para simular la descarga
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        dataset_folder = f"dataset_{dataset.id}/"

                        for file in dataset.files():
                            content = ""
                            temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
                            fm = UVLReader(hubfile_mock.get_path()).transform()
                            GlencoeWriter(temp_file.name, fm).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()

                            # Nombre del archivo dentro del ZIP
                            file_name_in_zip = f"{hubfile_mock.id}_glencoe.txt"
                            
                            # Agregar el archivo al archivo ZIP
                            zipf.writestr(os.path.join(dataset_folder, file_name_in_zip), content)

                            # Eliminar el archivo temporal después de agregarlo al ZIP
                            os.remove(temp_file.name)

                try:
                    # Verificación de la existencia del archivo ZIP
                    print(f"ZIP file exists at: {zip_path}")
                    assert os.path.exists(zip_path)
                    assert os.path.getsize(zip_path) > 0

                    # Abrir el ZIP y comprobar que contiene el archivo con el sufijo '_glencoe.txt'
                    with ZipFile(zip_path, 'r') as zipf:
                        # Obtener los nombres de los archivos dentro del ZIP
                        zip_file_names = zipf.namelist()
                        
                        # Verificar que al menos un archivo tenga el sufijo '_glencoe.txt'
                        assert any(name.endswith('_glencoe.txt') for name in zip_file_names)
                    # Simulamos una llamada a la descarga del archivo ZIP
                    response = client.get('/dataset/download/all')
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")


# Test para la descarga de todos los datasets
def test_download_all_dataset_dimacs(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:
        # Mockear al usuario correcto (user_33)
        mock_user = User(id=33, email="user33@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Crear datasets mock (dataset_33)
        mock_datasets = [
            mock.Mock(id=33, user_id=33, files=lambda: [mock.Mock(name="file33.uvl", id=1)]),
        ]

        # Mock de Hubfile con un id y un path
        hubfile_mock = mock.Mock(id=1, get_path=lambda: f"uploads/user_{mock_user.id}/dataset_{33}/file33.uvl")

        # Mockear la llamada a HubfileService.get_or_404
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404', return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f'user_{mock_user.id}', f'dataset_{33}', 'file33.uvl')
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, 'w') as f:
                    f.write('features\n')
                    f.write('    Chat\n')
                    f.write('        mandatory\n')
                    f.write('            Connection\n')
                    f.write('                alternative\n')
                    f.write('                    "Peer 2 Peer"\n')
                    f.write('                    Server\n')
                    f.write('            Messages\n')
                    f.write('                or\n')
                    f.write('                    Text\n')
                    f.write('                    Video\n')
                    f.write('                    Audio\n')
                    f.write('        optional\n')
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write('\n')
                    f.write('constraints\n')
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                # Crear el archivo ZIP de salida
                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # Crear un archivo ZIP para simular la descarga
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        dataset_folder = f"dataset_{dataset.id}/"

                        for file in dataset.files():
                            content = ""
                            temp_file = tempfile.NamedTemporaryFile(suffix='.cnf', delete=False)
                            fm = UVLReader(hubfile_mock.get_path()).transform()
                            sat = FmToPysat(fm).transform()
                            DimacsWriter(temp_file.name, sat).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()

                            # Nombre del archivo dentro del ZIP
                            file_name_in_zip = f"{hubfile_mock.id}_cnf.txt"
                            
                            # Agregar el archivo al archivo ZIP
                            zipf.writestr(os.path.join(dataset_folder, file_name_in_zip), content)

                            # Eliminar el archivo temporal después de agregarlo al ZIP
                            os.remove(temp_file.name)

                try:
                    # Verificación de la existencia del archivo ZIP
                    print(f"ZIP file exists at: {zip_path}")
                    assert os.path.exists(zip_path)
                    assert os.path.getsize(zip_path) > 0

                    # Abrir el ZIP y comprobar que contiene el archivo con el sufijo '_cnf.txt'
                    with ZipFile(zip_path, 'r') as zipf:
                        # Obtener los nombres de los archivos dentro del ZIP
                        zip_file_names = zipf.namelist()
                        
                        # Verificar que al menos un archivo tenga el sufijo '_cnf.txt'
                        assert any(name.endswith('_cnf.txt') for name in zip_file_names)
                    # Simulamos una llamada a la descarga del archivo ZIP
                    response = client.get('/dataset/download/all')
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")

# Test para la descarga de todos los datasets (cuando los archivos no se encuentran)
def test_download_all_dataset_files_not_found(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:
        mock_user = User(id=5, email="user5@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Configuramos el mock para `files()` que devuelve una lista vacía
        mock_datasets = [
            mock.Mock(id=20, user_id=5, files=lambda: [mock.Mock(name="fileX.uvl", id=1)]),
        ]

        # Simulamos un escenario donde el archivo no está presente
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404', side_effect=FileNotFoundError):
            # No deberíamos poder crear archivos si no hay archivos disponibles
            with tempfile.TemporaryDirectory() as tmpdirname:
                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # No deberíamos poder crear archivos si no hay archivos disponibles
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        for file in dataset.files():
                            try:
                                file.name = str(file.name)
                                file_path = os.path.join(tmpdirname, file.name)
                                with open(file_path, 'w') as f:
                                    f.write('Contenido simulado de archivo')
                                zipf.write(file_path, os.path.basename(file_path))
                            except FileNotFoundError:
                                pass
            try:
                # Llamamos a la ruta para descargar todos los datasets
                response = client.get('/dataset/download/all')

                # Verificamos que el status de la respuesta es 404 (No encontrado)
                assert response.status_code == 404

                # Verificar que la respuesta sea un JSON
                assert response.content_type == 'application/json'

                # Verificar el contenido del JSON (mensaje de error esperado)
                json_response = response.get_json()
                assert 'error' in json_response
                assert json_response['error'] == 'No se encontraron archivos disponibles para descargar'
            finally:
                if os.path.exists(zip_path):
                    os.remove(zip_path)


# Test para la descarga de todos los datasets (cuando los archivos no se encuentran)
def test_download_all_dataset_empty(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:
        mock_user = User(id=5, email="user5@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Configuramos el mock para `files()` que devuelve una lista vacía
        mock_datasets = [
            mock.Mock(id=20, user_id=5, files=lambda: []),
        ]

        # Simulamos un escenario donde el archivo no está presente
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404', side_effect=FileNotFoundError):
            # No deberíamos poder crear archivos si no hay archivos disponibles
            with tempfile.TemporaryDirectory() as tmpdirname:
                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # No deberíamos poder crear archivos si no hay archivos disponibles
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        for file in dataset.files():
                            try:
                                file.name = str(file.name)
                                file_path = os.path.join(tmpdirname, file.name)
                                with open(file_path, 'w') as f:
                                    f.write('Contenido simulado de archivo')
                                zipf.write(file_path, os.path.basename(file_path))
                            except FileNotFoundError:
                                pass
            try:
                # Llamamos a la ruta para descargar todos los datasets
                response = client.get('/dataset/download/all')

                # Verificamos que el status de la respuesta es 404 (No encontrado)
                assert response.status_code == 404

                # Verificar que la respuesta sea un JSON
                assert response.content_type == 'application/json'

                # Verificar el contenido del JSON (mensaje de error esperado)
                json_response = response.get_json()
                assert 'error' in json_response
                assert json_response['error'] == 'No se encontraron archivos disponibles para descargar'
            finally:
                if os.path.exists(zip_path):
                    os.remove(zip_path)


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
