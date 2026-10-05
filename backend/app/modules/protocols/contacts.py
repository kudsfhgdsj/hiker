"""Contacts: the tour partners of a user.

A contact starts as a placeholder name and can later be linked to a real user;
the link then applies to all tours that list the contact.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.modules.auth import service as auth_service
from app.modules.auth.models import User
from app.modules.protocols.models import Contact
from app.modules.protocols.schemas import ContactIn, ContactOut, ContactPatch, TourOwner


def contacts_out(db: Session, contacts: list[Contact]) -> list[ContactOut]:
    names = auth_service.get_display_names(db, {c.linked_user_id for c in contacts} - {None})
    result = []
    for contact in contacts:
        linked = None
        if contact.linked_user_id in names:
            linked = TourOwner(
                id=contact.linked_user_id, display_name=names[contact.linked_user_id]
            )
        result.append(
            ContactOut(id=contact.id, display_name=contact.display_name, linked_user=linked)
        )
    return result


def get_usable_contact(db: Session, user: User, contact_id: uuid.UUID) -> Contact | None:
    contact = db.get(Contact, contact_id)
    if contact is None or contact.owner_id != user.id or contact.deleted_at is not None:
        return None
    return contact


def get_owned_contact(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    contact = get_usable_contact(db, user, contact_id)
    if contact is None:
        raise NotFoundError("Contact not found")
    return contact


def list_contacts(db: Session, user: User) -> list[Contact]:
    query = select(Contact).where(Contact.owner_id == user.id, Contact.deleted_at.is_(None))
    return list(db.scalars(query.order_by(func.lower(Contact.display_name), Contact.id)))


def _check_linked_user(db: Session, user_id: uuid.UUID | None) -> None:
    if user_id is not None and user_id not in auth_service.get_display_names(db, {user_id}):
        raise UnprocessableError("Unknown user", code="unknown_user")


def create_contact(db: Session, user: User, data: ContactIn) -> Contact:
    if data.id is not None and db.get(Contact, data.id) is not None:
        raise ConflictError("A contact with this id already exists", code="id_taken")
    _check_linked_user(db, data.linked_user_id)
    contact = Contact(owner_id=user.id, **data.model_dump(exclude_none=True))
    db.add(contact)
    db.commit()
    return contact


def update_contact(db: Session, contact: Contact, data: ContactPatch) -> Contact:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("display_name", "") is None:
        raise UnprocessableError("display_name cannot be empty")
    _check_linked_user(db, changes.get("linked_user_id"))
    for field, value in changes.items():
        setattr(contact, field, value)
    db.commit()
    return contact


def delete_contact(db: Session, contact: Contact) -> None:
    """Soft delete: tours that list the contact keep showing its name."""
    contact.deleted_at = utcnow()
    db.commit()
