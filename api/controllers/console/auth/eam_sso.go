package controllers

import (
	"git.acceptplay.com/admin/api/modules/ai/service"
	"git.acceptplay.com/admin/library/logging"
	"git.acceptplay.com/admin/library/utils"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// EAMSSOController EAM SSO控制器
type EAMSSOController struct {
	DifyService *service.Dify
}

// EAMSSOLoginRequest EAM SSO登录请求
type EAMSSOLoginRequest struct {
	Token string `json:"token" binding:"required"`
	AppID string `json:"app_id,omitempty"`
}

// EAMSSOLoginResponse EAM SSO登录响应
type EAMSSOLoginResponse struct {
	AccessToken string `json:"access_token"`
	User        struct {
		ID       int64  `json:"id"`
		Username string `json:"username"`
		Email    string `json:"email"`
	} `json:"user"`
	ExpiresIn int64 `json:"expires_in"`
}

// EAMSSOLogin EAM SSO登录
// @Summary EAM SSO登录
// @Description 通过EAM JWT令牌进行SSO登录，自动创建或获取Dify用户
// @Tags EAMSSOControllers
// @Accept json
// @Produce json
// @Param request body EAMSSOLoginRequest true "登录请求"
// @Success 200 {object} utils.ResponseResult{data=EAMSSOLoginResponse}
// @Failure 400 {object} utils.ResponseResult
// @Failure 401 {object} utils.ResponseResult
// @Failure 500 {object} utils.ResponseResult
// @Router /api/console/auth/eam-sso [post]
func (e *EAMSSOController) EAMSSOLogin(c *gin.Context) {
	ctx := c.Request.Context()
	logger := logging.Context(ctx)
	logger.Info("收到EAM SSO登录请求")

	var req EAMSSOLoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		logger.Error("请求参数绑定失败", zap.Error(err))
		utils.ResError(c, utils.BadRequest("", "无效的请求参数"))
		return
	}

	logger.Info("开始EAM SSO登录流程", zap.String("app_id", req.AppID))

	// 1. 验证EAM JWT Token
	eamUser, err := e.DifyService.VerifyEAMToken(ctx, req.Token)
	if err != nil {
		logger.Error("EAM Token验证失败", zap.Error(err))
		utils.ResError(c, utils.Unauthorized("", "EAM认证失败"))
		return
	}

	logger.Info("EAM Token验证成功",
		zap.Int64("user_id", eamUser.Id),
		zap.String("username", eamUser.Username))

	// 2. 查找或创建Dify用户
	difyUser, err := e.DifyService.FindOrCreateDifyUser(ctx, eamUser)
	if err != nil {
		logger.Error("查找或创建Dify用户失败", zap.Error(err))
		utils.ResError(c, utils.InternalServerError("", "用户处理失败"))
		return
	}

	logger.Info("Dify用户处理成功",
		zap.Int64("dify_user_id", difyUser.Id),
		zap.String("username", difyUser.Username))

	// 3. 生成Dify访问Token
	accessToken, expiresIn, err := e.DifyService.GenerateDifyAccessToken(ctx, difyUser)
	if err != nil {
		logger.Error("生成Dify访问Token失败", zap.Error(err))
		utils.ResError(c, utils.InternalServerError("", "Token生成失败"))
		return
	}

	logger.Info("Dify访问Token生成成功", zap.Int64("expires_in", expiresIn))

	// 4. 返回登录响应
	response := EAMSSOLoginResponse{
		AccessToken: accessToken,
		ExpiresIn:   expiresIn,
	}
	response.User.ID = difyUser.Id
	response.User.Username = difyUser.Username
	response.User.Email = difyUser.Email

	logger.Info("EAM SSO登录完成", zap.Int64("user_id", difyUser.Id))
	utils.ResSuccess(c, response)
}
