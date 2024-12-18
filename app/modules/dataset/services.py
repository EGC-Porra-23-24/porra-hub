import logging
import os
import hashlib
import shutil
from typing import Optional
import uuid

from flask import abort, request

from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DSViewRecord, DataSet, DSMetaData
from app.modules.dataset.repositories import (
    AuthorRepository,
    DOIMappingRepository,
    DSDownloadRecordRepository,
    DSMetaDataRepository,
    DSMetricsRepository,
    DSViewRecordRepository,
    DataSetRepository,
    CommunityRepository
)
from app.modules.featuremodel.repositories import FMMetaDataRepository, FeatureModelRepository
from app.modules.hubfile.repositories import (
    HubfileDownloadRecordRepository,
    HubfileRepository,
    HubfileViewRecordRepository
)
from core.services.BaseService import BaseService

logger = logging.getLogger(__name__)


def calculate_checksum_and_size(file_path):
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as file:
        content = file.read()
        hash_md5 = hashlib.md5(content).hexdigest()
        return hash_md5, file_size


def calculate_features(file_path):
    with open(file_path, 'r') as file:
        # Counts features by counting the number of lines with an odd number of lines at the start
        odd_tabs_lines = 0
        while file.readline() != 'features\n':
            pass
        for line in file.readlines():
            if line == '\n':
                # Breakpoint
                return odd_tabs_lines
            line = line.replace(' '*4, '\t')
            n_tabs = len(line) - len(line.lstrip('\t'))
            if (n_tabs % 2 == 1):
                odd_tabs_lines += 1
    return odd_tabs_lines


