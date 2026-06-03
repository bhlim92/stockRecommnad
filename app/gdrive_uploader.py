import os
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from app.utils.logger import setup_logger

logger = setup_logger("gdrive_uploader", "logs/app.log")

class GoogleDriveUploader:
    """
    Authenticates with Google Drive APIs using Service Account JSON configurations
    to archive reports.
    """

    def __init__(self, credentials_path: str = None, token_json_str: str = None) -> None:
        """
        Args:
            credentials_path: Local filesystem path to the service account credentials JSON.
            token_json_str: JSON string containing OAuth2 user credentials (token.json).
        """
        self.credentials_path = credentials_path
        self.token_json_str = token_json_str
        self.service = None

    def authenticate(self) -> None:
        """
        Creates and stores the authenticated Google API Drive Client.
        """
        scopes = ["https://www.googleapis.com/auth/drive"]

        # 1. Try User OAuth2 credentials from in-memory token string (Option 1)
        if self.token_json_str:
            logger.info("Authenticating with Google Drive using User OAuth2 Token...")
            try:
                import json
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request

                creds_info = json.loads(self.token_json_str)
                creds = Credentials.from_authorized_user_info(creds_info, scopes=scopes)

                # Auto refresh token if expired
                if creds and creds.expired and creds.refresh_token:
                    logger.info("User OAuth2 Token is expired, refreshing token...")
                    creds.refresh(Request())

                self.service = build("drive", "v3", credentials=creds)
                logger.info("Google Drive API client initialized successfully using User OAuth2 Token.")
                return
            except Exception as e:
                logger.error(f"User OAuth2 token authentication failed: {str(e)}")
                # If path exists, fallback to service account, otherwise raise error
                if not self.credentials_path:
                    raise e

        # 2. Try Service Account JSON file (Fallback / Backwards Compatibility)
        if self.credentials_path:
            logger.info(f"Authenticating with Google Drive using Service Account: {self.credentials_path}")
            if not os.path.exists(self.credentials_path):
                logger.error(f"Google credentials file not found at: {self.credentials_path}")
                raise FileNotFoundError(f"Service account credential JSON not found: {self.credentials_path}")

            try:
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=scopes
                )
                self.service = build("drive", "v3", credentials=creds)
                logger.info("Google Drive API client initialized successfully using Service Account.")
            except Exception as e:
                logger.error(f"Google Drive authentication failed: {str(e)}")
                raise e

    def create_folder_if_not_exists(self, folder_name: str) -> str:
        """
        Checks for a folder by name; creates it in root if not present.
        
        Returns:
            Folder ID.
        """
        if not self.service:
            raise RuntimeError("Google Drive client is not authenticated. Call authenticate() first.")

        logger.info(f"Checking existence of folder: '{folder_name}' in Google Drive")
        try:
            # Query for the folder
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(
                q=query, 
                spaces="drive", 
                fields="files(id, name)"
            ).execute()
            files = results.get("files", [])

            if files:
                folder_id = files[0]["id"]
                logger.info(f"Folder '{folder_name}' already exists with ID: {folder_id}")
                return folder_id
            else:
                # Create the folder
                file_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder"
                }
                file = self.service.files().create(body=file_metadata, fields="id").execute()
                folder_id = file.get("id")
                logger.info(f"Created new folder '{folder_name}' with ID: {folder_id}")
                return folder_id
        except Exception as e:
            logger.error(f"Failed to check or create folder '{folder_name}': {str(e)}")
            raise e

    def upload_markdown_file(self, local_path: str, filename: str, target_folder_name: str = "Stock_Reports", folder_id: str = None) -> str:
        """
        Uploads local Markdown text files directly into the target Drive folder, converting them to Google Docs.
        
        Args:
            local_path: Local filesystem path to the markdown report file.
            filename: Target file name on Google Drive.
            target_folder_name: Google Drive folder to upload into (fallback if folder_id is not set).
            folder_id: Google Drive folder ID to upload into (highly recommended for shared folders).
            
        Returns:
            Web view URL of the uploaded document.
        """
        if not self.service:
            raise RuntimeError("Google Drive client is not authenticated. Call authenticate() first.")

        logger.info(f"Preparing to upload {local_path} as Google Doc to folder ID '{folder_id}' or folder name '{target_folder_name}'")
        try:
            # Get folder ID
            if not folder_id:
                folder_id = self.create_folder_if_not_exists(target_folder_name)

            # Metadata to convert to Google Doc format
            doc_name = filename.replace(".md", "")
            file_metadata = {
                "name": doc_name,
                "mimeType": "application/vnd.google-apps.document", # Converts to Google Doc automatically
                "parents": [folder_id]
            }

            # Upload media body
            media = MediaFileUpload(local_path, mimetype="text/plain", resumable=True)

            # Create the file on Drive
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, webViewLink"
            ).execute()

            file_id = file.get("id")
            web_link = file.get("webViewLink")
            logger.info(f"File uploaded successfully. Doc ID: {file_id}. Link: {web_link}")
            return web_link
        except Exception as e:
            logger.error(f"Failed to upload file to Google Drive: {str(e)}")
            raise e

    def list_files_in_folder(self, folder_id: str) -> list[str]:
        """
        Lists all reports inside the specified Google Drive folder, appending '.md'
        to document names to match the expected format.
        """
        if not self.service:
            raise RuntimeError("Google Drive client is not authenticated.")

        logger.info(f"Listing files in Google Drive folder: {folder_id}")
        try:
            query = f"'{folder_id}' in parents and trashed = false"
            results = self.service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name, mimeType, createdTime)",
                orderBy="name desc"
            ).execute()
            files = results.get("files", [])
            
            filenames = []
            for f in files:
                name = f.get("name", "")
                if not name.endswith(".md"):
                    name += ".md"
                filenames.append(name)
            return filenames
        except Exception as e:
            logger.error(f"Failed to list files in Google Drive folder {folder_id}: {str(e)}")
            raise e

    def download_file_by_name(self, filename: str, folder_id: str) -> Optional[str]:
        """
        Downloads or exports the text content of a file from Google Drive by its filename.
        """
        if not self.service:
            raise RuntimeError("Google Drive client is not authenticated.")

        doc_name = filename.replace(".md", "")
        logger.info(f"Downloading file content for '{doc_name}' from folder: {folder_id}")
        try:
            query = f"name = '{doc_name}' and '{folder_id}' in parents and trashed = false"
            results = self.service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name, mimeType)"
            ).execute()
            files = results.get("files", [])

            if not files:
                logger.warning(f"File '{doc_name}' not found in Google Drive folder: {folder_id}")
                return None

            file_id = files[0]["id"]
            mime_type = files[0]["mimeType"]

            if mime_type == "application/vnd.google-apps.document":
                content = self.service.files().export(
                    fileId=file_id, 
                    mimeType="text/plain"
                ).execute().decode("utf-8")
            else:
                content = self.service.files().get_media(
                    fileId=file_id
                ).execute().decode("utf-8")

            return content
        except Exception as e:
            logger.error(f"Failed to download file '{filename}' from Google Drive: {str(e)}")
            raise e
