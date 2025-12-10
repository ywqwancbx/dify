#!/usr/bin/env python3
"""
测试Dify外部登录流程的脚本
"""
import requests
import json
import sys

def test_external_login():
    """测试外部登录流程"""
    
    # 配置
    eam_server_url = "http://10.8.8.2:8000"
    dify_server_url = "http://10.8.8.2:8080"
    dify_web_url = "http://10.8.8.2:8080"
    
    # 测试用的EAM token（需要先获取）
    test_token = "your-test-token-here"
    test_app_id = "your-app-id-here"
    
    print("=== Dify外部登录流程测试 ===")
    
    # 1. 测试EAM Server的验证接口
    print("\n1. 测试EAM Server验证接口...")
    try:
        eam_verify_url = f"{eam_server_url}/api/v1/ai/dify/verify"
        response = requests.post(
            eam_verify_url,
            json={'token': test_token},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"✓ EAM验证成功: {user_info}")
        else:
            print(f"✗ EAM验证失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ EAM验证异常: {str(e)}")
        return False
    
    # 2. 测试Dify Server的外部登录接口
    print("\n2. 测试Dify Server外部登录接口...")
    try:
        dify_external_login_url = f"{dify_server_url}/api/webapp/external-login"
        response = requests.post(
            dify_external_login_url,
            json={
                'token': test_token,
                'app_id': test_app_id
            },
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            login_data = response.json()
            print(f"✓ Dify外部登录成功: {login_data}")
            access_token = login_data.get('access_token')
        else:
            print(f"✗ Dify外部登录失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Dify外部登录异常: {str(e)}")
        return False
    
    # 3. 测试Dify Web的auth页面
    print("\n3. 测试Dify Web auth页面...")
    try:
        auth_url = f"{dify_web_url}/auth?token={test_token}&app_id={test_app_id}&redirect_url=/chat"
        response = requests.get(auth_url, timeout=10)
        
        if response.status_code == 200:
            print(f"✓ Dify Web auth页面可访问")
        else:
            print(f"✗ Dify Web auth页面访问失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Dify Web auth页面异常: {str(e)}")
        return False
    
    print("\n=== 测试完成 ===")
    print("外部登录流程基本功能正常！")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("使用方法:")
            print("  python test_external_login.py")
            print("  python test_external_login.py --help")
            print("\n注意: 需要先配置正确的EAM token和app_id")
            sys.exit(0)
    
    success = test_external_login()
    sys.exit(0 if success else 1)