class DataSetService(BaseService):
    def __init__(self):
        super().__init__(DataSetRepository())
        self.feature_model_repository = FeatureModelRepository()
        self.author_repository = AuthorRepository()
        self.dsmetadata_repository = DSMetaDataRepository()
        self.fmmetadata_repository = FMMetaDataRepository()
        self.dsmetrics_repository = DSMetricsRepository()
        self.dsdownloadrecord_repository = DSDownloadRecordRepository()
        self.hubfiledownloadrecord_repository = HubfileDownloadRecordRepository()
        self.hubfilerepository = HubfileRepository()
        self.dsviewrecord_repostory = DSViewRecordRepository()
        self.hubfileviewrecord_repository = HubfileViewRecordRepository()

    def move_feature_models(self, dataset: DataSet):
        current_user = AuthenticationService().get_authenticated_user()
        source_dir = current_user.temp_folder()

        working_dir = os.getenv("WORKING_DIR", "")
        dest_dir = os.path.join(working_dir, "uploads", f"user_{current_user.id}", f"dataset_{dataset.id}")

        os.makedirs(dest_dir, exist_ok=True)

        for feature_model in dataset.feature_models:
            uvl_filename = feature_model.fm_meta_data.uvl_filename
            shutil.move(os.path.join(source_dir, uvl_filename), dest_dir)

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return self.repository.get_synchronized(current_user_id)

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return self.repository.get_unsynchronized(current_user_id)

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return self.repository.get_unsynchronized_dataset(current_user_id, dataset_id)

    def latest_synchronized(self):
        return self.repository.latest_synchronized()

    def count_synchronized_datasets(self):
        return self.repository.count_synchronized_datasets()

    def count_feature_models(self):
        return self.feature_model_service.count_feature_models()

    def count_authors(self) -> int:
        return self.author_repository.count()

    def count_dsmetadata(self) -> int:
        return self.dsmetadata_repository.count()

    def total_dataset_downloads(self) -> int:
        return self.dsdownloadrecord_repository.total_dataset_downloads()

    def total_dataset_views(self) -> int:
        return self.dsviewrecord_repostory.total_dataset_views()

    def get_all(self) -> list[DataSet]:
        return self.repository.get_all()

    def get_all_by_community(community_id):
        return DataSetRepository.get_all_by_community(community_id=community_id)

    def create_from_form(self, form, current_user) -> DataSet:
        main_author = {
            "name": f"{current_user.profile.surname}, {current_user.profile.name}",
            "affiliation": current_user.profile.affiliation,
            "orcid": current_user.profile.orcid,
        }

        try:
            logger.info(f"Creating DSMetaData with data: {form.get_dsmetadata()}")
            # Crear DSMetaData

            dsmetadata_data = form.get_dsmetadata()
            dsmetadata_data.pop('community_id', None)
            dsmetadata = self.dsmetadata_repository.create(**dsmetadata_data)

            # Añadir el autor principal y otros autores
            for author_data in [main_author] + form.get_authors():
                author = self.author_repository.create(
                    commit=False,
                    ds_meta_data_id=dsmetadata.id,
                    **author_data
                )
                dsmetadata.authors.append(author)

            # Crear el DataSet principal
            dataset = self.create(
                commit=False,
                user_id=current_user.id,
                ds_meta_data_id=dsmetadata.id,
                community_id=form.community.data if form.community.data else None
            )

            # Procesar cada modelo de características
            number_of_models = 0
            number_of_features = 0
            for feature_model in form.feature_models:
                # Crear metadata del modelo de características
                fmmetadata = self.fmmetadata_repository.create(
                    commit=False,
                    **feature_model.get_fmmetadata()
                )

                # Agregar autores al modelo de características
                for author_data in feature_model.get_authors():
                    author = self.author_repository.create(
                        commit=False,
                        fm_meta_data_id=fmmetadata.id,
                        **author_data
                    )
                    fmmetadata.authors.append(author)

                # Crear el modelo de características y asociarlo al dataset
                fm = self.feature_model_repository.create(
                    commit=False,
                    data_set_id=dataset.id,
                    fm_meta_data_id=fmmetadata.id
                )

                # Procesar los archivos asociados al modelo de características
                uvl_filename = feature_model.uvl_filename.data
                file_path = os.path.join(current_user.temp_folder(), uvl_filename)

                # Calcular el checksum y tamaño del archivo
                checksum, size = calculate_checksum_and_size(file_path)
                number_of_features += calculate_features(file_path)

                # Crear el archivo en el repositorio
                file = self.hubfilerepository.create(
                    commit=False,
                    name=uvl_filename,
                    checksum=checksum,
                    size=size,
                    feature_model_id=fm.id
                )
                fm.files.append(file)
                number_of_models += 1

            dsmetrics = self.dsmetrics_repository.create(number_of_models=number_of_models,
                                                         number_of_features=number_of_features)
            dsmetadata.ds_metrics_id = dsmetrics.id

            # Confirmar todos los cambios realizados
            self.repository.session.commit()

        except Exception as exc:
            logger.error(f"Exception creating dataset from form: {exc}", exc_info=True)
            self.repository.session.rollback()
            raise exc

        return dataset

    def update_dsmetadata(self, id, **kwargs):
        return self.dsmetadata_repository.update(id, **kwargs)

    def get_uvlhub_doi(self, dataset: DataSet) -> str:
        domain = os.getenv('DOMAIN', 'localhost')
        return f'http://{domain}/doi/{dataset.ds_meta_data.dataset_doi}'


class AuthorService(BaseService):
    def __init__(self):
        super().__init__(AuthorRepository())


class DSDownloadRecordService(BaseService):
    def __init__(self):
        super().__init__(DSDownloadRecordRepository())


class DSMetaDataService(BaseService):
    def __init__(self):
        super().__init__(DSMetaDataRepository())

    def update(self, id, **kwargs):
        return self.repository.update(id, **kwargs)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.repository.filter_by_doi(doi)


