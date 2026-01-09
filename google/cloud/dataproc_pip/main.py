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

import sys
import urllib.parse

from . import gcs_adapter

# Monkeypatching of `is_url` must happen before the rest of pip is imported.
# This is to ensure that any module that imports `is_url` gets the
# patched version.
try:
    from pip._internal.vcs import versioncontrol
    from pip._internal import vcs
except ImportError as e:
    raise RuntimeError(gcs_adapter.import_failed_msg(e))


_old_is_url = versioncontrol.is_url


def new_is_url(name: str) -> bool:
    if _old_is_url(name):
        return True
    scheme = urllib.parse.urlsplit(name).scheme
    return scheme == "gs"


# Patch in both the source module and the `vcs` namespace.
versioncontrol.is_url = new_is_url
vcs.is_url = new_is_url


# Now that the patch is in place, we can import the rest of pip.
try:
    from pip._internal.cli import main as pip_main
    from pip._internal.network.session import PipSession
except ImportError as e:
    raise RuntimeError(gcs_adapter.import_failed_msg(e))


from google.cloud.dataproc_pip.gcs_adapter import GCSAdapter

# Monkeypatch PipSession to support gs:// URLs
original_init = PipSession.__init__


def new_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.mount("gs://", GCSAdapter())


PipSession.__init__ = new_init


def main():
    """A wrapper for pip's main function that adds GCS support."""
    sys.exit(pip_main.main())


if __name__ == "__main__":
    main()
