import re
from datetime import datetime as dt, timedelta
from sqlalchemy import any_, or_, func
import unidecode
from app.modules.dataset.models import Author, DSMetaData, DataSet, PublicationType, DSMetrics
from app.modules.featuremodel.models import FMMetaData, FeatureModel
from app.modules.hubfile.models import Hubfile
from core.repositories.BaseRepository import BaseRepository
from flask_sqlalchemy import query


class ExploreRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)
      
    def advanced_filter(self, query: query.Query, min_creation_date=None, max_creation_date=None, min_size=None, 
                        max_size=None, min_features=None, max_features=None, **kwargs):
        format = "%Y-%m-%d"
        if min_creation_date:
            min_creation_date = dt.strptime(min_creation_date, format).date().strftime(format)
            query = query.filter(DataSet.created_at >= min_creation_date)
        if max_creation_date:
            max_creation_date = (dt.strptime(max_creation_date, format).date() + timedelta(days=1)).strftime(format)
            query = query.filter(DataSet.created_at <= max_creation_date)
        if min_features:
            query = query.filter(DSMetrics.number_of_features >= int(min_features))
        if max_features:
            query = query.filter(DSMetrics.number_of_features <= int(max_features))
        query = query.group_by(DataSet.id)
        if min_size:
            query = query.having(func.sum(Hubfile.size) >= min_size)
        if max_size:
            query = query.having(func.sum(Hubfile.size) <= max_size)
        return query

    def filter(self, query="", sorting="newest", publication_type="any", tags=[], **kwargs):
        # Normalize and remove unwanted characters
        normalized_query = unidecode.unidecode(query).lower()
        cleaned_query = re.sub(r'[,.":\'()\[\]^;!¡¿?]', "", normalized_query)

        filters = []
        for word in cleaned_query.split():
            filters.append(DSMetaData.title.ilike(f"%{word}%"))
            filters.append(DSMetaData.description.ilike(f"%{word}%"))
            filters.append(Author.name.ilike(f"%{word}%"))
            filters.append(Author.affiliation.ilike(f"%{word}%"))
            filters.append(Author.orcid.ilike(f"%{word}%"))
            filters.append(FMMetaData.uvl_filename.ilike(f"%{word}%"))
            filters.append(FMMetaData.title.ilike(f"%{word}%"))
            filters.append(FMMetaData.description.ilike(f"%{word}%"))
            filters.append(FMMetaData.publication_doi.ilike(f"%{word}%"))
            filters.append(FMMetaData.tags.ilike(f"%{word}%"))
            filters.append(DSMetaData.tags.ilike(f"%{word}%"))

        datasets = (
            self.model.query
            .join(DataSet.ds_meta_data)
            .join(DSMetaData.authors)
            .join(DataSet.feature_models)
            .join(FeatureModel.fm_meta_data)
            .join(FeatureModel.files)
            .join(DSMetaData.ds_metrics)
            .filter(or_(*filters))
            .filter(DSMetaData.dataset_doi.isnot(None))  # Exclude datasets with empty dataset_doi
        )

        if publication_type != "any":
            matching_type = None
            for member in PublicationType:
                if member.value.lower() == publication_type:
                    matching_type = member
                    break

            if matching_type is not None:
                datasets = datasets.filter(DSMetaData.publication_type == matching_type.name)

        if tags:
            datasets = datasets.filter(DSMetaData.tags.ilike(any_(f"%{tag}%" for tag in tags)))

        datasets = self.advanced_filter(datasets, **kwargs)

        # Order by created_at
        if sorting == "oldest":
            datasets = datasets.order_by(self.model.created_at.asc())
        else:
            datasets = datasets.order_by(self.model.created_at.desc())

        return datasets.all()
