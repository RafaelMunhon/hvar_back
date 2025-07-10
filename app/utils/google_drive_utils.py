import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO
import io
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s'
)

class GoogleDriveClient:
    """Utility class for Google Drive operations"""
    
    def __init__(self, credentials_path=None, credentials_dict=None):
        """
        Initialize Google Drive client with either a credentials file path or a credentials dictionary.
        
        Args:
            credentials_path (str, optional): Path to service account credentials JSON file
            credentials_dict (dict, optional): Dictionary containing service account credentials
        """
        try:
            if credentials_dict:
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            elif credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            else:
                raise ValueError("Either credentials_path or credentials_dict must be provided")
            
            self.drive_service = build('drive', 'v3', credentials=credentials)
            self.docs_service = build('docs', 'v1', credentials=credentials)
            logging.info("✅ Google Drive client initialized successfully")
        except Exception as e:
            logging.error(f"❌ Failed to initialize Google Drive client: {str(e)}")
            raise
    
    def create_folder(self, folder_name, parent_folder_id=None):
        """
        Create a folder in Google Drive
        
        Args:
            folder_name (str): Name of the folder to create
            parent_folder_id (str, optional): ID of the parent folder
            
        Returns:
            str: ID of the created folder
        """
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            
            folder = self.drive_service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logging.info(f"✅ Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        except Exception as e:
            logging.error(f"❌ Failed to create folder '{folder_name}': {str(e)}")
            raise
    
    def find_file_by_name(self, file_name, folder_id=None):
        """
        Find a file by name in a specific folder
        
        Args:
            file_name (str): The name of the file to find
            folder_id (str, optional): The ID of the folder to search in
            
        Returns:
            str or None: The file ID if found, None otherwise
        """
        try:
            query = f"name='{file_name}' and trashed=false"
            
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error finding file: {str(e)}")
            raise

    def create_document(self, title, content, folder_id=None):
        """
        Create a Google Document with the provided content. If a document with the same name exists,
        it will be updated instead of creating a new one.
        
        Args:
            title (str): The title of the document
            content (str or bytes): The content to add to the document
            folder_id (str, optional): The ID of the folder to save the document in
            
        Returns:
            str: The ID of the created or updated document
        """
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Check if document already exists
                existing_file_id = self.find_file_by_name(title, folder_id)
                
                if existing_file_id:
                    # If file exists, update it
                    file = self.drive_service.files().get(fileId=existing_file_id).execute()
                    
                    # Create media body
                    if isinstance(content, str):
                        media = MediaIoBaseUpload(
                            io.BytesIO(content.encode('utf-8')),
                            mimetype='text/plain',
                            resumable=True
                        )
                    else:  # content is already bytes
                        media = MediaIoBaseUpload(
                            io.BytesIO(content),
                            mimetype='application/pdf',
                            resumable=True
                        )
                    
                    # Update the file content
                    file = self.drive_service.files().update(
                        fileId=existing_file_id,
                        media_body=media
                    ).execute()
                    
                    # Verify update was successful
                    updated_file = self.drive_service.files().get(fileId=existing_file_id).execute()
                    if updated_file:
                        logging.info(f"✓ Updated existing Google Document with ID: {existing_file_id}")
                        return existing_file_id
                    else:
                        raise Exception("File update verification failed")
                
                # If file doesn't exist, create new one
                file_metadata = {
                    'name': title,
                    'mimeType': 'application/pdf'  # Changed to PDF mime type
                }
                
                # If folder_id is provided, add it to parents
                if folder_id:
                    file_metadata['parents'] = [folder_id]
                
                # Handle both string and bytes content
                if isinstance(content, str):
                    media = MediaIoBaseUpload(
                        io.BytesIO(content.encode('utf-8')),
                        mimetype='text/plain',
                        resumable=True
                    )
                else:  # content is already bytes
                    media = MediaIoBaseUpload(
                        io.BytesIO(content),
                        mimetype='application/pdf',
                        resumable=True
                    )
                
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                
                document_id = file.get('id')
                
                # Verify creation was successful
                created_file = self.drive_service.files().get(fileId=document_id).execute()
                if created_file:
                    logging.info(f"✓ Created new Google Document with ID: {document_id}")
                    return document_id
                else:
                    raise Exception("File creation verification failed")
                    
            except Exception as e:
                last_error = str(e)
                logging.error(f"❌ Attempt {attempt + 1} failed: {last_error}")
                if attempt < max_retries - 1:
                    logging.info(f"Retrying... ({attempt + 2}/{max_retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise Exception(f"Failed to create/update document after {max_retries} attempts. Last error: {last_error}")
                    
        raise Exception(f"Failed to create/update document after {max_retries} attempts. Last error: {last_error}")
    
    def upload_file(self, file_path, mime_type, folder_id=None):
        """
        Upload a file to Google Drive
        
        Args:
            file_path (str): Path to the file to upload
            mime_type (str): MIME type of the file
            folder_id (str, optional): ID of the folder to save the file in
            
        Returns:
            str: ID of the uploaded file
        """
        try:
            file_name = os.path.basename(file_path)
            file_metadata = {
                'name': file_name
            }
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            with open(file_path, 'rb') as f:
                media = MediaIoBaseUpload(BytesIO(f.read()), mimetype=mime_type)
                file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            
            file_id = file.get('id')
            logging.info(f"✅ Uploaded file '{file_name}' with ID: {file_id}")
            return file_id
        except Exception as e:
            logging.error(f"❌ Failed to upload file '{file_path}': {str(e)}")
            raise
    
    def get_file_link(self, file_id):
        """
        Get a shareable link for a file and make it publicly accessible
        
        Args:
            file_id (str): ID of the file
            
        Returns:
            str: Public shareable link for the file
        """
        try:
            # Update permissions to make the file accessible to anyone with the link
            self.drive_service.permissions().create(
                fileId=file_id,
                body={
                    'type': 'anyone',
                    'role': 'reader'
                }
            ).execute()
            
            # Get the web view link
            file = self.drive_service.files().get(
                fileId=file_id,
                fields='webViewLink'
            ).execute()
            
            # Log the public link
            public_link = file.get('webViewLink')
            logging.info(f"🔗 Public link generated: {public_link}")
            
            return public_link
            
        except Exception as e:
            logging.error(f"Error getting file link: {str(e)}")
            raise
    
    def find_folder_by_name(self, folder_name, parent_id=None):
        """
        Find a folder by name and optional parent folder
        
        Args:
            folder_name (str): The name of the folder to find
            parent_id (str, optional): The ID of the parent folder to search in
            
        Returns:
            str or None: The folder ID if found, None otherwise
        """
        try:
            query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
            
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error finding folder: {str(e)}")
            raise
    
    def find_or_create_folder(self, folder_name, parent_id=None):
        """
        Find a folder by name or create it if it doesn't exist
        
        Args:
            folder_name (str): The name of the folder
            parent_id (str, optional): The ID of the parent folder
            
        Returns:
            str: The ID of the found or created folder
        """
        folder_id = self.find_folder_by_name(folder_name, parent_id)
        
        if folder_id:
            logging.info(f"Found existing folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        else:
            return self.create_folder(folder_name, parent_id)
    
    def create_folder_path(self, path_components, base_folder_id=None):
        """
        Create a folder hierarchy from a list of path components
        
        Args:
            path_components (list): List of folder names to create
            base_folder_id (str, optional): The ID of the base folder to start from
            
        Returns:
            str: The ID of the deepest folder created
        """
        current_parent_id = base_folder_id
        
        for folder_name in path_components:
            if folder_name:  # Skip empty folder names
                current_parent_id = self.find_or_create_folder(folder_name, current_parent_id)
        
        return current_parent_id
    
    def upload_html_content(self, html_content, file_name, folder_id=None):
        """
        Upload HTML content directly to Google Drive as an HTML file
        
        Args:
            html_content (str): The HTML content to upload
            file_name (str): Name of the file to create (should end with .html)
            folder_id (str, optional): ID of the folder to save the file in
            
        Returns:
            dict: Contains 'id' of the uploaded file and 'webViewLink' for direct access
        """
        try:
            # Ensure file name has .html extension
            if not file_name.endswith('.html'):
                file_name += '.html'
            
            file_metadata = {
                'name': file_name,
                'mimeType': 'text/html'
            }
            
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Create HTML file in Google Drive
            media = MediaIoBaseUpload(
                io.BytesIO(html_content.encode('utf-8')),
                mimetype='text/html',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            
            # Make the file accessible to anyone with the link
            self.drive_service.permissions().create(
                fileId=file_id,
                body={
                    'type': 'anyone',
                    'role': 'reader'
                }
            ).execute()
            
            # Get the web view link
            file = self.drive_service.files().get(
                fileId=file_id,
                fields='webViewLink'
            ).execute()
            
            result = {
                'id': file_id,
                'webViewLink': file.get('webViewLink')
            }
            
            logging.info(f"✅ Uploaded HTML file '{file_name}' with ID: {file_id}")
            return result
            
        except Exception as e:
            logging.error(f"❌ Failed to upload HTML file '{file_name}': {str(e)}")
            raise
    
    def list_public_files(self, folder_id=None):
        """
        List all public files in a folder or root
        
        Args:
            folder_id (str, optional): ID of the folder to list files from
            
        Returns:
            list: List of dictionaries containing file information
        """
        try:
            query = "trashed=false"
            if folder_id:
                query += f" and '{folder_id}' in parents"
                
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, webViewLink, mimeType, createdTime)'
            ).execute()
            
            files = results.get('files', [])
            
            # Log the files found
            logging.info(f"📁 Found {len(files)} files")
            for file in files:
                logging.info(f"📄 {file['name']} - {file['webViewLink']}")
            
            return files
            
        except Exception as e:
            logging.error(f"Error listing files: {str(e)}")
            raise