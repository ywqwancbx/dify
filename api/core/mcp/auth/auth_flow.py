import base64
import hashlib
import json
import os
import secrets
import urllib.parse
from urllib.parse import urljoin, urlparse

import httpx
from httpx import RequestError
from pydantic import BaseModel, ValidationError

from core.entities.mcp_provider import MCPSupportGrantType
from core.helper import ssrf_proxy
from core.mcp.auth.auth_provider import OAuthClientProvider
from core.mcp.error import MCPRefreshTokenError
from core.mcp.types import (
    OAuthClientInformation,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthMetadata,
    OAuthTokens,
    ProtectedResourceMetadata,
)
from extensions.ext_redis import redis_client

LATEST_PROTOCOL_VERSION = "1.0"
OAUTH_STATE_EXPIRY_SECONDS = 5 * 60  # 5 minutes expiry
OAUTH_STATE_REDIS_KEY_PREFIX = "oauth_state:"


class OAuthCallbackState(BaseModel):
    provider_id: str
    tenant_id: str
    server_url: str
    metadata: OAuthMetadata | None = None
    client_information: OAuthClientInformation
    code_verifier: str
    redirect_uri: str


def generate_pkce_challenge() -> tuple[str, str]:
    """Generate PKCE challenge and verifier."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
    code_verifier = code_verifier.replace("=", "").replace("+", "-").replace("/", "_")

    code_challenge_hash = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge_hash).decode("utf-8")
    code_challenge = code_challenge.replace("=", "").replace("+", "-").replace("/", "_")

    return code_verifier, code_challenge


def build_protected_resource_metadata_discovery_urls(
    www_auth_resource_metadata_url: str | None, server_url: str
) -> list[str]:
    """
    Build a list of URLs to try for Protected Resource Metadata discovery.

    Per SEP-985, supports fallback when discovery fails at one URL.
    """
    urls = []

    # First priority: URL from WWW-Authenticate header
    if www_auth_resource_metadata_url:
        urls.append(www_auth_resource_metadata_url)

    # Fallback: construct from server URL
    parsed = urlparse(server_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    fallback_url = urljoin(base_url, "/.well-known/oauth-protected-resource")
    if fallback_url not in urls:
        urls.append(fallback_url)

    return urls


def build_oauth_authorization_server_metadata_discovery_urls(auth_server_url: str | None, server_url: str) -> list[str]:
    """
    Build a list of URLs to try for OAuth Authorization Server Metadata discovery.

    Supports both OAuth 2.0 (RFC 8414) and OpenID Connect discovery.

    Per RFC 8414 section 3:
    - If issuer has no path: https://example.com/.well-known/oauth-authorization-server
    - If issuer has path: https://example.com/.well-known/oauth-authorization-server{path}

    Example:
    - issuer: https://example.com/oauth
    - metadata: https://example.com/.well-known/oauth-authorization-server/oauth
    """
    urls = []
    base_url = auth_server_url or server_url

    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")  # Remove trailing slash

    # Try OpenID Connect discovery first (more common)
    urls.append(urljoin(base + "/", ".well-known/openid-configuration"))

    # OAuth 2.0 Authorization Server Metadata (RFC 8414)
    # Include the path component if present in the issuer URL
    if path:
        urls.append(urljoin(base, f".well-known/oauth-authorization-server{path}"))
    else:
        urls.append(urljoin(base, ".well-known/oauth-authorization-server"))

    return urls


def discover_protected_resource_metadata(
    prm_url: str | None, server_url: str, protocol_version: str | None = None
) -> ProtectedResourceMetadata | None:
    """Discover OAuth 2.0 Protected Resource Metadata (RFC 9470)."""
    urls = build_protected_resource_metadata_discovery_urls(prm_url, server_url)
    headers = {"MCP-Protocol-Version": protocol_version or LATEST_PROTOCOL_VERSION, "User-Agent": "Dify"}

    for url in urls:
        try:
            response = ssrf_proxy.get(url, headers=headers)
            if response.status_code == 200:
                return ProtectedResourceMetadata.model_validate(response.json())
            elif response.status_code == 404:
                continue  # Try next URL
        except (RequestError, ValidationError):
            continue  # Try next URL

    return None


def discover_oauth_authorization_server_metadata(
    auth_server_url: str | None, server_url: str, protocol_version: str | None = None
) -> OAuthMetadata | None:
    """Discover OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    urls = build_oauth_authorization_server_metadata_discovery_urls(auth_server_url, server_url)
    headers = {"MCP-Protocol-Version": protocol_version or LATEST_PROTOCOL_VERSION, "User-Agent": "Dify"}

    for url in urls:
        try:
            response = ssrf_proxy.get(url, headers=headers)
            if response.status_code == 200:
                return OAuthMetadata.model_validate(response.json())
            elif response.status_code == 404:
                continue  # Try next URL
        except (RequestError, ValidationError):
            continue  # Try next URL

    return None


