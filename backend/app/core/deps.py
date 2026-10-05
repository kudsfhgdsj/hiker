from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session_factory
from app.core.storage import Storage, get_storage


def get_db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
FileStorage = Annotated[Storage, Depends(get_storage)]
