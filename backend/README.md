# Distribution Management System - Backend

FastAPI backend for the Distribution Management System.

## Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: MongoDB (Cloud Atlas)
- **Authentication**: JWT (JSON Web Tokens)
- **ODM**: Motor (async MongoDB driver) + Pydantic

## Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

### 4. Run the Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@dms.com | admin123 |
| Manager | manager@dms.com | manager123 |
| Distributor | distributor@dms.com | dist123 |
| Sub-Distributor | subdist@dms.com | subdist123 |
| Operator | operator@dms.com | operator123 |

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   ├── database.py          # MongoDB connection
│   ├── models/              # Pydantic models
│   ├── schemas/             # Response schemas
│   ├── services/            # Business logic
│   ├── routes/              # API endpoints
│   ├── middleware/          # Custom middleware
│   └── utils/               # Utilities
├── requirements.txt
├── .env
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user

### Users
- `GET /api/users` - List users
- `POST /api/users` - Create user
- `GET /api/users/{id}` - Get user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user

### Devices
- `GET /api/devices` - List devices
- `POST /api/devices` - Register device
- `GET /api/devices/{id}` - Get device
- `GET /api/devices/{id}/history` - Get device history
- `GET /api/devices/track/{serial}` - Track device

### Distributions
- `GET /api/distributions` - List distributions
- `POST /api/distributions` - Create distribution
- `PATCH /api/distributions/{id}/status` - Update status

### Defects
- `GET /api/defects` - List defect reports
- `POST /api/defects` - Create defect report
- `PATCH /api/defects/{id}/resolve` - Resolve defect

### Returns
- `GET /api/returns` - List return requests
- `POST /api/returns` - Create return request
- `PATCH /api/returns/{id}/status` - Update status

### Approvals
- `GET /api/approvals` - List pending approvals
- `POST /api/approvals/{id}/approve` - Approve
- `POST /api/approvals/{id}/reject` - Reject

### Dashboard
- `GET /api/dashboard/stats` - Get statistics
- `GET /api/dashboard/recent-activities` - Recent activities

### Reports
- `GET /api/reports/inventory` - Inventory report
- `GET /api/reports/distribution-summary` - Distribution summary
