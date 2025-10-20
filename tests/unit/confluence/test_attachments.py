"""Tests for the Confluence attachments module (simplified for base64-only)."""

from unittest.mock import MagicMock

import pytest

from mcp_atlassian.confluence import ConfluenceFetcher
from mcp_atlassian.confluence.attachments import AttachmentsMixin
from mcp_atlassian.models.confluence.common import ConfluenceAttachment


@pytest.fixture
def attachments_mixin(mock_config) -> AttachmentsMixin:
    """Create a configured AttachmentsMixin instance for testing."""
    mixin = ConfluenceFetcher(mock_config)

    # Mock the Confluence client
    mixin.confluence = MagicMock()
    mixin.confluence._session = MagicMock()
    mixin.config = mock_config

    return mixin


class TestAttachmentsMixin:
    """Test suite for AttachmentsMixin."""

    def test_get_page_attachments_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful retrieval of page attachments."""
        mock_response = {
            "results": [
                {
                    "id": "att1",
                    "title": "test1.txt",
                    "mediaType": "text/plain",
                    "fileSize": 100,
                    "comment": "Test file 1",
                },
                {
                    "id": "att2",
                    "title": "test2.pdf",
                    "mediaType": "application/pdf",
                    "fileSize": 200,
                    "comment": "Test file 2",
                },
            ]
        }
        attachments_mixin.confluence.get_attachments_from_content.return_value = (
            mock_response
        )

        result = attachments_mixin.get_page_attachments("123")

        assert len(result) == 2
        assert result[0].id == "att1"
        assert result[1].id == "att2"

    def test_upload_attachment_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful attachment upload with base64 content."""
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
        )

        assert result["success"] is True
        assert result["page_id"] == "123"
        assert result["filename"] == "test.txt"
        assert result["size"] == len(test_content)
        assert result["id"] == "att123"

    def test_upload_attachment_no_page_id(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachment with no page ID."""
        result = attachments_mixin.upload_attachment(
            page_id="", filename="test.txt", content="base64content"
        )

        assert result["success"] is False
        assert "No page ID provided" in result["error"]

    def test_upload_attachment_no_filename(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachment with no filename."""
        result = attachments_mixin.upload_attachment(
            page_id="123", filename="", content="base64content"
        )

        assert result["success"] is False
        assert "No filename provided" in result["error"]

    def test_upload_attachment_no_content(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachment with no content."""
        result = attachments_mixin.upload_attachment(
            page_id="123", filename="test.txt", content=""
        )

        assert result["success"] is False
        assert "No content provided" in result["error"]

    def test_upload_attachment_with_comment(self, attachments_mixin: AttachmentsMixin):
        """Test upload attachment with comment."""
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
            comment="Test comment",
        )

        assert result["success"] is True
        attachments_mixin.confluence.attach_content.assert_called_once_with(
            content=test_content,
            name="test.txt",
            page_id="123",
            comment="Test comment",
        )

    def test_delete_attachment_success(self, attachments_mixin: AttachmentsMixin):
        """Test successful deletion of attachment."""
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
