# Distribution Management System - Backend Specification

## Technology Stack
- **Framework**: Python FastAPI 0.100+
- **Database**: MongoDB (Cloud Atlas)
- **Authentication**: JWT (JSON Web Tokens)
- **ORM/ODM**: Motor (async MongoDB driver) + Pydantic
- **Security**: bcrypt for password hashing, python-jose for JWT
- **Validation**: Pydantic models
- **CORS**: FastAPI CORS middleware
- **Environment**: python-dotenv for configuration

## MongoDB Connection
```
mongodb+srv://dms_db_user:WK56LWAAoBquBnCI@cluster0.gzmwm30.mongodb.net/?appName=Cluster0
Database Name: distribution_management_system
```

## Project Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app initialization
│   ├── config.py               # Configuration and environment variables
│   ├── database.py             # MongoDB connection and setup
│   │
│   ├── models/                 # Pydantic models (schemas)
│   │   ├── __init__.py
│   │   ├── user.py            # User, UserRole, UserCreate, UserUpdate
│   │   ├── device.py          # Device, DeviceCreate, DeviceUpdate, DeviceStatus
│   │   ├── distribution.py    # Distribution, DistributionCreate, DistributionUpdate
│   │   ├── defect.py          # DefectReport, DefectCreate, DefectUpdate
│   │   ├── return_device.py   # ReturnRequest, ReturnCreate, ReturnUpdate
│   │   ├── operator.py        # Operator, OperatorCreate, OperatorUpdate
│   │   ├── approval.py        # Approval, ApprovalCreate, ApprovalUpdate
│   │   ├── notification.py    # Notification, NotificationCreate
│   │   └── auth.py            # Token, TokenData, LoginRequest
│   │
│   ├── schemas/               # Response schemas
│   │   ├── __init__.py
│   │   └── responses.py       # StandardResponse, PaginatedResponse, ErrorResponse
│   │
│   ├── services/              # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py    # Authentication, JWT creation/validation
│   │   ├── user_service.py    # User CRUD operations
│   │   ├── device_service.py  # Device management, tracking, history
│   │   ├── distribution_service.py  # Distribution workflows
│   │   ├── defect_service.py  # Defect report management
│   │   ├── return_service.py  # Return request handling
│   │   ├── approval_service.py  # Approval workflows
│   │   ├── operator_service.py  # Operator management
│   │   ├── notification_service.py  # Notification handling
│   │   └── report_service.py  # Analytics and reporting
│   │
│   ├── routes/                # API endpoints (routers)
│   │   ├── __init__.py
│   │   ├── auth.py            # POST /auth/login, /auth/logout, /auth/refresh
│   │   ├── users.py           # CRUD for users
│   │   ├── devices.py         # CRUD for devices, tracking
│   │   ├── distributions.py   # CRUD for distributions
│   │   ├── defects.py         # CRUD for defect reports
│   │   ├── returns.py         # CRUD for return requests
│   │   ├── approvals.py       # Approval operations
│   │   ├── operators.py       # CRUD for operators
│   │   ├── notifications.py   # Notification endpoints
│   │   ├── reports.py         # Analytics and reports
│   │   └── dashboard.py       # Dashboard statistics
│   │
│   ├── middleware/            # Custom middleware
│   │   ├── __init__.py
│   │   ├── auth_middleware.py  # JWT validation
│   │   └── error_handler.py   # Global error handling
│   │
│   └── utils/                 # Utility functions
│       ├── __init__.py
│       ├── security.py        # Password hashing, JWT utilities
│       ├── permissions.py     # Role-based access control
│       └── helpers.py         # Common helper functions
│
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .env                      # Actual environment variables (gitignored)
├── .gitignore               # Git ignore file
└── README.md                # Backend documentation
```

## Core Models (MongoDB Collections)

### 1. Users Collection
```python
{
    "_id": ObjectId,
    "email": str,              # Unique, indexed
    "password_hash": str,      # bcrypt hashed
    "name": str,
    "role": str,              # admin, manager, distributor, sub_distributor, operator
    "phone": str,
    "department": str,        # Optional
    "location": str,          # Optional
    "status": str,            # active, inactive, suspended
    "is_verified": bool,
    "created_at": datetime,
    "updated_at": datetime,
    "last_login": datetime
}
```

### 2. Devices Collection
```python
{
    "_id": ObjectId,
    "device_id": str,         # Unique device identifier (e.g., ONU-2024-0001)
    "device_type": str,       # ONU, ONT, Router, Switch, etc.
    "model": str,
    "serial_number": str,     # Unique
    "mac_address": str,       # Unique
    "manufacturer": str,
    "status": str,            # available, distributed, in_use, defective, returned
    "current_location": str,  # Current location/holder
    "current_holder_id": ObjectId,  # Reference to User
    "current_holder_type": str,     # noc, distributor, sub_distributor, operator
    "purchase_date": datetime,
    "warranty_expiry": datetime,
    "created_at": datetime,
    "updated_at": datetime,
    "metadata": dict          # Additional device-specific data
}
```

### 3. Distributions Collection
```python
{
    "_id": ObjectId,
    "distribution_id": str,   # Unique (e.g., DIST-2024-0001)
    "device_ids": [ObjectId], # Array of device references
    "device_count": int,
    "from_user_id": ObjectId,
    "from_user_name": str,
    "from_user_type": str,    # noc, distributor, sub_distributor
    "to_user_id": ObjectId,
    "to_user_name": str,
    "to_user_type": str,      # distributor, sub_distributor, operator
    "status": str,            # pending, approved, in_transit, delivered, rejected, cancelled
    "request_date": datetime,
    "approval_date": datetime,
    "delivery_date": datetime,
    "notes": str,
    "approved_by": ObjectId,  # User who approved
    "created_by": ObjectId,
    "created_at": datetime,
    "updated_at": datetime
}
```

### 4. Defect Reports Collection
```python
{
    "_id": ObjectId,
    "report_id": str,         # Unique (e.g., DEFECT-2024-0001)
    "device_id": ObjectId,
    "device_serial": str,
    "device_type": str,
    "reported_by": ObjectId,
    "reported_by_name": str,
    "defect_type": str,       # hardware, software, physical_damage, performance
    "severity": str,          # critical, high, medium, low
    "description": str,
    "symptoms": str,
    "status": str,            # reported, under_review, approved, rejected, resolved
    "resolution": str,        # Optional
    "resolved_by": ObjectId,  # Optional
    "resolved_at": datetime,  # Optional
    "images": [str],          # Array of image URLs
    "created_at": datetime,
    "updated_at": datetime
}
```

### 5. Return Requests Collection
```python
{
    "_id": ObjectId,
    "return_id": str,         # Unique (e.g., RETURN-2024-0001)
    "device_id": ObjectId,
    "device_serial": str,
    "device_type": str,
    "requested_by": ObjectId,
    "requested_by_name": str,
    "return_to": ObjectId,    # User to return to
    "return_to_name": str,
    "reason": str,            # defective, unused, end_of_contract, other
    "description": str,
    "status": str,            # pending, approved, in_transit, received, rejected, cancelled
    "request_date": datetime,
    "approval_date": datetime,
    "received_date": datetime,
    "approved_by": ObjectId,
    "created_at": datetime,
    "updated_at": datetime
}
```

### 6. Operators Collection
```python
{
    "_id": ObjectId,
    "operator_id": str,       # Unique (e.g., OP-2024-0001)
    "name": str,
    "phone": str,
    "email": str,
    "address": str,
    "area": str,
    "city": str,
    "assigned_to": ObjectId,  # Sub-distributor managing this operator
    "assigned_to_name": str,
    "status": str,            # active, inactive, suspended
    "device_count": int,      # Current devices assigned
    "connection_type": str,   # fiber, broadband, etc.
    "created_at": datetime,
    "updated_at": datetime
}
```

### 7. Device History Collection
```python
{
    "_id": ObjectId,
    "device_id": ObjectId,
    "action": str,            # registered, distributed, returned, defect_reported, status_changed
    "from_user_id": ObjectId,
    "from_user_name": str,
    "to_user_id": ObjectId,
    "to_user_name": str,
    "status_before": str,
    "status_after": str,
    "location": str,
    "notes": str,
    "performed_by": ObjectId,
    "timestamp": datetime
}
```

### 8. Approvals Collection
```python
{
    "_id": ObjectId,
    "approval_type": str,     # distribution, return, defect
    "entity_id": ObjectId,    # Reference to Distribution/Return/Defect
    "entity_type": str,
    "requested_by": ObjectId,
    "requested_by_name": str,
    "status": str,            # pending, approved, rejected
    "priority": str,          # high, medium, low
    "request_date": datetime,
    "approved_by": ObjectId,
    "approved_by_name": str,
    "approval_date": datetime,
    "rejection_reason": str,
    "notes": str,
    "created_at": datetime,
    "updated_at": datetime
}
```

### 9. Notifications Collection
```python
{
    "_id": ObjectId,
    "user_id": ObjectId,
    "title": str,
    "message": str,
    "type": str,              # info, success, warning, error
    "category": str,          # distribution, return, defect, approval, system
    "is_read": bool,
    "link": str,              # Optional link to related resource
    "metadata": dict,
    "created_at": datetime
}
```

## API Endpoints Mapping

### Authentication Routes (`/api/auth`)
| Method | Endpoint | Description | Frontend Page |
|--------|----------|-------------|---------------|
| POST | `/auth/login` | User login | Login.jsx |
| POST | `/auth/logout` | User logout | All pages |
| POST | `/auth/refresh` | Refresh JWT token | - |
| GET | `/auth/me` | Get current user info | Profile.jsx |

### User Routes (`/api/users`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/users` | List all users (paginated) | Users.jsx | admin, manager |
| GET | `/users/{id}` | Get user by ID | Users.jsx, Profile.jsx | all |
| POST | `/users` | Create new user | Users.jsx | admin, manager |
| PUT | `/users/{id}` | Update user | Users.jsx, Profile.jsx | admin, manager |
| DELETE | `/users/{id}` | Delete user | Users.jsx | admin |
| PATCH | `/users/{id}/status` | Change user status | Users.jsx | admin |
| GET | `/users/role/{role}` | Get users by role | - | admin, manager |
| PUT | `/users/{id}/password` | Change password | Settings.jsx | all |

