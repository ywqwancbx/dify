import uuid
from datetime import UTC, datetime, timedelta
import json
import os

from flask import make_response, request
from flask_restx import Resource
from sqlalchemy import select
from sqlalchemy import text as sa_text
from werkzeug.exceptions import BadRequest, Unauthorized, InternalServerError, NotFound

from configs import dify_config
from controllers.web import web_ns
from core.helper import ssrf_proxy
from extensions.ext_database import db
from libs.passport import PassportService
from libs.token import generate_csrf_token
from models.model import Account
from models import Tenant, TenantAccountJoin
from services.account_service import AccountService


@web_ns.route("/eam-sso-login")
class EAMSSOLoginResource(Resource):
    """EAM SSO login resource for external authentication."""

    @web_ns.doc("eam_sso_login")
    @web_ns.doc(description="EAM SSO login for external authentication")
    @web_ns.doc(
        responses={
            200: "EAM SSO login successful",
            400: "Bad request - missing token",
            401: "Unauthorized - invalid token or verification failed",
            500: "Internal server error",
        }
    )
    def post(self):
        """EAM SSO login endpoint."""
        # 获取请求参数
        data = request.get_json()
        if not data:
            raise BadRequest("Request body is required.")
        
        token = data.get('token')
        if not token:
            raise BadRequest("Token is required.")
        
        try:
            # 1. 验证EAM Token
            eam_user_info = self._verify_eam_token(token)
            
            # 2. 获取或创建Account用户
            account = self._get_or_create_account(eam_user_info)
            
            # 3. 生成Dify登录token
            dify_token = self._generate_dify_login_token(account)
            
            # 4. 生成 CSRF token
            csrf_token = self._generate_csrf_token(account.id)
            
            # 5. 创建响应并设置Cookie（像标准登录一样）
            response = make_response({
                "result": "success",
                "access_token": dify_token,
                "csrf_token": csrf_token,
                "user_id": account.id,
                "external_user_id": eam_user_info.get('user_id'),
                "expires_in": dify_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            })
            
            # 设置Cookie（像标准登录一样）
            from libs.token import set_access_token_to_cookie, set_csrf_token_to_cookie
            set_access_token_to_cookie(request, response, dify_token)
            set_csrf_token_to_cookie(request, response, csrf_token)
            
            return response
            
        except Exception as e:
            raise InternalServerError(f"EAM SSO login failed: {str(e)}")
    
    def _verify_eam_token(self, token: str) -> dict:
        """验证EAM Token并获取用户信息."""
        # 从环境变量获取EAM验证URL（必须配置）
        eam_verify_url = os.environ.get('EAM_VERIFY_URL')
        if not eam_verify_url:
            raise InternalServerError("EAM_VERIFY_URL is not configured.")
        
        
        try:
            # 使用SSRF代理调用EAM Server验证接口
            response = ssrf_proxy.post(
                eam_verify_url,
                json={'token': token},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            
            if response.status_code != 200:
                raise Unauthorized(f"EAM token verification failed: {response.status_code}")
            
            response_data = response.json()
            
            # 处理EAM Server的响应格式
            if response_data.get('success') and response_data.get('data'):
                user_info = response_data['data']
            else:
                # 如果格式不匹配，尝试直接使用响应数据
                user_info = response_data
            
            # 验证返回的用户信息
            if not user_info.get('user_id'):
                raise Unauthorized("Invalid user information from EAM.")
            
            return user_info
            
        except Exception as e:
            raise Unauthorized(f"Failed to verify EAM token: {str(e)}")
    
    def _get_or_create_account(self, eam_user_info: dict) -> Account:
        """获取或创建Account用户.

        匹配策略：
        1) 若提供了 email，则优先用 email 查找；找不到再用伪邮箱(user_id@eam.user)兜底，找到后把邮箱更新为真实 email。
        2) 若未提供 email，则用稳定的伪邮箱 user_id@eam.user 作为唯一键，确保幂等。
        """
        external_user_id = str(eam_user_info.get('user_id'))
        username = eam_user_info.get('username', f'user_{external_user_id}')
        provided_email = (eam_user_info.get('email') or '').strip() or None
        pseudo_email = f"{external_user_id}@eam.user"
        
        # 优先按 external 映射（基于 user_id）查找
        account = self._get_account_by_external("EAM", external_user_id)
        
        # 若未命中映射，则优先用伪邮箱；仍未命中再用真实邮箱
        if not account:
            account = db.session.scalar(select(Account).where(Account.email == pseudo_email))
        if not account and provided_email:
            account = db.session.scalar(select(Account).where(Account.email == provided_email))
        
        if account:
            # 更新用户信息（名称；以及当提供真实邮箱且当前为伪邮箱时，迁移到真实邮箱）
            account.name = username
            if provided_email and account.email != provided_email:
                account.email = provided_email
            db.session.commit()
            
            # 检查是否有关联的Tenant，如果没有则创建
            existing_tenant_join = db.session.scalar(
                select(TenantAccountJoin).where(TenantAccountJoin.account_id == account.id)
            )
            if not existing_tenant_join:
                self._create_default_tenant_for_account(account)
            # 绑定 external 映射（幂等 upsert）
            self._bind_external_to_account("EAM", external_user_id, account.id)
        else:
            # 创建新的Account
            account = Account(
                name=username,
                email=(provided_email or pseudo_email),
                password='',  # 外部用户不需要密码
                status='active',
                interface_language='en-US'
            )
            
            db.session.add(account)
            db.session.commit()
            
            # 创建默认的Tenant和TenantAccountJoin记录
            self._create_default_tenant_for_account(account)
            # 绑定 external 映射
            self._bind_external_to_account("EAM", external_user_id, account.id)
        
        return account

    def _get_account_by_external(self, source: str, external_user_id: str) -> Account | None:
        row = db.session.execute(
            sa_text(
                """
                SELECT account_id FROM external_account_links
                WHERE external_source = :source AND external_user_id = :ext
                LIMIT 1
                """
            ),
            {"source": source, "ext": external_user_id},
        ).first()
        if not row:
            return None
        account_id = row[0]
        return db.session.scalar(select(Account).where(Account.id == account_id))

    def _bind_external_to_account(self, source: str, external_user_id: str, account_id: str):
        db.session.execute(
            sa_text(
                """
                INSERT INTO external_account_links (id, external_source, external_user_id, account_id)
                VALUES (:id, :source, :ext, :acc)
                ON CONFLICT (external_source, external_user_id)
                DO UPDATE SET account_id = EXCLUDED.account_id
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "source": source,
                "ext": external_user_id,
                "acc": account_id,
            },
        )
        db.session.commit()
    
    def _create_default_tenant_for_account(self, account: Account):
        """为Account创建默认的Tenant和TenantAccountJoin记录."""
        try:
            # 创建默认Tenant
            tenant = Tenant(
                name=f"{account.name}'s Workspace",
                status='active'
            )
            db.session.add(tenant)
            db.session.commit()
            
            # 创建TenantAccountJoin记录
            tenant_account_join = TenantAccountJoin(
                tenant_id=tenant.id,
                account_id=account.id,
                role='owner',
                current=True
            )
            db.session.add(tenant_account_join)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            raise
    
    def _generate_dify_login_token(self, account: Account) -> str:
        """生成Dify标准登录token."""
        # 使用AccountService生成标准的Dify登录token
        token = AccountService.get_account_jwt_token(account)
        return token
    
    def _generate_csrf_token(self, user_id: str) -> str:
        """生成CSRF token."""
        csrf_token = generate_csrf_token(user_id)
        return csrf_token
