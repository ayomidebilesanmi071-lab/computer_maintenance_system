"""Secure handling of *optional* fault-report attachments.

Attachments are never required by CMIMS.  When an ICT officer chooses to attach
a screenshot or a PDF to a fault report, this service is the only place that
touches the filesystem, and it enforces every rule in one spot:

* an **allowlist** of extensions (never a blocklist),
* the Werkzeug-cleaned base name plus a random UUID stem, so a hostile file
  name (``../../evil.exe``) cannot escape the upload directory,
* the upload directory is created with the application and files are stored
  *outside* the static asset tree, so a stored file can never be executed or
  served directly by the web server,
* the request body size is capped by ``MAX_CONTENT_LENGTH`` in the config.
"""

import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from services.errors import ValidationError


class AttachmentService:
    """Store and validate optional uploaded files."""

    @staticmethod
    def allowed(filename: str) -> bool:
        """Is ``filename``'s extension on the configured allowlist?"""
        if not filename or "." not in filename:
            return False
        extension = filename.rsplit(".", 1)[1].lower()
        return extension in current_app.config["ALLOWED_ATTACHMENT_EXTENSIONS"]

    @classmethod
    def save(cls, file_storage):
        """Persist an uploaded file and return the stored file name.

        Returns ``None`` when no file was supplied.  Raises
        :class:`ValidationError` when the file is not acceptable.
        """
        if file_storage is None or not getattr(file_storage, "filename", ""):
            return None

        original = file_storage.filename
        if not cls.allowed(original):
            allowed = ", ".join(sorted(current_app.config["ALLOWED_ATTACHMENT_EXTENSIONS"]))
            raise ValidationError(
                "That file type is not permitted. Allowed types: " + allowed,
                {"attachment": "Unsupported file type."},
            )

        extension = original.rsplit(".", 1)[1].lower()
        safe_stem = secure_filename(original.rsplit(".", 1)[0])[:60] or "attachment"
        stored_name = f"{safe_stem}-{uuid.uuid4().hex[:12]}.{extension}"

        folder = Path(current_app.config["UPLOAD_FOLDER"])
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / stored_name
        file_storage.save(destination)
        return stored_name

    @staticmethod
    def delete(stored_name: str) -> None:
        """Remove a previously stored attachment (best effort)."""
        if not stored_name:
            return
        path = Path(current_app.config["UPLOAD_FOLDER"]) / os.path.basename(stored_name)
        try:
            path.unlink()
        except OSError:
            pass
