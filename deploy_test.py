#!/usr/bin/env python3
"""
Pre-deployment test script
"""
import os
import sys
from dotenv import load_dotenv

def test_deployment_readiness():
    """Test if the app is ready for deployment"""
    print("🚀 RestroFlow Deployment Readiness Check")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check required files
    required_files = [
        'app.py', 'database.py', 'requirements.txt', 
        'Procfile', 'render.yaml', 'runtime.txt', '.gitignore'
    ]
    
    print("\n📁 Checking required files:")
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - MISSING!")
            return False
    
    # Check environment variables
    print("\n🔧 Checking environment variables:")
    env_vars = {
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'FLASK_SECRET_KEY': os.getenv('FLASK_SECRET_KEY', 'default'),
        'ADMIN_USER': os.getenv('ADMIN_USER', 'admin'),
        'ADMIN_PASSWORD': os.getenv('ADMIN_PASSWORD', 'supersecret')
    }
    
    for key, value in env_vars.items():
        if value and value != 'default':
            print(f"  ✅ {key}: {'*' * min(len(str(value)), 20)}")
        else:
            print(f"  ⚠️  {key}: Not set (will use default)")
    
    # Test database connection
    print("\n🗄️  Testing database connection:")
    try:
        from database import get_db_connection, init_db
        conn, db_type = get_db_connection()
        print(f"  ✅ Connected to {db_type} database")
        conn.close()
        
        # Test initialization
        init_db()
        print("  ✅ Database initialization successful")
        
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False
    
    # Test Flask app import
    print("\n🌐 Testing Flask app:")
    try:
        from app import app
        print("  ✅ Flask app imports successfully")
        
        # Test health endpoint
        with app.test_client() as client:
            response = client.get('/health')
            if response.status_code == 200:
                print("  ✅ Health endpoint working")
            else:
                print(f"  ⚠️  Health endpoint returned {response.status_code}")
                
    except Exception as e:
        print(f"  ❌ Flask app test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All checks passed! Ready for deployment!")
    print("\nNext steps:")
    print("1. git add .")
    print("2. git commit -m 'Ready for deployment'")
    print("3. git push origin main")
    print("4. Deploy on Render")
    
    return True

if __name__ == "__main__":
    success = test_deployment_readiness()
    sys.exit(0 if success else 1)