### Device Routes (`/api/devices`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/devices` | List all devices (paginated, filtered) | Devices.jsx | all |
| GET | `/devices/{id}` | Get device details | Devices.jsx, TrackDevice.jsx | all |
| POST | `/devices` | Register new device | RegisterDevice.jsx | admin, manager |
| PUT | `/devices/{id}` | Update device | Devices.jsx | admin, manager |
| DELETE | `/devices/{id}` | Delete device | Devices.jsx | admin |
| GET | `/devices/{id}/history` | Get device history | TrackDevice.jsx | all |
| GET | `/devices/track/{serial}` | Track device by serial | TrackDevice.jsx | all |
| GET | `/devices/available` | Get available devices | CreateDistribution.jsx | all |
| PATCH | `/devices/{id}/status` | Update device status | - | all |

### Distribution Routes (`/api/distributions`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/distributions` | List distributions (filtered by user role) | Distributions.jsx | all |
| GET | `/distributions/{id}` | Get distribution details | Distributions.jsx | all |
| POST | `/distributions` | Create distribution request | CreateDistribution.jsx | admin, manager, distributor |
| PUT | `/distributions/{id}` | Update distribution | Distributions.jsx | admin, manager |
| DELETE | `/distributions/{id}` | Cancel distribution | Distributions.jsx | creator only |
| PATCH | `/distributions/{id}/status` | Update distribution status | Distributions.jsx | all |
| GET | `/distributions/pending` | Get pending distributions | Approvals.jsx | all |

