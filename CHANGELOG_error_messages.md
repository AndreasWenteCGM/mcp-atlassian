# Error Message Enhancement

## Summary

Enhanced error handling for all MCP tools to provide detailed error messages to LLMs when tool calls fail.

## Problem

Previously, when a tool call failed, the LLM would only receive generic error messages like:
```
Error calling tool 'update_page'
```

This made it impossible for the LLM to diagnose and fix issues without detailed error information.

## Solution

Added a new `handle_mcp_tool_errors` decorator that:

1. **Catches all exceptions** from MCP tool functions
2. **Categorizes errors** into specific types (authentication, HTTP, network, validation, etc.)
3. **Provides detailed context** including:
   - Original exception type and message
   - Stack traces for unexpected errors
   - HTTP response details (status codes, response bodies)
   - Specific guidance for common error types
4. **Re-raises as ValueError** with comprehensive error messages that LLMs can understand and act upon

## Changes Made

### 1. New Decorator (`src/mcp_atlassian/utils/decorators.py`)

Added `handle_mcp_tool_errors` decorator that handles:
- `MCPAtlassianAuthenticationError`: Token expiry, permission issues
- `HTTPError`: HTTP status codes, response bodies, request details
- `RequestException`/`OSError`: Network connectivity issues
- `ValueError`: Validation and configuration issues
- `KeyError`: Missing data in API responses
- Generic `Exception`: Unexpected errors with full stack traces

### 2. Applied to All Tools

Applied the decorator to all Jira and Confluence MCP tools:
- **Jira tools** (31 tools): `get_issue`, `create_issue`, `search`, `update_issue`, etc.
- **Confluence tools** (11 tools): `get_page`, `create_page`, `update_page`, `search`, etc.

### 3. Enhanced Error Messages

Error messages now include:
- **What happened**: Clear description of the error
- **Why it happened**: Likely causes (e.g., "Token expired", "Resource not found")
- **How to fix it**: Actionable guidance (e.g., "Verify credentials", "Check parameters")
- **Technical details**: Status codes, URLs, response snippets, stack traces

## Example Error Messages

### Before
```
Error calling tool 'update_page'
```

### After - Authentication Error
```
Authentication error in tool 'update_page': Token expired

This typically means:
- Your API token or OAuth credentials have expired
- You don't have permission to access this resource
- The authentication method is misconfigured

Please verify your credentials and permissions.
```

### After - HTTP Error
```
HTTP error in tool 'update_page': HTTPError: 404 Not Found
Status Code: 404
Response (first 500 chars): {"message": "Page not found", "statusCode": 404}

Request details: PUT https://example.atlassian.net/wiki/rest/api/content/123456
```

### After - Validation Error
```
Validation error in tool 'update_page': Invalid page ID

This typically means:
- Invalid input parameters
- Resource not found
- Configuration issue

Please verify your input parameters and try again.
```

### After - Unexpected Error
```
Unexpected error in tool 'update_page': AttributeError: 'NoneType' object has no attribute 'title'

Stack trace:
Traceback (most recent call last):
  File "decorators.py", line 67, in wrapper
    return await func(*args, **kwargs)
  File "confluence.py", line 521, in update_page
    page_title = page.title
AttributeError: 'NoneType' object has no attribute 'title'

This is an unexpected error. Please report this issue with the full error details above.
```

## Testing

- Added comprehensive tests in `tests/unit/utils/test_decorators.py`
- Tests cover all error types (authentication, HTTP, network, validation, etc.)
- Tests verify exception chaining is preserved
- All existing tests still pass (1016 passed)

## Benefits

1. **Better LLM decision-making**: LLMs can now diagnose issues and suggest fixes
2. **Faster debugging**: Developers see exactly what went wrong
3. **Improved user experience**: Clear, actionable error messages
4. **Maintainability**: Centralized error handling logic
5. **Consistency**: All tools use the same error handling approach

## Migration Notes

- No breaking changes
- All existing functionality preserved
- Error messages are more detailed but still programmatically parseable
- Exception chaining is preserved for debugging
