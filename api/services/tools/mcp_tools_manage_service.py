import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from core.helper import encrypter
from core.helper.provider_cache import NoOpProviderCredentialCache
from core.mcp.error import MCPAuthError, MCPError
from core.mcp.mcp_client import MCPClient
from core.tools.entities.api_entities import ToolProviderApiEntity
from core.tools.entities.common_entities import I18nObject
from core.tools.entities.tool_entities import ToolProviderType
from core.tools.mcp_tool.provider import MCPToolProviderController
from core.tools.utils.encryption import ProviderConfigEncrypter
from extensions.ext_database import db
from models.tools import MCPToolProvider
from services.tools.tools_transform_service import ToolTransformService

UNCHANGED_SERVER_URL_PLACEHOLDER = "[__HIDDEN__]"


class MCPToolManageService:
    """
    Service class for managing mcp tools.
    """

    @staticmethod
    def _encrypt_headers(headers: dict[str, str], tenant_id: str) -> dict[str, str]:
        """
        Encrypt headers using ProviderConfigEncrypter with all headers as SECRET_INPUT.

        Args:
            headers: Dictionary of headers to encrypt
            tenant_id: Tenant ID for encryption

        Returns:
            Dictionary with all headers encrypted
        """
        if not headers:
            return {}

        from core.entities.provider_entities import BasicProviderConfig
        from core.helper.provider_cache import NoOpProviderCredentialCache
        from core.tools.utils.encryption import create_provider_encrypter

        # Create dynamic config for all headers as SECRET_INPUT
        config = [BasicProviderConfig(type=BasicProviderConfig.Type.SECRET_INPUT, name=key) for key in headers]

        encrypter_instance, _ = create_provider_encrypter(
            tenant_id=tenant_id,
            config=config,
            cache=NoOpProviderCredentialCache(),
        )

        return encrypter_instance.encrypt(headers)

    @staticmethod
    def get_mcp_provider_by_provider_id(provider_id: str, tenant_id: str) -> MCPToolProvider:
        res = (
            db.session.query(MCPToolProvider)
            .where(MCPToolProvider.tenant_id == tenant_id, MCPToolProvider.id == provider_id)
            .first()
        )
        if not res:
            raise ValueError("MCP tool not found")
        return res

    @staticmethod
    def get_mcp_provider_by_server_identifier(server_identifier: str, tenant_id: str) -> MCPToolProvider:
        res = (
            db.session.query(MCPToolProvider)
            .where(MCPToolProvider.tenant_id == tenant_id, MCPToolProvider.server_identifier == server_identifier)
            .first()
        )
        if not res:
            raise ValueError("MCP tool not found")
        return res

    @staticmethod
    def create_mcp_provider(
        tenant_id: str,
        name: str,
        server_url: str,
        user_id: str,
        icon: str,
        icon_type: str,
        icon_background: str,
        server_identifier: str,
        timeout: float,
        sse_read_timeout: float,
        headers: dict[str, str] | None = None,
    ) -> ToolProviderApiEntity:
        server_url_hash = hashlib.sha256(server_url.encode()).hexdigest()
        existing_provider = (
            db.session.query(MCPToolProvider)
            .where(
                MCPToolProvider.tenant_id == tenant_id,
                or_(
                    MCPToolProvider.name == name,
                    MCPToolProvider.server_url_hash == server_url_hash,
                    MCPToolProvider.server_identifier == server_identifier,
                ),
            )
            .first()
        )
        if existing_provider:
            if existing_provider.name == name:
                raise ValueError(f"MCP tool {name} already exists")
            if existing_provider.server_url_hash == server_url_hash:
                raise ValueError(f"MCP tool {server_url} already exists")
            if existing_provider.server_identifier == server_identifier:
                raise ValueError(f"MCP tool {server_identifier} already exists")
        encrypted_server_url = encrypter.encrypt_token(tenant_id, server_url)
        # Encrypt headers
        encrypted_headers = None
        if headers:
            encrypted_headers_dict = MCPToolManageService._encrypt_headers(headers, tenant_id)
            encrypted_headers = json.dumps(encrypted_headers_dict)

        mcp_tool = MCPToolProvider(
            tenant_id=tenant_id,
            name=name,
            server_url=encrypted_server_url,
            server_url_hash=server_url_hash,
            user_id=user_id,
            authed=False,
            tools="[]",
            icon=json.dumps({"content": icon, "background": icon_background}) if icon_type == "emoji" else icon,
            server_identifier=server_identifier,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            encrypted_headers=encrypted_headers,
        )
        db.session.add(mcp_tool)
        db.session.commit()
        return ToolTransformService.mcp_provider_to_user_provider(mcp_tool, for_list=True)

    @staticmethod
    def retrieve_mcp_tools(tenant_id: str, for_list: bool = False) -> list[ToolProviderApiEntity]:
        mcp_providers = (
            db.session.query(MCPToolProvider)
            .where(MCPToolProvider.tenant_id == tenant_id)
            .order_by(MCPToolProvider.name)
            .all()
        )
        return [
            ToolTransformService.mcp_provider_to_user_provider(mcp_provider, for_list=for_list)
            for mcp_provider in mcp_providers
        ]

    @classmethod
    def list_mcp_tool_from_remote_server(cls, tenant_id: str, provider_id: str) -> ToolProviderApiEntity:
        mcp_provider = cls.get_mcp_provider_by_provider_id(provider_id, tenant_id)
        server_url = mcp_provider.decrypted_server_url
        authed = mcp_provider.authed
        headers = mcp_provider.decrypted_headers
        timeout = mcp_provider.timeout
        sse_read_timeout = mcp_provider.sse_read_timeout

        try:
            with MCPClient(
                server_url,
                provider_id,
                tenant_id,
                authed=authed,
                for_list=True,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            ) as mcp_client:
                tools = mcp_client.list_tools()
        except MCPAuthError:
            raise ValueError("Please auth the tool first")
        except MCPError as e:
            raise ValueError(f"Failed to connect to MCP server: {e}")

        try:
            mcp_provider = cls.get_mcp_provider_by_provider_id(provider_id, tenant_id)
            mcp_provider.tools = json.dumps([tool.model_dump() for tool in tools])
            mcp_provider.authed = True
            mcp_provider.updated_at = datetime.now()
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        user = mcp_provider.load_user()
        if not mcp_provider.icon:
            raise ValueError("MCP provider icon is required")
        return ToolProviderApiEntity(
            id=mcp_provider.id,
            name=mcp_provider.name,
            tools=ToolTransformService.mcp_tool_to_user_tool(mcp_provider, tools),
            type=ToolProviderType.MCP,
            icon=mcp_provider.icon,
            author=user.name if user else "Anonymous",
            server_url=mcp_provider.masked_server_url,
            updated_at=int(mcp_provider.updated_at.timestamp()),
            description=I18nObject(en_US="", zh_Hans=""),
            label=I18nObject(en_US=mcp_provider.name, zh_Hans=mcp_provider.name),
            plugin_unique_identifier=mcp_provider.server_identifier,
        )

        self._session.add(mcp_tool)
        self._session.flush()

        mcp_providers = ToolTransformService.mcp_provider_to_user_provider(mcp_tool, for_list=True)
        return mcp_providers

    @classmethod
    def delete_mcp_tool(cls, tenant_id: str, provider_id: str):
        mcp_tool = cls.get_mcp_provider_by_provider_id(provider_id, tenant_id)
        db.session.delete(mcp_tool)
        db.session.commit()

    @classmethod
    def update_mcp_provider(
        cls,
        tenant_id: str,
        provider_id: str,
        name: str,
        server_url: str,
        icon: str,
        icon_type: str,
        icon_background: str,
        server_identifier: str,
        timeout: float | None = None,
        sse_read_timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ):
        mcp_provider = cls.get_mcp_provider_by_provider_id(provider_id, tenant_id)

        reconnect_result = None
        encrypted_server_url = None
        server_url_hash = None

        if UNCHANGED_SERVER_URL_PLACEHOLDER not in server_url:
            encrypted_server_url = encrypter.encrypt_token(tenant_id, server_url)
            server_url_hash = hashlib.sha256(server_url.encode()).hexdigest()

            if server_url_hash != mcp_provider.server_url_hash:
                reconnect_result = cls._re_connect_mcp_provider(server_url, provider_id, tenant_id)

        try:
            mcp_provider.updated_at = datetime.now()
            mcp_provider.name = name
            mcp_provider.icon = (
                json.dumps({"content": icon, "background": icon_background}) if icon_type == "emoji" else icon
            )
            mcp_provider.server_identifier = server_identifier

            if encrypted_server_url is not None and server_url_hash is not None:
                mcp_provider.server_url = encrypted_server_url
                mcp_provider.server_url_hash = server_url_hash

                if reconnect_result:
                    mcp_provider.authed = reconnect_result["authed"]
                    mcp_provider.tools = reconnect_result["tools"]
                    mcp_provider.encrypted_credentials = reconnect_result["encrypted_credentials"]

            if timeout is not None:
                mcp_provider.timeout = timeout
            if sse_read_timeout is not None:
                mcp_provider.sse_read_timeout = sse_read_timeout
            if headers is not None:
                # Merge masked headers from frontend with existing real values
                if headers:
                    # existing decrypted and masked headers
                    existing_decrypted = mcp_provider.decrypted_headers
                    existing_masked = mcp_provider.masked_headers

                    # Build final headers: if value equals masked existing, keep original decrypted value
                    final_headers: dict[str, str] = {}
                    for key, incoming_value in headers.items():
                        if (
                            key in existing_masked
                            and key in existing_decrypted
                            and isinstance(incoming_value, str)
                            and incoming_value == existing_masked.get(key)
                        ):
                            # unchanged, use original decrypted value
                            final_headers[key] = str(existing_decrypted[key])
                        else:
                            final_headers[key] = incoming_value

                    encrypted_headers_dict = MCPToolManageService._encrypt_headers(final_headers, tenant_id)
                    mcp_provider.encrypted_headers = json.dumps(encrypted_headers_dict)
                else:
                    # Explicitly clear headers if empty dict passed
                    mcp_provider.encrypted_headers = None
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            error_msg = str(e.orig)
            if "unique_mcp_provider_name" in error_msg:
                raise ValueError(f"MCP tool {name} already exists")
            if "unique_mcp_provider_server_url" in error_msg:
                raise ValueError(f"MCP tool {server_url} already exists")
            if "unique_mcp_provider_server_identifier" in error_msg:
                raise ValueError(f"MCP tool {server_identifier} already exists")
            raise
        except Exception:
            db.session.rollback()
            raise

    def delete_provider(self, *, tenant_id: str, provider_id: str) -> None:
        """Delete an MCP provider."""
        mcp_tool = self.get_provider(provider_id=provider_id, tenant_id=tenant_id)
        self._session.delete(mcp_tool)

    def list_providers(
        self, *, tenant_id: str, for_list: bool = False, include_sensitive: bool = True
    ) -> list[ToolProviderApiEntity]:
        """List all MCP providers for a tenant.

        Args:
            tenant_id: Tenant ID
            for_list: If True, return provider ID; if False, return server identifier
            include_sensitive: If False, skip expensive decryption operations (default: True for backward compatibility)
        """
        from models.account import Account

        stmt = select(MCPToolProvider).where(MCPToolProvider.tenant_id == tenant_id).order_by(MCPToolProvider.name)
        mcp_providers = self._session.scalars(stmt).all()

        if not mcp_providers:
            return []

        # Batch query all users to avoid N+1 problem
        user_ids = {provider.user_id for provider in mcp_providers}
        users = self._session.query(Account).where(Account.id.in_(user_ids)).all()
        user_name_map = {user.id: user.name for user in users}

        return [
            ToolTransformService.mcp_provider_to_user_provider(
                provider,
                for_list=for_list,
                user_name=user_name_map.get(provider.user_id),
                include_sensitive=include_sensitive,
            )
            for provider in mcp_providers
        ]

    # ========== Tool Operations ==========

    def list_provider_tools(self, *, tenant_id: str, provider_id: str) -> ToolProviderApiEntity:
        """List tools from remote MCP server."""
        # Load provider and convert to entity
        db_provider = self.get_provider(provider_id=provider_id, tenant_id=tenant_id)
        provider_entity = db_provider.to_entity()

        # Verify authentication
        if not provider_entity.authed:
            raise ValueError("Please auth the tool first")

        # Prepare headers with auth token
        headers = self._prepare_auth_headers(provider_entity)

        # Retrieve tools from remote server
        server_url = provider_entity.decrypt_server_url()
        try:
            tools = self._retrieve_remote_mcp_tools(server_url, headers, provider_entity)
        except MCPError as e:
            raise ValueError(f"Failed to connect to MCP server: {e}")

        # Update database with retrieved tools
        db_provider.tools = json.dumps([tool.model_dump() for tool in tools])
        db_provider.authed = True
        db_provider.updated_at = datetime.now()
        self._session.flush()

        # Build API response
        return self._build_tool_provider_response(db_provider, provider_entity, tools)

    # ========== OAuth and Credentials Operations ==========

    def update_provider_credentials(
        self, *, provider_id: str, tenant_id: str, credentials: dict[str, Any], authed: bool | None = None
    ) -> None:
        """
        Update provider credentials with encryption.

        Args:
            provider_id: Provider ID
            tenant_id: Tenant ID
            credentials: Credentials to save
            authed: Whether provider is authenticated (None means keep current state)
        """
        from core.tools.mcp_tool.provider import MCPToolProviderController

        # Get provider from current session
        provider = self.get_provider(provider_id=provider_id, tenant_id=tenant_id)

        # Encrypt new credentials
        provider_controller = MCPToolProviderController.from_db(provider)