### Defect Report Routes (`/api/defects`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/defects` | List defect reports (filtered) | DefectReports.jsx | all |
| GET | `/defects/{id}` | Get defect details | DefectReports.jsx | all |
| POST | `/defects` | Create defect report | CreateDefectReport.jsx | all |
| PUT | `/defects/{id}` | Update defect report | DefectReports.jsx | admin, manager |
| DELETE | `/defects/{id}` | Delete defect report | DefectReports.jsx | admin |
| PATCH | `/defects/{id}/status` | Update defect status | DefectReports.jsx | admin, manager |
| PATCH | `/defects/{id}/resolve` | Resolve defect | DefectReports.jsx | admin, manager |

### Return Request Routes (`/api/returns`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/returns` | List return requests (filtered) | Returns.jsx | all |
| GET | `/returns/{id}` | Get return details | Returns.jsx | all |
| POST | `/returns` | Create return request | CreateReturn.jsx | all |
| PUT | `/returns/{id}` | Update return request | Returns.jsx | admin, manager |
| DELETE | `/returns/{id}` | Cancel return request | Returns.jsx | creator only |
| PATCH | `/returns/{id}/status` | Update return status | Returns.jsx | all |

### Approval Routes (`/api/approvals`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/approvals` | List pending approvals | Approvals.jsx | all with approval rights |
| GET | `/approvals/{id}` | Get approval details | Approvals.jsx | all |
| POST | `/approvals/{id}/approve` | Approve request | Approvals.jsx | admin, manager, distributor |
| POST | `/approvals/{id}/reject` | Reject request | Approvals.jsx | admin, manager, distributor |

