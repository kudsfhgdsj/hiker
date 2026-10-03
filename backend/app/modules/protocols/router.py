import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from pydantic import AwareDatetime

from app.core.config import get_settings
from app.core.deps import DbSession, FileStorage
from app.core.errors import PayloadTooLargeError, error_responses
from app.core.pagination import Page, Paging
from app.core.ratelimit import rate_limit
from app.modules.auth.deps import CurrentUser
from app.modules.protocols import (
    contacts,
    export,
    history,
    photos,
    public,
    service,
    sharing,
    track_service,
)
from app.modules.protocols.elevation import Elevations
from app.modules.protocols.schemas import (
    ContactIn,
    ContactOut,
    ContactPatch,
    DrawnTrackIn,
    PhotoOut,
    PhotoPatch,
    PhotoTimeOffsetIn,
    PublicLinkIn,
    PublicLinkOut,
    PublicTourOut,
    RevisionComparison,
    RevisionListItem,
    RevisionOut,
    ShareIn,
    ShareOut,
    SharePatch,
    TourCreate,
    TourExport,
    TourListItem,
    TourOut,
    TourUpdate,
    TrackOut,
    VersionConflict,
    WaypointIn,
    WaypointOut,
    WaypointPatch,
)
from app.modules.protocols.sharing import (
    OWNER,
    EditableTour,
    OwnedTour,
    ReadableTour,
    TourAccess,
)

router = APIRouter(responses=error_responses(401))
# Routes that work without login.
public_router = APIRouter()


