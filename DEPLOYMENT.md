# RestroFlow Deployment Guide

## Pre-deployment Checklist ✅

### Files Ready:
- ✅ `app.py` - Main Flask application
- ✅ `database.py` - PostgreSQL/SQLite database handler
- ✅ `requirements.txt` - Python dependencies
- ✅ `Procfile` - Process configuration
- ✅ `render.yaml` - Render deployment config
- ✅ `runtime.txt` - Python version specification
- ✅ `.gitignore` - Git ignore rules
- ✅ `.env.example` - Environment variables template

### Database:
- ✅ PostgreSQL database configured (Neon)
- ✅ Connection string tested
- ✅ Database initialization working
- ✅ Fallback to SQLite if needed

### Environment Variables:
- ✅ `DATABASE_URL` - PostgreSQL connection string
- ✅ `FLASK_SECRET_KEY` - Flask session security
- ✅ `ADMIN_USER` - Admin username
- ✅ `ADMIN_PASSWORD` - Admin password

## Deployment Steps:

### 1. Push to GitHub:
```bash
git init
git add .
git commit -m "Initial deployment"
git branch -M main
git remote add origin https://github.com/yourusername/restroflow.git
git push -u origin main
```

### 2. Deploy on Render:
1. Go to [render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Render will auto-detect the `render.yaml` configuration

### 3. Verify Deployment:
- Check `/health` endpoint for database connectivity
- Login with admin credentials
- Test table management functionality

## Default Credentials:
- **Username**: `admin`
- **Password**: `supersecret`

⚠️ **Important**: Change the default password in production!

## Features:
- 🍽️ Restaurant table management
- 👥 Customer queue system
- 📊 Analytics dashboard
- 👨‍💼 Waiter management
- 📱 WhatsApp integration (optional)
- 🔄 Real-time updates

## Health Check:
- URL: `https://your-app.onrender.com/health`
- Returns database status and connectivity info