def get_effective_scope(
    scope_from_www_auth: str | None,
    prm: ProtectedResourceMetadata | None,
    asm: OAuthMetadata | None,
    client_scope: str | None,
) -> str | None:
    """
    Determine effective scope using priority-based selection strategy.

    Priority order:
    1. WWW-Authenticate header scope (server explicit requirement)
    2. Protected Resource Metadata scopes
    3. OAuth Authorization Server Metadata scopes
    4. Client configured scope
    """
    if scope_from_www_auth:
        return scope_from_www_auth

    if prm and prm.scopes_supported:
        return " ".join(prm.scopes_supported)

    if asm and asm.scopes_supported:
        return " ".join(asm.scopes_supported)

    return client_scope


def _create_secure_redis_state(state_data: OAuthCallbackState) -> str:
    """Create a secure state parameter by storing state data in Redis and returning a random state key."""
    # Generate a secure random state key
    state_key = secrets.token_urlsafe(32)

    # Store the state data in Redis with expiration
    redis_key = f"{OAUTH_STATE_REDIS_KEY_PREFIX}{state_key}"
    redis_client.setex(redis_key, OAUTH_STATE_EXPIRY_SECONDS, state_data.model_dump_json())

    return state_key


def _retrieve_redis_state(state_key: str) -> OAuthCallbackState:
    """Retrieve and decode OAuth state data from Redis using the state key, then delete it."""
    redis_key = f"{OAUTH_STATE_REDIS_KEY_PREFIX}{state_key}"

    # Get state data from Redis
    state_data = redis_client.get(redis_key)

    if not state_data:
        raise ValueError("State parameter has expired or does not exist")

    # Delete the state data from Redis immediately after retrieval to prevent reuse
    redis_client.delete(redis_key)

    try:
        # Parse and validate the state data
        oauth_state = OAuthCallbackState.model_validate_json(state_data)

        return oauth_state
    except ValidationError as e:
        raise ValueError(f"Invalid state parameter: {str(e)}")


def handle_callback(state_key: str, authorization_code: str) -> OAuthCallbackState:
    """Handle the callback from the OAuth provider."""
    # Retrieve state data from Redis (state is automatically deleted after retrieval)
    full_state_data = _retrieve_redis_state(state_key)

    tokens = exchange_authorization(
        full_state_data.server_url,
        full_state_data.metadata,
        full_state_data.client_information,
        authorization_code,
        full_state_data.code_verifier,
        full_state_data.redirect_uri,
    )
    provider = OAuthClientProvider(full_state_data.provider_id, full_state_data.tenant_id, for_list=True)
    provider.save_tokens(tokens)
    return full_state_data


def check_support_resource_discovery(server_url: str) -> tuple[bool, str]:
    """Check if the server supports OAuth 2.0 Resource Discovery."""
    b_scheme, b_netloc, b_path, _, b_query, b_fragment = urlparse(server_url, "", True)
    url_for_resource_discovery = f"{b_scheme}://{b_netloc}/.well-known/oauth-protected-resource{b_path}"
    if b_query:
        url_for_resource_discovery += f"?{b_query}"
    if b_fragment:
        url_for_resource_discovery += f"#{b_fragment}"
    try:
        headers = {"MCP-Protocol-Version": LATEST_PROTOCOL_VERSION, "User-Agent": "Dify"}
        response = httpx.get(url_for_resource_discovery, headers=headers)
        if 200 <= response.status_code < 300:
            body = response.json()
            if "authorization_server_url" in body:
                return True, body["authorization_server_url"][0]
            else:
                return False, ""
        return False, ""
    except httpx.RequestError:
        # Not support resource discovery, fall back to well-known OAuth metadata
        return False, ""