@router.get("/tours", response_model=Page[TourListItem])
def list_tours(
    user: CurrentUser,
    db: DbSession,
    paging: Paging,
    scope: Annotated[
        Literal["all", "mine", "shared"], Query(description="Own tours, tours shared with me")
    ] = "all",
    q: Annotated[
        str | None, Query(max_length=100, description="Search in title and summary")
    ] = None,
    start_from: Annotated[AwareDatetime | None, Query(description="start_time not before")] = None,
    start_to: Annotated[AwareDatetime | None, Query(description="start_time not after")] = None,
):
    items, total = service.list_tours(
        db,
        user,
        scope=scope,
        q=q,
        start_from=start_from,
        start_to=start_to,
        limit=paging.limit,
        offset=paging.offset,
    )
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.post(
    "/tours",
    response_model=TourOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_tour(body: TourCreate, user: CurrentUser, db: DbSession):
    tour = service.create_tour(db, user, body)
    return service.tour_out(db, TourAccess(tour=tour, user=user, permission=OWNER))


@router.get("/tours/{tour_id}", response_model=TourOut, responses=error_responses(404))
def read_tour(access: ReadableTour, db: DbSession):
    return service.tour_out(db, access)


@router.put(
    "/tours/{tour_id}",
    response_model=TourOut,
    responses={**error_responses(403, 404), 409: {"model": VersionConflict}},
)
def update_tour(body: TourUpdate, access: EditableTour, db: DbSession):
    """Replace the tour document including its lists.

    `version` must be the version the change is based on. If the tour was changed
    in the meantime the answer is 409 `version_conflict` with the current tour, so
    that the client can merge field by field and try again.

    With `edit` permission the owner-only fields (times, duration, pack weight,
    calories burned) must be sent back unchanged.
    """
    service.update_tour(db, access, body)
    return service.tour_out(db, access)


@router.delete(
    "/tours/{tour_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_tour(access: OwnedTour, db: DbSession, storage: FileStorage):
    service.delete_tour(db, storage, access)


@router.get("/tours/{tour_id}/export", response_model=TourExport, responses=error_responses(404))
def export_tour(access: ReadableTour, response: Response, db: DbSession):
    """The tour as a JSON document in a versioned format, offered as a download."""
    filename = export.export_filename(access.tour.title)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return export.export_tour(db, access)


# --- Track ---


@router.put(
    "/tours/{tour_id}/gpx", response_model=TourOut, responses=error_responses(403, 404, 413)
)
def upload_gpx(
    file: UploadFile, access: OwnedTour, db: DbSession, storage: FileStorage, elevations: Elevations
):
    """Upload a GPX file (multipart field `file`) and evaluate it. Owner only.

    The file is stored unchanged. Missing time, elevation or heart rate is no error.
    Start and end point and, if the track has time stamps, the times of the tour follow
    the track.
    """
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError(f"File is larger than {get_settings().max_upload_mb} MB")
    track_service.upload_gpx(db, storage, elevations, access, data)
    return service.tour_out(db, access)


@router.get(
    "/tours/{tour_id}/gpx",
    response_class=Response,
    responses={200: {"content": {"application/gpx+xml": {}}}, **error_responses(403, 404)},
)
def download_gpx(access: OwnedTour, db: DbSession, storage: FileStorage):
    """The GPX file as stored. Owner only, because it can contain heart rate data."""
    data = track_service.gpx_file(db, storage, access.tour)
    filename = export.export_filename(access.tour.title).removesuffix(".json") + ".gpx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=data, media_type=track_service.GPX_MIME, headers=headers)


@router.post(
    "/tours/{tour_id}/track/drawn", response_model=TourOut, responses=error_responses(403, 404)
)
def save_drawn_track(
    body: DrawnTrackIn,
    access: OwnedTour,
    db: DbSession,
    storage: FileStorage,
    elevations: Elevations,
):
    """Save a track drawn on the map as GPX. Missing elevations are looked up. Owner only."""
    track_service.save_drawn_track(db, storage, elevations, access, body)
    return service.tour_out(db, access)


@router.get("/tours/{tour_id}/track", response_model=TrackOut, responses=error_responses(404))
def read_track(access: ReadableTour, db: DbSession):
    """Statistics and series for the map and the charts. Heart rate only for the owner."""
    return track_service.track_out(db, access.tour, health=access.is_owner)


@router.delete(
    "/tours/{tour_id}/track", response_model=TourOut, responses=error_responses(403, 404)
)
def remove_track(access: OwnedTour, db: DbSession):
    """Remove the track from the tour. Owner only."""
    track_service.remove_track(db, access)
    return service.tour_out(db, access)


# --- Photos ---

IMAGE_RESPONSE = {200: {"content": {"image/jpeg": {}}}}
ImageSize = Annotated[Literal["full", "thumb"], Query(description="thumb: at most 400 px")]


def _image_response(file, data: bytes) -> Response:
    headers = {"Cache-Control": "private, max-age=86400", "ETag": f'"{file.sha256}"'}
    return Response(content=data, media_type=file.mime, headers=headers)


def _read_upload(upload: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError(f"File is larger than {get_settings().max_upload_mb} MB")
    return data


@router.get(
    "/tours/{tour_id}/photos", response_model=list[PhotoOut], responses=error_responses(404)
)
def list_photos(access: ReadableTour):
    """Photos in gallery order: along the track, photos without position at the end."""
    return photos.photos_out(access.tour)


@router.post(
    "/tours/{tour_id}/photos",
    response_model=list[PhotoOut],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 404, 409, 413),
)
def upload_photos(
    files: list[UploadFile], access: EditableTour, db: DbSession, storage: FileStorage
):
    """Upload photos (multipart, field `files`, several at once).

    EXIF capture time and GPS are read and the photo is matched to the track. The
    images are re-encoded and stored without EXIF data. One bad file rejects the upload.
    """
    added = photos.add_photos(db, storage, access, [_read_upload(file) for file in files])
    return [photos.photo_out(access.tour, photo) for photo in added]


@router.put(
    "/tours/{tour_id}/photos/time-offset",
    response_model=list[PhotoOut],
    responses=error_responses(403, 404),
)
def set_photo_time_offset(body: PhotoTimeOffsetIn, access: EditableTour, db: DbSession):
    """Correct the camera clock for all photos of the tour and match them to the track again."""
    photos.set_time_offset(db, access, body.seconds)
    return photos.photos_out(access.tour)


@router.patch(
    "/tours/{tour_id}/photos/{photo_id}",
    response_model=PhotoOut,
    responses=error_responses(403, 404),
)
def update_photo(photo_id: uuid.UUID, body: PhotoPatch, access: EditableTour, db: DbSession):
    """Change caption, position, waypoint or make the photo the cover of the tour."""
    photo = photos.get_photo(access.tour, photo_id)
    photos.update_photo(db, access, photo, body)
    return photos.photo_out(access.tour, photo)


@router.delete(
    "/tours/{tour_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_photo(photo_id: uuid.UUID, access: EditableTour, db: DbSession, storage: FileStorage):
    photos.delete_photo(db, storage, access, photos.get_photo(access.tour, photo_id))


@router.get(
    "/tours/{tour_id}/photos/{photo_id}/image",
    response_class=Response,
    responses={**IMAGE_RESPONSE, **error_responses(404)},
)
def read_photo_image(
    photo_id: uuid.UUID,
    access: ReadableTour,
    db: DbSession,
    storage: FileStorage,
    size: ImageSize = "full",
):
    photo = photos.get_photo(access.tour, photo_id)
    return _image_response(*photos.image(db, storage, photo, size))


@router.post(
    "/tours/{tour_id}/waypoints/from-photos",
    response_model=list[WaypointOut],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 404),
)
def waypoints_from_photos(access: EditableTour, db: DbSession):
    """Create waypoints from photos with GPS; photos close together share a waypoint."""
    return photos.waypoints_from_photos(db, access)


# --- Waypoints ---


@router.get(
    "/tours/{tour_id}/waypoints", response_model=list[WaypointOut], responses=error_responses(404)
)
def list_waypoints(access: ReadableTour):
    return access.tour.waypoints


@router.post(
    "/tours/{tour_id}/waypoints",
    response_model=WaypointOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 404, 409),
)
def create_waypoint(body: WaypointIn, access: EditableTour, db: DbSession):
    return service.create_waypoint(db, access, body)


@router.patch(
    "/tours/{tour_id}/waypoints/{waypoint_id}",
    response_model=WaypointOut,
    responses=error_responses(403, 404),
)
def update_waypoint(
    waypoint_id: uuid.UUID, body: WaypointPatch, access: EditableTour, db: DbSession
):
    waypoint = service.get_waypoint(access, waypoint_id)
    return service.update_waypoint(db, access, waypoint, body)


@router.delete(
    "/tours/{tour_id}/waypoints/{waypoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_waypoint(waypoint_id: uuid.UUID, access: EditableTour, db: DbSession):
    service.delete_waypoint(db, access, service.get_waypoint(access, waypoint_id))


# --- History ---


@router.get(
    "/tours/{tour_id}/revisions",
    response_model=Page[RevisionListItem],
    responses=error_responses(404),
)
def list_revisions(access: ReadableTour, db: DbSession, paging: Paging):
    """The change history, newest first."""
    revisions, total = history.list_revisions(
        db, access.tour, limit=paging.limit, offset=paging.offset
    )
    items = service.revision_items(db, revisions, RevisionListItem)
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.get(
    "/tours/{tour_id}/revisions/{version}",
    response_model=RevisionOut,
    responses=error_responses(404),
)
def read_revision(version: int, access: ReadableTour, db: DbSession):
    """One revision with the full state of the tour and the diff to its predecessor."""
    revision = history.get_revision(db, access.tour, version)
    return service.revision_items(db, [revision], RevisionOut)[0]


@router.get(
    "/tours/{tour_id}/revisions/{version}/compare/{other_version}",
    response_model=RevisionComparison,
    responses=error_responses(404),
)
def compare_revisions(version: int, other_version: int, access: ReadableTour, db: DbSession):
    """Difference between two versions (from `version` to `other_version`)."""
    old = history.get_revision(db, access.tour, version)
    new = history.get_revision(db, access.tour, other_version)
    return RevisionComparison(
        from_version=version,
        to_version=other_version,
        diff=history.diff_snapshots(old.snapshot, new.snapshot),
    )


@router.post(
    "/tours/{tour_id}/revisions/{version}/restore",
    response_model=TourOut,
    responses=error_responses(403, 404),
)
def restore_revision(version: int, access: EditableTour, db: DbSession, storage: FileStorage):
    """Bring the tour back to an earlier state. The history grows by one revision.

    With `edit` permission this only works if the owner-only fields stay as they are.
    """
    history.restore(db, storage, access, history.get_revision(db, access.tour, version))
    return service.tour_out(db, access)


# --- Shares ---


@router.get(
    "/tours/{tour_id}/shares", response_model=list[ShareOut], responses=error_responses(403, 404)
)
def list_shares(access: OwnedTour, db: DbSession):
    return sharing.list_shares(db, access.tour)


@router.post(
    "/tours/{tour_id}/shares",
    response_model=ShareOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 404, 409),
)
def create_share(body: ShareIn, access: OwnedTour, db: DbSession):
    """Share the tour with another user (`read` or `edit`)."""
    return sharing.create_share(db, access.tour, body.user_id, body.permission)


@router.patch(
    "/tours/{tour_id}/shares/{user_id}",
    response_model=ShareOut,
    responses=error_responses(403, 404),
)
def update_share(user_id: uuid.UUID, body: SharePatch, access: OwnedTour, db: DbSession):
    return sharing.update_share(db, access.tour, user_id, body.permission)


@router.delete(
    "/tours/{tour_id}/shares/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_share(user_id: uuid.UUID, access: ReadableTour, db: DbSession):
    """Remove a share. The owner removes any, other users only their own."""
    sharing.require_owner_or_self(access, user_id)
    sharing.delete_share(db, access.tour, user_id)


# --- Contacts ---


@router.get("/contacts", response_model=list[ContactOut], tags=["contacts"])
def list_contacts(user: CurrentUser, db: DbSession):
    """The caller's tour partners."""
    return contacts.contacts_out(db, contacts.list_contacts(db, user))


@router.post(
    "/contacts",
    response_model=ContactOut,
    status_code=status.HTTP_201_CREATED,
    tags=["contacts"],
    responses=error_responses(409),
)
def create_contact(body: ContactIn, user: CurrentUser, db: DbSession):
    return contacts.contacts_out(db, [contacts.create_contact(db, user, body)])[0]


@router.patch(
    "/contacts/{contact_id}",
    response_model=ContactOut,
    tags=["contacts"],
    responses=error_responses(404),
)
def update_contact(contact_id: uuid.UUID, body: ContactPatch, user: CurrentUser, db: DbSession):
    """Rename a contact or link the placeholder to a real user (null unlinks)."""
    contact = contacts.get_owned_contact(db, user, contact_id)
    return contacts.contacts_out(db, [contacts.update_contact(db, contact, body)])[0]


@router.delete(
    "/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["contacts"],
    responses=error_responses(404),
)
def delete_contact(contact_id: uuid.UUID, user: CurrentUser, db: DbSession):
    contacts.delete_contact(db, contacts.get_owned_contact(db, user, contact_id))


# --- Public links ---


@router.get(
    "/tours/{tour_id}/public-link",
    response_model=list[PublicLinkOut],
    responses=error_responses(403, 404),
)
def list_public_links(access: OwnedTour, db: DbSession):
    return [public.link_out(link) for link in public.list_links(db, access.tour)]


@router.post(
    "/tours/{tour_id}/public-link",
    response_model=PublicLinkOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 404),
)
def create_public_link(body: PublicLinkIn, access: OwnedTour, db: DbSession):
    """Create a read-only link that works without login until it expires or is revoked."""
    return public.link_out(public.create_link(db, access.tour, access.user, body))


@router.delete(
    "/tours/{tour_id}/public-link/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def revoke_public_link(link_id: uuid.UUID, access: OwnedTour, db: DbSession):
    public.revoke_link(db, access.tour, link_id)


@public_router.get(
    "/public/tours/{token}",
    response_model=PublicTourOut,
    responses=error_responses(404, 429),
    dependencies=[Depends(rate_limit("public", limit=60))],
)
def read_public_tour(token: str, response: Response, db: DbSession):
    """The tour behind a public link. No login; not to be indexed or cached."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return public.public_tour(db, token)


@public_router.get(
    "/public/tours/{token}/track",
    response_model=TrackOut,
    responses=error_responses(404, 429),
    dependencies=[Depends(rate_limit("public", limit=60))],
)
def read_public_track(token: str, response: Response, db: DbSession):
    """Track of a publicly linked tour; shortened at both ends if the start is hidden."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "no-store"
    return public.public_track(db, token)


@public_router.get(
    "/public/tours/{token}/photos/{index}",
    response_class=Response,
    responses={**IMAGE_RESPONSE, **error_responses(404, 429)},
    dependencies=[Depends(rate_limit("public-image", limit=600))],
)
def read_public_photo(
    token: str, index: int, db: DbSession, storage: FileStorage, size: ImageSize = "full"
):
    """An image of a publicly linked tour, addressed by its position in the gallery."""
    file, data = public.public_photo_image(db, storage, token, index, size)
    headers = {"X-Robots-Tag": "noindex, nofollow", "Cache-Control": "private, max-age=3600"}
    return Response(content=data, media_type=file.mime, headers=headers)
