from unittest.mock import patch
import pytest

from app.modules.auth.models import User
from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import Author, DSMetaData, DSMetrics, DataSet
from app.modules.dataset.services import DataSetService
from app.modules.featuremodel.models import FMMetaData, FeatureModel
from app.modules.hubfile.models import Hubfile
from app.modules.profile.models import UserProfile


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