### Operator Routes (`/api/operators`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/operators` | List operators (filtered by assigned user) | SubDistributorDashboard.jsx | sub_distributor |
| GET | `/operators/{id}` | Get operator details | SubDistributorDashboard.jsx | sub_distributor |
| POST | `/operators` | Create operator | SubDistributorDashboard.jsx | sub_distributor |
| PUT | `/operators/{id}` | Update operator | SubDistributorDashboard.jsx | sub_distributor |
| DELETE | `/operators/{id}` | Delete operator | SubDistributorDashboard.jsx | sub_distributor |
| GET | `/operators/{id}/devices` | Get devices assigned to operator | SubDistributorDashboard.jsx | sub_distributor |

### Notification Routes (`/api/notifications`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/notifications` | List user notifications | Navbar.jsx | all |
| GET | `/notifications/unread` | Get unread count | Navbar.jsx | all |
| PATCH | `/notifications/{id}/read` | Mark as read | Navbar.jsx | all |
| PATCH | `/notifications/read-all` | Mark all as read | Navbar.jsx | all |
| DELETE | `/notifications/{id}` | Delete notification | Navbar.jsx | all |

### Report Routes (`/api/reports`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/reports/inventory` | Device inventory report | Reports.jsx | admin, manager |
| GET | `/reports/distribution-summary` | Distribution summary | Reports.jsx | admin, manager |
| GET | `/reports/defect-summary` | Defect summary report | Reports.jsx | admin, manager |
| GET | `/reports/return-summary` | Return summary report | Reports.jsx | admin, manager |
| GET | `/reports/user-activity` | User activity report | Reports.jsx | admin, manager |
| GET | `/reports/device-utilization` | Device utilization | Reports.jsx | admin, manager |
| POST | `/reports/export` | Export report (CSV/PDF) | Reports.jsx | admin, manager |

### Dashboard Routes (`/api/dashboard`)
| Method | Endpoint | Description | Frontend Page | Roles |
|--------|----------|-------------|---------------|-------|
| GET | `/dashboard/stats` | Get role-based stats | All Dashboard pages | all |
| GET | `/dashboard/recent-activities` | Recent activities | Dashboard pages | all |
| GET | `/dashboard/charts/distributions` | Distribution chart data | AdminDashboard.jsx | admin |
| GET | `/dashboard/charts/defects` | Defect trend data | ManagerDashboard.jsx | manager |
| GET | `/dashboard/alerts` | System alerts | Dashboard pages | all |

## Authentication & Authorization

### JWT Token Structure
```python
{
    "sub": user_id,           # Subject (user ID)
    "email": user_email,
    "role": user_role,
    "name": user_name,
    "exp": expiration_time,   # 24 hours
    "iat": issued_at_time,
    "type": "access"          # or "refresh"
}
```

### Role-Based Access Control (RBAC)

#### Admin
- Full access to all endpoints
- User management
- System configuration
- All reports and analytics

#### Manager
- View all devices, distributions, defects, returns
- Approve/reject requests
- Generate reports
- Cannot delete users or modify admin settings

#### Distributor
- Manage distributions to sub-distributors
- View assigned devices
- Create distribution requests
- Approve sub-distributor requests
- Report defects
- Request returns

#### Sub-Distributor
- Manage operators
- Distribute devices to operators
- View assigned devices
- Report defects
- Request returns from operators

#### Operator
- View assigned devices
- Report defects
- Request device returns
- View own activity

## Key Features & Business Logic

### 1. Device Tracking System
- Real-time device location tracking
- Complete history trail from NOC → Distributor → Sub-Distributor → Operator
- Status updates: available → distributed → in_use → defective → returned
- Automatic history logging on every status change

### 2. Distribution Workflow
- Request creation (from higher level to lower level)
- Approval system (requires approval from admin/manager/distributor)
- Status tracking: pending → approved → in_transit → delivered
- Automatic device assignment on delivery
- Notification system for all parties

### 3. Defect Management
- Report creation with images
- Severity classification
- Status tracking: reported → under_review → approved → resolved
- Automatic device status update to "defective"
- Resolution tracking

### 4. Return System
- Return request creation
- Approval workflow
- Status tracking: pending → approved → in_transit → received
- Automatic device reassignment
- Device condition verification

### 5. Notification System
- Real-time notifications for:
  - New distribution requests
  - Approval/rejection updates
  - Device status changes
  - Defect reports
  - Return requests
  - System alerts
- Unread count tracking
- Mark as read functionality

### 6. Analytics & Reporting
- Device inventory reports
- Distribution analytics
- Defect trend analysis
- Return statistics
- User activity tracking
- Device utilization metrics
- Export to CSV/PDF

## Security Requirements

1. **Password Security**
   - bcrypt hashing with salt rounds = 12
   - Minimum 8 characters, must include uppercase, lowercase, number

