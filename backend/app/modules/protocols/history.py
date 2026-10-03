"""Change history of tours.

Every change of a tour, including its lists and waypoints, must be finished
with `record_change`, so that the revision counter stays reliable.
"""

from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.auth.models import User
from app.modules.protocols.models import Tour


def record_change(db: Session, tour: Tour, author: User, summary: str) -> None:
    """Raise the version of the tour and commit the pending changes."""
    tour.version += 1
    tour.updated_at = utcnow()
    db.commit()
