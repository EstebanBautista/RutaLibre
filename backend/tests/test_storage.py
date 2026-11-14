import boto3
import pytest
from moto import mock_aws

from core import storage
from core.storage import ObjectInfo, StorageError

BUCKET = "rutalibre-test"
FULL = {
    "endpoint_url": "",  # moto intercepts the default AWS endpoint
    "region": "us-east-1",
    "bucket": BUCKET,
    "access_key_id": "testing",
    "secret_access_key": "testing",
}


@pytest.fixture
def bucket(settings):
    """A mocked S3 with an empty bucket, and settings pointing at it."""
    with mock_aws():
        settings.S3 = dict(FULL)
        client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        client.create_bucket(Bucket=BUCKET)
        # Backblaze buckets always keep versions; mimic that.
        client.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        storage._client.cache_clear()
        yield client
        storage._client.cache_clear()


def test_is_configured_needs_every_value(settings):
    complete = {**FULL, "endpoint_url": "https://s3.example.com"}
    settings.S3 = dict(complete)
    assert storage.is_configured() is True

    for field in complete:
        settings.S3 = {**complete, field: ""}
        assert storage.is_configured() is False, field


def test_presigned_put_is_signed_and_expires_in_five_minutes(bucket):
    url = storage.presigned_put("a/b.jpg", size=100)

    assert "a/b.jpg" in url
    assert "X-Amz-Expires=300" in url
    assert "X-Amz-Signature=" in url


def test_presigned_put_signs_the_exact_size(bucket):
    """The size is part of the signature: a bigger body is rejected by the bucket."""
    url = storage.presigned_put("a/b.jpg", size=100)

    signed_headers = url.split("X-Amz-SignedHeaders=")[1].split("&")[0]
    assert "content-length" in signed_headers


def all_versions(client, prefix=""):
    page = client.list_object_versions(Bucket=BUCKET, Prefix=prefix)
    return page.get("Versions", []) + page.get("DeleteMarkers", [])


def test_copy_duplicates_an_object(bucket):
    bucket.put_object(Bucket=BUCKET, Key="tmp/a.jpg", Body=b"0123456789", ContentType="image/jpeg")

    storage.copy("tmp/a.jpg", "final/a.jpg")

    assert storage.head("final/a.jpg") == ObjectInfo(size=10, content_type="image/jpeg")


def test_delete_removes_every_version_and_frees_the_space(bucket):
    bucket.put_object(Bucket=BUCKET, Key="x.jpg", Body=b"1")
    bucket.put_object(Bucket=BUCKET, Key="x.jpg", Body=b"22")

    storage.delete("x.jpg")

    assert all_versions(bucket, "x.jpg") == []


def test_delete_leaves_objects_with_a_longer_key_alone(bucket):
    bucket.put_object(Bucket=BUCKET, Key="x.jpg", Body=b"1")
    bucket.put_object(Bucket=BUCKET, Key="x.jpg.bak", Body=b"1")

    storage.delete("x.jpg")

    assert [v["Key"] for v in all_versions(bucket)] == ["x.jpg.bak"]


def test_delete_prefix_removes_every_version(bucket):
    bucket.put_object(Bucket=BUCKET, Key="businesses/1/a.jpg", Body=b"1")
    bucket.put_object(Bucket=BUCKET, Key="businesses/1/a.jpg", Body=b"2")
    bucket.delete_object(Bucket=BUCKET, Key="businesses/1/a.jpg")  # leaves a delete marker

    storage.delete_prefix("businesses/1/")

    assert all_versions(bucket, "businesses/1/") == []


def test_presigned_get_expires_in_one_hour(bucket):
    url = storage.presigned_get("a/b.jpg")

    assert "X-Amz-Expires=3600" in url


def test_head_of_a_missing_object_is_none(bucket):
    assert storage.head("nope.jpg") is None


def test_head_reports_size_and_content_type(bucket):
    bucket.put_object(Bucket=BUCKET, Key="x.jpg", Body=b"0123456789", ContentType="image/jpeg")

    assert storage.head("x.jpg") == ObjectInfo(size=10, content_type="image/jpeg")


def test_delete_of_a_missing_object_does_not_raise(bucket):
    storage.delete("nope.jpg")


def test_delete_removes_the_object(bucket):
    bucket.put_object(Bucket=BUCKET, Key="x.jpg", Body=b"1")

    storage.delete("x.jpg")

    assert storage.head("x.jpg") is None


def test_delete_prefix_only_removes_that_prefix(bucket):
    for i in range(3):
        bucket.put_object(Bucket=BUCKET, Key=f"businesses/1/{i}.jpg", Body=b"1")
    bucket.put_object(Bucket=BUCKET, Key="businesses/2/x.jpg", Body=b"1")

    assert storage.delete_prefix("businesses/1/") == 3

    remaining = [o["Key"] for o in bucket.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert remaining == ["businesses/2/x.jpg"]


def test_delete_prefix_with_nothing_to_delete_returns_zero(bucket):
    assert storage.delete_prefix("businesses/9/") == 0


def test_delete_prefix_handles_more_than_one_page(bucket):
    for i in range(1005):
        bucket.put_object(Bucket=BUCKET, Key=f"businesses/1/{i}.jpg", Body=b"1")

    assert storage.delete_prefix("businesses/1/") == 1005
    assert "Contents" not in bucket.list_objects_v2(Bucket=BUCKET)


def test_a_missing_bucket_raises_storage_error(bucket, settings):
    settings.S3 = dict(FULL, bucket="does-not-exist")
    storage._client.cache_clear()

    with pytest.raises(StorageError):
        storage.head("x.jpg")


def test_calls_without_configuration_raise_storage_error(settings):
    settings.S3 = {k: "" for k in FULL}
    storage._client.cache_clear()

    with pytest.raises(StorageError):
        storage.presigned_put("x.jpg", size=1)
