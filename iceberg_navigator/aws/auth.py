import boto3
from botocore.exceptions import ProfileNotFound

def get_boto3_session(profile_name=None, region_name=None):
    session_args = {}
    if profile_name:
        session_args["profile_name"] = profile_name
    if region_name:
        session_args["region_name"] = region_name

    try:
        session = boto3.Session(**session_args)
        return session
    except ProfileNotFound as e:
        raise RuntimeError(f"AWS profile '{profile_name}' Not Found: {e}")

def get_s3_client(profile_name=None, region_name=None):
    session = get_boto3_session(profile_name, region_name)
    return session.client("s3")

def get_glue_client(profile_name=None, region_name=None):
    session = get_boto3_session(profile_name, region_name)
    return session.client("glue")
