# RestroFlow Frontend

React frontend for the RestroFlow Restaurant Management System.

## 🚀 Features

- **Modern React UI** - Clean, responsive design
- **Real-time Dashboard** - Live updates every 30 seconds
- **Table Management** - Visual table status and controls
- **Customer Queue** - Manage waiting customers
- **Waiter Management** - Add and manage staff
- **Mobile Responsive** - Works on all devices

## 🛠️ Tech Stack

- **React 18** - Frontend framework
- **React Router** - Client-side routing
- **Axios** - HTTP client for API calls
- **CSS3** - Modern styling with CSS variables

## 📦 Deployment on Render

### Option 1: Automatic Deployment (Recommended)

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "React frontend ready for deployment"
   git push origin main
   ```

2. **Deploy on Render**:
   - Go to [render.com](https://render.com)
   - Click "New +" → "Static Site"
   - Connect your GitHub repository
   - Select the `frontend` folder as root directory
   - Render will auto-detect React and deploy

### Option 2: Manual Configuration

If auto-detection doesn't work:

- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `build`
- **Environment Variables**:
  - `REACT_APP_API_URL`: `https://your-backend-url.onrender.com`

## 🔧 Local Development

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Set environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your backend URL
   ```

3. **Start development server**:
   ```bash
   npm start
   ```

4. **Open browser**: http://localhost:3000

## 🌐 Environment Variables

- `REACT_APP_API_URL` - Backend API URL (required)

## 📱 Demo Credentials

- **Username**: `admin`
- **Password**: `supersecret`

## 🔗 API Integration

The frontend connects to your Flask backend API:

- **Login**: `POST /login`
- **Dashboard Data**: `GET /api/dashboard_data`
- **Table Actions**: `POST /free_table`, `POST /block_table`
- **Customer Management**: `POST /add_customer`, `POST /remove_customer`
- **Waiter Management**: `POST /admin/add_waiter`

## 📊 Features Overview

### Dashboard
- Real-time statistics
- System status indicators
- Auto-refresh functionality

### Table Management
- Visual table grid
- Click to change status
- Add new tables
- Color-coded status (Free/Occupied/Blocked)

### Customer Queue
- Live customer list
- Wait time tracking
- Add/remove customers
- Queue statistics

### Quick Actions
- Add waiters
- Toggle auto-seating
- System health check

## 🎨 UI/UX Features

- **Professional Design** - Clean, modern interface
- **Responsive Layout** - Mobile-first design
- **Real-time Updates** - Live data refresh
- **Interactive Elements** - Hover effects and animations
- **Status Indicators** - Visual feedback for all actions
- **Modal Forms** - Clean form interfaces
- **Error Handling** - User-friendly error messages

## 🚀 Production Ready

- Optimized build process
- Environment-based configuration
- Error boundaries
- Loading states
- Responsive design
- SEO-friendly routing