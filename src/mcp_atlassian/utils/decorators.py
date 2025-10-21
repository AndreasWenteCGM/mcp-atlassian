import logging
import traceback
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

import requests
from fastmcp import Context
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError

logger = logging.getLogger(__name__)


F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def check_write_access(func: F) -> F:
    """
    Decorator for FastMCP tools to check if the application is in read-only mode.
    If in read-only mode, it raises a ValueError.
    Assumes the decorated function is async and has `ctx: Context` as its first argument.
    """

    @wraps(func)
    async def wrapper(ctx: Context, *args: Any, **kwargs: Any) -> Any:
        lifespan_ctx_dict = ctx.request_context.lifespan_context
        app_lifespan_ctx = (
            lifespan_ctx_dict.get("app_lifespan_context")
            if isinstance(lifespan_ctx_dict, dict)
            else None
        )  # type: ignore

        if app_lifespan_ctx is not None and app_lifespan_ctx.read_only:
            tool_name = func.__name__
            action_description = tool_name.replace(
                "_", " "
            )  # e.g., "create_issue" -> "create issue"
            logger.warning(f"Attempted to call tool '{tool_name}' in read-only mode.")
            raise ValueError(f"Cannot {action_description} in read-only mode.")

        return await func(ctx, *args, **kwargs)

    return wrapper  # type: ignore


def handle_mcp_tool_errors(func: F) -> F:
    """
    Decorator for FastMCP tools to catch all exceptions and convert them into detailed error messages.
    This ensures LLMs receive comprehensive error information to diagnose and fix issues.

    The decorator catches exceptions and re-raises them with enhanced error messages including:
    - The original exception type and message
    - Stack trace information for debugging
    - Context about the tool that failed
    - Specific guidance for common error types

    Args:
        func: The async tool function to wrap.

    Returns:
        Wrapped function that provides detailed error messages.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        tool_name = func.__name__
        try:
            return await func(*args, **kwargs)
        except MCPAtlassianAuthenticationError as e:
            # Authentication errors already have good messages, just re-raise with context
            error_msg = (
                f"Authentication error in tool '{tool_name}': {str(e)}\n\n"
                "This typically means:\n"
                "- Your API token or OAuth credentials have expired\n"
                "- You don't have permission to access this resource\n"
                "- The authentication method is misconfigured\n\n"
                "Please verify your credentials and permissions."
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except HTTPError as e:
            # HTTP errors - provide detailed response information
            status_code = e.response.status_code if e.response else "unknown"
            response_text = (
                e.response.text[:500]
                if e.response and e.response.text
                else "No response body"
            )
            error_msg = (
                f"HTTP error in tool '{tool_name}': {type(e).__name__}: {str(e)}\n"
                f"Status Code: {status_code}\n"
                f"Response (first 500 chars): {response_text}\n\n"
                f"Request details: {e.request.method} {e.request.url if e.request else 'unknown URL'}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except (requests.RequestException, OSError) as e:
            # Network/connection errors
            error_msg = (
                f"Network error in tool '{tool_name}': {type(e).__name__}: {str(e)}\n\n"
                "This typically means:\n"
                "- Network connectivity issues\n"
                "- The Atlassian instance is unreachable\n"
                "- SSL/TLS certificate verification failed\n"
                "- Proxy or firewall blocking the connection\n\n"
                "Please check your network settings and the Atlassian instance URL."
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except ValueError as e:
            # ValueError - often from validation or configuration issues
            # Check if it's already a wrapped error (starts with specific patterns)
            error_str = str(e)
            if any(
                error_str.startswith(prefix)
                for prefix in [
                    "Authentication error",
                    "HTTP error",
                    "Network error",
                    "Unexpected error",
                ]
            ):
                # Already wrapped, just re-raise
                raise
            # Otherwise, add context
            error_msg = (
                f"Validation error in tool '{tool_name}': {str(e)}\n\n"
                "This typically means:\n"
                "- Invalid input parameters\n"
                "- Resource not found\n"
                "- Configuration issue\n\n"
                "Please verify your input parameters and try again."
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        except KeyError as e:
            # Missing expected data in API response
            error_msg = (
                f"Data structure error in tool '{tool_name}': Missing key {str(e)}\n\n"
                "This typically means:\n"
                "- The API response format has changed\n"
                "- Required data is missing from the response\n"
                "- The API version may be incompatible\n\n"
                "This may be a bug in the MCP server. Please report this issue."
            )
            logger.error(error_msg)
            logger.debug("Full exception details:", exc_info=True)
            raise ValueError(error_msg) from e
        except Exception as e:
            # Catch-all for unexpected errors
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            error_msg = (
                f"Unexpected error in tool '{tool_name}': {type(e).__name__}: {str(e)}\n\n"
                f"Stack trace:\n{tb_str}\n\n"
                "This is an unexpected error. Please report this issue with the full error details above."
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    return wrapper  # type: ignore


def handle_atlassian_api_errors(service_name: str = "Atlassian API") -> Callable:
    """
    Decorator to handle common Atlassian API exceptions (Jira, Confluence, etc.).

    Args:
        service_name: Name of the service for error logging (e.g., "Jira API").
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except HTTPError as http_err:
                if http_err.response is not None and http_err.response.status_code in [
                    401,
                    403,
                ]:
                    error_msg = (
                        f"Authentication failed for {service_name} "
                        f"({http_err.response.status_code}). "
                        "Token may be expired or invalid. Please verify credentials."
                    )
                    logger.error(error_msg)
                    raise MCPAtlassianAuthenticationError(error_msg) from http_err
                else:
                    operation_name = getattr(func, "__name__", "API operation")
                    logger.error(
                        f"HTTP error during {operation_name}: {http_err}",
                        exc_info=False,
                    )
                    raise http_err
            except KeyError as e:
                operation_name = getattr(func, "__name__", "API operation")
                logger.error(f"Missing key in {operation_name} results: {str(e)}")
                return []
            except requests.RequestException as e:
                operation_name = getattr(func, "__name__", "API operation")
                logger.error(f"Network error during {operation_name}: {str(e)}")
                return []
            except (ValueError, TypeError) as e:
                operation_name = getattr(func, "__name__", "API operation")
                logger.error(f"Error processing {operation_name} results: {str(e)}")
                return []
            except Exception as e:  # noqa: BLE001 - Intentional fallback with logging
                operation_name = getattr(func, "__name__", "API operation")
                logger.error(f"Unexpected error during {operation_name}: {str(e)}")
                logger.debug(
                    f"Full exception details for {operation_name}:", exc_info=True
                )
                return []

        return wrapper

    return decorator
