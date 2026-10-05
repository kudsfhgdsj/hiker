import uuid
from io import BytesIO

import pytest
from PIL import Image

from app.core import files
from app.core.errors import NotFoundError, UnprocessableError
from app.core.images import reencode_image
from app.core.storage.local_fs import LocalFsStorage
from app.tests.conftest import make_image


def test_local_storage_round_trip(tmp_path):
    storage = LocalFsStorage(tmp_path)

    storage.save("ab/abcdef.jpg", b"data")

    assert storage.exists("ab/abcdef.jpg")
    assert storage.read("ab/abcdef.jpg") == b"data"
    storage.delete("ab/abcdef.jpg")
    storage.delete("ab/abcdef.jpg")
    assert not storage.exists("ab/abcdef.jpg")


@pytest.mark.parametrize("key", ["../secret", "/etc/passwd", "a/../../b", "a//b", "", "A.jpg"])
def test_local_storage_rejects_keys_outside_its_root(tmp_path, key):
    storage = LocalFsStorage(tmp_path / "files")

    with pytest.raises(ValueError):
        storage.save(key, b"data")


def test_store_load_copy_and_delete_file(db, storage):
    owner, other = uuid.uuid4(), uuid.uuid4()

    stored = files.store_file(
        db, storage, owner_id=owner, data=b"abc", mime="image/jpeg", extension="jpg"
    )
    db.commit()
    copy = files.copy_file(db, storage, stored.id, owner_id=other)
    db.commit()

    assert stored.size == 3
    assert stored.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert files.load_file(db, storage, stored.id)[1] == b"abc"
    assert copy.id != stored.id and copy.storage_key != stored.storage_key
    assert copy.owner_id == other

    files.delete_file(db, storage, stored.id)

    assert not storage.exists(stored.storage_key)
    with pytest.raises(NotFoundError):
        files.load_file(db, storage, stored.id)
    assert files.load_file(db, storage, copy.id)[1] == b"abc"
    assert files.copy_file(db, storage, stored.id, owner_id=other) is None


def test_reencode_scales_down_and_strips_metadata():
    original = make_image(size=(1200, 600), exif_gps=True)
    assert Image.open(BytesIO(original)).getexif().get_ifd(0x8825)

    data, mime = reencode_image(original, max_edge=400)

    image = Image.open(BytesIO(data))
    assert mime == "image/jpeg"
    assert image.format == "JPEG"
    assert image.size == (400, 200)
    assert len(image.getexif()) == 0


def test_reencode_flattens_transparency_and_keeps_small_images():
    data, _ = reencode_image(
        make_image(size=(50, 40), image_format="PNG", mode="RGBA"), max_edge=400
    )

    image = Image.open(BytesIO(data))
    assert image.mode == "RGB"
    assert image.size == (50, 40)


@pytest.mark.parametrize(
    "data",
    [b"", b"not an image", b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"\xff\xd8\xff\xe0broken"],
)
def test_reencode_rejects_non_images(data):
    with pytest.raises(UnprocessableError):
        reencode_image(data, max_edge=400)


def test_reencode_rejects_unsupported_format():
    with pytest.raises(UnprocessableError):
        reencode_image(make_image(image_format="GIF", mode="P"), max_edge=400)
