"""Stored files (`file_object`): the database row plus the object in the storage.

Access control is the job of the module that owns the reference to a file.
"""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Uuid
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, UTCDateTime, utcnow
from app.core.errors import NotFoundError
from app.core.storage import Storage


class FileObject(Base):
    __tablename__ = "file_object"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # A user id; no foreign key, because core does not know the auth module.
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


def store_file(
    db: Session, storage: Storage, *, owner_id: uuid.UUID, data: bytes, mime: str, extension: str
) -> FileObject:
    """Write the data to the storage and add the row to the session (not committed)."""
    file_id = uuid.uuid4()
    file = FileObject(
        id=file_id,
        owner_id=owner_id,
        storage_key=f"{file_id.hex[:2]}/{file_id.hex}.{extension}",
        mime=mime,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    storage.save(file.storage_key, data)
    db.add(file)
    db.flush()
    return file


def load_file(db: Session, storage: Storage, file_id: uuid.UUID | None) -> tuple[FileObject, bytes]:
    file = db.get(FileObject, file_id) if file_id else None
    if file is None or not storage.exists(file.storage_key):
        raise NotFoundError("File not found")
    return file, storage.read(file.storage_key)


def copy_file(
    db: Session, storage: Storage, file_id: uuid.UUID | None, *, owner_id: uuid.UUID
) -> FileObject | None:
    """Duplicate a file for another record; returns None if the source is missing."""
    try:
        source, data = load_file(db, storage, file_id)
    except NotFoundError:
        return None
    extension = source.storage_key.rsplit(".", 1)[-1]
    return store_file(
        db, storage, owner_id=owner_id, data=data, mime=source.mime, extension=extension
    )


def delete_file(db: Session, storage: Storage, file_id: uuid.UUID | None) -> None:
    """Delete the row (committed) and then the stored object."""
    file = db.get(FileObject, file_id) if file_id else None
    if file is None:
        return
    key = file.storage_key
    db.delete(file)
    db.commit()
    storage.delete(key)