def discover_oauth_metadata(
    server_url: str,
    resource_metadata_url: str | None = None,
    scope_hint: str | None = None,
    protocol_version: str | None = None,
) -> tuple[OAuthMetadata | None, ProtectedResourceMetadata | None, str | None]:
    """
    Discover OAuth metadata using RFC 8414/9470 standards.

    Args:
        server_url: The MCP server URL
        resource_metadata_url: Protected Resource Metadata URL from WWW-Authenticate header
        scope_hint: Scope hint from WWW-Authenticate header
        protocol_version: MCP protocol version

    Returns:
        (oauth_metadata, protected_resource_metadata, scope_hint)
    """
    # Discover Protected Resource Metadata
    prm = discover_protected_resource_metadata(resource_metadata_url, server_url, protocol_version)

    # Get authorization server URL from PRM or use server URL
    auth_server_url = None
    if prm and prm.authorization_servers:
        auth_server_url = prm.authorization_servers[0]

    # Discover OAuth Authorization Server Metadata
    asm = discover_oauth_authorization_server_metadata(auth_server_url, server_url, protocol_version)

    return asm, prm, scope_hint


def start_authorization(
    server_url: str,
    metadata: OAuthMetadata | None,
    client_information: OAuthClientInformation,
    redirect_url: str,
    provider_id: str,
    tenant_id: str,
    scope: str | None = None,
) -> tuple[str, str]:
    """Begins the authorization flow with secure Redis state storage."""
    response_type = "code"
    code_challenge_method = "S256"

    if metadata:
        authorization_url = metadata.authorization_endpoint
        if response_type not in metadata.response_types_supported:
            raise ValueError(f"Incompatible auth server: does not support response type {response_type}")
    else:
        authorization_url = urljoin(server_url, "/authorize")

    code_verifier, code_challenge = generate_pkce_challenge()

    # Prepare state data with all necessary information
    state_data = OAuthCallbackState(
        provider_id=provider_id,
        tenant_id=tenant_id,
        server_url=server_url,
        metadata=metadata,
        client_information=client_information,
        code_verifier=code_verifier,
        redirect_uri=redirect_url,
    )

    # Store state data in Redis and generate secure state key
    state_key = _create_secure_redis_state(state_data)

    params = {
        "response_type": response_type,
        "client_id": client_information.client_id,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "redirect_uri": redirect_url,
        "state": state_key,
    }

    # Add scope if provided
    if scope:
        params["scope"] = scope

    authorization_url = f"{authorization_url}?{urllib.parse.urlencode(params)}"
    return authorization_url, code_verifier


def _parse_token_response(response: httpx.Response) -> OAuthTokens:
    """
    Parse OAuth token response supporting both JSON and form-urlencoded formats.

    Per RFC 6749 Section 5.1, the standard format is JSON.
    However, some legacy OAuth providers (e.g., early GitHub OAuth Apps) return
    application/x-www-form-urlencoded format for backwards compatibility.

    Args:
        response: The HTTP response from token endpoint

    Returns:
        Parsed OAuth tokens

    Raises:
        ValueError: If response cannot be parsed
    """
    content_type = response.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        # Standard OAuth 2.0 JSON response (RFC 6749)
        return OAuthTokens.model_validate(response.json())
    elif "application/x-www-form-urlencoded" in content_type:
        # Legacy form-urlencoded response (non-standard but used by some providers)
        token_data = dict(urllib.parse.parse_qsl(response.text))
        return OAuthTokens.model_validate(token_data)
    else:
        # No content-type or unknown - try JSON first, fallback to form-urlencoded
        try:
            return OAuthTokens.model_validate(response.json())
        except (ValidationError, json.JSONDecodeError):
            token_data = dict(urllib.parse.parse_qsl(response.text))
            return OAuthTokens.model_validate(token_data)


