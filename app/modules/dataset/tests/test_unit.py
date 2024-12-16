from datetime import datetime
import os
import tempfile
from unittest import mock
import pytest
from flask import url_for
from app import create_app, db
from app.modules.auth.models import User
from app.modules.dataset.models import Community
from flask_login import login_user, logout_user
from app.modules.dataset.services import CommunityService, DataSetService
from app.modules.profile.models import UserProfile

from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from app import create_app, db
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
    app = create_app("testing")  # Usamos el entorno de testing
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
            dsmetadata = DSMetaData(
                id=33,
                title="Sample Dataset 33",
                description="Description for dataset 33",
                publication_type=PublicationType.DATA_MANAGEMENT_PLAN.name,
            )
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
            hubfile = Hubfile(
                id=1, feature_model_id=feature_model.id, name="file33.uvl", checksum="dummy_checksum", size=1234
            )
            db.session.add(hubfile)
            db.session.commit()

            yield client

            db.session.remove()
            db.drop_all()


# Test para la descarga de todos los datasets (esperando un archivo ZIP)
def test_download_all_dataset(client):
    with mock.patch("flask_login.utils._get_user") as mock_get_user:
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
        with mock.patch("app.modules.hubfile.services.HubfileService.get_or_404", return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f"user_{mock_user.id}", f"dataset_{33}", "file33.uvl")
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, "w") as f:
                    f.write("features\n")
                    f.write("    Chat\n")
                    f.write("        mandatory\n")
                    f.write("            Connection\n")
                    f.write("                alternative\n")
                    f.write('                    "Peer 2 Peer"\n')
                    f.write("                    Server\n")
                    f.write("            Messages\n")
                    f.write("                or\n")
                    f.write("                    Text\n")
                    f.write("                    Video\n")
                    f.write("                    Audio\n")
                    f.write("        optional\n")
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write("\n")
                    f.write("constraints\n")
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                zip_path = os.path.join(tmpdirname, "all_datasets.zip")

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
                    with ZipFile(zip_path, "r") as zipf:
                        # Verifica el contenido
                        zipf.testzip()  # Esto puede levantar una excepción si el ZIP está dañado

                    response = client.get("/dataset/download/all")
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")


# Test para la descarga de todos los datasets
def test_download_all_dataset_splx(client):
    with mock.patch("flask_login.utils._get_user") as mock_get_user:
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
        with mock.patch("app.modules.hubfile.services.HubfileService.get_or_404", return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f"user_{mock_user.id}", f"dataset_{33}", "file33.uvl")
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, "w") as f:
                    f.write("features\n")
                    f.write("    Chat\n")
                    f.write("        mandatory\n")
                    f.write("            Connection\n")
                    f.write("                alternative\n")
                    f.write('                    "Peer 2 Peer"\n')
                    f.write("                    Server\n")
                    f.write("            Messages\n")
                    f.write("                or\n")
                    f.write("                    Text\n")
                    f.write("                    Video\n")
                    f.write("                    Audio\n")
                    f.write("        optional\n")
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write("\n")
                    f.write("constraints\n")
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                # Crear el archivo ZIP de salida
                zip_path = os.path.join(tmpdirname, "all_datasets.zip")

                # Crear un archivo ZIP para simular la descarga
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        dataset_folder = f"dataset_{dataset.id}/"

                        for file in dataset.files():
                            content = ""
                            # Convertir el archivo UVL a SPLX directamente aquí
                            temp_file = tempfile.NamedTemporaryFile(suffix=".splx", delete=False)
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
                    with ZipFile(zip_path, "r") as zipf:
                        # Obtener los nombres de los archivos dentro del ZIP
                        zip_file_names = zipf.namelist()

                        # Verificar que al menos un archivo tenga el sufijo '_splot.txt'
                        assert any(name.endswith("_splot.txt") for name in zip_file_names)
                    # Simulamos una llamada a la descarga del archivo ZIP
                    response = client.get("/dataset/download/all")
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")


