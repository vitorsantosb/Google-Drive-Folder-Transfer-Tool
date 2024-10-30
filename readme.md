# Google Drive Folder Transfer Tool

This tool allows you to transfer files and folders from one Google Drive account to another, preserving folder structure. It is particularly useful for migrating data or creating backups between accounts.

## Requirements

- Python 3.x
- Google Client Library (`google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client`)
- `click` (for progress bar display)
- Google OAuth credentials (`credentials.json`)
- `psutil` library (optional, only needed if you want to use `find_locking_process` function on files)

## Installation

1. Install the necessary libraries:
   ```bash
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client click psutil
   ```

2. Obtain Google OAuth credentials:

  Go to Google Cloud Console, create a project, and enable Google Drive API.
  Download the OAuth 2.0 credentials as credentials.json and place it in the project directory.

## Project Structure

`authorize(userString, port)`: Authenticates with Google Drive API and manages user-specific token storage.

`convertSizeToBiggerUnit(size)`: Converts file size into human-readable units.
  listFiles(service, parentFolder, fileAmount=1000): Lists files in a specified Google Drive folder.

`fileExistsInDrive(service, filename, folder_path)`: Checks if a file exists in a specified Google Drive folder.

`getFoldersFromFolder(service, folder_id)`: Retrieves all subfolders from a specified folder in Google Drive.

`transferFile(serviceOrigin, serviceTarget, filename, originFolderId, targetFolderId, copy=True)`: Transfers files between Google Drive accounts.
  createFolder(service, folder_name, parent_folder_id): Creates a folder in Google Drive if it doesn’t exist.

`runFolderFiles(serviceOrigin, serviceTarget, originFolderId, targetSubfolderId)`: Recursively transfers files and folders, maintaining folder structure.

`main()`: Initializes services and starts the transfer process from origin to target.

Usage

    Update folder IDs in main() for both originFolderId and targetFolderId.
    Run the script:

    bash

    python <script_name>.py

Optional Log Settings

    LOG_FILES: Log file listing.
    LOG_FOLDERS: Log folder listing.
    LOG_TRANSFER: Log file transfer actions.
    LOG_FOLDER_CREATION: Log folder creation actions.

License

This project is licensed under the MIT License. EOF
