import os.path
import time
import io
import click
import subprocess
import platform


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


LOG_FILES = True
LOG_FOLDERS = True
LOG_TRANSFER = True
LOG_FOLDER_CREATION = True


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive"]

def authorize(userString, port):
    creds = None
    tokenName = f"token_{userString}.json"

    if os.path.exists(tokenName):
        creds = Credentials.from_authorized_user_file(tokenName, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=port)
            with open(tokenName, "w") as token:
                token.write(creds.to_json())  # save the credentials for the next run

    return creds
     

def convertSizeToBiggerUnit(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"
      

def listFiles(service, parentFolder, fileAmount=1000):
    try:
        results = (
            service.files()
            .list(pageSize=fileAmount, fields="nextPageToken, files(id, name, size)", q=f"'{parentFolder}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false")
            .execute()
        )
        items = results.get("files", [])

        if not items:
            print("No files found.")
            return
        if LOG_FILES:
            print(f"Files from {parentFolder}:")
            for item in items:
                print(f"{item['name']} ({item['id']}) - {convertSizeToBiggerUnit(int(item['size']))}")
        return items
    except HttpError as error:
        # TODO(developer) - Handle errors from drive API.
        print(f"An error occurred: {error}")


def fileExistsInDrive(service, filename, folder_path):
    results = (
        service.files()
        .list(q=f"name='{filename}' and '{folder_path}' in parents and trashed = false", fields="files(id, name)")
        .execute()
    )
    items = results.get("files", [])
    if items:
        return True
    else:
        return False

def fileExistsLocally(filePath):
    return os.path.exists(filePath)


def getFoldersFromFolder(service, folder_id):
    results = (
        service.files()
        .list(q=f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false", fields="files(id, name)")
        .execute()
    )
    items = results.get("files", [])
    if items:
        if LOG_FOLDERS:
            print(f"Folders from {folder_id}:")
            for item in items:
                print(f"{item['name']} ({item['id']})")
        return items
    else:
        return None

# transfer a file from one drive to another
def transferFile(serviceOrigin, serviceTarget, filename, originFolderId, targetFolderId, copy=True):
    try:
        # Get the file ID of the file in the origin drive
        origin_file_id = None
        origin_file_mimetype = None
        origin_file_size = None
        results = (
            serviceOrigin.files()
            .list(q=f"name='{filename}' and '{originFolderId}' in parents", fields="files(id, mimeType, size)")
            .execute()
        )
        items = results.get("files", [])
        if items:
            origin_file_id = items[0]["id"]
            origin_file_mimetype = items[0]["mimeType"]
            origin_file_size = int(items[0]["size"])
        else:
            if LOG_TRANSFER: print(f"File '{filename}' not found in the origin drive.")
            return

        # check if a file with the same name exists in the target folder
        if fileExistsInDrive(serviceTarget, filename, targetFolderId):
            if LOG_TRANSFER: print(f"File '{filename}' already exists in the target folder.")
            return

        # check if the file is already downloaded, if so, delete the local file and download it again
        localFilePath = f"temp/{filename}"
        if fileExistsLocally(localFilePath):
            if LOG_TRANSFER: print(f"File '{filename}' already exists in the temp folder.")
            deleteFile(localFilePath)

        # Download the file from the origin drive
        request = serviceOrigin.files().get_media(fileId=origin_file_id)
        with open(localFilePath, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            with click.progressbar(length=origin_file_size, label=f"Downloading '{filename}'") as pbar:
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        pbar.update(int(status.resumable_progress))
                        # if status is 100%, the file has been downloaded
                        if LOG_TRANSFER and status.progress() == 1:
                            print(f"File '{filename}' has been downloaded, starting local transfer.")
        if LOG_TRANSFER: print(f"File '{filename}' has been saved.")

        # Create the file in the target drive
        file_metadata = {
            "name": filename,
            "parents": [targetFolderId],
        }
        media = MediaFileUpload(localFilePath, mimetype=origin_file_mimetype, chunksize=256*1024, resumable=True)
        request = serviceTarget.files().create(body=file_metadata, media_body=media, fields='id')
       
        # Upload the file in chunks
        response = None
        with click.progressbar(length=origin_file_size, label=f"uploading '{filename}'") as pbar:
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pbar.update(int(status.progress() * origin_file_size))
                    if LOG_TRANSFER and status.progress() == 1:
                        print(f"File '{filename}' has been uploaded.")

        # Explicitly close and clean up
        del downloader

        # Delete the file from the temp folder
        deleteFile(localFilePath)
    except HttpError as error:
        # TODO: Handle errors from drive API.
        print(f"An error occurred: {error}")
    

def find_locking_process(file_path):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for file in proc.open_files():
                if file.path == file_path:
                    print(f"Process '{proc.name()}' (PID: {proc.pid}) is locking the file.")
                    return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    print("No locking process found.")
    return None

def deleteFile(filePath):
    if os.path.exists(filePath):
        while os.path.exists(filePath):
            try:
                if platform.system() == 'Windows':
                    # Use del command for Windows
                    subprocess.run(['del', f".\{filePath}"], check=True, shell=True)
                else:
                    # Use rm command for Unix-based systems
                    subprocess.run(['rm', '-f', filePath], check=True)
                if LOG_TRANSFER: print(f"File '{filePath}' has been deleted.")
            except PermissionError:
                print(f"Permission error while trying to delete '{filePath}'.")
                time.sleep(1)
        if LOG_TRANSFER: print(f"File '{filePath}' has been deleted.")
    else:
        if LOG_TRANSFER: print(f"File '{filePath}' does not exist.")

# create a folder in the service drive
# returns the folder ID
def createFolder(service, folder_name, parent_folder_id): 
    if fileExistsInDrive(service, folder_name, parent_folder_id):
        if LOG_FOLDER_CREATION: print(f"Folder '{folder_name}' already exists in the target folder.")
        return service.files().list(q=f"name='{folder_name}' and '{parent_folder_id}' in parents and trashed = false", fields="files(id)").execute().get("files")[0].get("id")
    file_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    file = service.files().create(body=file_metadata, fields="id").execute()
    if LOG_FOLDER_CREATION: print(f"Folder '{folder_name}' created with ID: {file.get('id')} inside {parent_folder_id}")
    return file.get("id")


def runFolderFiles(serviceOrigin, serviceTarget, originFolderId, targetSubfolderId):
    print (f"----- Starting folder {originFolderId}")
    items = listFiles(serviceOrigin, originFolderId)
    folders = getFoldersFromFolder(serviceOrigin, originFolderId)

    # iterate over files and transfer them
    if items is not None:
        for item in items:
            transferFile(serviceOrigin, serviceTarget, item["name"], originFolderId, targetSubfolderId)

    # iterate over folders and get the files inside them
    if folders is not None:
        for folder in folders:
            newFolderId = createFolder(serviceTarget, folder["name"], targetSubfolderId)
            runFolderFiles(serviceOrigin, serviceTarget, folder["id"], newFolderId)
    print (f"----- Finished folder {originFolderId}")
    items = None
    folders = None


def main():
    credsOrigin = authorize('origin', 52772)
    serviceOrigin = build("drive", "v3", credentials=credsOrigin)

    time.sleep(5)

    credsTarget = authorize('target', 52773)
    serviceTarget = build("drive", "v3", credentials=credsTarget)

    originFolderId = "1OR8P-vsEFSjXLcoEyedZWvVAksjJi1SK"
    targetFolderId = "1L0UJtP-WcYwyeLTzd9H8rcztcNYk5h9E"

    print("Starting transfer...")
    runFolderFiles(serviceOrigin, serviceTarget, originFolderId, targetFolderId)
    

if __name__ == "__main__":
    main()