# Test para la descarga de todos los datasets
def test_download_all_dataset_glencoe(client):
    with mock.patch("flask_login.utils._get_user") as mock_get_user:
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
        with mock.patch("app.modules.hubfile.services.HubfileService.get_or_404", return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f"user_{mock_user.id}", f"dataset_{33}", "file33.uvl")
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, "w") as f:
                    f.write("features\n")
                    f.write("    Chat\n")
                    f.write("        mandatory\n")
                    f.write("            Connection\n")
                    f.write("                alternative\n")
                    f.write('                    "Peer 2 Peer"\n')
                    f.write("                    Server\n")
                    f.write("            Messages\n")
                    f.write("                or\n")
                    f.write("                    Text\n")
                    f.write("                    Video\n")
                    f.write("                    Audio\n")
                    f.write("        optional\n")
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write("\n")
                    f.write("constraints\n")
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                # Crear el archivo ZIP de salida
                zip_path = os.path.join(tmpdirname, "all_datasets.zip")

                # Crear un archivo ZIP para simular la descarga
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        dataset_folder = f"dataset_{dataset.id}/"

                        for file in dataset.files():
                            content = ""
                            temp_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
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
                    with ZipFile(zip_path, "r") as zipf:
                        # Obtener los nombres de los archivos dentro del ZIP
                        zip_file_names = zipf.namelist()

                        # Verificar que al menos un archivo tenga el sufijo '_glencoe.txt'
                        assert any(name.endswith("_glencoe.txt") for name in zip_file_names)
                    # Simulamos una llamada a la descarga del archivo ZIP
                    response = client.get("/dataset/download/all")
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")


# Test para la descarga de todos los datasets
def test_download_all_dataset_dimacs(client):
    with mock.patch("flask_login.utils._get_user") as mock_get_user:
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
        with mock.patch("app.modules.hubfile.services.HubfileService.get_or_404", return_value=hubfile_mock):
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Aquí guardamos el archivo en la ruta esperada por la aplicación
                file_path = os.path.join("uploads/", f"user_{mock_user.id}", f"dataset_{33}", "file33.uvl")
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Crear un archivo UVL válido para que Flamapy pueda procesarlo
                with open(file_path, "w") as f:
                    f.write("features\n")
                    f.write("    Chat\n")
                    f.write("        mandatory\n")
                    f.write("            Connection\n")
                    f.write("                alternative\n")
                    f.write('                    "Peer 2 Peer"\n')
                    f.write("                    Server\n")
                    f.write("            Messages\n")
                    f.write("                or\n")
                    f.write("                    Text\n")
                    f.write("                    Video\n")
                    f.write("                    Audio\n")
                    f.write("        optional\n")
                    f.write('            "Data Storage"\n')
                    f.write('            "Media Player"\n')
                    f.write("\n")
                    f.write("constraints\n")
                    f.write('    Server => "Data Storage"\n')
                    f.write('    Video | Audio => "Media Player"\n')

                # Crear el archivo ZIP de salida
                zip_path = os.path.join(tmpdirname, "all_datasets.zip")

                # Crear un archivo ZIP para simular la descarga
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        dataset_folder = f"dataset_{dataset.id}/"

                        for file in dataset.files():
                            content = ""
                            temp_file = tempfile.NamedTemporaryFile(suffix=".cnf", delete=False)
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
                    with ZipFile(zip_path, "r") as zipf:
                        # Obtener los nombres de los archivos dentro del ZIP
                        zip_file_names = zipf.namelist()

                        # Verificar que al menos un archivo tenga el sufijo '_cnf.txt'
                        assert any(name.endswith("_cnf.txt") for name in zip_file_names)
                    # Simulamos una llamada a la descarga del archivo ZIP
                    response = client.get("/dataset/download/all")
                    assert response.status_code == 200

                finally:
                    # Eliminar el archivo ZIP al final del test
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                        print(f"Deleted ZIP file at: {zip_path}")


