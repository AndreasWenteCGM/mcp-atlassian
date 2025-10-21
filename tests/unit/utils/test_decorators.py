from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.utils.decorators import check_write_access, handle_mcp_tool_errors


class DummyContext:
    def __init__(self, read_only):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = {
            "app_lifespan_context": MagicMock(read_only=read_only)
        }


@pytest.mark.asyncio
async def test_check_write_access_blocks_in_read_only():
    @check_write_access
    async def dummy_tool(ctx, x):
        return x * 2

    ctx = DummyContext(read_only=True)
    with pytest.raises(ValueError) as exc:
        await dummy_tool(ctx, 3)
    assert "read-only mode" in str(exc.value)


@pytest.mark.asyncio
async def test_check_write_access_allows_in_writable():
    @check_write_access
    async def dummy_tool(ctx, x):
        return x * 2

    ctx = DummyContext(read_only=False)
    result = await dummy_tool(ctx, 4)
    assert result == 8


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_authentication_error():
    """Test that authentication errors are properly wrapped with detailed messages."""

    @handle_mcp_tool_errors
    async def dummy_tool():
        raise MCPAtlassianAuthenticationError("Token expired")

    with pytest.raises(ValueError) as exc:
        await dummy_tool()
    error_msg = str(exc.value)
    assert "Authentication error in tool 'dummy_tool'" in error_msg
    assert "Token expired" in error_msg
    assert "API token or OAuth credentials have expired" in error_msg


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_http_error():
    """Test that HTTP errors are properly wrapped with detailed messages."""

    @handle_mcp_tool_errors
    async def dummy_tool():
        response = MagicMock()
        response.status_code = 404
        response.text = "Page not found"
        request = MagicMock()
        request.method = "GET"
        request.url = "https://example.com/api/page"
        error = HTTPError()
        error.response = response
        error.request = request
        raise error

    with pytest.raises(ValueError) as exc:
        await dummy_tool()
    error_msg = str(exc.value)
    assert "HTTP error in tool 'dummy_tool'" in error_msg
    assert "Status Code: 404" in error_msg
    assert "Page not found" in error_msg


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_value_error():
    """Test that ValueError is properly wrapped with context."""

    @handle_mcp_tool_errors
    async def dummy_tool():
        raise ValueError("Invalid page ID")

    with pytest.raises(ValueError) as exc:
        await dummy_tool()
    error_msg = str(exc.value)
    assert "Validation error in tool 'dummy_tool'" in error_msg
    assert "Invalid page ID" in error_msg
    assert "Invalid input parameters" in error_msg


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_key_error():
    """Test that KeyError is properly wrapped with detailed messages."""

    @handle_mcp_tool_errors
    async def dummy_tool():
        data = {"foo": "bar"}
        return data["missing_key"]

    with pytest.raises(ValueError) as exc:
        await dummy_tool()
    error_msg = str(exc.value)
    assert "Data structure error in tool 'dummy_tool'" in error_msg
    assert "Missing key" in error_msg
    assert "API response format has changed" in error_msg


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_unexpected_error():
    """Test that unexpected errors include full stack trace."""

    @handle_mcp_tool_errors
    async def dummy_tool():
        raise RuntimeError("Something unexpected happened")

    with pytest.raises(ValueError) as exc:
        await dummy_tool()
    error_msg = str(exc.value)
    assert "Unexpected error in tool 'dummy_tool'" in error_msg
    assert "RuntimeError" in error_msg
    assert "Something unexpected happened" in error_msg
    assert "Stack trace:" in error_msg


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_success():
    """Test that successful execution passes through unchanged."""

    @handle_mcp_tool_errors
    async def dummy_tool(x, y):
        return x + y

    result = await dummy_tool(3, 4)
    assert result == 7


@pytest.mark.asyncio
async def test_handle_mcp_tool_errors_preserves_exception_chain():
    """Test that exception chaining is preserved."""

    @handle_mcp_tool_errors
    async def dummy_tool():
        try:
            raise ValueError("Original error")
        except ValueError as e:
            raise KeyError("Wrapped error") from e

    with pytest.raises(ValueError) as exc:
        await dummy_tool()
    # Check that the original exception chain is preserved
    assert exc.value.__cause__ is not None
    assert isinstance(exc.value.__cause__, KeyError)
