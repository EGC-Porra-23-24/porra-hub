import os
import shutil
from app.modules.auth.models import Community, User
from app.modules.featuremodel.models import FMMetaData, FeatureModel
from app.modules.hubfile.models import Hubfile
from core.seeders.BaseSeeder import BaseSeeder
from app.modules.dataset.models import (
    DataSet,
    DSMetaData,
    PublicationType,
    DSMetrics,
    Author)
from datetime import datetime
from dotenv import load_dotenv


class DataSetSeeder(BaseSeeder):

    priority = 2  # Lower priority

    def run(self):
        # Retrieve users
        user1 = User.query.filter_by(email='user1@example.com').first()
        user2 = User.query.filter_by(email='user2@example.com').first()

        if not user1 or not user2:
            raise Exception("Users not found. Please seed users first.")

        # Create DSMetrics instances
        base_ds_metrics = DSMetrics(number_of_models=2, number_of_features=20)
        little_models_ds_metrics = DSMetrics(number_of_models=1, number_of_features=20)  # Needs file with 20 feats
        many_models_ds_metrics = DSMetrics(number_of_models=3, number_of_features=30)
        little_features_ds_metrics = DSMetrics(number_of_models=2, number_of_features=10)  # Needs file with 5 feats
        many_features_ds_metrics = DSMetrics(number_of_models=2, number_of_features=40)  # Needs file with 20 feats
        ds_metrics_list = [base_ds_metrics, little_models_ds_metrics, many_models_ds_metrics,
                           little_features_ds_metrics, many_features_ds_metrics]
        seeded_ds_metrics = self.seed(ds_metrics_list)

        # Create DSMetaData instances
        ds_meta_data_list = [
            DSMetaData(
                deposition_id=1 + i,
                title=f'Sample dataset {i+1}',
                description=f'Description for dataset {i+1}',
                publication_type=PublicationType.DATA_MANAGEMENT_PLAN,
                publication_doi=f'10.1234/dataset{i+1}',
                dataset_doi=f'10.1234/dataset{i+1}',
                tags='tag1, tag2',
                ds_metrics_id=seeded_ds_metrics[i-2].id if i in range(3, 7) else seeded_ds_metrics[0].id
            ) for i in range(7)
        ]
        seeded_ds_meta_data = self.seed(ds_meta_data_list)

        # Create Author instances and associate with DSMetaData
        authors = [
            Author(
                name=f'Author {i+1}',
                affiliation=f'Affiliation {i+1}',
                orcid=f'0000-0000-0000-000{i}',
                ds_meta_data_id=seeded_ds_meta_data[i % 7].id
            ) for i in range(7)
        ]
        self.seed(authors)

        # Retrieve communities
        community1 = Community.query.filter_by(name='Data Science Enthusiasts').first()
        community2 = Community.query.filter_by(name='AI Researchers').first()
        community3 = Community.query.filter_by(name='Python Developers').first()

        if not community1 or not community2 or not community3:
            raise Exception("Communities not found. Please seed communities first.")

        # Create DataSet instances and assign communities
        datasets = [
            DataSet(
                user_id=user1.id if i % 2 == 0 else user2.id,
                ds_meta_data_id=seeded_ds_meta_data[i].id,
                community_id=community1.id if i % 3 == 0 else community2.id if i % 3 == 1 else community3.id,
                created_at=datetime.strptime('2024-12-9' if i == 1 else '2024-12-11' if i == 2 else '2024-12-10',
                                             '%Y-%m-%d')
            ) for i in range(7)
        ]
        seeded_datasets = self.seed(datasets)

        # Assume there are 12 UVL files, create corresponding FMMetaData and FeatureModel
        fm_meta_data_list = [
            FMMetaData(
                uvl_filename=f'file{i+1}.uvl',
                title=f'Feature Model {i+1}',
                description=f'Description for feature model {i+1}',
                publication_type=PublicationType.SOFTWARE_DOCUMENTATION,
                publication_doi=f'10.1234/fm{i+1}',
                tags='tag1, tag2',
                uvl_version='1.0'
            ) for i in range(14)
        ]
        seeded_fm_meta_data = self.seed(fm_meta_data_list)

        # Create Author instances and associate with FMMetaData
        fm_authors = [
            Author(
                name=f'Author {i+5}',
                affiliation=f'Affiliation {i+5}',
                orcid=f'0000-0000-0000-000{i+5}',
                fm_meta_data_id=seeded_fm_meta_data[i].id
            ) for i in range(14)
        ]
        self.seed(fm_authors)

        feature_models = [
            FeatureModel(
                data_set_id=seeded_datasets[4].id if i == 7 else seeded_datasets[i // 2].id,
                fm_meta_data_id=seeded_fm_meta_data[i].id
            ) for i in range(14)
        ]
        seeded_feature_models = self.seed(feature_models)

        # Create files, associate them with FeatureModels and copy files
        load_dotenv()
        working_dir = os.getenv('WORKING_DIR', '')
        src_folder = os.path.join(working_dir, 'app', 'modules', 'dataset', 'uvl_examples')
        for i in range(14):
            file_name = f'file{i+1}.uvl'
            feature_model = seeded_feature_models[i]
            dataset = next(ds for ds in seeded_datasets if ds.id == feature_model.data_set_id)
            user_id = dataset.user_id

            dest_folder = os.path.join(working_dir, 'uploads', f'user_{user_id}', f'dataset_{dataset.id}')
            os.makedirs(dest_folder, exist_ok=True)
            shutil.copy(os.path.join(src_folder, file_name), dest_folder)

            file_path = os.path.join(dest_folder, file_name)

            uvl_file = Hubfile(
                name=file_name,
                checksum=f'checksum{i+1}',
                size=os.path.getsize(file_path),
                feature_model_id=feature_model.id
            )
            self.seed([uvl_file])
