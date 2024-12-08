import pytest
import os
from enum import Enum
from app import create_app, db
from app.modules.dataset.models import DataSet, DSMetaData
from app.modules.auth.models import User
from datetime import datetime
from unittest import mock
from zipfile import ZipFile
import tempfile


class PublicationType(Enum):
    NONE = 'none'
    DATA_MANAGEMENT_PLAN = 'datamanagementplan'


# Fixture de pytest para configurar el cliente de pruebas
@pytest.fixture
def client():
    app = create_app('testing')  # Usamos el entorno de testing
    with app.test_client() as client:
        with app.app_context():
            # Configuración de la base de datos en modo de prueba
            db.drop_all()
            db.create_all()

            # Crear un usuario de prueba
            user = User(id=5, email="user5@example.com", password="1234", created_at=datetime(2022, 3, 13))
            db.session.add(user)
            db.session.commit()

            # Crear metadata para el dataset
            dsmetadata = DSMetaData(id=20, title="Sample Dataset 20", description="Description for dataset 20",
                                    publication_type=PublicationType.DATA_MANAGEMENT_PLAN.name)
            db.session.add(dsmetadata)
            db.session.commit()

            # Crear el dataset
            dataset = DataSet(id=20, user_id=user.id, ds_meta_data_id=dsmetadata.id)
            db.session.add(dataset)
            db.session.commit()

            # Crear un archivo temporal en la ruta esperada para pruebas
            temp_folder = os.path.join('uploads', 'temp', str(user.id))
            os.makedirs(temp_folder, exist_ok=True)
            with open(os.path.join(temp_folder, 'file9.uvl'), 'w') as f:
                f.write('Contenido simulado del archivo')

            yield client

            # Limpiar el archivo temporal después de la prueba
            if os.path.exists(os.path.join(temp_folder, 'file9.uvl')):
                os.remove(os.path.join(temp_folder, 'file9.uvl'))
            if os.path.exists(temp_folder):
                os.rmdir(temp_folder)

            db.session.remove()
            db.drop_all()


# Test para la descarga de todos los datasets
def test_download_all_dataset(client):
    with mock.patch('flask_login.utils._get_user') as mock_get_user:

        mock_user = User(id=5, email="user5@example.com", password="1234", created_at=datetime(2022, 3, 13))
        mock_get_user.return_value = mock_user

        mock_datasets = [
            mock.Mock(id=20, user_id=5, files=lambda: [mock.Mock(name="file9.uvl", id=1)]),
        ]

        # Mock de la clase HubfileService
        with mock.patch('app.modules.hubfile.services.HubfileService.get_or_404',
                        return_value=mock.Mock(id=1, name='hubfile_name', get_path=lambda: '/mock/path')):
            with tempfile.TemporaryDirectory() as tmpdirname:
                print('directorio temporal creado en:', tmpdirname)

                # El archivo ZIP donde se almacenarán los datasets
                zip_path = os.path.join(tmpdirname, 'all_datasets.zip')

                # Aquí comenzamos a crear el archivo ZIP
                with ZipFile(zip_path, "w") as zipf:
                    for dataset in mock_datasets:
                        for file in dataset.files():
                            file.name = str(file.name)
                            file_path = os.path.join(tmpdirname, file.name)
                            with open(file_path, 'w') as f:
                                f.write('Contenido simulado de archivo')
                            zipf.write(file_path, os.path.basename(file_path))

                # Verificar que el archivo ZIP se haya creado correctamente
                assert os.path.exists(zip_path)  # Comprobamos que el archivo ZIP exista
                assert os.path.getsize(zip_path) > 0  # Comprobamos que el archivo ZIP no esté vacío

                # Llamamos a la ruta para descargar todos los datasets
                response = client.get('/dataset/download/all')

                # Verificamos que el status de la respuesta es 200 (OK)
                assert response.status_code == 200

                # Verificar que el archivo ZIP generado en la respuesta se ha enviado correctamente
                assert 'content-type' in response.headers
                assert response.headers['content-type'] == 'application/zip'
