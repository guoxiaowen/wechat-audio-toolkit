"""OSS upload + signed URL + delete."""
import os

import oss2


class OSSClient:
    def __init__(self):
        key_id = os.environ["OSS_ACCESS_KEY_ID"]
        key_secret = os.environ["OSS_ACCESS_KEY_SECRET"]
        endpoint = os.environ["OSS_ENDPOINT"]
        bucket_name = os.environ["OSS_BUCKET"]
        # Normalize endpoint: accept both "oss-cn-beijing.aliyuncs.com" and "https://..."
        if not endpoint.startswith("http"):
            endpoint = f"https://{endpoint}"
        auth = oss2.Auth(key_id, key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name)

    def upload_and_sign(self, local_path, object_key, ttl=3600):
        """Upload local_path to object_key, return a signed GET URL valid for ttl seconds."""
        self.bucket.put_object_from_file(object_key, local_path)
        return self.bucket.sign_url("GET", object_key, ttl, slash_safe=True)

    def delete(self, object_key):
        self.bucket.delete_object(object_key)
