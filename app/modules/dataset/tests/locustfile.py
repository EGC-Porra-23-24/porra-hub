from io import BytesIO
import secrets
from zipfile import ZipFile
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




class DatasetUser(HttpUser):
    tasks = [DatasetBehavior, DatasetGithubBehavior DatasetZipBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
