from locust import HttpUser, TaskSet, task
from core.locust.common import get_csrf_token
from core.environment.host import get_host_for_locust_testing
import zipfile


class DatasetBehavior(TaskSet):
    def on_start(self):
        # Llamada inicial, se ejecuta cuando el usuario comienza
        self.dataset()

    @task
    def dataset(self):
        # Realiza la carga del dataset (simula la acción de subir o acceder a una página de carga)
        response = self.client.get("/dataset/upload")
        get_csrf_token(response)

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
    tasks = [DatasetBehavior, DatasetBehavior.download_all_datasets]  # Asegurándonos de agregar la tarea de descarga
    min_wait = 5000  # Tiempo mínimo de espera entre tareas (5 segundos)
    max_wait = 9000  # Tiempo máximo de espera entre tareas (9 segundos)
    host = get_host_for_locust_testing()  # Cambiar con tu URL base para testing
