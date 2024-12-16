from io import BytesIO
import secrets
from zipfile import ZipFile
import zipfile
from locust import HttpUser, TaskSet, task
from core.locust.common import get_csrf_token
from core.environment.host import get_host_for_locust_testing


class DatasetBehavior(TaskSet):
    def on_start(self):
        self.dataset()

    @task
    def dataset(self):
        response = self.client.get("/dataset/upload")
        get_csrf_token(response)


class DatasetZipBehavior(TaskSet):

    @task
    def upload_zip(self):
        """Prueba para cargar un archivo ZIP"""
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr('testfile.uvl', 'contenido del archivo UVL')

        zip_buffer.seek(0)

        zip_filename = f"{secrets.token_hex(5)}.zip"

        data = {
            'file': (zip_buffer, zip_filename)
        }

        headers = {
            'Content-Type': 'multipart/form-data'
        }

        response = self.client.post(
            "/dataset/file/upload/zip",
            files=data,
            headers=headers
        )

        if response.status_code == 200:
            print("Zip subido y archivos .uvl extraídos con éxito.")
        else:
            print(f"Error al subir el ZIP: {response.json()['message']}")

    @task
    def upload_invalid_zip(self):
        """Prueba para intentar cargar un archivo no ZIP"""
        response = self.client.post(
            "/dataset/file/upload/zip",
            data={"file": "Not a zip file"},
            headers={"Content-Type": "multipart/form-data"}
        )

        if response.status_code == 400:
            print("Error esperado: archivo no válido.")
        else:
            print(f"Respuesta inesperada: {response.status_code}")


class DatasetGithubBehavior(TaskSet):

    @task
    def upload_github(self):
        """Prueba para cargar un archivo desde GitHub"""
        github_url = "https://github.com/jorgomde/prueba-archivos-zip-y-uvl/raw/main/prueba.zip"
        data = {
            'github_url': github_url
        }

        headers = {
            'Content-Type': 'application/json'
        }

        response = self.client.post(
            "/dataset/file/upload/github",
            json=data,
            headers=headers
        )

        if response.status_code == 200:
            print("Archivo de GitHub subido y procesado con éxito.")
        else:
            print(f"Error al subir el archivo de GitHub: {response.json()['message']}")

    @task
    def upload_invalid_github_url(self):
        """Prueba para intentar cargar un archivo con una URL de GitHub no válida"""
        invalid_github_url = "https://github.com/jorgomde/invalid-repo/raw/main/invalid-file.zip"
        data = {
            'github_url': invalid_github_url
        }

        headers = {
            'Content-Type': 'application/json'
        }

        response = self.client.post(
            "/dataset/file/upload/github",
            json=data,
            headers=headers
        )

        if response.status_code == 400:
            print("Error esperado: URL de GitHub no válida.")
        else:
            print(f"Respuesta inesperada: {response.status_code}")


class DatsetDownloadAllBehavior(TaskSet):
    @task
    def download_all_datasets(self):
        # Simula la solicitud GET al endpoint que descarga todos los datasets
        print("Iniciando descarga de todos los datasets...")
        response = self.client.get("/dataset/download/all")

        # Verificar que la respuesta es exitosa (200 OK)
        if response.status_code == 200:
            print("Archivo ZIP descargado exitosamente.")

            # Guardamos el archivo ZIP descargado
            zip_filename = "all_datasets.zip"
            with open(zip_filename, 'wb') as f:
                f.write(response.content)
            print(f"Archivo guardado como {zip_filename}")

            # Verificación del contenido del archivo ZIP
            self.verify_zip_content(zip_filename)

        else:
            print(f"Error al descargar el archivo: {response.status_code}")

    def verify_zip_content(self, zip_filename):
        # Verificar que el archivo ZIP no esté dañado
        try:
            with zipfile.ZipFile(zip_filename, 'r') as zipf:
                # Comprobamos si el archivo ZIP está dañado
                zipf.testzip()  # Si no lanza error, el ZIP es válido
                print(f"El archivo ZIP {zip_filename} es válido.")

                # Listamos los archivos dentro del ZIP
                file_list = zipf.namelist()
                print(f"Contenido del archivo ZIP: {file_list}")

                # Verificar que contenga el archivo esperado "file33.uvl"
                expected_file_name = "file33.uvl"
                assert expected_file_name in file_list, f"El archivo esperado '{expected_file_name}' no está en el ZIP"
                print(f"El archivo {expected_file_name} está presente en el ZIP.")

        except zipfile.BadZipFile:
            print(f"Error: El archivo {zip_filename} está dañado.")
        except Exception as e:
            print(f"Error al verificar el contenido del archivo ZIP: {e}")


class DatasetUser(HttpUser):
    tasks = [DatasetBehavior, DatasetGithubBehavior, DatasetZipBehavior, DatsetDownloadAllBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
