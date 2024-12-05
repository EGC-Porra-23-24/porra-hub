import logging
import os
import json
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from zipfile import ZipFile
import zipfile

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    jsonify,
    send_from_directory,
    make_response,
    abort,
    url_for,
)
from flask_login import login_required, current_user
import requests

from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import (
    DSDownloadRecord
)
from app.modules.dataset import dataset_bp
from app.modules.dataset.services import (
    AuthorService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
    DataSetService,
    DOIMappingService,
    CommunityService
)
from flamapy.metamodels.fm_metamodel.transformations import UVLReader, GlencoeWriter, SPLOTWriter, JSONWriter, AFMWriter
from flamapy.metamodels.pysat_metamodel.transformations import FmToPysat, DimacsWriter
from app.modules.hubfile.services import HubfileService
from app.modules.zenodo.services import ZenodoService

logger = logging.getLogger(__name__)


dataset_service = DataSetService()
author_service = AuthorService()
dsmetadata_service = DSMetaDataService()
zenodo_service = ZenodoService()
doi_mapping_service = DOIMappingService()
ds_view_record_service = DSViewRecordService()


@dataset_bp.route("/dataset/upload", methods=["GET", "POST"])
@login_required
def create_dataset():
    form = DataSetForm()
    if request.method == "POST":

        dataset = None

        if not form.validate_on_submit():
            return jsonify({"message": form.errors}), 400

        try:
            logger.info("Creating dataset...")
            dataset = dataset_service.create_from_form(form=form, current_user=current_user)
            logger.info(f"Created dataset: {dataset}")
            dataset_service.move_feature_models(dataset)
        except Exception as exc:
            logger.exception(f"Exception while create dataset data in local {exc}")
            return jsonify({"Exception while create dataset data in local: ": str(exc)}), 400

        # send dataset as deposition to Zenodo
        data = {}
        try:
            zenodo_response_json = zenodo_service.create_new_deposition(dataset)
            response_data = json.dumps(zenodo_response_json)
            data = json.loads(response_data)
        except Exception as exc:
            data = {}
            zenodo_response_json = {}
            logger.exception(f"Exception while create dataset data in Zenodo {exc}")

        if data.get("conceptrecid"):
            deposition_id = data.get("id")

            # update dataset with deposition id in Zenodo
            dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

            try:
                # iterate for each feature model (one feature model = one request to Zenodo)
                for feature_model in dataset.feature_models:
                    zenodo_service.upload_file(dataset, deposition_id, feature_model)

                # publish deposition
                zenodo_service.publish_deposition(deposition_id)

                # update DOI
                deposition_doi = zenodo_service.get_doi(deposition_id)
                dataset_service.update_dsmetadata(dataset.ds_meta_data_id, dataset_doi=deposition_doi)
            except Exception as e:
                msg = f"it has not been possible upload feature models in Zenodo and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        # Delete temp folder
        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    return render_template("dataset/upload_dataset.html", form=form)


@dataset_bp.route("/dataset/list", methods=["GET", "POST"])
@login_required
def list_dataset():
    return render_template(
        "dataset/list_datasets.html",
        datasets=dataset_service.get_synchronized(current_user.id),
        local_datasets=dataset_service.get_unsynchronized(current_user.id),
    )


@dataset_bp.route("/dataset/file/upload", methods=["POST"])
@login_required
def upload():
    file = request.files["file"]
    print(file.filename)
    temp_folder = current_user.temp_folder()

    if not file or not file.filename.endswith(".uvl"):
        return jsonify({"message": "No valid file"}), 400

    # create temp folder
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    if os.path.exists(file_path):
        # Generate unique filename (by recursion)
        base_name, extension = os.path.splitext(file.filename)
        i = 1
        while os.path.exists(
            os.path.join(temp_folder, f"{base_name} ({i}){extension}")
        ):
            i += 1
        new_filename = f"{base_name} ({i}){extension}"
        file_path = os.path.join(temp_folder, new_filename)
    else:
        new_filename = file.filename

    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

    return (
        jsonify(
            {
                "message": "UVL uploaded and validated successfully",
                "filename": new_filename,
            }
        ),
        200,
    )


