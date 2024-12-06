from datetime import datetime, timezone
import logging
from flask_login import current_user
from typing import Optional

from sqlalchemy import desc, func

from app.modules.dataset.models import (
    Author,
    DOIMapping,
    DSDownloadRecord,
    DSMetaData,
    DSViewRecord,
    DataSet
)
from core.repositories.BaseRepository import BaseRepository

from app import db
from app.modules.auth.models import Community, User, community_request
from app.modules.auth.models import community_members

logger = logging.getLogger(__name__)


class AuthorRepository(BaseRepository):
    def __init__(self):
        super().__init__(Author)


class DSDownloadRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSDownloadRecord)

    def total_dataset_downloads(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0


class DSMetaDataRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSMetaData)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.model.query.filter_by(dataset_doi=doi).first()


class DSViewRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSViewRecord)

    def total_dataset_views(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.model.query.filter_by(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_cookie=user_cookie
        ).first()

    def create_new_record(self, dataset: DataSet, user_cookie: str) -> DSViewRecord:
        return self.create(
                user_id=current_user.id if current_user.is_authenticated else None,
                dataset_id=dataset.id,
                view_date=datetime.now(timezone.utc),
                view_cookie=user_cookie,
            )


class DataSetRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DSMetaData.dataset_doi.isnot(None))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DSMetaData.dataset_doi.is_(None))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DataSet.id == dataset_id, DSMetaData.dataset_doi.is_(None))
            .first()
        )

    def count_synchronized_datasets(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .count()
        )

    def count_unsynchronized_datasets(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.is_(None))
            .count()
        )

    def latest_synchronized(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .order_by(desc(self.model.id))
            .limit(5)
            .all()
        )

    def get_all(self) -> list[DataSet]:
        return self.model.query.all()


class DOIMappingRepository(BaseRepository):
    def __init__(self):
        super().__init__(DOIMapping)

    def get_new_doi(self, old_doi: str) -> str:
        return self.model.query.filter_by(dataset_doi_old=old_doi).first()


class CommunityRepository:
    @staticmethod
    def get_all_communities():
        return Community.query.all()

    @staticmethod
    def get_community_by_id(community_id):
        return Community.query.get(community_id)

    @staticmethod
    def get_communities_by_member(current_user_id):
        return (
            Community.query
            .join(community_members, community_members.c.community_id == Community.id)
            .filter(community_members.c.user_id == current_user_id)
            .all()
        )

    @staticmethod
    def search_by_name(query):
        search = f"%{query}%"
        return Community.query.filter(Community.name.ilike(search)).all()

    @staticmethod
    def get_community_by_name(name):
        return Community.query.filter_by(name=name).first()

    @staticmethod
    def create_community(name, current_user) -> Community:
        owners_list = [current_user]
        new_community = Community(
            name=name,
            created_at=datetime.now(timezone.utc),
            owners=owners_list,
            members=owners_list,
            requests=[]
        )

        db.session.add(new_community)
        db.session.commit()
        return new_community

    @staticmethod
    def delete_community(community_id):
        community = Community.query.get(community_id)
        if community:
            db.session.delete(community)
            db.session.commit()

    @staticmethod
    def save_community():
        db.session.commit()

    @staticmethod
    def request_community(community_id, current_user):
        community = Community.query.get(community_id)
        if community:
            db.session.execute(
                community_request.insert().values(
                    community_id=community_id,
                    user_id=current_user.id
                )
            )
        db.session.commit()

    @staticmethod
    def add_member(community_id, user_id):
        community = Community.query.get(community_id)
        if community:
            user = User.query.get(user_id)
            if user and user not in community.members:
                community.members.append(user)
                db.session.commit()
                return True
        return False

    @staticmethod
    def remove_request(community_id, user_id):
        community = Community.query.get(community_id)
        if community:
            user = User.query.get(user_id)
            if user and user in community.requests:
                community.requests.remove(user)
                db.session.commit()
                return True
        return False