# Test para la descarga de todos los datasets (cuando los archivos no se encuentran)
def test_download_all_dataset_files_not_found(client):
    with mock.patch("flask_login.utils._get_user") as mock_get_user:
        mock_user = User(id=5, email="user5@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Configuramos el mock para `files()` que devuelve una lista vacía
        mock_datasets = [
            mock.Mock(id=20, user_id=5, files=lambda: [mock.Mock(name="fileX.uvl", id=1)]),
        ]

        # Simulamos un escenario donde el archivo no está presente
        with mock.patch("app.modules.hubfile.services.HubfileService.get_or_404", side_effect=FileNotFoundError):
            # No deberíamos poder crear archivos si no hay archivos disponibles
            with tempfile.TemporaryDirectory() as tmpdirname:
                zip_path = os.path.join(tmpdirname, "all_datasets.zip")

                # No deberíamos poder crear archivos si no hay archivos disponibles
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        for file in dataset.files():
                            try:
                                file.name = str(file.name)
                                file_path = os.path.join(tmpdirname, file.name)
                                with open(file_path, "w") as f:
                                    f.write("Contenido simulado de archivo")
                                zipf.write(file_path, os.path.basename(file_path))
                            except FileNotFoundError:
                                pass
            try:
                # Llamamos a la ruta para descargar todos los datasets
                response = client.get("/dataset/download/all")

                # Verificamos que el status de la respuesta es 404 (No encontrado)
                assert response.status_code == 404

                # Verificar que la respuesta sea un JSON
                assert response.content_type == "application/json"

                # Verificar el contenido del JSON (mensaje de error esperado)
                json_response = response.get_json()
                assert "error" in json_response
                assert json_response["error"] == "No se encontraron archivos disponibles para descargar"
            finally:
                if os.path.exists(zip_path):
                    os.remove(zip_path)


# Test para la descarga de todos los datasets (cuando los archivos no se encuentran)
def test_download_all_dataset_empty(client):
    with mock.patch("flask_login.utils._get_user") as mock_get_user:
        mock_user = User(id=5, email="user5@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        # Configuramos el mock para `files()` que devuelve una lista vacía
        mock_datasets = [
            mock.Mock(id=20, user_id=5, files=lambda: []),
        ]

        # Simulamos un escenario donde el archivo no está presente
        with mock.patch("app.modules.hubfile.services.HubfileService.get_or_404", side_effect=FileNotFoundError):
            # No deberíamos poder crear archivos si no hay archivos disponibles
            with tempfile.TemporaryDirectory() as tmpdirname:
                zip_path = os.path.join(tmpdirname, "all_datasets.zip")

                # No deberíamos poder crear archivos si no hay archivos disponibles
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        for file in dataset.files():
                            try:
                                file.name = str(file.name)
                                file_path = os.path.join(tmpdirname, file.name)
                                with open(file_path, "w") as f:
                                    f.write("Contenido simulado de archivo")
                                zipf.write(file_path, os.path.basename(file_path))
                            except FileNotFoundError:
                                pass
            try:
                # Llamamos a la ruta para descargar todos los datasets
                response = client.get("/dataset/download/all")

                # Verificamos que el status de la respuesta es 404 (No encontrado)
                assert response.status_code == 404

                # Verificar que la respuesta sea un JSON
                assert response.content_type == "application/json"

                # Verificar el contenido del JSON (mensaje de error esperado)
                json_response = response.get_json()
                assert "error" in json_response
                assert json_response["error"] == "No se encontraron archivos disponibles para descargar"
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

    cookies = response.headers.getlist("Set-Cookie")

    remember_token = None
    session = None

    for cookie in cookies:
        if "remember_token" in cookie:
            remember_token = cookie.split(";")[0].split("=")[1]
        elif "session" in cookie:
            session = cookie.split(";")[0].split("=")[1]

    return remember_token, session


@pytest.fixture
def app():
    app = create_app("testing")
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
    """Create initial data for tests"""

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
        affiliation="University of Example",
    )
    profile2 = UserProfile(
        user_id=user2.id,
        name="Member 1",
        surname="Surname 2",
        orcid="0000-0000-0000-0002",
        affiliation="Institute of Example",
    )
    profile3 = UserProfile(
        user_id=user3.id,
        name="Requester 1",
        surname="Surname 3",
        orcid="0000-0000-0000-0003",
        affiliation="Research Center Example",
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


@pytest.fixture()
def dataset_service():
    dataset_service = DataSetService()
    with patch.object(dataset_service.dsmetadata_repository, "create", return_value=DSMetaData(id=1)), patch.object(
        dataset_service.author_repository, "create", return_value=Author(id=1)
    ), patch.object(dataset_service.repository, "create", return_value=DataSet(id=1)), patch.object(
        dataset_service.fmmetadata_repository, "create", return_value=FMMetaData(id=1)
    ), patch.object(
        dataset_service.feature_model_repository, "create", return_value=FeatureModel(id=1)
    ), patch.object(
        dataset_service.hubfilerepository, "create", return_value=Hubfile(id=1)
    ):

        yield dataset_service


@pytest.fixture()
def current_user(dataset_service):
    profile = UserProfile(name="Jane", surname="Doe")
    current_user = User(email="test@example.com", password="test1234", profile=profile)
    yield current_user


def test_list_communities_authenticated(client, app, setup_data):
    """Test access to the communities view with an authenticated user"""
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.list_communities"))

        assert response.status_code == 200
        # Decode the bytes to string
        response_data = response.data.decode("utf-8")

        assert "Scientific Community" in response_data
        assert "Data Community" in response_data


def test_list_communities_not_authenticated(client):
    """Test access without authentication"""
    response = client.get("/communities")
    assert response.status_code == 302  # Redirect to login


def test_search_communities_valid_query(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.search_communities", query="Scientific"), follow_redirects=True)

        assert response.status_code == 200
        assert "Search Results" in response.data.decode("utf-8")
        assert "Scientific Community" in response.data.decode("utf-8")


def test_search_communities_empty_query(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.search_communities", query=""), follow_redirects=True)

        assert response.status_code == 200
        assert "Search Results" in response.data.decode("utf-8")
        assert "No communities found" in response.data.decode("utf-8")


def test_search_communities_no_results(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.search_communities", query="Nonexistent"), follow_redirects=True)

        assert response.status_code == 200
        assert "Search Results" in response.data.decode("utf-8")
        assert "No communities found" in response.data.decode("utf-8")


def test_view_community_existing(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(url_for("community.view_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        assert "Scientific Community" in response.data.decode("utf-8")
        assert user.profile.name in response.data.decode("utf-8")


def test_view_community_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.view_community", community_id=9999), follow_redirects=True)

        assert response.status_code == 404
        assert "Community not found" in response.data.decode("utf-8")


def test_view_community_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(url_for("community.view_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        assert "Scientific Community" in response.data.decode("utf-8")
        assert "Requests" in response.data.decode("utf-8")


def test_create_community_page_access(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.create_community_page"))

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        assert "Create a New Community" in response_data

        logout_user()


def test_create_community_page_unauthenticated_access(client, app, setup_data):
    response = client.get("/community/create")

    assert response.status_code == 302


def test_create_community_success(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.post(
            url_for("community.create_community"), data={"name": "New Community test"}, follow_redirects=True
        )

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        assert "New Community test" in response_data


def test_create_community_missing_name(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.post(url_for("community.create_community"), data={"name": ""}, follow_redirects=True)

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        print(response_data)
        assert "Create a New Community" in response_data


def test_edit_community_page_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(url_for("community.edit_community_page", community_id=community.id))

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        assert "Edit Community" in response_data
        assert community.name in response_data


def test_edit_community_page_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.get(url_for("community.edit_community_page", community_id=community.id))

        assert response.status_code == 403
        response_data = response.data.decode("utf-8")
        assert "Forbidden" in response_data


def test_edit_community_page_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        response = client.get(url_for("community.edit_community_page", community_id=9999))

        assert response.status_code == 404
        response_data = response.data.decode("utf-8")
        assert "Community not found" in response_data


def test_edit_community_page_unauthenticated(client, app, setup_data):
    community = Community.query.filter_by(name="Scientific Community").first()
    url = "/community/" + str(community.id) + "/edit"

    response = client.get(url, follow_redirects=True)

    assert response.status_code == 200
    response_data = response.data.decode("utf-8")
    assert "Login" in response_data


def test_edit_community_post_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        new_name = "Updated Community Name"

        response = client.post(
            url_for("community.edit_community", community_id=community.id),
            data={"name": new_name},
            follow_redirects=True,
        )

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        assert "Updated Community Name" in response_data

        updated_community = Community.query.filter_by(id=community.id).first()
        assert updated_community.name == new_name


def test_edit_community_post_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(
            url_for("community.edit_community", community_id=community.id),
            data={"name": "New Name"},
            follow_redirects=True,
        )

        assert response.status_code == 403
        response_data = response.data.decode("utf-8")
        assert "Forbidden" in response_data


def test_edit_community_post_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        response = client.post(
            url_for("community.edit_community", community_id=9999), data={"name": "New Name"}, follow_redirects=True
        )

        assert response.status_code == 404
        response_data = response.data.decode("utf-8")
        assert "Community not found" in response_data


def test_delete_community_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.delete_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        assert "My Communities" in response_data

        deleted_community = Community.query.filter_by(id=community.id).first()
        assert deleted_community is None


def test_delete_community_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.delete_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 403
        response_data = response.data.decode("utf-8")
        assert "Forbidden" in response_data


def test_delete_community_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        response = client.post(url_for("community.delete_community", community_id=9999), follow_redirects=True)

        assert response.status_code == 404
        response_data = response.data.decode("utf-8")
        assert "Community not found" in response_data


def test_delete_community_unauthenticated(client, app, setup_data):
    community = Community.query.filter_by(name="Scientific Community").first()
    url = "/community/" + str(community.id) + "/delete"

    response = client.post(url, follow_redirects=True)

    assert response.status_code == 200
    response_data = response.data.decode("utf-8")
    assert "Login" in response_data


def test_request_community_as_non_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="requester1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Data Community").first()

        response = client.post(url_for("community.request_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        print(response_data)
        assert "Community: Data Community" in response_data
        assert user in community.requests


def test_request_community_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.request_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        print(response_data)
        assert "Community: Scientific Community" in response_data


def test_request_community_as_requester(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="requester1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.request_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        response_data = response.data.decode("utf-8")
        assert "Community: Scientific Community" in response_data


def test_leave_community_as_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.leave_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 200
        assert not CommunityService.is_member(community, user)


def test_leave_community_as_owner(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="owner1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.leave_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 403
        assert CommunityService.is_member(community, user)
        assert CommunityService.is_owner(community, user)


def test_leave_community_nonexistent(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="member1@example.com").first()
        login_user(user)

        response = client.post(url_for("community.leave_community", community_id=9999), follow_redirects=True)

        assert response.status_code == 404
        assert "Community not found" in response.data.decode("utf-8")


def test_leave_community_not_a_member(client, app, setup_data):
    with app.test_request_context():
        user = User.query.filter_by(email="requester1@example.com").first()
        login_user(user)

        community = Community.query.filter_by(name="Scientific Community").first()

        response = client.post(url_for("community.leave_community", community_id=community.id), follow_redirects=True)

        assert response.status_code == 403
        assert "Forbidden" in response.data.decode("utf-8")
        assert not CommunityService.is_member(community, user)


def test_upload_valid_zip(test_client, login):
    """
    Prueba para cargar un archivo ZIP válido.
    """
    remember_token, session = login

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("testfile.uvl", "contenido del archivo UVL")

    zip_buffer.seek(0)
    data = {"file": (zip_buffer, "test.zip")}

    headers = {"Cookie": f"remember_token={remember_token}; session={session}"}

    response = test_client.post(
        "/dataset/file/upload/zip", data=data, headers=headers, content_type="multipart/form-data"
    )

    assert response.status_code == 200


def test_upload_zip_without_uvl(test_client, login):
    """
    Verifica que no se encuentran archivos .uvl en el zip.
    """
    remember_token, session = login

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("testfile.txt", "contenido del archivo de texto")

    zip_buffer.seek(0)
    data = {"file": (zip_buffer, "test.zip")}

    headers = {"Cookie": f"remember_token={remember_token}; session={session}"}

    response = test_client.post(
        "/dataset/file/upload/zip", data=data, headers=headers, content_type="multipart/form-data"
    )

    assert response.status_code == 400


def test_upload_invalid_zip(test_client, login):
    """
    Verifica que un archivo que no es un ZIP da un error.
    """
    remember_token, session = login

    data = {"file": (BytesIO(b"Not a zip file"), "invalid.zip")}

    headers = {"Cookie": f"remember_token={remember_token}; session={session}"}

    response = test_client.post(
        "/dataset/file/upload/zip", data=data, headers=headers, content_type="multipart/form-data"
    )

    assert response.status_code == 400


def test_upload_no_file(test_client, login):
    """
    Verifica que no se envía archivo en la solicitud.
    """
    remember_token, session = login

    data = {}

    headers = {"Cookie": f"remember_token={remember_token}; session={session}"}

    response = test_client.post(
        "/dataset/file/upload/zip", data=data, headers=headers, content_type="multipart/form-data"
    )

    assert response.status_code == 400


@pytest.fixture()
def dataset_service():
    dataset_service = DataSetService()
    with patch.object(dataset_service.dsmetadata_repository, "create", return_value=DSMetaData(id=1)), patch.object(
        dataset_service.author_repository, "create", return_value=Author(id=1)
    ), patch.object(dataset_service.repository, "create", return_value=DataSet(id=1)), patch.object(
        dataset_service.fmmetadata_repository, "create", return_value=FMMetaData(id=1)
    ), patch.object(
        dataset_service.feature_model_repository, "create", return_value=FeatureModel(id=1)
    ), patch.object(
        dataset_service.hubfilerepository, "create", return_value=Hubfile(id=1)
    ):

        yield dataset_service


@pytest.fixture()
def current_user(dataset_service):
    profile = UserProfile(name="Jane", surname="Doe")
    current_user = User(email="test@example.com", password="test1234", profile=profile)
    yield current_user


def test_dsmetrics_with_whitespaces(dataset_service, current_user, test_app):

    with test_app.app_context():
        form = DataSetForm()
        form.feature_models[0].uvl_filename.data = "file_that_uses_whitespaces.uvl"

    with patch.object(current_user, "temp_folder", return_value="app/modules/dataset/uvl_examples"), patch.object(
        dataset_service.dsmetrics_repository, "create"
    ) as mock_create_dsmetrics:
        mock_create_dsmetrics.return_value = DSMetrics(id=1)

        dataset_service.create_from_form(form=form, current_user=current_user)
        mock_create_dsmetrics.assert_called_once_with(number_of_models=1, number_of_features=10)


def test_dsmetrics_with_tabs(dataset_service, current_user, test_app):

    with test_app.app_context():
        form = DataSetForm()
        form.feature_models[0].uvl_filename.data = "file_that_uses_tabs.uvl"

    with patch.object(current_user, "temp_folder", return_value="app/modules/dataset/uvl_examples"), patch.object(
        dataset_service.dsmetrics_repository, "create"
    ) as mock_create_dsmetrics:
        mock_create_dsmetrics.return_value = DSMetrics(id=1)

        dataset_service.create_from_form(form=form, current_user=current_user)
        mock_create_dsmetrics.assert_called_once_with(number_of_models=1, number_of_features=24)


def test_dsmetrics_both(dataset_service, current_user, test_app):

    with test_app.app_context():
        form = DataSetForm()
        form.feature_models[0].uvl_filename.data = "file_that_uses_whitespaces.uvl"
        form.feature_models.append_entry(data={"uvl_filename": "file_that_uses_tabs.uvl"})

    with patch.object(current_user, "temp_folder", return_value="app/modules/dataset/uvl_examples"), patch.object(
        dataset_service.dsmetrics_repository, "create"
    ) as mock_create_dsmetrics:
        mock_create_dsmetrics.return_value = DSMetrics(id=1)

        dataset_service.create_from_form(form=form, current_user=current_user)
        mock_create_dsmetrics.assert_called_once_with(number_of_models=2, number_of_features=34)


# Caso: URL válida de GitHub con archivo ZIP
def test_upload_github_valid_zip(test_client, login):
    remember_token, session = login  # Obtenemos el token de autenticación

    # URL válida del archivo ZIP en GitHub
    github_url = "https://github.com/jorgomde/prueba-archivos-zip-y-uvl/blob/main/prueba.zip"

    # Crear los headers con las cookies
    headers = {"Cookie": f"remember_token={remember_token}; session={session}", "Content-Type": "application/json"}

    response = test_client.post(
        "/dataset/file/upload/github",
        headers=headers,
        json={"url": github_url},
    )
    response_data = response.get_json()

    # Verificar la respuesta
    assert response.status_code == 200
    assert response_data["message"] == "ZIP file uploaded and extracted successfully"


# Caso: URL válida de GitHub con archivo UVL
def test_upload_github_valid_uvl(test_client, login):
    remember_token, session = login  # Obtenemos el token de autenticación

    github_url = "https://github.com/jorgomde/prueba-archivos-zip-y-uvl/blob/main/file1.uvl"

    # Crear los headers con las cookies
    headers = {"Cookie": f"remember_token={remember_token}; session={session}", "Content-Type": "application/json"}

    response = test_client.post("/dataset/file/upload/github", json={"url": github_url}, headers=headers)
    response_data = response.get_json()

    # Verificar la respuesta
    assert response.status_code == 200
    assert response_data["message"] == "UVL file uploaded and validated successfully"


# Caso: URL inválida de GitHub
def test_upload_github_invalid_url(test_client, login):
    remember_token, session = login  # Obtenemos el token de autenticación

    github_url = "https://invalid-url.com/file.zip"

    # Crear los headers con las cookies
    headers = {"Cookie": f"remember_token={remember_token}; session={session}", "Content-Type": "application/json"}

    response = test_client.post("/dataset/file/upload/github", json={"url": github_url}, headers=headers)
    response_data = response.get_json()

    # Verificar la respuesta
    assert response.status_code == 400  # Aseguramos que el status code es 400
    assert response_data["error"] == "Invalid GitHub URL"


# Caso: Falta la URL en la solicitud
def test_upload_github_missing_url(test_client, login):
    remember_token, session = login  # Obtenemos el token de autenticación

    # Crear los headers con las cookies
    headers = {"Cookie": f"remember_token={remember_token}; session={session}", "Content-Type": "application/json"}

    response = test_client.post("/dataset/file/upload/github", json={}, headers=headers)
    response_data = response.get_json()

    # Verificar la respuesta
    assert response.status_code == 400  # Aseguramos que el status code es 400
    assert response_data["error"] == "GitHub URL is required"


# Caso: Error genérico al descargar desde GitHub
def test_upload_github_request_error(test_client, login):
    remember_token, session = login  # Obtenemos el token de autenticación

    github_url = "https://github.com/user/repo/blob/main/test.zip"

    # Crear los headers con las cookies
    headers = {"Cookie": f"remember_token={remember_token}; session={session}", "Content-Type": "application/json"}

    response = test_client.post("/dataset/file/upload/github", json={"url": github_url}, headers=headers)
    response_data = response.get_json()

    # Verificar la respuesta
    assert response.status_code == 500  # Aseguramos que el status code es 500
    assert response_data["error"].startswith("Error uploading file from GitHub")