@dataset_bp.route("/dataset/file/upload/github", methods=["POST", "GET"])
@login_required
def upload_from_github():
    github_url = request.json.get('url')
    if not github_url:
        return jsonify({"error": "GitHub URL is required"}), 400

    # Cambiar la URL a la versión raw
    if 'github.com' in github_url:
        raw_url = github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    else:
        return jsonify({"error": "Invalid GitHub URL"}), 400

    try:
        # Descargar el archivo desde la URL raw
        response = requests.get(raw_url, timeout=15)
        response.raise_for_status()  # Si la respuesta es mala (404, 500), lanza una excepción

        file_name = raw_url.split('/')[-1]
        file_type = response.headers['Content-Type']
        file_size = response.headers['Content-Length']

        # Obtener la carpeta temporal específica para el usuario actual
        temp_folder = current_user.temp_folder()

        # Crear la carpeta si no existe
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        # Ruta completa para el archivo descargado
        file_path = os.path.join(temp_folder, file_name)

        # Si el archivo ya existe, generar un nuevo nombre único
        if os.path.exists(file_path):
            base_name, extension = os.path.splitext(file_name)
            i = 1
            while os.path.exists(os.path.join(temp_folder, f"{base_name} ({i}){extension}")):
                i += 1
            file_name = f"{base_name} ({i}){extension}"
            file_path = os.path.join(temp_folder, file_name)

        # Guardar el archivo descargado en la carpeta temporal
        with open(file_path, 'wb') as temp_file:
            temp_file.write(response.content)

        # Procesar si es un ZIP
        if file_name.endswith('.zip'):
            extracted_files = []
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for zip_info in zip_ref.infolist():
                    if zip_info.filename.endswith('.uvl'):  # Excluir directorios
                        extracted_filename = os.path.basename(zip_info.filename)
                        extracted_path = os.path.join(temp_folder, extracted_filename)

                        base_name, extension = os.path.splitext(extracted_filename)
                        i = 1
                        while os.path.exists(extracted_path):
                            extracted_path = os.path.join(temp_folder, f"{base_name} ({i}){extension}")
                            i += 1

                        with zip_ref.open(zip_info) as source, open(extracted_path, 'wb') as target:
                            target.write(source.read())

                    # Agregar el nombre del archivo extraído a la lista de archivos
                        extracted_files.append(extracted_filename)

            return jsonify({
                "message": "ZIP file uploaded and extracted successfully",
                "fileName": file_name,
                "fileType": file_type,
                "extracted_files": extracted_files,
                "fileSize": file_size
            })

        # Si el archivo es un uvl o cualquier otro archivo que no sea zip
        elif file_name.endswith('.uvl'):
            uvl_file_path = os.path.join(temp_folder, file_name)
            with open(uvl_file_path, 'wb') as uvl_file:
                uvl_file.write(response.content)

            return jsonify({
                "message": "UVL file uploaded and validated successfully",
                "fileName": file_name,
                "filePath": uvl_file_path,  # Ruta del archivo UVL
                "fileSize": file_size
            })

        else:
            return jsonify({"error": "Unsupported file type"}), 400

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error uploading file from GitHub: {str(e)}"}), 500
    except requests.exceptions.Timeout:
        return jsonify({"error": "The request to GitHub timed out"}), 408

@dataset_bp.route("/dataset/file/upload/zip", methods=["GET", "POST"])
@login_required
def upload_from_zip():
    file = request.files["file"]
    temp_folder = current_user.temp_folder()

    if not file or not file.filename.endswith(".zip"):
        return jsonify({"message": "No valid file"}), 400

    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    # Manejar conflictos de nombre de archivo
    if os.path.exists(file_path):
        base_name, extension = os.path.splitext(file.filename)
        i = 1
        while os.path.exists(
            os.path.join(temp_folder, f"{base_name} ({i}){extension}")
        ):
            i += 1
        new_filename = f"{base_name} ({i}){extension}"
        file_path = os.path.join(temp_folder, new_filename)
    else:
        new_filename = file.filename

    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

    # Extraer archivos .uvl del zip
    extracted_files = []
    try:
        with ZipFile(file_path, 'r') as zip_ref:
            for zip_info in zip_ref.infolist():
                if zip_info.filename.endswith(".uvl"):
                    # Extraer archivo en la carpeta temporal del usuario
                    extracted_path = os.path.join(temp_folder, zip_info.filename)
                    zip_ref.extract(zip_info, temp_folder)
                    extracted_files.append(zip_info.filename)
    except zipfile.BadZipFile:
        return jsonify({"message": "Invalid zip file"}), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500

    if not extracted_files:
        return jsonify({"message": "No .uvl files found in the zip"}), 400

    return (
        jsonify(
            {
                "message": "Zip uploaded and .uvl files extracted successfully",
                "extracted_files": extracted_files,
                "extracted_path": extracted_path,
            }
        ),
        200,
    )