def exchange_authorization(
    server_url: str,
    metadata: OAuthMetadata | None,
    client_information: OAuthClientInformation,
    authorization_code: str,
    code_verifier: str,
    redirect_uri: str,
) -> OAuthTokens:
    """Exchanges an authorization code for an access token."""
    grant_type = "authorization_code"

    if metadata:
        token_url = metadata.token_endpoint
        if metadata.grant_types_supported and grant_type not in metadata.grant_types_supported:
            raise ValueError(f"Incompatible auth server: does not support grant type {grant_type}")
    else:
        token_url = urljoin(server_url, "/token")

    params = {
        "grant_type": grant_type,
        "client_id": client_information.client_id,
        "code": authorization_code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }

    if client_information.client_secret:
        params["client_secret"] = client_information.client_secret

    response = httpx.post(token_url, data=params)
    if not response.is_success:
        raise ValueError(f"Token exchange failed: HTTP {response.status_code}")
    return _parse_token_response(response)


def refresh_authorization(
    server_url: str,
    metadata: OAuthMetadata | None,
    client_information: OAuthClientInformation,
    refresh_token: str,
) -> OAuthTokens:
    """Exchange a refresh token for an updated access token."""
    grant_type = "refresh_token"

    if metadata:
        token_url = metadata.token_endpoint
        if metadata.grant_types_supported and grant_type not in metadata.grant_types_supported:
            raise ValueError(f"Incompatible auth server: does not support grant type {grant_type}")
    else:
        token_url = urljoin(server_url, "/token")

    params = {
        "grant_type": grant_type,
        "client_id": client_information.client_id,
        "refresh_token": refresh_token,
    }

    if client_information.client_secret:
        params["client_secret"] = client_information.client_secret

    response = httpx.post(token_url, data=params)
    if not response.is_success:
        raise MCPRefreshTokenError(response.text)
    return _parse_token_response(response)


def client_credentials_flow(
    server_url: str,
    metadata: OAuthMetadata | None,
    client_information: OAuthClientInformation,
    scope: str | None = None,
) -> OAuthTokens:
    """Execute Client Credentials Flow to get access token."""
    grant_type = MCPSupportGrantType.CLIENT_CREDENTIALS.value

    if metadata:
        token_url = metadata.token_endpoint
        if metadata.grant_types_supported and grant_type not in metadata.grant_types_supported:
            raise ValueError(f"Incompatible auth server: does not support grant type {grant_type}")
    else:
        token_url = urljoin(server_url, "/token")

    # Support both Basic Auth and body parameters for client authentication
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": grant_type}

    if scope:
        data["scope"] = scope

    # If client_secret is provided, use Basic Auth (preferred method)
    if client_information.client_secret:
        credentials = f"{client_information.client_id}:{client_information.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded_credentials}"
    else:
        # Fall back to including credentials in the body
        data["client_id"] = client_information.client_id
        if client_information.client_secret:
            data["client_secret"] = client_information.client_secret

    response = ssrf_proxy.post(token_url, headers=headers, data=data)
    if not response.is_success:
        raise ValueError(
            f"Client credentials token request failed: HTTP {response.status_code}, Response: {response.text}"
        )

    return _parse_token_response(response)


def register_client(
    server_url: str,
    metadata: OAuthMetadata | None,
    client_metadata: OAuthClientMetadata,
) -> OAuthClientInformationFull:
    """Performs OAuth 2.0 Dynamic Client Registration."""
    if metadata:
        if not metadata.registration_endpoint:
            raise ValueError("Incompatible auth server: does not support dynamic client registration")
        registration_url = metadata.registration_endpoint
    else:
        registration_url = urljoin(server_url, "/register")

    response = httpx.post(
        registration_url,
        json=client_metadata.model_dump(),
        headers={"Content-Type": "application/json"},
    )
    if not response.is_success:
        response.raise_for_status()
    return OAuthClientInformationFull.model_validate(response.json())


