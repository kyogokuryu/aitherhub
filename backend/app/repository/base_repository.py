from contextlib import AbstractContextManager
from typing import Callable, Generic, TypeVar

from sqlalchemy.orm import Session

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository class for common CRUD operations"""

    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]], model: type[T]):
        self.session_factory = session_factory
        self.model = model

    def create(self, obj: T) -> T:
        """Create a new record"""
        with self.session_factory() as session:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj

    def read_by_id(self, obj_id) -> T | None:
        """Read a record by ID"""
        with self.session_factory() as session:
            return session.query(self.model).filter(self.model.id == obj_id).first()

    def read_by_options(self, options) -> dict:
        """Read records by filter options"""
        with self.session_factory() as session:
            query = session.query(self.model)
            # This is a placeholder - subclasses should override for specific filtering
            return {"founds": query.all()}

    def update(self, obj: T) -> T:
        """Update a record"""
        with self.session_factory() as session:
            session.merge(obj)
            session.commit()
            return obj

    def delete(self, obj_id) -> bool:
        """Delete a record"""
        with self.session_factory() as session:
            obj = session.query(self.model).filter(self.model.id == obj_id).first()
            if obj:
                session.delete(obj)
                session.commit()
                return True
            return False