@dataset_bp.route("/dataset/upload/zip", methods=["POST", "GET"])
@login_required
def create_from_zip():
    form = DataSetForm()
    if request.method == "POST":

        dataset = None

        if not form.validate_on_submit():
            return jsonify({"message": form.errors}), 400

        try:
            logger.info("Creating dataset...")
            dataset = dataset_service.create_from_form(form=form, current_user=current_user)
            logger.info(f"Created dataset: {dataset}")
            dataset_service.move_feature_models(dataset)
        except Exception as exc:
            logger.exception(f"Exception while create dataset data in local {exc}")
            return jsonify({"Exception while create dataset data in local: ": str(exc)}), 400

        # send dataset as deposition to Zenodo
        data = {}
        try:
            zenodo_response_json = zenodo_service.create_new_deposition(dataset)
            response_data = json.dumps(zenodo_response_json)
            data = json.loads(response_data)
        except Exception as exc:
            data = {}
            zenodo_response_json = {}
            logger.exception(f"Exception while create dataset data in Zenodo {exc}")

        if data.get("conceptrecid"):
            deposition_id = data.get("id")

            # update dataset with deposition id in Zenodo
            dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

            try:
                # iterate for each feature model (one feature model = one request to Zenodo)
                for feature_model in dataset.feature_models:
                    zenodo_service.upload_file(dataset, deposition_id, feature_model)

                # publish deposition
                zenodo_service.publish_deposition(deposition_id)

                # update DOI
                deposition_doi = zenodo_service.get_doi(deposition_id)
                dataset_service.update_dsmetadata(dataset.ds_meta_data_id, dataset_doi=deposition_doi)
            except Exception as e:
                msg = f"it has not been possible upload feature models in Zenodo and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        # Delete temp folder
        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    return render_template("dataset/upload_zip.html", form=form)


@dataset_bp.route("/dataset/file/delete", methods=["POST"])
def delete():
    data = request.get_json()
    filename = data.get("file")
    temp_folder = current_user.temp_folder()
    filepath = os.path.join(temp_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"message": "File deleted successfully"})

    return jsonify({"error": "Error: File not found"})


@dataset_bp.route("/dataset/download/<int:dataset_id>", methods=["GET"])
def download_dataset(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    file_path = f"uploads/user_{dataset.user_id}/dataset_{dataset.id}/"

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"dataset_{dataset_id}.zip")

    with ZipFile(zip_path, "w") as zipf:
        for subdir, dirs, files in os.walk(file_path):
            for file in files:
                full_path = os.path.join(subdir, file)

                relative_path = os.path.relpath(full_path, file_path)

                zipf.write(
                    full_path,
                    arcname=os.path.join(
                        os.path.basename(zip_path[:-4]), relative_path
                    ),
                )

    user_cookie = request.cookies.get("download_cookie")
    if not user_cookie:
        user_cookie = str(
            uuid.uuid4()
        )  # Generate a new unique identifier if it does not exist
        # Save the cookie to the user's browser
        resp = make_response(
            send_from_directory(
                temp_dir,
                f"dataset_{dataset_id}.zip",
                as_attachment=True,
                mimetype="application/zip",
            )
        )
        resp.set_cookie("download_cookie", user_cookie)
    else:
        resp = send_from_directory(
            temp_dir,
            f"dataset_{dataset_id}.zip",
            as_attachment=True,
            mimetype="application/zip",
        )

    # Check if the download record already exists for this cookie
    existing_record = DSDownloadRecord.query.filter_by(
        user_id=current_user.id if current_user.is_authenticated else None,
        dataset_id=dataset_id,
        download_cookie=user_cookie
    ).first()

    if not existing_record:
        # Record the download in your database
        DSDownloadRecordService().create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset_id,
            download_date=datetime.now(timezone.utc),
            download_cookie=user_cookie,
        )

    return resp