=======
    @classmethod
    def update_mcp_provider_credentials(
        cls, mcp_provider: MCPToolProvider, credentials: dict[str, Any], authed: bool = False
    ):
        provider_controller = MCPToolProviderController.from_db(mcp_provider)
>>>>>>> eam-integration-passthrough
        tool_configuration = ProviderConfigEncrypter(
            tenant_id=mcp_provider.tenant_id,
            config=list(provider_controller.get_credentials_schema()),
            provider_config_cache=NoOpProviderCredentialCache(),
        )
        credentials = tool_configuration.encrypt(credentials)
        mcp_provider.updated_at = datetime.now()
        mcp_provider.encrypted_credentials = json.dumps({**mcp_provider.credentials, **credentials})
        mcp_provider.authed = authed
        if not authed:
            mcp_provider.tools = "[]"
        db.session.commit()

<<<<<<< HEAD
        # Update provider
        provider.updated_at = datetime.now()
        provider.encrypted_credentials = json.dumps({**provider.credentials, **encrypted_credentials})

        if authed is not None:
            provider.authed = authed
            if not authed:
                provider.tools = EMPTY_TOOLS_JSON

        # Flush changes to database
        self._session.flush()

    def save_oauth_data(
        self, provider_id: str, tenant_id: str, data: dict[str, Any], data_type: OAuthDataType = OAuthDataType.MIXED
    ) -> None:
        """
        Save OAuth-related data (tokens, client info, code verifier).

        Args:
            provider_id: Provider ID
            tenant_id: Tenant ID
            data: Data to save (tokens, client info, or code verifier)
            data_type: Type of OAuth data to save
        """
        # Determine if this makes the provider authenticated
        authed = (
            data_type == OAuthDataType.TOKENS or (data_type == OAuthDataType.MIXED and "access_token" in data) or None
        )

        # update_provider_credentials will validate provider existence
        self.update_provider_credentials(provider_id=provider_id, tenant_id=tenant_id, credentials=data, authed=authed)

    def clear_provider_credentials(self, *, provider_id: str, tenant_id: str) -> None:
        """
        Clear all credentials for a provider.

        Args:
            provider_id: Provider ID
            tenant_id: Tenant ID
        """
        # Get provider from current session
        provider = self.get_provider(provider_id=provider_id, tenant_id=tenant_id)

        provider.tools = EMPTY_TOOLS_JSON
        provider.encrypted_credentials = EMPTY_CREDENTIALS_JSON
        provider.updated_at = datetime.now()
        provider.authed = False

    # ========== Private Helper Methods ==========

    def _check_provider_exists(self, tenant_id: str, name: str, server_url_hash: str, server_identifier: str) -> None:
        """Check if provider with same attributes already exists."""
        stmt = select(MCPToolProvider).where(
            MCPToolProvider.tenant_id == tenant_id,
            or_(
                MCPToolProvider.name == name,
                MCPToolProvider.server_url_hash == server_url_hash,
                MCPToolProvider.server_identifier == server_identifier,
            ),
        )
        existing_provider = self._session.scalar(stmt)

        if existing_provider:
            if existing_provider.name == name:
                raise ValueError(f"MCP tool {name} already exists")
            if existing_provider.server_url_hash == server_url_hash:
                raise ValueError("MCP tool with this server URL already exists")
            if existing_provider.server_identifier == server_identifier:
                raise ValueError(f"MCP tool {server_identifier} already exists")

    def _prepare_icon(self, icon: str, icon_type: str, icon_background: str) -> str:
        """Prepare icon data for storage."""
        if icon_type == "emoji":
            return json.dumps({"content": icon, "background": icon_background})
        return icon

    def _encrypt_dict_fields(self, data: dict[str, Any], secret_fields: list[str], tenant_id: str) -> Mapping[str, str]:
        """Encrypt specified fields in a dictionary.

        Args:
            data: Dictionary containing data to encrypt
            secret_fields: List of field names to encrypt
            tenant_id: Tenant ID for encryption

        Returns:
            JSON string of encrypted data
        """
        from core.entities.provider_entities import BasicProviderConfig
        from core.tools.utils.encryption import create_provider_encrypter

        # Create config for secret fields
        config = [
            BasicProviderConfig(type=BasicProviderConfig.Type.SECRET_INPUT, name=field) for field in secret_fields
        ]

        encrypter_instance, _ = create_provider_encrypter(
            tenant_id=tenant_id,
            config=config,
            cache=NoOpProviderCredentialCache(),
        )

        encrypted_data = encrypter_instance.encrypt(data)
        return encrypted_data

    def _prepare_encrypted_dict(self, headers: dict[str, str], tenant_id: str) -> str:
        """Encrypt headers and prepare for storage."""
        # All headers are treated as secret
        return json.dumps(self._encrypt_dict_fields(headers, list(headers.keys()), tenant_id))

    def _prepare_auth_headers(self, provider_entity: MCPProviderEntity) -> dict[str, str]:
        """Prepare headers with OAuth token if available."""
        headers = provider_entity.decrypt_headers()
        tokens = provider_entity.retrieve_tokens()
        if tokens:
            headers["Authorization"] = f"{tokens.token_type.capitalize()} {tokens.access_token}"
        return headers

    def _retrieve_remote_mcp_tools(
        self,
        server_url: str,
        headers: dict[str, str],
        provider_entity: MCPProviderEntity,
    ):
        """Retrieve tools from remote MCP server."""
        with MCPClient(
            server_url,
            provider_entity.id,
            provider_entity.tenant_id,
            authed=True,
            headers=headers,
            timeout=provider_entity.timeout,
            sse_read_timeout=provider_entity.sse_read_timeout,
        ) as mcp_client:
            return mcp_client.list_tools()

    def execute_auth_actions(self, auth_result: Any) -> dict[str, str]:
        """
        Execute the actions returned by the auth function.

        This method processes the AuthResult and performs the necessary database operations.

        Args:
            auth_result: The result from the auth function

        Returns:
            The response from the auth result
        """
        from core.mcp.entities import AuthAction, AuthActionType

        action: AuthAction
        for action in auth_result.actions:
            if action.provider_id is None or action.tenant_id is None:
                continue

            if action.action_type == AuthActionType.SAVE_CLIENT_INFO:
                self.save_oauth_data(action.provider_id, action.tenant_id, action.data, OAuthDataType.CLIENT_INFO)
            elif action.action_type == AuthActionType.SAVE_TOKENS:
                self.save_oauth_data(action.provider_id, action.tenant_id, action.data, OAuthDataType.TOKENS)
            elif action.action_type == AuthActionType.SAVE_CODE_VERIFIER:
                self.save_oauth_data(action.provider_id, action.tenant_id, action.data, OAuthDataType.CODE_VERIFIER)

        return auth_result.response

    @classmethod
    def _re_connect_mcp_provider(cls, server_url: str, provider_id: str, tenant_id: str):
        # Get the existing provider to access headers and timeout settings
        mcp_provider = cls.get_mcp_provider_by_provider_id(provider_id, tenant_id)
        headers = mcp_provider.decrypted_headers
        timeout = mcp_provider.timeout
        sse_read_timeout = mcp_provider.sse_read_timeout
>>>>>>> eam-integration-passthrough

        try:
            with MCPClient(
                server_url,
                provider_id,
                tenant_id,
                authed=False,
                for_list=True,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            ) as mcp_client:
                tools = mcp_client.list_tools()
                return {
                    "authed": True,
                    "tools": json.dumps([tool.model_dump() for tool in tools]),
                    "encrypted_credentials": "{}",
                }
        except MCPAuthError:
            return {"authed": False, "tools": "[]", "encrypted_credentials": "{}"}
        except MCPError as e:
            raise ValueError(f"Failed to re-connect MCP server: {e}") from e
