"""Google Drive backup storage provider implementing BaseBackupStorage.

Uses OAuth 2.0 Desktop Application flow with scoped access to drive.file.
Supports configurable target folder routing via GDRIVE_FOLDER_ID in .env.
"""

from datetime import datetime, timezone
import io
import os
from pathlib import Path
from typing import Any, List, Optional, Union

import dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from arc_life_diary.backup import is_valid_backup_filename
from arc_life_diary.interfaces import BaseBackupStorage, RemoteBackupMetadata

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveAuthError(Exception):
    """Raised when authentication fails or required credentials are missing."""
    pass


class GoogleDriveStorage(BaseBackupStorage):
    """Storage provider for uploading and downloading backups using Google Drive v3 API."""

    def __init__(
        self,
        credentials_path: Union[str, Path] = "credentials.json",
        token_path: Union[str, Path] = "token.json",
        env_path: Union[str, Path] = ".env",
        drive_service: Optional[Any] = None,
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.env_path = Path(env_path)

        env_vars = dotenv.dotenv_values(self.env_path) if self.env_path.is_file() else {}
        folder_id = env_vars.get("GDRIVE_FOLDER_ID", os.environ.get("GDRIVE_FOLDER_ID", "")).strip()
        self.folder_id: Optional[str] = folder_id if folder_id else None

        self._service = drive_service

    @property
    def service(self):
        """Lazy-loaded, authenticated Google Drive service instance."""
        if self._service is None:
            self._service = self._authenticate()
        return self._service

    def _authenticate(self):
        """Authenticates user via OAuth 2.0 Desktop flow and returns Drive service."""
        creds: Optional[Credentials] = None

        if self.token_path.is_file():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds or not creds.valid:
                if not self.credentials_path.is_file():
                    raise GoogleDriveAuthError(
                        f"Google Drive OAuth credentials file '{self.credentials_path}' not found. "
                        "Please download OAuth 2.0 Desktop credentials from Google Cloud Console "
                        "and place them at the project root."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json())

        return build("drive", "v3", credentials=creds)

    def upload(self, local_path: Path, remote_filename: str) -> RemoteBackupMetadata:
        """Uploads an encrypted archive file to the destination Google Drive folder."""
        file_metadata = {
            "name": remote_filename,
            "parents": [self.folder_id] if self.folder_id else ["root"],
            "description": "arc-life-diary encrypted backup",
        }

        media = MediaFileUpload(
            str(local_path),
            mimetype="application/x-7z-compressed",
            resumable=True,
        )

        created = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id, name, createdTime, size",
            )
            .execute()
        )

        created_time = created.get("createdTime")
        created_at = datetime.fromisoformat(created_time) if created_time else datetime.now(timezone.utc)
        size_bytes = int(created.get("size", local_path.stat().st_size))

        return RemoteBackupMetadata(
            file_id=created["id"],
            name=created["name"],
            created_at=created_at,
            size_bytes=size_bytes,
        )

    def list_backups(self) -> List[RemoteBackupMetadata]:
        """Lists available backup archives on Google Drive, sorted newest first."""
        query_parts = [
            "name contains 'arc-life-diary_backup_'",
            "mimeType != 'application/vnd.google-apps.folder'",
            "trashed = false",
        ]
        if self.folder_id:
            query_parts.append(f"'{self.folder_id}' in parents")

        results = (
            self.service.files()
            .list(
                q=" and ".join(query_parts),
                fields="files(id, name, createdTime, size)",
                orderBy="createdTime desc",
                pageSize=100,
            )
            .execute()
        )

        backups: List[RemoteBackupMetadata] = []
        for f in results.get("files", []):
            name = f.get("name", "")
            if is_valid_backup_filename(name):
                created_time = f.get("createdTime")
                created_at = datetime.fromisoformat(created_time) if created_time else datetime.now(timezone.utc)
                backups.append(
                    RemoteBackupMetadata(
                        file_id=f["id"],
                        name=name,
                        created_at=created_at,
                        size_bytes=int(f.get("size", 0)),
                    )
                )

        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def download(self, file_id: str, destination_path: Path) -> Path:
        """Downloads a remote backup archive by ID to a local destination path."""
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        request = self.service.files().get_media(fileId=file_id)
        with io.FileIO(destination_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return destination_path
