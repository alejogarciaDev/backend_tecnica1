import boto3
from botocore.client import Config
from fastapi import UploadFile
import uuid
import os

# Cloudflare R2 Credentials (Hardcoded temporarily as requested, usually put in .env)
R2_ACCESS_KEY_ID = "cf2155736e91f5fadc0bddcb6336c578"
R2_SECRET_ACCESS_KEY = "5672e994e6fcf8bf3344bd15fbdad7b87dce8801cc3ba1982bbbc23f779e2121"
R2_ACCOUNT_ID = "c1caf6d7883a99e1bddf770297519873"
R2_BUCKET_NAME = "tecnica-prueba"

R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
# Public URL if configured in Cloudflare (Optional, for direct download)
# R2_PUBLIC_URL = f"https://pub-xxxx.r2.dev"

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

def upload_file_to_r2(school_prefix: str, user_email: str, file: UploadFile, folder_name: str = "general"):
    """
    Uploads a file to Cloudflare R2.
    Path structure: {school_prefix}/drive/{user_email}/{folder_name}/{filename}
    """
    ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"
    
    # Clean up folder name
    safe_folder = folder_name.replace(" ", "_").replace("/", "")
    safe_email = user_email.replace("@", "_at_")
    
    object_key = f"{school_prefix}/drive/{safe_email}/{safe_folder}/{file.filename}"
    
    # Upload
    s3.upload_fileobj(
        file.file,
        R2_BUCKET_NAME,
        object_key,
        ExtraArgs={"ContentType": file.content_type}
    )
    
    # Return S3 URL (Pre-signed URL for downloading later)
    return object_key

def get_presigned_url(object_key: str, expiration=3600):
    """Generate a presigned URL to share an S3 object"""
    response = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': R2_BUCKET_NAME, 'Key': object_key},
        ExpiresIn=expiration
    )
    return response

def list_user_files(school_prefix: str, user_email: str):
    """
    List all files in the user's drive directory.
    Returns a list of folders containing files.
    """
    safe_email = user_email.replace("@", "_at_")
    prefix = f"{school_prefix}/drive/{safe_email}/"
    
    response = s3.list_objects_v2(Bucket=R2_BUCKET_NAME, Prefix=prefix)
    
    folders = {}
    if "Contents" in response:
        for obj in response["Contents"]:
            key = obj["Key"]
            # key: tecnica1/drive/user_email/Folder_Name/file.pdf
            parts = key.replace(prefix, "").split("/")
            if len(parts) >= 2:
                folder_name = parts[0]
                file_name = parts[1]
                if folder_name not in folders:
                    folders[folder_name] = {"name": folder_name, "files": [], "shared_with": []}
                download_url = get_presigned_url(key)
                folders[folder_name]["files"].append({"name": file_name, "url": download_url, "key": key})
                
    return list(folders.values())
