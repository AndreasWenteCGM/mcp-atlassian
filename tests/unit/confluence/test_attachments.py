"""Tests for the Confluence attachments module."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from mcp_atlassian.confluence import ConfluenceFetcher
from mcp_atlassian.confluence.attachments import AttachmentsMixin
from mcp_atlassian.confluence.config import ConfluenceConfig
from mcp_atlassian.models.confluence.common import ConfluenceAttachment

# Test scenarios for AttachmentsMixin
#
# 1. Get Page Attachments (get_page_attachments method):
#    - Success case: Returns list of attachment models
#    - Edge case: No attachments found
#    - Error case: API error during fetch
#
# 2. Single Attachment Upload (upload_attachment method):
#    - Success case: Uploads file correctly
#    - Path handling: Converts relative file path to absolute path
#    - Error cases:
#      - No page ID provided
#      - No file path provided
#      - File not found
#      - API error during upload
#      - No response from API
#
# 3. Multiple Attachments Upload (upload_attachments method):
#    - Success case: Uploads multiple files correctly
#    - Partial success: Some files upload successfully, others fail
#    - Error cases:
#      - Empty list of file paths
#      - No page ID provided
#
# 4. Single Attachment Download (download_attachment method):
#    - Success case: Downloads attachment correctly with proper HTTP response
#    - Path handling: Converts relative path to absolute path
#    - Error cases:
#      - No page ID or attachment ID provided
#      - No target path provided
#      - Attachment not found
#      - HTTP error during download
#      - File write error
#      - File not created after write operation
#
# 5. Page Attachments Download (download_page_attachments method):
#    - Success case: Downloads all attachments for a page
#    - Path handling: Converts relative target directory to absolute path
#    - Edge cases:
#      - Page has no attachments
#      - Some attachments fail to download
#      - Attachment has missing ID or title
#
# 6. Delete Attachment (delete_attachment method):
#    - Success case: Deletes attachment successfully
#    - Error cases:
#      - No page ID or attachment ID provided
#      - API error during deletion
#      - API returns false


class TestAttachmentsMixin:
    """Tests for the AttachmentsMixin class."""

    @pytest.fixture
    def attachments_mixin(self) -> AttachmentsMixin:
        """Set up test fixtures before each test method."""
        # Create a minimal config
        config = ConfluenceConfig(
            url="https://test.atlassian.net/wiki",
            auth_type="basic",
            username="test@example.com",
            api_token="fake_token",
        )

        # Create a ConfluenceFetcher instance
        with patch("mcp_atlassian.confluence.client.Confluence"):
            fetcher = ConfluenceFetcher(config)
            fetcher.confluence = MagicMock()
            fetcher.confluence._session = MagicMock()
            return fetcher

    def test_get_page_attachments_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful retrieval of page attachments."""
        # Mock the response
        mock_response = {
            "results": [
                {
                    "id": "att1",
                    "type": "attachment",
                    "status": "current",
                    "title": "test1.txt",
                    "extensions": {"mediaType": "text/plain", "fileSize": 100},
                    "_links": {
                        "download": "/download/attachments/123/test1.txt",
                        "webui": "/pages/123/test1.txt",
                    },
                },
                {
                    "id": "att2",
                    "type": "attachment",
                    "status": "current",
                    "title": "test2.pdf",
                    "extensions": {"mediaType": "application/pdf", "fileSize": 200},
                    "_links": {
                        "download": "/download/attachments/123/test2.pdf",
                        "webui": "/pages/123/test2.pdf",
                    },
                },
            ]
        }
        attachments_mixin.confluence.get_attachments_from_content.return_value = (
            mock_response
        )

        # Call the method
        result = attachments_mixin.get_page_attachments("123")

        # Assertions
        assert len(result) == 2
        assert result[0].id == "att1"
        assert result[0].title == "test1.txt"
        assert result[0].file_size == 100
        assert result[1].id == "att2"
        assert result[1].title == "test2.pdf"
        assert result[1].file_size == 200

    def test_get_page_attachments_no_results(self, attachments_mixin: AttachmentsMixin):
        """Test get_page_attachments when page has no attachments."""
        mock_response = {"results": []}
        attachments_mixin.confluence.get_attachments_from_content.return_value = (
            mock_response
        )

        result = attachments_mixin.get_page_attachments("123")

        assert result == []

    def test_get_page_attachments_error(self, attachments_mixin: AttachmentsMixin):
        """Test get_page_attachments with API error."""
        attachments_mixin.confluence.get_attachments_from_content.side_effect = (
            Exception("API error")
        )

        result = attachments_mixin.get_page_attachments("123")

        assert result == []

    def test_upload_attachment_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful attachment upload."""
        # Mock the Confluence API response
        mock_attachment_response = {
            "id": "att123",
            "title": "test_file.txt",
        }
        attachments_mixin.confluence.attach_file.return_value = mock_attachment_response

        # Mock file operations
        with (
            patch("os.path.exists") as mock_exists,
            patch("os.path.getsize") as mock_getsize,
            patch("os.path.isabs") as mock_isabs,
            patch("os.path.basename") as mock_basename,
        ):
            mock_exists.return_value = True
            mock_getsize.return_value = 100
            mock_isabs.return_value = True
            mock_basename.return_value = "test_file.txt"

            # Call the method
            result = attachments_mixin.upload_attachment(
                "123", "/path/to/test_file.txt"
            )

            # Assertions
            assert result["success"] is True
            assert result["page_id"] == "123"
            assert result["filename"] == "test_file.txt"
            assert result["size"] == 100
            assert result["id"] == "att123"

    def test_upload_attachment_no_page_id(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachment with no page ID."""
        result = attachments_mixin.upload_attachment("", "/path/to/file.txt")

        assert result["success"] is False
        assert "No page ID provided" in result["error"]

    def test_upload_attachment_no_file_path(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachment with no file path and no content."""
        result = attachments_mixin.upload_attachment("123", file_path="")

        assert result["success"] is False
        assert (
            "Either file_path or (filename + content) must be provided"
            in result["error"]
        )

    def test_upload_attachment_file_not_found(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test upload attachment with file not found."""
        with (
            patch("os.path.exists") as mock_exists,
            patch("os.path.isabs") as mock_isabs,
            patch("os.path.abspath") as mock_abspath,
        ):
            mock_exists.return_value = False
            mock_isabs.return_value = False
            mock_abspath.return_value = "/absolute/path/missing.txt"

            result = attachments_mixin.upload_attachment("123", "missing.txt")

            assert result["success"] is False
            assert "File not found" in result["error"]

    def test_upload_attachment_with_content_success(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test upload attachment with base64 content."""
        import base64

        test_content = b"Test file content"
        encoded_content = base64.b64encode(test_content).decode("utf-8")

        attachments_mixin.confluence.attach_content.return_value = {
            "id": "att123",
            "title": "test.txt",
        }

        result = attachments_mixin.upload_attachment(
            page_id="123",
            filename="test.txt",
            content=encoded_content,
            comment="Test upload",
        )

        assert result["success"] is True
        assert result["filename"] == "test.txt"
        assert result["size"] == len(test_content)
        attachments_mixin.confluence.attach_content.assert_called_once_with(
            content=test_content,
            name="test.txt",
            page_id="123",
            comment="Test upload",
        )

    def test_upload_attachment_both_path_and_content(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test upload attachment with both file_path and content (should fail)."""
        result = attachments_mixin.upload_attachment(
            page_id="123",
            file_path="/path/to/file.txt",
            filename="test.txt",
            content="base64content",
        )

        assert result["success"] is False
        assert "Cannot specify both file_path and content" in result["error"]

    def test_upload_attachment_content_without_filename(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test upload attachment with content but no filename."""
        result = attachments_mixin.upload_attachment(
            page_id="123",
            content="base64content",
        )

        assert result["success"] is False
        assert (
            "Either file_path or (filename + content) must be provided"
            in result["error"]
        )

    def test_upload_attachments_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful upload of multiple attachments."""
        # Mock successful results for each file
        mock_results = [
            {
                "success": True,
                "page_id": "123",
                "filename": f"file{i + 1}.txt",
                "size": 100 * (i + 1),
                "id": f"att{i + 1}",
            }
            for i in range(3)
        ]

        with patch.object(
            attachments_mixin, "upload_attachment", side_effect=mock_results
        ) as mock_upload:
            # Call the method
            file_paths = [
                "/path/to/file1.txt",
                "/path/to/file2.txt",
                "/path/to/file3.txt",
            ]
            result = attachments_mixin.upload_attachments("123", file_paths)

            # Assertions
            assert result["success"] is True
            assert result["page_id"] == "123"
            assert result["total"] == 3
            assert len(result["uploaded"]) == 3
            assert len(result["failed"]) == 0

            # Check that upload_attachment was called for each file
            assert mock_upload.call_count == 3

    def test_upload_attachments_mixed_results(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test upload of multiple attachments with mixed success and failure."""
        mock_results = [
            {"success": True, "filename": "file1.txt", "size": 100, "id": "att1"},
            {"success": False, "error": "Upload failed"},
            {"success": True, "filename": "file3.txt", "size": 300, "id": "att3"},
        ]

        with patch.object(
            attachments_mixin, "upload_attachment", side_effect=mock_results
        ):
            file_paths = [
                "/path/to/file1.txt",
                "/path/to/file2.txt",
                "/path/to/file3.txt",
            ]
            result = attachments_mixin.upload_attachments("123", file_paths)

            assert result["success"] is True
            assert len(result["uploaded"]) == 2
            assert len(result["failed"]) == 1

    def test_upload_attachments_with_content(self, attachments_mixin: AttachmentsMixin):
        """Test upload multiple attachments using base64 content."""
        import base64

        test_attachments = [
            {
                "filename": "file1.txt",
                "content": base64.b64encode(b"Content 1").decode("utf-8"),
            },
            {
                "filename": "file2.txt",
                "content": base64.b64encode(b"Content 2").decode("utf-8"),
            },
        ]

        mock_results = [
            {"success": True, "filename": "file1.txt", "size": 9},
            {"success": True, "filename": "file2.txt", "size": 9},
        ]

        with patch.object(
            attachments_mixin, "upload_attachment", side_effect=mock_results
        ) as mock_upload:
            result = attachments_mixin.upload_attachments(
                page_id="123", attachments=test_attachments
            )

            assert result["success"] is True
            assert result["total"] == 2
            assert len(result["uploaded"]) == 2
            assert mock_upload.call_count == 2

    def test_upload_attachments_both_params(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachments with both file_paths and attachments (should fail)."""
        result = attachments_mixin.upload_attachments(
            page_id="123",
            file_paths=["/path/to/file.txt"],
            attachments=[{"filename": "test.txt", "content": "base64"}],
        )

        assert result["success"] is False
        assert "Cannot specify both file_paths and attachments" in result["error"]

    def test_download_attachment_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful attachment download."""
        # Mock get_page_attachments
        from mcp_atlassian.models.confluence import ConfluenceAttachment

        mock_attachment = ConfluenceAttachment(
            id="att1",
            title="test.txt",
            download_url="/download/attachments/123/test.txt",
        )

        with patch.object(
            attachments_mixin, "get_page_attachments", return_value=[mock_attachment]
        ):
            # Mock the response
            mock_response = MagicMock()
            mock_response.iter_content.return_value = [b"test content"]
            mock_response.raise_for_status = MagicMock()
            attachments_mixin.confluence._session.get.return_value = mock_response

            # Mock file operations
            with (
                patch("builtins.open", mock_open()) as mock_file,
                patch("os.path.exists") as mock_exists,
                patch("os.path.getsize") as mock_getsize,
                patch("os.makedirs") as mock_makedirs,
                patch("os.path.isabs") as mock_isabs,
                patch("os.path.dirname") as mock_dirname,
            ):
                mock_exists.return_value = True
                mock_getsize.return_value = 12
                mock_isabs.return_value = True
                mock_dirname.return_value = "/tmp"

                # Call the method
                result = attachments_mixin.download_attachment(
                    "123", "att1", "/tmp/test.txt"
                )

                # Assertions
                assert result is True

    def test_download_attachment_no_ids(self, attachments_mixin: AttachmentsMixin):
        """Test download attachment with no page ID or attachment ID."""
        result = attachments_mixin.download_attachment("", "att1", "/tmp/test.txt")
        assert result is False

        result = attachments_mixin.download_attachment("123", "", "/tmp/test.txt")
        assert result is False

    def test_download_attachment_no_target_path(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test download attachment with no target path."""
        result = attachments_mixin.download_attachment("123", "att1", "")
        assert result is False

    def test_download_attachment_not_found(self, attachments_mixin: AttachmentsMixin):
        """Test download attachment when attachment is not found."""
        with patch.object(attachments_mixin, "get_page_attachments", return_value=[]):
            result = attachments_mixin.download_attachment(
                "123", "att1", "/tmp/test.txt"
            )
            assert result is False

    def test_download_page_attachments_success(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test successful download of all page attachments."""
        from mcp_atlassian.models.confluence import ConfluenceAttachment

        mock_attachments = [
            ConfluenceAttachment(
                id="att1",
                title="test1.txt",
                file_size=100,
                download_url="/download/test1.txt",
            ),
            ConfluenceAttachment(
                id="att2",
                title="test2.pdf",
                file_size=200,
                download_url="/download/test2.pdf",
            ),
        ]

        with (
            patch.object(
                attachments_mixin,
                "get_page_attachments",
                return_value=mock_attachments,
            ),
            patch.object(attachments_mixin, "download_attachment", return_value=True),
            patch("os.path.isabs") as mock_isabs,
            patch("os.path.abspath") as mock_abspath,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            mock_isabs.return_value = False
            mock_abspath.return_value = "/absolute/path/attachments"

            result = attachments_mixin.download_page_attachments(
                "123", "/tmp/attachments"
            )

            assert result["success"] is True
            assert result["page_id"] == "123"
            assert result["total"] == 2
            assert len(result["downloaded"]) == 2
            assert len(result["failed"]) == 0

    def test_download_page_attachments_no_attachments(
        self, attachments_mixin: AttachmentsMixin
    ):
        """Test download page attachments when page has no attachments."""
        with (
            patch.object(attachments_mixin, "get_page_attachments", return_value=[]),
            patch("os.path.isabs") as mock_isabs,
            patch("os.path.abspath") as mock_abspath,
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            mock_isabs.return_value = True
            mock_abspath.return_value = "/tmp/attachments"

            result = attachments_mixin.download_page_attachments(
                "123", "/tmp/attachments"
            )

            assert result["success"] is True
            assert "No attachments found" in result["message"]
            assert len(result["downloaded"]) == 0

    def test_delete_attachment_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful deletion of attachment."""
        # Mock get_page_attachments to return an attachment with the ID
        mock_attachment = ConfluenceAttachment(
            id="att1",
            title="test.txt",
            media_type="text/plain",
            file_size=100,
            comment="Test attachment",
        )
        attachments_mixin.get_page_attachments = MagicMock(
            return_value=[mock_attachment]
        )
        attachments_mixin.confluence.delete_attachment.return_value = True

        result = attachments_mixin.delete_attachment("123", "att1")

        assert result is True
        attachments_mixin.get_page_attachments.assert_called_once_with("123")
        attachments_mixin.confluence.delete_attachment.assert_called_once_with(
            page_id="123", filename="test.txt"
        )

    def test_delete_attachment_no_ids(self, attachments_mixin: AttachmentsMixin):
        """Test delete attachment with no page ID or attachment ID."""
        result = attachments_mixin.delete_attachment("", "att1")
        assert result is False

        result = attachments_mixin.delete_attachment("123", "")
        assert result is False

    def test_delete_attachment_failure(self, attachments_mixin: AttachmentsMixin):
        """Test delete attachment when API returns false."""
        # Mock get_page_attachments to return an attachment
        mock_attachment = ConfluenceAttachment(
            id="att1",
            title="test.txt",
            media_type="text/plain",
            file_size=100,
            comment="Test attachment",
        )
        attachments_mixin.get_page_attachments = MagicMock(
            return_value=[mock_attachment]
        )
        attachments_mixin.confluence.delete_attachment.return_value = False

        result = attachments_mixin.delete_attachment("123", "att1")

        assert result is False

    def test_delete_attachment_error(self, attachments_mixin: AttachmentsMixin):
        """Test delete attachment with API error."""
        # Mock get_page_attachments to return an attachment
        mock_attachment = ConfluenceAttachment(
            id="att1",
            title="test.txt",
            media_type="text/plain",
            file_size=100,
            comment="Test attachment",
        )
        attachments_mixin.get_page_attachments = MagicMock(
            return_value=[mock_attachment]
        )
        attachments_mixin.confluence.delete_attachment.side_effect = Exception(
            "API error"
        )

        result = attachments_mixin.delete_attachment("123", "att1")

        assert result is False

    def test_delete_attachment_not_found(self, attachments_mixin: AttachmentsMixin):
        """Test delete attachment when attachment ID doesn't exist."""
        # Mock get_page_attachments to return different attachment
        mock_attachment = ConfluenceAttachment(
            id="different_id",
            title="other.txt",
            media_type="text/plain",
            file_size=100,
            comment="Test attachment",
        )
        attachments_mixin.get_page_attachments = MagicMock(
            return_value=[mock_attachment]
        )

        result = attachments_mixin.delete_attachment("123", "att1")

        assert result is False
        attachments_mixin.get_page_attachments.assert_called_once_with("123")
        # delete_attachment should not be called if attachment not found
        attachments_mixin.confluence.delete_attachment.assert_not_called()
