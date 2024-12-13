from app.modules.fakenodo.models import Fakenodo
from app.modules.fakenodo.models import Deposition
from core.repositories.BaseRepository import BaseRepository


class FakenodoRepository(BaseRepository):
    def __init__(self):
        super().__init__(Fakenodo)


class DepositionRepository(BaseRepository):
    def __init__(self):
        super().__init__(Deposition)

    def create_deposition(self, metadata):
        return self.create(deposition_metadata=metadata)