class DSViewRecordService(BaseService):
    def __init__(self):
        super().__init__(DSViewRecordRepository())

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.repository.the_record_exists(dataset, user_cookie)

    def create_new_record(self, dataset: DataSet,  user_cookie: str) -> DSViewRecord:
        return self.repository.create_new_record(dataset, user_cookie)

    def create_cookie(self, dataset: DataSet) -> str:

        user_cookie = request.cookies.get("view_cookie")
        if not user_cookie:
            user_cookie = str(uuid.uuid4())

        existing_record = self.the_record_exists(dataset=dataset, user_cookie=user_cookie)

        if not existing_record:
            self.create_new_record(dataset=dataset, user_cookie=user_cookie)

        return user_cookie


class DOIMappingService(BaseService):
    def __init__(self):
        super().__init__(DOIMappingRepository())

    def get_new_doi(self, old_doi: str) -> str:
        doi_mapping = self.repository.get_new_doi(old_doi)
        if doi_mapping:
            return doi_mapping.dataset_doi_new
        else:
            return None


class SizeService():

    def __init__(self):
        pass

    def get_human_readable_size(self, size: int) -> str:
        if size < 1024:
            return f'{size} bytes'
        elif size < 1024 ** 2:
            return f'{round(size / 1024, 2)} KB'
        elif size < 1024 ** 3:
            return f'{round(size / (1024 ** 2), 2)} MB'
        else:
            return f'{round(size / (1024 ** 3), 2)} GB'


class CommunityService:
    @staticmethod
    def list_communities():
        return CommunityRepository.get_all_communities()

    @staticmethod
    def get_community_by_id(community_id):
        return CommunityRepository.get_community_by_id(community_id)

    @staticmethod
    def get_communities_by_member(current_user):
        return CommunityRepository.get_communities_by_member(current_user.id)

    @staticmethod
    def get_communities_by_owner(current_user):
        return CommunityRepository.get_communities_by_owner(current_user.id)

    @staticmethod
    def search_communities(query):
        if not query:
            return []
        return CommunityRepository.search_by_name(query)

    @staticmethod
    def create_community(name, current_user):
        if CommunityRepository.get_community_by_name(name):
            abort(400, description="A community with this name already exists.")
        return CommunityRepository.create_community(name, current_user)

    @staticmethod
    def update_community(community_id, new_name):
        community = CommunityRepository.get_community_by_id(community_id)
        if not community:
            return None
        community.name = new_name
        CommunityRepository.save_community()
        return community

    @staticmethod
    def remove_community(community_id):
        CommunityRepository.delete_community(community_id)

    @staticmethod
    def is_owner(community, current_user):
        return current_user.id in [owner.id for owner in community.owners]

    @staticmethod
    def is_member(community, current_user):
        return current_user.id in [member.id for member in community.members]

    @staticmethod
    def is_request(community, current_user):
        return current_user.id in [request.id for request in community.requests]

    @staticmethod
    def request_community(community_id, current_user):
        community = CommunityService.get_community_by_id(community_id)
        result_member = CommunityService.is_member(community, current_user)
        if result_member:
            raise Exception("User is already a member of this community.")
        result_request = CommunityService.is_request(community, current_user)
        if result_request:
            raise Exception("Request to join the community is already pending.")
        CommunityRepository.request_community(community_id, current_user)

    @staticmethod
    def remove_member(community_id, user):
        community = CommunityService.get_community_by_id(community_id)

        if not community:
            raise Exception("Community not found")

        if not CommunityService.is_member(community, user):
            raise Exception("User is not a member of this community.")

        if CommunityService.is_owner(community, user):
            raise Exception("Owners cannot leave the community.")

        CommunityRepository.remove_member(community, user)

    @staticmethod
    def handle_request(community_id, user_id, action):
        if action == "accept":
            added = CommunityRepository.add_member(community_id, user_id)
            if added:
                CommunityRepository.remove_request(community_id, user_id)
                return True
        elif action == "reject":
            return CommunityRepository.remove_request(community_id, user_id)
        return False