@dataset_bp.route("/dataset/download/all", methods=["GET"])
def download_all_dataset():
    # Obtener la cookie de descarga
    user_cookie = request.cookies.get("download_cookie")
    if not user_cookie:
        user_cookie = str(uuid.uuid4())

    # Crear un directorio temporal para almacenar el archivo ZIP
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "all_datasets.zip")

    with ZipFile(zip_path, "w") as zipf:
        # Obtener todos los datasets existentes (sin filtrar por usuario)
        datasets = dataset_service.get_all()
        # Iterar sobre todos los datasets
        for dataset in datasets:
            file_path = f"uploads/user_{dataset.user_id}/dataset_{dataset.id}/"
            # Verificar que el directorio del dataset existe
            if os.path.exists(file_path):
                # Crear una carpeta para el dataset dentro del ZIP (usando el ID o nombre del dataset)
                dataset_folder = f"dataset_{dataset.id}/"
                # Iterar sobre todos los archivos del dataset usando dataset.files()
                for file in dataset.files():
                    full_path = os.path.join(file_path, file.name)
                    # Verificar que el archivo existe
                    if not os.path.exists(full_path):
                        print(f"Archivo no encontrado: {full_path}")
                        continue
                    # Obtener el Hubfile correspondiente a este archivo
                    try:
                        hubfile = HubfileService().get_or_404(file.id)
                        if not hubfile:
                            print(f"No se encontró el Hubfile para el archivo {file.name}")
                            continue
                    except Exception as e:
                        print(f"Error al obtener Hubfile para {file.name}: {str(e)}")
                        continue

                    # Convertir cada archivo a los formatos deseados
                    for format in ["glencoe", "dimacs", "splot", "json", "afm", "uvl"]:
                        content = ""
                        name = f"{hubfile.name}_{format}.txt"

                        # Realizar la conversión según el formato
                        if format == "glencoe":
                            temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
                            fm = UVLReader(hubfile.get_path()).transform()
                            GlencoeWriter(temp_file.name, fm).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()
                            name = f"{hubfile.name}_glencoe.txt"
                        elif format == "dimacs":
                            temp_file = tempfile.NamedTemporaryFile(suffix='.cnf', delete=False)
                            fm = UVLReader(hubfile.get_path()).transform()
                            sat = FmToPysat(fm).transform()
                            DimacsWriter(temp_file.name, sat).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()
                            name = f"{hubfile.name}_cnf.txt"
                        elif format == "splot":
                            temp_file = tempfile.NamedTemporaryFile(suffix='.splx', delete=False)
                            fm = UVLReader(hubfile.get_path()).transform()
                            SPLOTWriter(temp_file.name, fm).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()
                            name = f"{hubfile.name}_splot.txt"
                        elif format == "json":
                            temp_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
                            fm = UVLReader(hubfile.get_path()).transform()
                            JSONWriter(temp_file.name, fm).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()
                            name = f"{hubfile.name}_json.txt"
                        elif format == "afm":
                            temp_file = tempfile.NamedTemporaryFile(suffix='.afm', delete=False)
                            fm = UVLReader(hubfile.get_path()).transform()
                            AFMWriter(temp_file.name, fm).transform()
                            with open(temp_file.name, "r") as new_format_file:
                                content = new_format_file.read()
                            name = f"{hubfile.name}_afm.txt"
                        elif format == "uvl":
                            # Para UVL no hacemos transformación adicional, solo agregamos el archivo original
                            content = open(full_path, "r").read()
                            name = f"{file.name}_uvl.txt"

                        # Agregar el archivo convertido al ZIP en la carpeta correspondiente al dataset
                        zipf.writestr(os.path.join(dataset_folder, name), content)
            else:
                print(f"Archivo no encontrado para el dataset {dataset.id}")

    # Responder con el archivo ZIP
    resp = make_response(
        send_from_directory(
            temp_dir,
            "all_datasets.zip",
            as_attachment=True,
            mimetype="application/zip"
        )
    )

    # Establecer la cookie "download_cookie" para que no se genere nuevamente
    resp.set_cookie("download_cookie", user_cookie)

    # Registrar la descarga en la base de datos
    existing_record = DSDownloadRecord.query.filter_by(
        user_id=current_user.id if current_user.is_authenticated else None,
        download_cookie=user_cookie
    ).first()

    if not existing_record:
        # Registrar la descarga en la base de datos
        DSDownloadRecordService().create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=None,  # No es necesario asociar con un dataset en particular
            download_date=datetime.now(timezone.utc),
            download_cookie=user_cookie,
        )

    return resp


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):

    # Check if the DOI is an old DOI
    new_doi = doi_mapping_service.get_new_doi(doi)
    if new_doi:
        # Redirect to the same path with the new DOI
        return redirect(url_for('dataset.subdomain_index', doi=new_doi), code=302)

    # Try to search the dataset by the provided DOI (which should already be the new one)
    ds_meta_data = dsmetadata_service.filter_by_doi(doi)

    if not ds_meta_data:
        abort(404)

    # Get dataset
    dataset = ds_meta_data.data_set

    # Save the cookie to the user's browser
    user_cookie = ds_view_record_service.create_cookie(dataset=dataset)
    resp = make_response(render_template("dataset/view_dataset.html", dataset=dataset))
    resp.set_cookie("view_cookie", user_cookie)

    return resp


