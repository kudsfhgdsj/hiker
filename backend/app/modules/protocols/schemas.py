import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.core.fields import Name, optional_text

EntryId = Annotated[
    uuid.UUID | None,
    Field(description="Id of an existing entry, or an optional client-generated id for a new one"),
]
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


# --- Lists inside the tour document ---


class TourGearIn(BaseModel):
    id: EntryId = None
    gear_item_id: uuid.UUID | None = Field(
        default=None, description="Required for a new entry; must be a gear item of the caller"
    )
    quantity: int = Field(default=1, ge=1, le=999)
    carried: bool = Field(default=True, description="Counts towards the pack weight")


class TourGearOut(BaseModel):
    id: uuid.UUID
    gear_item_id: uuid.UUID | None
    name: str
    brand: str | None
    weight_g: int | None = Field(description="Weight of one piece when it was added (snapshot)")
    quantity: int
    carried: bool


class TourFoodIn(BaseModel):
    id: EntryId = None
    food_item_id: uuid.UUID | None = Field(
        default=None, description="Required for a new entry; own food or one from the catalog"
    )
    amount_g: float = Field(gt=0, le=100_000, allow_inf_nan=False)
    carried: bool = Field(default=True, description="Counts towards the pack weight")
    eaten: bool = Field(default=False, description="Counts towards the calories eaten")
    eaten_at: AwareDatetime | None = None


class TourFoodOut(BaseModel):
    id: uuid.UUID
    food_item_id: uuid.UUID | None
    name: str
    kcal_per_100g: float | None = Field(description="Value when the entry was added (snapshot)")
    amount_g: float
    kcal: float | None
    carried: bool
    eaten: bool
    eaten_at: datetime | None


