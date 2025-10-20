"""Attachment operations for Confluence API."""

import logging
import os
from pathlib import Path
from typing import Any

from ..models.confluence import ConfluenceAttachment
from .client import ConfluenceClient

# Configure logging
logger = logging.getLogger("mcp-atlassian")


class AttachmentsMixin(ConfluenceClient):
    """Mixin for Confluence attachment operations."""

    def get_page_attachments(self, page_id: str) -> list[ConfluenceAttachment]:
        """
        Get all attachments for a Confluence page.

        Args:
            page_id: The ID of the page to get attachments from

        Returns:
            List of ConfluenceAttachment models
        """
        try:
            logger.info(f"Fetching attachments for page {page_id}")

            # Use the Atlassian Python API to get attachments
            attachments_response = self.confluence.get_attachments_from_content(
                page_id=page_id
            )

            # Process each attachment
            attachment_models = []
            if attachments_response and "results" in attachments_response:
                for attachment_data in attachments_response["results"]:
                    attachment = ConfluenceAttachment.from_api_response(attachment_data)
                    attachment_models.append(attachment)

            logger.info(
                f"Found {len(attachment_models)} attachments for page {page_id}"
            )
            return attachment_models

        except Exception:
            logger.exception(f"Error fetching attachments for page {page_id}")
            return []

    def upload_attachment(
        self, page_id: str, file_path: str, comment: str | None = None
    ) -> dict[str, Any]:
        """
        Upload a single attachment to a Confluence page.

        Args:
            page_id: The ID of the page to attach the file to
            file_path: The path to the file to upload
            comment: Optional comment for the attachment

        Returns:
            A dictionary with upload result information
        """
        if not page_id:
            logger.error("No page ID provided for attachment upload")
            return {"success": False, "error": "No page ID provided"}

        if not file_path:
            logger.error("No file path provided for attachment upload")
            return {"success": False, "error": "No file path provided"}

        try:
            # Convert to absolute path if relative
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)

            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return {"success": False, "error": f"File not found: {file_path}"}

            logger.info(f"Uploading attachment from {file_path} to page {page_id}")

            # Use the Confluence API to upload the file
            filename = os.path.basename(file_path)
            attachment = self.confluence.attach_file(
                filename=file_path,
                page_id=page_id,
                comment=comment,
            )

            if attachment:
                file_size = os.path.getsize(file_path)
                logger.info(
                    f"Successfully uploaded attachment {filename} to page "
                    f"{page_id} (size: {file_size} bytes)"
                )
                return {
                    "success": True,
                    "page_id": page_id,
                    "filename": filename,
                    "size": file_size,
                    "id": (
                        attachment.get("id") if isinstance(attachment, dict) else None
                    ),
                }
            else:
                logger.error(
                    f"Failed to upload attachment {filename} to page {page_id}"
                )
                return {
                    "success": False,
                    "error": (
                        f"Failed to upload attachment {filename} to page {page_id}"
                    ),
                }

        except Exception:
            logger.exception("Error uploading attachment")
            return {"success": False, "error": "Failed to upload attachment"}

    def upload_attachments(
        self, page_id: str, file_paths: list[str], comment: str | None = None
    ) -> dict[str, Any]:
        """
        Upload multiple attachments to a Confluence page.

        Args:
            page_id: The ID of the page to attach files to
            file_paths: List of paths to files to upload
            comment: Optional comment for the attachments

        Returns:
            A dictionary with upload results
        """
        if not page_id:
            logger.error("No page ID provided for attachment upload")
            return {"success": False, "error": "No page ID provided"}

        if not file_paths:
            logger.error("No file paths provided for attachment upload")
            return {"success": False, "error": "No file paths provided"}

        logger.info(f"Uploading {len(file_paths)} attachments to page {page_id}")

        # Upload each attachment
        uploaded = []
        failed = []

        for file_path in file_paths:
            result = self.upload_attachment(page_id, file_path, comment)

            if result.get("success"):
                uploaded.append(
                    {
                        "filename": result.get("filename"),
                        "size": result.get("size"),
                        "id": result.get("id"),
                    }
                )
            else:
                failed.append(
                    {
                        "filename": os.path.basename(file_path),
                        "error": result.get("error"),
                    }
                )

        return {
            "success": True,
            "page_id": page_id,
            "total": len(file_paths),
            "uploaded": uploaded,
            "failed": failed,
        }

    def download_attachment(
        self, page_id: str, attachment_id: str, target_path: str
    ) -> bool:
        """
        Download a Confluence attachment to the specified path.

        Args:
            page_id: The ID of the page containing the attachment
            attachment_id: The ID of the attachment to download
            target_path: The path where the attachment should be saved

        Returns:
            True if successful, False otherwise
        """
        if not page_id or not attachment_id:
            logger.error("Page ID and attachment ID are required for download")
            return False

        if not target_path:
            logger.error("No target path provided for attachment download")
            return False

        try:
            # Convert to absolute path if relative
            if not os.path.isabs(target_path):
                target_path = os.path.abspath(target_path)

            logger.info(
                f"Downloading attachment {attachment_id} from page "
                f"{page_id} to {target_path}"
            )

            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # Get attachment details to find download URL
            attachments = self.get_page_attachments(page_id)

            download_url = None
            for attachment in attachments:
                if attachment.id == attachment_id:
                    download_url = attachment.download_url
                    if not download_url:
                        # Fallback to web URL
                        download_url = attachment.web_url
                    break

            if not download_url:
                logger.error(
                    f"Could not find download URL for attachment {attachment_id}"
                )
                return False

            # Make the download URL absolute if it's relative
            if download_url.startswith("/"):
                download_url = f"{self.config.url}{download_url}"

            # Use the Confluence session to download the file
            response = self.confluence._session.get(download_url, stream=True)
            response.raise_for_status()

            # Write the file to disk
            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Verify the file was created
            if os.path.exists(target_path):
                file_size = os.path.getsize(target_path)
                logger.info(
                    f"Successfully downloaded attachment to {target_path} "
                    f"(size: {file_size} bytes)"
                )
                return True
            else:
                logger.error(f"File was not created at {target_path}")
                return False

        except Exception:
            logger.exception("Error downloading attachment")
            return False

    def download_page_attachments(
        self, page_id: str, target_dir: str
    ) -> dict[str, Any]:
        """
        Download all attachments for a Confluence page.

        Args:
            page_id: The ID of the page to download attachments from
            target_dir: The directory where attachments should be saved

        Returns:
            A dictionary with download results
        """
        # Convert to absolute path if relative
        if not os.path.isabs(target_dir):
            target_dir = os.path.abspath(target_dir)

        logger.info(
            f"Downloading attachments for page {page_id} to directory: {target_dir}"
        )

        # Create the target directory if it doesn't exist
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        # Get all attachments for the page
        attachments = self.get_page_attachments(page_id)

        if not attachments:
            return {
                "success": True,
                "message": f"No attachments found for page {page_id}",
                "downloaded": [],
                "failed": [],
            }

        # Download each attachment
        downloaded = []
        failed = []

        for attachment in attachments:
            if not attachment.id:
                logger.warning(f"No ID for attachment {attachment.title}")
                failed.append(
                    {"filename": attachment.title, "error": "No ID available"}
                )
                continue

            if not attachment.title:
                logger.warning(f"No filename for attachment {attachment.id}")
                failed.append(
                    {"filename": attachment.id, "error": "No filename available"}
                )
                continue

            # Create a safe filename
            safe_filename = Path(attachment.title).name
            file_path = target_path / safe_filename

            # Download the attachment
            success = self.download_attachment(page_id, attachment.id, str(file_path))

            if success:
                downloaded.append(
                    {
                        "filename": attachment.title,
                        "path": str(file_path),
                        "size": attachment.file_size,
                    }
                )
            else:
                failed.append(
                    {"filename": attachment.title, "error": "Download failed"}
                )

        return {
            "success": True,
            "page_id": page_id,
            "total": len(attachments),
            "downloaded": downloaded,
            "failed": failed,
        }

    def delete_attachment(self, page_id: str, attachment_id: str) -> bool:
        """
        Delete an attachment from a Confluence page.

        Args:
            page_id: The ID of the page containing the attachment
            attachment_id: The ID of the attachment to delete

        Returns:
            True if successful, False otherwise
        """
        if not page_id or not attachment_id:
            logger.error("Page ID and attachment ID are required for deletion")
            return False

        try:
            logger.info(f"Deleting attachment {attachment_id} from page {page_id}")

            # First, get the attachment to find its filename
            attachments = self.get_page_attachments(page_id)
            filename = None
            for attachment in attachments:
                if attachment.id == attachment_id:
                    filename = attachment.title
                    break

            if not filename:
                logger.error(
                    f"Could not find attachment {attachment_id} on page {page_id}"
                )
                return False

            # Use the Confluence API to delete the attachment
            # The API requires page_id and filename, not attachment_id
            result = self.confluence.delete_attachment(
                page_id=page_id, filename=filename
            )

            # The delete method may return different types depending on success
            if result:
                logger.info(
                    f"Successfully deleted attachment {attachment_id} "
                    f"from page {page_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to delete attachment {attachment_id} from page {page_id}"
                )
                return False

        except Exception:
            logger.exception("Error deleting attachment")
            return False
