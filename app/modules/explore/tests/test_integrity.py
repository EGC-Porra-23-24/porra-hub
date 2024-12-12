import os
from dotenv import load_dotenv
import pytest
from app import app, db
from app.modules.auth.models import User
from time import sleep
from app.modules.dataset.models import Author, DSMetaData, DSMetrics, DataSet, PublicationType
from datetime import datetime

from app.modules.featuremodel.models import FMMetaData, FeatureModel
from app.modules.hubfile.models import Hubfile

@pytest.fixture(scope='module')
def test_client(test_client):
    with test_client.application.app_context():
        
        #Create Users
        user1 = User(email='user1@example.com', password='1234')
        user2 = User(email='user2@example.com', password='1234')
        users = [user1, user2]
        db.session.add_all(users)
        db.session.commit()
        
        # Create DSMetrics instances
        base_ds_metrics = DSMetrics(number_of_models=2, number_of_features=20)
        little_models_ds_metrics = DSMetrics(number_of_models=1, number_of_features=20)
        many_models_ds_metrics = DSMetrics(number_of_models=3, number_of_features=30)
        little_features_ds_metrics = DSMetrics(number_of_models=2, number_of_features=10)
        many_features_ds_metrics = DSMetrics(number_of_models=2, number_of_features=40)
        ds_metrics_list = [base_ds_metrics, little_models_ds_metrics, many_models_ds_metrics,
                           little_features_ds_metrics, many_features_ds_metrics]
        db.session.add_all(ds_metrics_list)
        db.session.commit()
        
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
                ds_metrics_id=ds_metrics_list[i-2].id if i in range(3, 7) else ds_metrics_list[0].id
            ) for i in range(7)
        ]
        db.session.add_all(ds_meta_data_list)
        db.session.commit()
        
        # Create Author instances and associate with DSMetaData
        authors = [
            Author(
                name=f'Author {i+1}',
                affiliation=f'Affiliation {i+1}',
                orcid=f'0000-0000-0000-000{i}',
                ds_meta_data_id=ds_meta_data_list[i % 7].id
            ) for i in range(7)
        ]
        db.session.add_all(authors)
        db.session.commit()
        
        # Create DataSet instances and assign communities
        datasets = [
            DataSet(
                id=i+1,
                user_id=user1.id if i % 2 == 0 else user2.id,
                ds_meta_data_id=ds_meta_data_list[i].id,
                created_at=datetime.strptime('2024-12-9' if i == 1 else '2024-12-11' if i == 2 else '2024-12-10',
                                             '%Y-%m-%d')
            ) for i in range(7)
        ]
        db.session.add_all(datasets)
        db.session.commit()
        
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
        db.session.add_all(fm_meta_data_list)
        db.session.commit()
        
        # Create Author instances and associate with FMMetaData
        fm_authors = [
            Author(
                name=f'Author {i+5}',
                affiliation=f'Affiliation {i+5}',
                orcid=f'0000-0000-0000-000{i+5}',
                fm_meta_data_id=fm_meta_data_list[i].id
            ) for i in range(14)
        ]
        db.session.add_all(fm_authors)
        db.session.commit()

        feature_models = [
            FeatureModel(
                data_set_id=datasets[4].id if i == 7 else datasets[i // 2].id,
                fm_meta_data_id=fm_meta_data_list[i].id
            ) for i in range(14)
        ]
        db.session.add_all(feature_models)
        db.session.commit()
        
        load_dotenv()
        working_dir = os.getenv('WORKING_DIR', '')
        src_folder = os.path.join(working_dir, 'app', 'modules', 'dataset', 'uvl_examples')
        uvl_files=[]
        for i in range(14):
            file_name = f'file{i+1}.uvl'
            feature_model = feature_models[i]

            src_path = os.path.join(src_folder, file_name)

            uvl_file = Hubfile(
                name=file_name,
                checksum=f'checksum{i+1}',
                size=os.path.getsize(src_path),
                feature_model_id=feature_model.id
            )
            uvl_files.append(uvl_file)
        db.session.add_all(uvl_files)
        db.session.commit()
        
    yield test_client

#Check whether the provided list of datasets (as dicts) has all 7 datasets except the ones specified by the passed ids
def got_all_datasets_except(json, *args):
    return set(map(lambda ds:ds['id'], json)) == {i for i in range(1,8) if i not in args}

def test_no_filters(test_client):
    response = test_client.post("/explore", data='{}')
    assert response.status_code == 200
    json = response.json
    assert len(json)==7

def test_filter_by_start_date(test_client):
    response = test_client.post("/explore", data='{"min_creation_date":"2024-12-10"}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 2)

def test_filter_by_end_date(test_client):
    response = test_client.post("/explore", data='{"max_creation_date":"2024-12-10"}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 3)
    
def test_filter_by_min_size(test_client):
    response = test_client.post("/explore", data='{"min_size":751}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 6)
    
def test_filter_by_max_size(test_client):
    response = test_client.post("/explore", data='{"max_size":1242}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 7)

def test_filter_by_min_models(test_client):  
    response = test_client.post("/explore", data='{"min_models":2}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 4)
 
def test_filter_by_max_models(test_client):  
    response = test_client.post("/explore", data='{"max_models":2}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 5)
    
def test_filter_by_min_features(test_client):  
    response = test_client.post("/explore", data='{"min_features":20}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 6)
    
def test_filter_by_max_features(test_client):  
    response = test_client.post("/explore", data='{"max_features":20}')
    assert response.status_code == 200
    json = response.json
    assert got_all_datasets_except(json , 5, 7)