# Distribution Management System

A full-stack web application for managing device distribution across different organizational levels with role-based access control.

## 🚀 Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **MongoDB** - NoSQL database with Motor async driver
- **JWT** - JSON Web Token for authentication
- **Pydantic** - Data validation and serialization
- **Bcrypt** - Password hashing

### Frontend
- **React** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **Context API** - State management

## 📁 Project Structure

```
distribution-management-system/
├── backend/
│   ├── app/
│   │   ├── models/          # Pydantic models
│   │   ├── routes/          # API endpoints
│   │   ├── services/        # Business logic
│   │   ├── middleware/      # Auth & error handling
│   │   ├── utils/           # Helper functions
│   │   ├── schemas/         # Response schemas
│   │   ├── main.py          # FastAPI app
│   │   ├── config.py        # Settings
│   │   └── database.py      # MongoDB connection
│   ├── requirements.txt
│   ├── .env
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Page components
│   │   ├── context/         # Context providers
│   │   ├── services/        # API service layer
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/
│   │   └── favicon.svg      # Application icon
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
└── README.md
```

## 🔧 Setup Instructions

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **MongoDB Atlas account** (or local MongoDB)

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Update MongoDB connection string if needed
   - The default `.env` is already configured

5. **Run the backend server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
   ```

   Or use Python module:
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
   ```

6. **Access API documentation:**
   - Swagger UI: http://localhost:8080/docs
   - ReDoc: http://localhost:8080/redoc

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment (already configured):**
   - `.env` file is already created with correct API URL
   - Default: `VITE_API_URL=http://localhost:8080/api`

4. **Run the development server:**
   ```bash
   npm run dev
   ```

5. **Access the application:**
   - Frontend: http://localhost:5173

## 👥 Demo Accounts

| Email | Password | Role | Access Level |
|-------|----------|------|--------------|
| admin@dms.com | admin123 | Admin | Full system access |
| manager@dms.com | manager123 | Manager | Management operations |
| distributor@dms.com | dist123 | Distributor | Distribution management |
| subdist@dms.com | subdist123 | Sub Distributor | Sub-distribution management |
| operator@dms.com | operator123 | Operator | Field operations |

## 🎯 Features

### User Management
- Create, read, update, delete users
- Role-based access control (Admin, Manager, Distributor, Sub-Distributor, Operator)
- User status management (Active, Inactive, Suspended)
- Profile management

### Device Management
- Register new devices
- Track device status and location
- Device history and audit trail
- Serial number tracking
- Device holder management

### Distribution System
- Create distribution requests
- Approval workflow
- Status tracking (Pending, Approved, Delivered, Rejected)
- Distribution history

### Defect Reporting
- Report device defects
- Categorize by type and severity
- Resolution workflow
- Defect history tracking

### Return Management
- Create return requests
- Approval workflow
- Status tracking
- Return reason categorization

### Approval System
- Centralized approval dashboard
- Approve/reject distributions, returns, and defects
- Approval history and notes

### Notifications
- Real-time notifications
- Notification center
- Mark as read functionality
- Unread count badge

### Reports & Analytics
- Inventory reports
- Distribution summaries
- Defect analysis
- Return statistics
- User activity reports
- Device utilization metrics

### Dashboard
- Role-specific dashboards
- Real-time statistics
- Recent activities
- Visual charts and graphs
- System alerts

## 🔐 Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Permission-based route protection
- Token expiration and refresh
- CORS configuration
- Input validation with Pydantic

## 🌐 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user
- `PUT /api/auth/password` - Change password

### Users
- `GET /api/users` - List users (paginated)
- `GET /api/users/{id}` - Get user by ID
- `POST /api/users` - Create user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user
- `PATCH /api/users/{id}/status` - Update user status

### Devices
- `GET /api/devices` - List devices (paginated)
- `GET /api/devices/{id}` - Get device by ID
- `GET /api/devices/available` - Get available devices
- `GET /api/devices/track/{serial}` - Track by serial number
- `GET /api/devices/{id}/history` - Get device history
- `POST /api/devices` - Register device
- `PUT /api/devices/{id}` - Update device
- `DELETE /api/devices/{id}` - Delete device
- `PATCH /api/devices/{id}/status` - Update device status

### Distributions
- `GET /api/distributions` - List distributions
- `GET /api/distributions/{id}` - Get distribution by ID
- `GET /api/distributions/pending` - Get pending distributions
- `POST /api/distributions` - Create distribution
- `PATCH /api/distributions/{id}/status` - Update status
- `DELETE /api/distributions/{id}` - Cancel distribution

