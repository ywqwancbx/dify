import React, { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { RiContractLine, RiDoorLockLine, RiErrorWarningFill } from '@remixicon/react'
import Loading from '../components/base/loading'
import MailAndCodeAuth from './components/mail-and-code-auth'
import MailAndPasswordAuth from './components/mail-and-password-auth'
import SocialAuth from './components/social-auth'
import SSOAuth from './components/sso-auth'
import cn from '@/utils/classnames'
import { invitationCheck } from '@/service/common'
import { LicenseStatus } from '@/types/feature'
import Toast from '@/app/components/base/toast'
import { IS_CE_EDITION } from '@/config'
import { useGlobalPublicStore } from '@/context/global-public-context'
import { resolvePostLoginRedirect } from './utils/post-login-redirect'
import Split from './split'
import { useIsLogin } from '@/service/use-common'

const NormalForm = () => {
  const { t } = useTranslation()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isLoading: isCheckLoading, data: loginData } = useIsLogin()
  const isLoggedIn = loginData?.logged_in
  const message = decodeURIComponent(searchParams.get('message') || '')
  const invite_token = decodeURIComponent(searchParams.get('invite_token') || '')
  const eam_token = searchParams.get('eam_token')
  const [isInitCheckLoading, setInitCheckLoading] = useState(true)
  const isLoading = isCheckLoading || loginData?.logged_in || isInitCheckLoading
  const { systemFeatures } = useGlobalPublicStore()
  const [authType, updateAuthType] = useState<'code' | 'password'>('password')
  const [showORLine, setShowORLine] = useState(false)
  const [allMethodsAreDisabled, setAllMethodsAreDisabled] = useState(false)
  const [workspaceName, setWorkSpaceName] = useState('')

  const isInviteLink = Boolean(invite_token && invite_token !== 'null')

  const init = useCallback(async () => {
    try {
      if (isLoggedIn) {
        const redirectUrl = resolvePostLoginRedirect(searchParams)
        router.replace(redirectUrl || '/apps')
        return
      }

      // 处理 EAM SSO 登录
      if (eam_token) {
        try {
          setInitCheckLoading(true)
          const response = await fetch('/api/eam-sso-login', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              token: eam_token,
            }),
          })

          if (response.ok) {
            const loginData = await response.json()
             if (loginData.access_token) {
               // 设置 localStorage（用于 Public API）
               localStorage.setItem('access_token', loginData.access_token)
               
               // 设置 Cookie（用于 Console API）
               document.cookie = `access_token=${loginData.access_token}; path=/; max-age=${loginData.expires_in || 3600}; SameSite=Lax`
               
               // 设置 CSRF token Cookie（Console API 需要）
               if (loginData.csrf_token) {
                 document.cookie = `csrf_token=${loginData.csrf_token}; path=/; max-age=${loginData.expires_in || 3600}; SameSite=Lax`
               }
               
               const redirectUrl = resolvePostLoginRedirect(searchParams)
               router.replace(redirectUrl || '/apps')
               return
             }
          }
          
          // EAM SSO 登录失败，显示错误
          Toast.notify({
            type: 'error',
            message: 'EAM SSO 登录失败，请使用其他方式登录',
          })
        } catch (error) {
          console.error('EAM SSO login error:', error)
          Toast.notify({
            type: 'error',
            message: 'EAM SSO 登录失败，请使用其他方式登录',
          })
        }
      }

      if (message) {
        Toast.notify({
          type: 'error',
          message,
        })
      }
      setAllMethodsAreDisabled(!systemFeatures.enable_social_oauth_login && !systemFeatures.enable_email_code_login && !systemFeatures.enable_email_password_login && !systemFeatures.sso_enforced_for_signin)
      setShowORLine((systemFeatures.enable_social_oauth_login || systemFeatures.sso_enforced_for_signin) && (systemFeatures.enable_email_code_login || systemFeatures.enable_email_password_login))
      updateAuthType(systemFeatures.enable_email_password_login ? 'password' : 'code')
      if (isInviteLink) {
        const checkRes = await invitationCheck({
          url: '/activate/check',
          params: {
            token: invite_token,
          },
        })
        setWorkSpaceName(checkRes?.data?.workspace_name || '')
      }
    }
    catch (error) {
      console.error(error)
      setAllMethodsAreDisabled(true)
    }
    finally { setInitCheckLoading(false) }
  }, [isLoggedIn, message, router, invite_token, isInviteLink, systemFeatures, eam_token])
  useEffect(() => {
    init()
  }, [init])
  if (isLoading) {
    return <div className={
      cn(
        'flex w-full grow flex-col items-center justify-center',
        'px-6',
        'md:px-[108px]',
      )
    }>
      <Loading type='area' />
    </div>
  }
  if (systemFeatures.license?.status === LicenseStatus.LOST) {
    return <div className='mx-auto mt-8 w-full'>
      <div className='relative'>
        <div className="rounded-lg bg-gradient-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
          <div className='shadows-shadow-lg relative mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-components-card-bg shadow'>
            <RiContractLine className='h-5 w-5' />
            <RiErrorWarningFill className='absolute -right-1 -top-1 h-4 w-4 text-text-warning-secondary' />
          </div>
          <p className='system-sm-medium text-text-primary'>{t('login.licenseLost')}</p>
          <p className='system-xs-regular mt-1 text-text-tertiary'>{t('login.licenseLostTip')}</p>
        </div>
      </div>
    </div>
  }
  if (systemFeatures.license?.status === LicenseStatus.EXPIRED) {
    return <div className='mx-auto mt-8 w-full'>
      <div className='relative'>
        <div className="rounded-lg bg-gradient-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
          <div className='shadows-shadow-lg relative mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-components-card-bg shadow'>
            <RiContractLine className='h-5 w-5' />
            <RiErrorWarningFill className='absolute -right-1 -top-1 h-4 w-4 text-text-warning-secondary' />
          </div>
          <p className='system-sm-medium text-text-primary'>{t('login.licenseExpired')}</p>
          <p className='system-xs-regular mt-1 text-text-tertiary'>{t('login.licenseExpiredTip')}</p>
        </div>
      </div>
    </div>
  }
  if (systemFeatures.license?.status === LicenseStatus.INACTIVE) {
    return <div className='mx-auto mt-8 w-full'>
      <div className='relative'>
        <div className="rounded-lg bg-gradient-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
          <div className='shadows-shadow-lg relative mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-components-card-bg shadow'>
            <RiContractLine className='h-5 w-5' />
            <RiErrorWarningFill className='absolute -right-1 -top-1 h-4 w-4 text-text-warning-secondary' />
          </div>
          <p className='system-sm-medium text-text-primary'>{t('login.licenseInactive')}</p>
          <p className='system-xs-regular mt-1 text-text-tertiary'>{t('login.licenseInactiveTip')}</p>
        </div>
      </div>
    </div>
  }

  return (
    <>
      <div className="mx-auto mt-8 w-full">
        {isInviteLink
          ? <div className="mx-auto w-full">
            <h2 className="title-4xl-semi-bold text-text-primary">{t('login.join')}{workspaceName}</h2>
            {!systemFeatures.branding.enabled && <p className='body-md-regular mt-2 text-text-tertiary'>{t('login.joinTipStart')}{workspaceName}{t('login.joinTipEnd')}</p>}
          </div>
          : <div className="mx-auto w-full">
            <h2 className="title-4xl-semi-bold text-text-primary">{systemFeatures.branding.enabled ? t('login.pageTitleForE') : t('login.pageTitle')}</h2>
            <p className='body-md-regular mt-2 text-text-tertiary'>{t('login.welcome')}</p>
          </div>}
        <div className="relative">
          <div className="mt-6 flex flex-col gap-3">
            {systemFeatures.enable_social_oauth_login && <SocialAuth />}
            {systemFeatures.sso_enforced_for_signin && <div className='w-full'>
              <SSOAuth protocol={systemFeatures.sso_enforced_for_signin_protocol} />
            </div>}
          </div>

          {showORLine && <div className="relative mt-6">
            <div className="flex items-center">
              <div className="h-px flex-1 bg-gradient-to-r from-background-gradient-mask-transparent to-divider-regular"></div>
              <span className="system-xs-medium-uppercase px-3 text-text-tertiary">{t('login.or')}</span>
              <div className="h-px flex-1 bg-gradient-to-l from-background-gradient-mask-transparent to-divider-regular"></div>
            </div>
          </div>}
          {
            (systemFeatures.enable_email_code_login || systemFeatures.enable_email_password_login) && <>
              {systemFeatures.enable_email_code_login && authType === 'code' && <>
                <MailAndCodeAuth isInvite={isInviteLink} />
                {systemFeatures.enable_email_password_login && <div className='cursor-pointer py-1 text-center' onClick={() => { updateAuthType('password') }}>
                  <span className='system-xs-medium text-components-button-secondary-accent-text'>{t('login.usePassword')}</span>
                </div>}
              </>}
              {systemFeatures.enable_email_password_login && authType === 'password' && <>
                <MailAndPasswordAuth isInvite={isInviteLink} isEmailSetup={systemFeatures.is_email_setup} allowRegistration={systemFeatures.is_allow_register} />
                {systemFeatures.enable_email_code_login && <div className='cursor-pointer py-1 text-center' onClick={() => { updateAuthType('code') }}>
                  <span className='system-xs-medium text-components-button-secondary-accent-text'>{t('login.useVerificationCode')}</span>
                </div>}
              </>}
              <Split className='mb-5 mt-4' />
            </>
          }

          {systemFeatures.is_allow_register && authType === 'password' && (
            <div className='mb-3 text-[13px] font-medium leading-4 text-text-secondary'>
              <span>{t('login.signup.noAccount')}</span>
              <Link
                className='text-text-accent'
                href='/signup'
              >{t('login.signup.signUp')}</Link>
            </div>
          )}
          {allMethodsAreDisabled && <>
            <div className="rounded-lg bg-gradient-to-r from-workflow-workflow-progress-bg-1 to-workflow-workflow-progress-bg-2 p-4">
              <div className='shadows-shadow-lg mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-components-card-bg shadow'>
                <RiDoorLockLine className='h-5 w-5' />
              </div>
              <p className='system-sm-medium text-text-primary'>{t('login.noLoginMethod')}</p>
              <p className='system-xs-regular mt-1 text-text-tertiary'>{t('login.noLoginMethodTip')}</p>
            </div>
            <div className="relative my-2 py-2">
              <div className="absolute inset-0 flex items-center" aria-hidden="true">
                <div className='h-px w-full bg-gradient-to-r from-background-gradient-mask-transparent via-divider-regular to-background-gradient-mask-transparent'></div>
              </div>
            </div>
          </>}
          {!systemFeatures.branding.enabled && <>
            <div className="system-xs-regular mt-2 block w-full text-text-tertiary">
              {t('login.tosDesc')}
              &nbsp;
              <Link
                className='system-xs-medium text-text-secondary hover:underline'
                target='_blank' rel='noopener noreferrer'
                href='#'
              >{t('login.tos')}</Link>
              &nbsp;&&nbsp;
              <Link
                className='system-xs-medium text-text-secondary hover:underline'
                target='_blank' rel='noopener noreferrer'
                href='#'
              >{t('login.pp')}</Link>
            </div>
            {IS_CE_EDITION && <div className="w-hull system-xs-regular mt-2 block text-text-tertiary">
              {t('login.goToInit')}
              &nbsp;
              <Link
                className='system-xs-medium text-text-secondary hover:underline'
                href='/install'
              >{t('login.setAdminAccount')}</Link>
            </div>}
          </>}
        </div>
      </div>
    </>
  )
}

export default NormalForm
