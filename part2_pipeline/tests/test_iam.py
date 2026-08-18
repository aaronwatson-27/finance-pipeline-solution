"""Verify least privilege on the finance_analyst role against real AWS.

LocalStack's free tier does not enforce IAM policies, so these assertions are
meaningless there. Marked `aws`; skipped when AWS credentials are absent.
"""

import os

import boto3
import pytest
from botocore.exceptions import ClientError

pytestmark = pytest.mark.aws

AWS_ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID")
BUCKET_PREFIX = os.environ.get("AWS_TEST_BUCKET_PREFIX", "aaron-fdp-")
PROFILE = os.environ.get("AWS_PROFILE_REAL", "finance-platform-aws")
REGION = "ap-southeast-2"


# Retrieve credentials after assuming finance analyst role
@pytest.fixture(scope="module")
def analyst_s3():
    """An S3 client holding temporary credentials for the finance_analyst role."""
    if not AWS_ACCOUNT_ID:
        pytest.skip("AWS_ACCOUNT_ID not set — copy .env.example to .env and fill it in")

    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    creds = session.client("sts").assume_role(
        RoleArn=f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/finance_analyst",
        RoleSessionName="pytest-least-privilege",
    )["Credentials"]

    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


# Confirm analyst role can list objects in the curated bucket
def test_analyst_can_list_curated(analyst_s3):
    """The analyst role is granted ListBucket on the curated layer."""
    analyst_s3.list_objects_v2(Bucket=f"{BUCKET_PREFIX}finance-data-curated")


# Confirm analyst role cannot list objects in the landing bucket
def test_analyst_cannot_list_landing(analyst_s3):
    """The analyst role has no grant on the landing layer, so access is denied."""
    with pytest.raises(ClientError) as exc:
        analyst_s3.list_objects_v2(Bucket=f"{BUCKET_PREFIX}finance-data-landing")

    assert exc.value.response["Error"]["Code"] == "AccessDenied"


# Confirm analyst role cannot write objects to the curated bucket
def test_analyst_cannot_write_to_curated(analyst_s3):
    """Read-only means read-only: PutObject is denied even on the granted bucket."""
    with pytest.raises(ClientError) as exc:
        analyst_s3.put_object(
            Bucket=f"{BUCKET_PREFIX}finance-data-curated",
            Key="_pytest_should_not_exist.txt",
            Body=b"",
        )

    assert exc.value.response["Error"]["Code"] == "AccessDenied"