### Defects
- `GET /api/defects` - List defect reports
- `GET /api/defects/{id}` - Get defect by ID
- `POST /api/defects` - Create defect report
- `PUT /api/defects/{id}` - Update defect
- `PATCH /api/defects/{id}/status` - Update status
- `PATCH /api/defects/{id}/resolve` - Resolve defect
- `DELETE /api/defects/{id}` - Delete defect

### Returns
- `GET /api/returns` - List return requests
- `GET /api/returns/{id}` - Get return by ID
- `POST /api/returns` - Create return request
- `PATCH /api/returns/{id}/status` - Update status
- `DELETE /api/returns/{id}` - Cancel return

### Approvals
- `GET /api/approvals` - List pending approvals
- `GET /api/approvals/{id}` - Get approval by ID
- `POST /api/approvals/{id}/approve` - Approve request
- `POST /api/approvals/{id}/reject` - Reject request

### Operators
- `GET /api/operators` - List operators
- `GET /api/operators/{id}` - Get operator by ID
- `GET /api/operators/{id}/devices` - Get operator devices
- `POST /api/operators` - Create operator
- `PUT /api/operators/{id}` - Update operator
- `DELETE /api/operators/{id}` - Delete operator

### Notifications
- `GET /api/notifications` - List notifications
- `GET /api/notifications/unread` - Get unread count
- `PATCH /api/notifications/{id}/read` - Mark as read
- `PATCH /api/notifications/read-all` - Mark all as read
- `DELETE /api/notifications/{id}` - Delete notification

### Reports
- `GET /api/reports/inventory` - Inventory report
- `GET /api/reports/distribution-summary` - Distribution summary
- `GET /api/reports/defect-summary` - Defect summary
- `GET /api/reports/return-summary` - Return summary
- `GET /api/reports/user-activity` - User activity report
- `GET /api/reports/device-utilization` - Device utilization report

### Dashboard
- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/dashboard/recent-activities` - Recent activities
- `GET /api/dashboard/charts/distributions` - Distribution chart data
- `GET /api/dashboard/charts/defects` - Defect chart data
- `GET /api/dashboard/alerts` - System alerts

## 🚦 Running Both Servers

### Option 1: Separate Terminals

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Option 2: PowerShell Script (Windows)

Create `start.ps1` in the root directory:
```powershell
# Start backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"

# Wait a moment for backend to start
Start-Sleep -Seconds 3

# Start frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
```

Run with:
```bash
.\start.ps1
```

## 🧪 Testing

### Test Backend API
```bash
# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@dms.com","password":"admin123"}'

# Get dashboard stats (replace TOKEN with actual token)
curl http://localhost:8080/api/dashboard/stats \
  -H "Authorization: Bearer TOKEN"
```

### Test Frontend
1. Open http://localhost:5173
2. Login with demo credentials
3. Navigate through different features
4. Check browser console for any errors

## 📝 Development Notes

### Database Seeding
- Initial seed data is automatically created on first startup
- Includes 5 demo users, 20 sample devices, and example data
- To reset data, clear MongoDB collections and restart backend

### CORS Configuration
- Backend CORS is configured for `localhost:5173` and `localhost:3002`
- Update `backend/.env` if using different ports

### Environment Variables

**Backend (.env):**
```env
MONGODB_URL=mongodb+srv://...
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:5173,http://localhost:3002
```

**Frontend (.env):**
```env
VITE_API_URL=http://localhost:8080/api
```

## 🐛 Troubleshooting

### Backend Issues

**MongoDB Connection Error:**
- Check internet connection
- Verify MongoDB Atlas cluster is running
- Ensure IP address is whitelisted in MongoDB Atlas

**Port 8080 Already in Use:**
```bash
# Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8080
kill -9 <PID>
```

### Frontend Issues

**port 5173 Already in Use:**
- Change port in `frontend/vite.config.js`
- Update `CORS_ORIGINS` in backend `.env`

**API Connection Error:**
- Ensure backend is running on port 8080
- Check `.env` file has correct API URL
- Verify CORS settings in backend

**Module Not Found:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## 📦 Building for Production

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Frontend
```bash
cd frontend
npm run build
npm run preview  # Test production build
```

The build will be in `frontend/dist/` directory.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👨‍💻 Support

For issues and questions:
- Check the troubleshooting section
- Review API documentation at http://localhost:8080/docs
- Check browser console for frontend errors
- Check terminal output for backend errors

---

**Happy Coding! 🚀**