2. **JWT Security**
   - Access token: 24 hours expiry
   - Refresh token: 7 days expiry
   - Secure HTTP-only cookies (production)
   - Token blacklisting on logout

3. **API Security**
   - Rate limiting: 100 requests/minute per IP
   - CORS configuration for frontend origin
   - Request validation using Pydantic
   - SQL injection prevention (MongoDB parameterized queries)
   - XSS protection

4. **Data Privacy**
   - Never return password hashes in API responses
   - Filter user data based on role
   - Audit logging for sensitive operations

## Environment Variables (.env)
```
# Application
APP_NAME=Distribution Management System
APP_VERSION=1.0.0
DEBUG=False
ENVIRONMENT=production

# Server
HOST=0.0.0.0
PORT=8000

# Database
MONGODB_URL=mongodb+srv://dms_db_user:WK56LWAAoBquBnCI@cluster0.gzmwm30.mongodb.net/?appName=Cluster0
DATABASE_NAME=distribution_management_system

# Security
SECRET_KEY=your-secret-key-here-generate-with-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:3002,http://localhost:5173

# API
API_V1_PREFIX=/api
```

## Dependencies (requirements.txt)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
motor==3.3.2
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
python-dotenv==1.0.0
email-validator==2.1.0
pymongo==4.6.0
bcrypt==4.1.2
```

## Validation & Error Handling

### Standard Response Format
```python
# Success Response
{
    "success": true,
    "message": "Operation successful",
    "data": {...}
}

# Error Response
{
    "success": false,
    "message": "Error description",
    "error": {
        "code": "ERROR_CODE",
        "details": "Detailed error message"
    }
}

# Paginated Response
{
    "success": true,
    "data": [...],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 100,
        "total_pages": 5
    }
}
```

### HTTP Status Codes
- 200: Success
- 201: Created
- 400: Bad Request (validation error)
- 401: Unauthorized (not logged in)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 409: Conflict (duplicate entry)
- 422: Unprocessable Entity (validation error)
- 500: Internal Server Error

## Database Indexes (for Performance)

```python
# Users Collection
users.create_index([("email", 1)], unique=True)
users.create_index([("role", 1)])

# Devices Collection
devices.create_index([("device_id", 1)], unique=True)
devices.create_index([("serial_number", 1)], unique=True)
devices.create_index([("status", 1)])
devices.create_index([("current_holder_id", 1)])

# Distributions Collection
distributions.create_index([("distribution_id", 1)], unique=True)
distributions.create_index([("status", 1)])
distributions.create_index([("from_user_id", 1)])
distributions.create_index([("to_user_id", 1)])

# Defects Collection
defects.create_index([("report_id", 1)], unique=True)
defects.create_index([("device_id", 1)])
defects.create_index([("status", 1)])
defects.create_index([("reported_by", 1)])

# Returns Collection
returns.create_index([("return_id", 1)], unique=True)
returns.create_index([("device_id", 1)])
returns.create_index([("status", 1)])

# Notifications Collection
notifications.create_index([("user_id", 1)])
notifications.create_index([("is_read", 1)])
notifications.create_index([("created_at", -1)])

# Device History Collection
device_history.create_index([("device_id", 1)])
device_history.create_index([("timestamp", -1)])
```

## Testing Requirements

1. **Unit Tests**
   - Test all service functions
   - Test authentication and authorization
   - Test data validation

2. **Integration Tests**
   - Test API endpoints
   - Test database operations
   - Test workflow processes

3. **Load Tests**
   - Test concurrent users
   - Test database query performance
   - Test API response times

## API Documentation
- Automatic Swagger UI at `/docs`
- ReDoc at `/redoc`
- OpenAPI schema at `/openapi.json`

## Initial Seed Data

Create demo users matching frontend:
1. Admin: admin@dms.com / admin123
2. Manager: manager@dms.com / manager123
3. Distributor: distributor@dms.com / dist123
4. Sub-Distributor: subdist@dms.com / subdist123
5. Operator: operator@dms.com / operator123

Create sample devices, distributions, and reports for testing.

## Deployment Considerations

1. **Production Server**: Use Gunicorn with Uvicorn workers
2. **Reverse Proxy**: Nginx for serving static files and SSL
3. **Monitoring**: Implement logging and error tracking
4. **Backup**: Regular MongoDB Atlas backups
5. **Scaling**: MongoDB connection pooling, async operations

---

**Implementation Priority:**
1. Database connection and models ✅
2. Authentication system ✅
3. User management ✅
4. Device management ✅
5. Distribution workflow ✅
6. Defect and return management ✅
7. Approval system ✅
8. Notifications ✅
9. Reports and analytics ✅
10. Testing and documentation ✅