class TourPeakIn(BaseModel):
    id: EntryId = None
    name: Name
    elevation_m: int | None = Field(default=None, ge=-500, le=9000)
    lat: Latitude | None = None
    lon: Longitude | None = None
    reached_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _position_is_complete(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must be given together")
        return self


class TourPeakOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    elevation_m: int | None
    lat: float | None
    lon: float | None
    reached_at: datetime | None


class TourPartnerIn(BaseModel):
    contact_id: uuid.UUID = Field(description="A new partner must be a contact of the caller")


class TourPartnerOut(BaseModel):
    contact_id: uuid.UUID
    display_name: str
    linked_user_id: uuid.UUID | None = Field(description="Set if the contact is a real user")


class PartnerSnapshot(BaseModel):
    id: uuid.UUID
    name: str


PositionSource = Literal["exif_gps", "exif_time", "manual", "none"]


class PhotoSnapshot(BaseModel):
    """Metadata of a photo in the history; `name` is its caption."""

    id: uuid.UUID
    name: str | None
    taken_at: datetime | None
    lat: float | None
    lon: float | None
    position_source: PositionSource
    track_distance_m: float | None
    elevation_m: float | None
    waypoint_id: uuid.UUID | None


class WeatherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sample_point: Literal["start", "summit", "end", "manual"]
    lat: float
    lon: float
    elevation_m: float | None
    time: datetime
    temperature_c: float | None
    apparent_temperature_c: float | None
    wind_speed_kmh: float | None
    wind_gusts_kmh: float | None
    precipitation_mm: float | None
    cloud_cover_pct: float | None
    freezing_level_m: float | None = Field(description="Only available from the forecast service")
    weather_code: int | None = Field(description="WMO weather code")
    source: str
    fetched_at: datetime


# --- Tour ---


class TourIn(BaseModel):
    """The editable tour document. PUT replaces it as a whole, including the lists."""

    title: Name
    summary: optional_text(20_000) = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    duration_minutes: int | None = Field(
        default=None, ge=0, le=100_000, description="Manual value; null = computed from the times"
    )
    pack_weight_start_g: int | None = Field(
        default=None, ge=0, le=200_000, description="Manual value; null = computed from the lists"
    )
    calories_burned: float | None = Field(
        default=None, ge=0, le=50_000, allow_inf_nan=False, description="Manual value"
    )
    gear: list[TourGearIn] = Field(default_factory=list, max_length=500)
    food: list[TourFoodIn] = Field(default_factory=list, max_length=500)
    peaks: list[TourPeakIn] = Field(default_factory=list, max_length=100)
    partners: list[TourPartnerIn] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _end_is_not_before_start(self):
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must not be before start_time")
        return self


class TourUpdate(TourIn):
    version: int = Field(
        description="Version the change is based on; an outdated one is answered with 409"
    )


class TourCreate(TourIn):
    id: uuid.UUID | None = Field(default=None, description="Optional id generated by the client")


class TourOwner(BaseModel):
    id: uuid.UUID
    display_name: str | None


class GeoPoint(BaseModel):
    lat: float
    lon: float
    name: str | None


class CaloriesEstimate(BaseModel):
    method: Literal["heart_rate", "acsm_walking"] | None = Field(
        description="heart_rate: Keytel et al. 2005; acsm_walking: ACSM walking equation"
    )
    reason: Literal["no_profile", "no_track", "no_duration"] | None = Field(
        description="Why no estimate is possible"
    )
    parameters: dict = Field(description="The values that went into the formula")


class TourComputed(BaseModel):
    """Values derived by the server; used wherever the manual value is empty."""

    duration_minutes: int | None = Field(description="From start_time and end_time")
    pack_weight_start_g: int = Field(description="Carried gear plus carried food")
    calories_eaten: float = Field(description="Sum of the eaten food entries")
    calories_burned: float | None = Field(
        default=None, description="Estimate; applies while no manual value is set"
    )


class TourBase(BaseModel):
    id: uuid.UUID
    owner: TourOwner
    permission: Literal["owner", "edit", "read"] = Field(description="Access of the caller")
    title: str
    start_time: datetime | None
    end_time: datetime | None
    cover_photo_id: uuid.UUID | None = Field(
        description="Load it from /tours/{id}/photos/{cover_photo_id}/image"
    )
    version: int
    created_at: datetime
    updated_at: datetime


class TourListItem(TourBase):
    peaks: list[str] = Field(description="Names of the peaks")


class TourOut(TourBase):
    summary: str | None
    duration_minutes: int | None
    pack_weight_start_g: int | None
    calories_burned: float | None = Field(description="Manual value; null = use the estimate")
    calories_burned_source: Literal["manual", "estimated"] | None = Field(
        description="Source of the value to show: the manual one or computed.calories_burned"
    )
    calories_estimate: CaloriesEstimate | None = Field(
        description="How the estimate was made, for the owner only (contains profile data)"
    )
    computed: TourComputed
    start_point: GeoPoint | None
    end_point: GeoPoint | None
    points_source: Literal["gpx", "manual"] | None
    track_source: Literal["device", "drawn", "none"]
    track_stats: dict | None = Field(
        description="Statistics of the track; heart rate only for the owner. See GET .../track"
    )
    photo_time_offset_seconds: int
    photo_count: int
    weather: list[WeatherOut]
    weather_outdated: bool = Field(
        description="Points or times changed since the weather was fetched; offer a new fetch"
    )
    gear: list[TourGearOut]
    food: list[TourFoodOut]
    peaks: list[TourPeakOut]
    partners: list[TourPartnerOut]


# --- Waypoints ---


class WaypointIn(BaseModel):
    id: uuid.UUID | None = Field(default=None, description="Optional id generated by the client")
    name: Name
    description: optional_text(5000) = None
    icon: optional_text(50) = None
    lat: Latitude
    lon: Longitude
    elevation_m: float | None = Field(default=None, ge=-500, le=9000, allow_inf_nan=False)


class WaypointPatch(BaseModel):
    name: Name | None = None
    description: optional_text(5000) = None
    icon: optional_text(50) = None
    lat: Latitude | None = None
    lon: Longitude | None = None
    elevation_m: float | None = Field(default=None, ge=-500, le=9000, allow_inf_nan=False)


class WaypointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    icon: str | None
    lat: float
    lon: float
    track_distance_m: float | None
    elevation_m: float | None


# --- History ---


class TourSnapshot(BaseModel):
    """The complete editable state of a tour at one version."""

    title: str
    summary: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_minutes: int | None
    pack_weight_start_g: int | None
    calories_burned: float | None
    calories_burned_source: Literal["manual", "estimated"] | None
    gear: list[TourGearOut]
    food: list[TourFoodOut]
    peaks: list[TourPeakOut]
    waypoints: list[WaypointOut]
    partners: list[PartnerSnapshot] = Field(default_factory=list)
    photos: list[PhotoSnapshot] = Field(default_factory=list)
    cover_photo_id: uuid.UUID | None = None
    photo_time_offset_seconds: int = 0
    track_source: Literal["device", "drawn", "none"] = "none"
    gpx_file_id: uuid.UUID | None = None
    points_source: Literal["gpx", "manual"] | None = None
    start_lat: float | None = None
    start_lon: float | None = None
    start_name: str | None = None
    end_lat: float | None = None
    end_lon: float | None = None
    end_name: str | None = None


class RevisionListItem(BaseModel):
    version: int
    kind: Literal["created", "updated", "restored", "deleted"]
    change_summary: str = Field(
        description="Changed fields, or the restored version for kind = restored"
    )
    author: TourOwner | None = Field(description="null if the user no longer exists")
    created_at: datetime


class RevisionOut(RevisionListItem):
    snapshot: TourSnapshot
    diff: dict = Field(
        description="Difference to the previous version: scalar fields as {old, new}, "
        "lists as {added, removed, changed, reordered}"
    )


class RevisionComparison(BaseModel):
    from_version: int
    to_version: int
    diff: dict


class VersionConflict(BaseModel):
    """Body of a 409 with code version_conflict."""

    error: dict
    current: TourOut


# --- Shares ---


class ShareIn(BaseModel):
    user_id: uuid.UUID = Field(description="Found with /users/lookup")
    permission: Literal["read", "edit"]


class SharePatch(BaseModel):
    permission: Literal["read", "edit"]


class ShareOut(BaseModel):
    user: TourOwner
    permission: Literal["read", "edit"]
    created_at: datetime


# --- Contacts ---

ContactName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ContactIn(BaseModel):
    id: uuid.UUID | None = Field(default=None, description="Optional id generated by the client")
    display_name: ContactName
    linked_user_id: uuid.UUID | None = Field(
        default=None, description="The real user behind the contact, found with /users/lookup"
    )


class ContactPatch(BaseModel):
    display_name: ContactName | None = None
    linked_user_id: uuid.UUID | None = Field(
        default=None, description="Set to link the placeholder to a user, null to unlink"
    )


class ContactOut(BaseModel):
    id: uuid.UUID
    display_name: str
    linked_user: TourOwner | None


# --- Public links ---


class PublicLinkIn(BaseModel):
    expires_at: AwareDatetime | None = Field(default=None, description="Empty = no expiry")
    hide_exact_start: bool = Field(
        default=False, description="Show start and end point only roughly (about 1 km)"
    )
    strip_photo_gps: bool = Field(default=False, description="Remove the position from photos")
    show_health_data: bool = Field(
        default=False, description="Show calories burned and heart rate; hidden by default"
    )


class PublicLinkOut(BaseModel):
    id: uuid.UUID
    url: str
    active: bool
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    hide_exact_start: bool
    strip_photo_gps: bool
    show_health_data: bool


class PublicPoint(BaseModel):
    lat: float
    lon: float
    name: str | None
    approximate: bool


class PublicGear(BaseModel):
    name: str
    brand: str | None
    weight_g: int | None
    quantity: int
    carried: bool


class PublicFood(BaseModel):
    name: str
    amount_g: float
    kcal: float | None
    carried: bool
    eaten: bool


class PublicPeak(BaseModel):
    name: str
    elevation_m: int | None
    lat: float | None
    lon: float | None
    reached_at: datetime | None


class PublicWaypoint(BaseModel):
    name: str
    description: str | None
    icon: str | None
    lat: float
    lon: float
    elevation_m: float | None


class PublicPhoto(BaseModel):
    index: int = Field(description="Load the image from /public/tours/{token}/photos/{index}")
    caption: str | None
    taken_at: datetime | None
    lat: float | None
    lon: float | None
    track_distance_m: float | None
    elevation_m: float | None
    is_cover: bool


class PublicTourOut(BaseModel):
    """What a public link shows: no ids, no e-mail addresses, health data only on request."""

    title: str
    summary: str | None
    owner_name: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_minutes: int | None
    pack_weight_start_g: int | None
    calories_eaten: float
    calories_burned: float | None = Field(description="Health data; null unless enabled")
    calories_burned_source: Literal["manual", "estimated"] | None
    start_point: PublicPoint | None
    end_point: PublicPoint | None
    track_source: Literal["device", "drawn", "none"]
    track_stats: dict | None
    photos: list[PublicPhoto]
    weather: list[WeatherOut]
    partners: list[str]
    peaks: list[PublicPeak]
    waypoints: list[PublicWaypoint]
    gear: list[PublicGear]
    food: list[PublicFood]


# --- Photos ---


class PhotoOut(BaseModel):
    id: uuid.UUID
    caption: str | None
    taken_at: datetime | None
    lat: float | None
    lon: float | None
    position_source: PositionSource
    track_distance_m: float | None = Field(description="Position along the track")
    elevation_m: float | None
    waypoint_id: uuid.UUID | None
    is_cover: bool


class PhotoPatch(BaseModel):
    """Only the given fields change. Set the position with lat/lon (map) or with
    track_distance_m (elevation profile); auto_position brings back the automatic one."""

    caption: optional_text(500) = None
    lat: Latitude | None = None
    lon: Longitude | None = None
    track_distance_m: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    auto_position: bool | None = None
    waypoint_id: uuid.UUID | None = None
    is_cover: bool | None = None

    @model_validator(mode="after")
    def _one_way_to_set_the_position(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must be given together")
        ways = [self.lat is not None, self.track_distance_m is not None, bool(self.auto_position)]
        if sum(ways) > 1:
            raise ValueError("use only one of lat/lon, track_distance_m and auto_position")
        return self


class PhotoTimeOffsetIn(BaseModel):
    seconds: int = Field(
        ge=-172_800,
        le=172_800,
        description="Added to the capture time of all photos, e.g. -7200 for a camera on CEST",
    )


# --- Export ---


class ExportedTour(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None
    owner_name: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_minutes: int | None = Field(description="Manual value, otherwise the computed one")
    pack_weight_start_g: int | None = Field(description="Manual value, otherwise the computed one")
    calories_eaten: float
    calories_burned: float | None = Field(description="Manual value, otherwise the estimate")
    calories_burned_source: Literal["manual", "estimated"] | None
    start_point: GeoPoint | None
    end_point: GeoPoint | None
    points_source: Literal["gpx", "manual"] | None
    version: int
    created_at: datetime
    updated_at: datetime


class ExportedTrack(BaseModel):
    source: Literal["device", "drawn", "none"]
    stats: dict | None
    file: str | None = Field(description="Name of the GPX file inside a ZIP export")


class TourExport(BaseModel):
    """Versioned export format; `schema_version` rises with every incompatible change."""

    schema_version: int
    exported_at: datetime
    tour: ExportedTour
    partners: list[str] = Field(description="Display names")
    peaks: list[TourPeakOut]
    waypoints: list[WaypointOut]
    gear: list[TourGearOut] = Field(description="Snapshots as stored in the tour")
    food: list[TourFoodOut]
    track: ExportedTrack
    weather: list[WeatherOut]
    photos: list[PhotoOut] = Field(description="Metadata; the images are not part of the JSON")


# --- Track ---


class DrawnPoint(BaseModel):
    lat: Latitude
    lon: Longitude
    elevation_m: float | None = Field(default=None, ge=-500, le=9000, allow_inf_nan=False)
    time: AwareDatetime | None = None


class DrawnTrackIn(BaseModel):
    points: list[DrawnPoint] = Field(min_length=2, max_length=5000)


class TrackSeriesOut(BaseModel):
    """Columns of equal length; a column is null if the track has no such values."""

    time: list[datetime | None] | None
    distance_m: list[float]
    lat: list[float]
    lon: list[float]
    elevation_m: list[float | None] | None
    heart_rate: list[int | None] | None = Field(description="Health data: owner only")
    cadence: list[int | None] | None
    temperature: list[float | None] | None


class TrackOut(BaseModel):
    source: Literal["device", "drawn", "none"]
    stats: dict | None = Field(
        description="distance_m, ascent_m, descent_m, min/max_elevation_m, start/end_time, "
        "total_time_s, moving_time_s, heart_rate (owner only), cadence, temperature, "
        "elevation_source"
    )
    series: TrackSeriesOut | None


# --- Points and weather ---


class PointIn(BaseModel):
    lat: Latitude
    lon: Longitude
    name: optional_text(200) = None


class PointsIn(BaseModel):
    """Start and end point. With a track the positions come from the track and only
    the names can be set; send the positions back unchanged."""

    start: PointIn | None = None
    end: PointIn | None = None


class ManualWeatherIn(BaseModel):
    lat: Latitude
    lon: Longitude
    time: AwareDatetime
    elevation_m: float | None = Field(default=None, ge=-500, le=9000, allow_inf_nan=False)


class WeatherFetchIn(BaseModel):
    manual: ManualWeatherIn | None = Field(
        default=None, description="An additional sample point chosen by the user"
    )