@dataset_bp.route("/dataset/unsynchronized/<int:dataset_id>/", methods=["GET"])
@login_required
def get_unsynchronized_dataset(dataset_id):

    # Get dataset
    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)

    if not dataset:
        abort(404)

    return render_template("dataset/view_dataset.html", dataset=dataset)


community_bp = Blueprint('community', __name__)
community_service = CommunityService()


@community_bp.route('/communities', methods=['GET'])
@login_required
def list_communities():
    communities = CommunityService.list_communities()
    return render_template('community/list_communities.html',
                           communities=communities,
                           current_user=current_user,
                           is_owner=CommunityService.is_owner,
                           is_member=CommunityService.is_member,
                           is_request=CommunityService.is_request)


@community_bp.route('/community/<int:community_id>', methods=['GET'])
@login_required
def view_community(community_id):
    community = CommunityService.get_community_by_id(community_id)
    if not community:
        return "Community not found", 404

    owners = [owner.profile.name for owner in community.owners.all()]
    members = [member.profile.name for member in community.members.all()]
    requests = community.requests.all()

    return render_template('community/view_community.html',
                           community=community,
                           current_user=current_user,
                           owners=owners,
                           members=members,
                           requests=requests,
                           is_owner=CommunityService.is_owner,
                           is_member=CommunityService.is_member,
                           is_request=CommunityService.is_request)


@community_bp.route('/community/create', methods=['GET'])
@login_required
def create_community_page():
    return render_template('community/create_community.html')


@community_bp.route('/community/create', methods=['POST'])
@login_required
def create_community():
    name = request.form.get('name')
    if not name:
        flash('Community name is required', 'danger')
        return redirect(url_for('community.create_community_page'))
    CommunityService.create_community(name, current_user)
    flash('Community created successfully!', 'success')
    return redirect(url_for('community.list_communities'))


@community_bp.route('/community/<int:community_id>/edit', methods=['GET'])
@login_required
def edit_community_page(community_id):
    community = CommunityService.get_community_by_id(community_id)
    if not community:
        return "Community not found", 404
    if not CommunityService.is_owner(community, current_user):
        return "Forbidden", 403

    return render_template('community/edit_community.html', community=community)


@community_bp.route('/community/<int:community_id>/edit', methods=['POST'])
@login_required
def edit_community(community_id):
    community = CommunityService.get_community_by_id(community_id)
    if not community:
        return "Community not found", 404
    if not CommunityService.is_owner(community, current_user):
        return "Forbidden", 403
    new_name = request.form.get('name')
    updated_community = CommunityService.update_community(community_id, new_name)

    return redirect(url_for('community.view_community', community_id=updated_community.id))


@community_bp.route('/community/<int:community_id>/delete', methods=['POST'])
@login_required
def delete_community(community_id):
    community = CommunityService.get_community_by_id(community_id)
    if not community:
        return "Community not found", 404
    if not CommunityService.is_owner(community, current_user):
        return "Forbidden", 403
    CommunityService.remove_community(community_id)
    return redirect(url_for('community.list_communities'))


@community_bp.route('/community/<int:community_id>/request', methods=['POST'])
@login_required
def request_community(community_id):
    try:
        CommunityService.request_community(community_id, current_user)
        flash('Request to join the community has been sent successfully.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('community.view_community', community_id=community_id))


@community_bp.route('/community/<int:community_id>/requests/<int:user_id>/<string:action>', methods=['POST'])
@login_required
def handle_request(community_id, user_id, action):
    community = CommunityService.get_community_by_id(community_id)
    if not community or not CommunityService.is_owner(community, current_user):
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('community.view_community', community_id=community_id))

    if action not in ["accept", "reject"]:
        flash('Invalid action.', 'danger')
        return redirect(url_for('community.view_community', community_id=community_id))

    success = CommunityService.handle_request(community_id, user_id, action)
    if success:
        flash('Request handled successfully.', 'success')
    else:
        flash('Failed to handle the request.', 'danger')

    return redirect(url_for('community.view_community', community_id=community_id))
