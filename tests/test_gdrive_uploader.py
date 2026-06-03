import pytest
import os
from unittest.mock import MagicMock, patch
from app.gdrive_uploader import GoogleDriveUploader

@patch("app.gdrive_uploader.service_account.Credentials.from_service_account_file")
@patch("app.gdrive_uploader.build")
def test_authenticate(mock_build, mock_creds, tmp_path):
    cred_file = tmp_path / "creds.json"
    cred_file.write_text("{}")
    
    uploader = GoogleDriveUploader(str(cred_file))
    uploader.authenticate()
    
    assert uploader.service is not None
    mock_creds.assert_called_once_with(str(cred_file), scopes=["https://www.googleapis.com/auth/drive"])
    mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds.return_value)

@patch("app.gdrive_uploader.service_account.Credentials.from_service_account_file")
@patch("app.gdrive_uploader.build")
def test_create_folder_if_not_exists_finds_folder(mock_build, mock_creds, tmp_path):
    cred_file = tmp_path / "creds.json"
    cred_file.write_text("{}")
    
    # Mocking Google Drive list service call returning existing folder
    mock_service = MagicMock()
    mock_service.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "folder-123", "name": "Stock_Reports"}]
    }
    mock_build.return_value = mock_service
    
    uploader = GoogleDriveUploader(str(cred_file))
    uploader.authenticate()
    
    folder_id = uploader.create_folder_if_not_exists("Stock_Reports")
    assert folder_id == "folder-123"
    mock_service.files.return_value.create.assert_not_called()

@patch("app.gdrive_uploader.service_account.Credentials.from_service_account_file")
@patch("app.gdrive_uploader.build")
def test_create_folder_if_not_exists_creates_folder(mock_build, mock_creds, tmp_path):
    cred_file = tmp_path / "creds.json"
    cred_file.write_text("{}")
    
    # Mocking Google Drive list returns no folder, create returns new folder id
    mock_service = MagicMock()
    mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}
    mock_service.files.return_value.create.return_value.execute.return_value = {"id": "new-folder-456"}
    mock_build.return_value = mock_service
    
    uploader = GoogleDriveUploader(str(cred_file))
    uploader.authenticate()
    
    folder_id = uploader.create_folder_if_not_exists("Stock_Reports")
    assert folder_id == "new-folder-456"
    mock_service.files.return_value.create.assert_called_once_with(
        body={"name": "Stock_Reports", "mimeType": "application/vnd.google-apps.folder"},
        fields="id"
    )