def auth(
    provider: OAuthClientProvider,
    server_url: str,
    authorization_code: str | None = None,
    state_param: str | None = None,
    resource_metadata_url: str | None = None,
    scope_hint: str | None = None,
    for_list: bool = False,
) -> dict[str, str]:
    """Orchestrates the full auth flow with a server using secure Redis state storage."""
    # Discover OAuth metadata using RFC 8414/9470 standards
    server_metadata, prm, scope_from_www_auth = discover_oauth_metadata(
        server_url, resource_metadata_url, scope_hint, LATEST_PROTOCOL_VERSION
    )
    metadata = server_metadata

    # Handle client registration if needed
    client_information = provider.client_information()
    if not client_information:
        if authorization_code is not None:
            raise ValueError("Existing OAuth client information is required when exchanging an authorization code")
        try:
            full_information = register_client(server_url, metadata, provider.client_metadata)
        except httpx.RequestError as e:
            raise ValueError(f"Could not register OAuth client: {e}")
        provider.save_client_information(full_information)
        client_information = full_information

    # Determine grant type and scope if metadata is available
    effective_grant_type = None
    effective_scope = None
    if metadata:
        supported_grant_types = metadata.grant_types_supported or []
        supported_grant_types_lower = [gt.lower() for gt in supported_grant_types]
        
        # Determine which grant type to use
        if MCPSupportGrantType.AUTHORIZATION_CODE.value in supported_grant_types_lower:
            effective_grant_type = MCPSupportGrantType.AUTHORIZATION_CODE.value
        else:
            effective_grant_type = MCPSupportGrantType.CLIENT_CREDENTIALS.value
        
        # Determine effective scope using priority-based strategy
        credentials = provider.decrypt_credentials() if hasattr(provider, 'decrypt_credentials') else {}
        effective_scope = get_effective_scope(scope_from_www_auth, prm, metadata, credentials.get("scope"))
        
        # Handle client credentials flow if no authorization code and grant type is client_credentials
        if (
            authorization_code is None
            and state_param is None
            and effective_grant_type == MCPSupportGrantType.CLIENT_CREDENTIALS.value
        ):
            try:
                tokens = client_credentials_flow(
                    server_url,
                    metadata,
                    client_information,
                    effective_scope,
                )
                provider.save_tokens(tokens)
                return {"result": "success"}
            except (RequestError, ValueError, KeyError) as e:
                raise ValueError(f"Client credentials flow failed: {e}")

    # Exchange authorization code for tokens
    if authorization_code is not None:
        if not state_param:
            raise ValueError("State parameter is required when exchanging authorization code")

        try:
            # Retrieve state data from Redis using state key
            full_state_data = _retrieve_redis_state(state_param)

            code_verifier = full_state_data.code_verifier
            redirect_uri = full_state_data.redirect_uri

            if not code_verifier or not redirect_uri:
                raise ValueError("Missing code_verifier or redirect_uri in state data")

        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid state parameter: {e}")

        tokens = exchange_authorization(
            server_url,
            metadata,
            client_information,
            authorization_code,
            code_verifier,
            redirect_uri,
        )
        provider.save_tokens(tokens)
        return {"result": "success"}

    provider_tokens = provider.tokens()

    # Handle token refresh or new authorization
    if provider_tokens and provider_tokens.refresh_token:
        try:
            new_tokens = refresh_authorization(server_url, metadata, client_information, provider_tokens.refresh_token)
            provider.save_tokens(new_tokens)
            return {"result": "success"}
        except Exception as e:
            raise ValueError(f"Could not refresh OAuth tokens: {e}")

    # Start new authorization flow
    authorization_url, code_verifier = start_authorization(
        server_url,
        metadata,
        client_information,
        provider.redirect_url,
        provider.mcp_provider.id,
        provider.mcp_provider.tenant_id,
        effective_scope,
    )

    provider.save_code_verifier(code_verifier)
    return {"authorization_url": authorization_url}
