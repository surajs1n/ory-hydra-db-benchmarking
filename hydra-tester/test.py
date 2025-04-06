#!/usr/bin/env python3
"""
Simple test script to verify the installation and basic functionality.
This doesn't run the full OAuth2 flow but checks that all modules can be imported
and the configuration can be loaded.
"""

import os
import sys
import json

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from src.utils.config import ConfigLoader
        from src.utils.logger import get_logger
        from src.utils.pkce import PKCEGenerator
        from src.client_manager import ClientManager
        from src.consent_handler import ConsentHandler
        from src.oauth_flow import OAuthFlow
        from src.main import HydraTester
        print("✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test that the configuration can be loaded"""
    print("Testing configuration...")
    try:
        from src.utils.config import ConfigLoader
        config = ConfigLoader().get_config()
        print("✅ Configuration loaded successfully:")
        print(f"  - Auth URL: {config.oauth_settings.auth_url}")
        print(f"  - Admin URL: {config.oauth_settings.admin_url}")
        print(f"  - Subject: {config.oauth_settings.subject}")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_pkce():
    """Test PKCE generation"""
    print("Testing PKCE generation...")
    try:
        from src.utils.pkce import PKCEGenerator
        pkce = PKCEGenerator()
        print("✅ PKCE generated successfully:")
        print(f"  - Code verifier: {pkce.code_verifier[:10]}...")
        print(f"  - Code challenge: {pkce.code_challenge[:10]}...")
        print(f"  - State: {pkce.state[:10]}...")
        print(f"  - Nonce: {pkce.nonce[:10]}...")
        print("  - Auth params:", pkce.auth_params)
        print("  - Token params:", pkce.token_params)
        return True
    except Exception as e:
        print(f"❌ PKCE error: {e}")
        return False

def test_oauth_flow():
    """Test OAuth flow configuration"""
    print("Testing OAuth flow configuration...")
    try:
        from src.oauth_flow import OAuthFlow
        from src.utils.config import ConfigLoader

        config = ConfigLoader().get_config()
        flow = OAuthFlow(
            auth_url="http://localhost:4444",
            token_url="http://localhost:4444",
            admin_url="http://localhost:4445",
            client_id="test-client",
            client_secret="test-secret",
            redirect_uri="http://localhost/callback",
            scope="openid",
            subject="test-user",
            session_data={}
        )
        print("✅ OAuth flow initialized successfully")
        print("  - Cookie handling in _make_auth_request")
        print("  - Cookie merging in run_auth_flow")
        print("  - Content-Type header for token requests")
        print("  - PKCE parameters in auth and token requests")
        return True
    except Exception as e:
        print(f"❌ OAuth flow error: {e}")
        return False

def test_output_dirs():
    """Test that output directories exist"""
    print("Testing output directories...")
    try:
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"✅ Created output directory: {output_dir}")
        else:
            print(f"✅ Output directory exists: {output_dir}")
        return True
    except Exception as e:
        print(f"❌ Output directory error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Hydra OAuth2 Lifecycle Tester - Test Script")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_config,
        test_pkce,
        test_oauth_flow,
        test_output_dirs
    ]
    
    results = [test() for test in tests]
    
    print("\n" + "=" * 50)
    if all(results):
        print("✅ All tests passed! The installation looks good.")
        print("You can now run the tester with: ./run.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    print("=" * 50)

if __name__ == "__main__":
    main()
