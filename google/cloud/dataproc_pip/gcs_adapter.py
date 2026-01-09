# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import email.utils
import io
import urllib.parse
from collections.abc import Mapping
from typing import Any, Optional, Union

from google.cloud import storage


def import_failed_msg(msg: Any) -> str:
    return (
        "Failed to import pip internals, maybe due to version incompatibility: "
        + msg
    )


try:
    from pip._vendor.requests import adapters
    from pip._vendor.requests import models
    from pip._vendor.requests import structures
except ImportError as e:
    raise RuntimeError(import_failed_msg(e))


class GCSAdapter(adapters.BaseAdapter):

    def send(
        self,
        request: models.PreparedRequest,
        stream: bool = False,
        timeout: Optional[Union[float, tuple[float, float]]] = None,
        verify: Union[bool, str] = True,
        cert: Optional[Union[str, tuple[str, str]]] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> models.Response:
        parsed = urllib.parse.urlparse(request.url)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")

        resp = models.Response()
        resp.url = request.url

        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.get_blob(blob_name)

            if blob is None:
                resp.status_code = 404
                resp.reason = "Not Found"
                err = f"gs://{bucket_name}/{blob_name} not found"
                resp.raw = io.BytesIO(err.encode("utf8"))
            else:
                resp.status_code = 200
                resp.reason = "OK"
                headers = {
                    "Content-Type": blob.content_type
                    or "application/octet-stream",
                }
                if blob.size is not None:
                    headers["Content-Length"] = str(blob.size)
                if blob.updated:
                    headers["Last-Modified"] = email.utils.formatdate(
                        blob.updated.timestamp(), usegmt=True
                    )
                resp.headers = structures.CaseInsensitiveDict(headers)

                if hasattr(blob, "open"):
                    resp.raw = blob.open("rb")
                else:
                    # TODO: stream large blobs
                    resp.raw = io.BytesIO(blob.download_as_bytes())

                resp.close = resp.raw.close

        except Exception as exc:
            # TODO: return 401/403/etc if necessary
            resp.status_code = 500
            resp.reason = "Internal Server Error"
            resp.raw = io.BytesIO(f"GCS Error: {exc}".encode("utf8"))
            resp.close = resp.raw.close

        return resp

    def close(self) -> None:
        pass
