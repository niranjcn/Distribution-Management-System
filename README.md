# Distribution Management System

A full-stack web application for managing device distribution across different organizational levels with role-based access control.

## Table of Contents

- [1. Core Idea](#1-core-idea)
- [2. Technology Stack](#2-technology-stack)
- [3. System Architecture](#3-system-architecture)
- [4. Project Structure](#4-project-structure)
- [5. Key Features](#5-key-features)
- [6. Role Hierarchy & Access Control](#6-role-hierarchy--access-control)
- [7. Core Workflows](#7-core-workflows)
- [8. API Overview](#8-api-overview)
- [9. Security Features](#9-security-features)
- [10. Setup Instructions](#10-setup-instructions)
- [11. Configuration](#11-configuration)
- [12. Running Both Servers](#12-running-both-servers)
- [13. Demo Accounts](#13-demo-accounts)
- [14. Monitoring](#14-monitoring)
- [14. Monitoring](#14-monitoring)
- [15. Testing](#15-testing)
- [16. Building for Production](#16-building-for-production)
- [17. Troubleshooting](#17-troubleshooting)
- [18. Development Notes](#18-development-notes)
- [19. Contributing](#19-contributing)
- [20. License](#20-license)

---

## 1. Core Idea

The Distribution Management System (DMS) provides end-to-end visibility and control over how devices move through an organisational hierarchy:

1. Devices are registered and given a trackable identity.
2. Distribution requests flow through a structured approval chain.
3. Defects and returns are captured, categorised, and resolved.
4. Role-scoped dashboards give every actor — from Admin to Operator — the right view of the system.

---

## 2. Technology Stack

### Backend

- **FastAPI** — Modern Python async web framework
- **MySQL 8.4** — Relational database with aiomysql async driver
- **JWT** — JSON Web Tokens for stateless authentication
- **Pydantic** — Data validation and serialisation
- **Bcrypt** — Secure password hashing

### Monitoring

- **Prometheus** — Metrics collection and query engine
- **Grafana** — Metrics visualisation and dashboards

### Frontend

- **React** — Component-based UI library
- **Vite** — Fast build toolchain and dev server
- **Tailwind CSS** — Utility-first CSS framework
- **React Router** — Client-side routing
- **Context API** — Lightweight state management

---

## 3. System Architecture

```mermaid
flowchart TD
  subgraph Client ["Presentation Layer"]
    FE[React + Vite Frontend\nRole-scoped Dashboards]
  end

  subgraph Gateway ["API Gateway"]
    API[FastAPI Application\nRoutes · Middleware · Auth]
  end

  subgraph Services ["Business Logic Layer"]
    US[User Service]
    DS[Device Service]
    DIS[Distribution Service]
    DEF[Defect Service]
    RET[Return Service]
    APR[Approval Service]
    NOT[Notification Service]
    REP[Report Service]
  end

  subgraph Data ["Persistence Layer"]
    DB[(MySQL 8.4\nRelational Database)]
  end

  subgraph Monitoring ["Observability Stack"]
    P[Prometheus\nMetrics Scraper]
    G[Grafana\nDashboards]
  end

  FE -- HTTP/REST --> API
  API --> Services
  Services --> DB
  P -- /metrics --> API
  G -.-> P
```

---

## 4. Project Structure

```text
distribution-management-system/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── metrics.py           # Prometheus metric definitions
│   │   │   └── ...
│   │   ├── models/          # Pydantic models
│   │   ├── routes/          # API endpoints
│   │   ├── services/
│   │   │   ├── metrics_collector.py # Background Prometheus metric updater
│   │   │   └── ...
│   │   ├── middleware/      # Auth & error handling
│   │   ├── utils/           # Helper functions
│   │   ├── schemas/         # Response schemas
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── config.py        # Settings
│   │   └── database.py      # MySQL connection pool & schema
│   ├── requirements.txt
│   ├── .env
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Page-level components
│   │   ├── context/         # Context providers
│   │   ├── services/        # API service layer
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/
│   │   └── favicon.svg
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml    # Scrape config
│   │   └── alert.rules.yml   # Alert rules
│   └── grafana/
│       ├── datasources/      # Provisioned data source
│       └── dashboards/       # Pre-built dashboards
│
├── docker-compose.yml
├── docker-compose.override.yml
├── nginx/
└── README.md
```

---

## 5. Key Features

### User Management
- Create, read, update, delete users
- Role-based access control (Admin, Manager, Distributor, Sub-Distributor, Operator)
- User status management (Active, Inactive, Suspended)
- Profile management

### Device Management
- Register new devices with serial number tracking
- Track device status, location, and current holder
- Full device history and audit trail

### Distribution System
- Create and manage distribution requests
- Structured approval workflow
- Status tracking: Pending → Approved → Delivered / Rejected

### Defect Reporting
- Report and categorise device defects by type and severity
- Resolution workflow with history tracking

### Return Management
- Create and approve return requests
- Reason categorisation and status tracking

### Approval System
- Centralised approval dashboard for distributions, returns, and defects
- Approval notes and full history

### Notifications
- Real-time notification centre
- Unread count badge and mark-as-read functionality

### Reports & Analytics
- Inventory, distribution, defect, return, user activity, and device utilisation reports

### Dashboard
- Role-specific views with live statistics, activity feeds, charts, and system alerts

### Monitoring (Prometheus + Grafana)
- **Prometheus** scrapes the backend `/metrics` endpoint every 10s for HTTP, database, and business metrics
- **Grafana** provisions dashboards automatically on startup:
  - **Business Metrics** — total/active users, operators, clusters, sub-distributors, device inventory, distributions, login activity
  - **Database Dashboard** — MySQL query throughput, durations, failure rates, active connections
  - **Backend API Dashboard** — HTTP request rates, latencies, error rates, in-flight requests
- A background **metrics collector** (`app/services/metrics_collector.py`) syncs database state to Prometheus gauges every 60s

---

## 6. Role Hierarchy & Access Control

```mermaid
flowchart TD
  ADM[Admin\nFull System Access]
  MGR[Manager\nManagement Operations]
  DIST[Distributor\nDistribution Management]
  SDIST[Sub-Distributor\nSub-Distribution Management]
  OPR[Operator\nField Operations]

  ADM --> MGR
  MGR --> DIST
  DIST --> SDIST
  SDIST --> OPR
```

| Role | Email | Access Scope |
|---|---|---|
| Admin | admin@dms.com | Full system access |
| Manager | manager@dms.com | Management operations |
| Distributor | distributor@dms.com | Distribution management |
| Sub-Distributor | subdist@dms.com | Sub-distribution management |
| Operator | operator@dms.com | Field operations |

---

## 7. Core Workflows

### Distribution Lifecycle

```mermaid
stateDiagram-v2
  [*] --> Pending : Distribution request created
  Pending --> Approved : Approver accepts
  Pending --> Rejected : Approver rejects
  Approved --> Delivered : Device handed over
  Rejected --> [*]
  Delivered --> [*]
```

### Defect & Return Resolution

```mermaid
stateDiagram-v2
  [*] --> Reported : Defect / Return request filed
  Reported --> UnderReview : Assigned to reviewer
  UnderReview --> Resolved : Fix confirmed / Return accepted
  UnderReview --> Rejected : Request declined
  Resolved --> [*]
  Rejected --> [*]
```

### Request Approval Flow

```mermaid
sequenceDiagram
  participant U as User (any role)
  participant API as FastAPI Backend
  participant DB as MongoDB
  participant APR as Approver (Manager/Admin)
  participant NOT as Notification Service

  U->>API: Submit distribution / defect / return request
  API->>DB: Persist request with status=Pending
  API->>NOT: Trigger notification to approver
  NOT-->>APR: Alert: new request awaiting review
  APR->>API: Approve or Reject with notes
  API->>DB: Update request status
  API->>NOT: Notify originating user of decision
  NOT-->>U: Alert: request approved / rejected
```

---

## 8. API Overview

All endpoints are mounted under `/api`.

### Authentication
- `POST /api/auth/login` — User login
- `POST /api/auth/logout` — User logout
- `GET /api/auth/me` — Get current user
- `PUT /api/auth/password` — Change password

### Users
- `GET /api/users` — List users (paginated)
- `GET /api/users/{id}` — Get user by ID
- `POST /api/users` — Create user
- `PUT /api/users/{id}` — Update user
- `DELETE /api/users/{id}` — Delete user
- `PATCH /api/users/{id}/status` — Update user status

### Devices
- `GET /api/devices` — List devices (paginated)
- `GET /api/devices/{id}` — Get device by ID
- `GET /api/devices/available` — Get available devices
- `GET /api/devices/track/{serial}` — Track by serial number
- `GET /api/devices/{id}/history` — Get device history
- `POST /api/devices` — Register device
- `PUT /api/devices/{id}` — Update device
- `DELETE /api/devices/{id}` — Delete device
- `PATCH /api/devices/{id}/status` — Update device status

### Distributions
- `GET /api/distributions` — List distributions
- `GET /api/distributions/{id}` — Get distribution by ID
- `GET /api/distributions/pending` — Get pending distributions
- `POST /api/distributions` — Create distribution
- `PATCH /api/distributions/{id}/status` — Update status
- `DELETE /api/distributions/{id}` — Cancel distribution

### Defects
- `GET /api/defects` — List defect reports
- `GET /api/defects/{id}` — Get defect by ID
- `POST /api/defects` — Create defect report
- `PUT /api/defects/{id}` — Update defect
- `PATCH /api/defects/{id}/status` — Update status
- `PATCH /api/defects/{id}/resolve` — Resolve defect
- `DELETE /api/defects/{id}` — Delete defect

### Returns
- `GET /api/returns` — List return requests
- `GET /api/returns/{id}` — Get return by ID
- `POST /api/returns` — Create return request
- `PATCH /api/returns/{id}/status` — Update status
- `DELETE /api/returns/{id}` — Cancel return

### Approvals
- `GET /api/approvals` — List pending approvals
- `GET /api/approvals/{id}` — Get approval by ID
- `POST /api/approvals/{id}/approve` — Approve request
- `POST /api/approvals/{id}/reject` — Reject request

### Operators
- `GET /api/operators` — List operators
- `GET /api/operators/{id}` — Get operator by ID
- `GET /api/operators/{id}/devices` — Get operator devices
- `POST /api/operators` — Create operator
- `PUT /api/operators/{id}` — Update operator
- `DELETE /api/operators/{id}` — Delete operator

### Notifications
- `GET /api/notifications` — List notifications
- `GET /api/notifications/unread` — Get unread count
- `PATCH /api/notifications/{id}/read` — Mark as read
- `PATCH /api/notifications/read-all` — Mark all as read
- `DELETE /api/notifications/{id}` — Delete notification

### Reports
- `GET /api/reports/inventory` — Inventory report
- `GET /api/reports/distribution-summary` — Distribution summary
- `GET /api/reports/defect-summary` — Defect summary
- `GET /api/reports/return-summary` — Return summary
- `GET /api/reports/user-activity` — User activity report
- `GET /api/reports/device-utilization` — Device utilisation report

### Dashboard
- `GET /api/dashboard/stats` — Dashboard statistics
- `GET /api/dashboard/recent-activities` — Recent activities
- `GET /api/dashboard/advanced-metrics` — Advanced graph/metrics payload
- `GET /api/dashboard/charts/distributions` — Distribution chart data
- `GET /api/dashboard/charts/defects` — Defect chart data
- `GET /api/dashboard/alerts` — System alerts

### Bulk Upload
- `POST /api/devices/bulk-upload` — Bulk register devices (CSV/XLSX/XLS)
- `POST /api/users/bulk-upload` — Bulk create users (CSV/XLSX/XLS)

### System
- `GET /metrics` — Prometheus metrics endpoint (no auth)
- `GET /health` — Health check

---

## 9. Security Features

```mermaid
flowchart LR
  REQ[Incoming Request] --> CORS[CORS Check]
  CORS --> JWT[JWT Token Validation]
  JWT --> RBAC[Role-Based Access Check]
  RBAC --> PYDANTIC[Input Validation\nPydantic]
  PYDANTIC --> HANDLER[Route Handler]
  HANDLER --> BCRYPT[Bcrypt Password Hashing\nfor auth mutations]
```

- JWT-based authentication with configurable token expiry
- Password hashing with bcrypt
- Role-based access control (RBAC) with permission-based route protection
- Token expiration and refresh support
- CORS configuration for allowed origins
- Input validation with Pydantic on all request bodies

---

## 10. Setup Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL 8.4
- Docker & Docker Compose (recommended for monitoring stack)

### Quick Start (Docker — Recommended)

The entire stack including MySQL, backend, frontend, reverse proxy, Prometheus, and Grafana can be started with Docker Compose:

```bash
# Ensure environment variables are set
cp .env.example .env       # or configure manually

# Start all services
docker compose up -d

# Wait for services to be healthy, then access:
```

| Service | URL |
|---|---|
| Web Application | https://localhost |
| Backend API | https://localhost/api |
| API Docs (Swagger) | https://localhost/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / password from `.env`) |

### Backend Setup (Manual)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate       # Linux / macOS
   venv\Scripts\activate          # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Update the MySQL connection string if needed

5. Start the backend server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
   ```

6. Access API docs:
   - Swagger UI: http://localhost:8080/docs
   - ReDoc: http://localhost:8080/redoc

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open the app at: http://localhost:5173

---

## 11. Configuration

### Backend (`backend/.env`)

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=dms_user
DB_PASSWORD=your-db-password
DB_NAME=distribution_management_system
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:5173,http://localhost:3002
ENVIRONMENT=development
```

### Frontend (`frontend/.env`)

```env
VITE_API_URL=http://localhost:8080/api
```

---

## 12. Running Both Servers

### Option 1 — Separate Terminals

**Terminal 1 (Backend):**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev
```

### Option 2 — PowerShell Script (Windows)

Create `start.ps1` in the root directory:

```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"
```

Run with:
```powershell
.\start.ps1
```

---

## 13. Demo Accounts

| Email | Password | Role | Access Level |
|---|---|---|---|
| admin@dms.com | admin123 | Admin | Full system access |
| manager@dms.com | manager123 | Manager | Management operations |
| distributor@dms.com | dist123 | Distributor | Distribution management |
| subdist@dms.com | subdist123 | Sub Distributor | Sub-distribution management |
| operator@dms.com | operator123 | Operator | Field operations |

---

## 14. Monitoring

### Accessing Grafana Dashboards

Grafana is available at **http://localhost:3000** when running via Docker Compose.

| Default Credential | Value |
|---|---|
| Username | `admin` |
| Password | Set via `GRAFANA_ADMIN_PASSWORD` in `.env` (defaults to `admin`) |

Three dashboards are provisioned automatically on startup:

| Dashboard | UID | Key Panels |
|---|---|---|
| **Business Metrics** | `business-metrics` | Total/Active Users, Operators, Clusters, Sub-Distributors, Distributions, Login Activity |
| **Backend API** | `backend-api` | HTTP request rate, latency (P50/P95/P99), error rate, in-flight requests |
| **Database** | `database` | MySQL query throughput, duration, failure rate, active connections |

### Prometheus Metrics Endpoint

The backend exposes a `/metrics` endpoint scraped by Prometheus:

```bash
# View raw metrics directly
curl http://localhost:8080/metrics
```

### Metrics Collection Architecture

```
┌─────────────────┐    scrape(10s)    ┌────────────┐    query     ┌─────────┐
│  FastAPI App    │ ────────────────→ │ Prometheus │ ←────────── │ Grafana │
│  /metrics       │                   │ :9090      │             │ :3000   │
└────────┬────────┘                   └────────────┘             └─────────┘
         │
    ┌────┴────┐
    │ metrics │  <── background loop (60s)
    │ collector│       updates gauges from DB
    └─────────┘
```

- **`app/core/metrics.py`** — Declares all Prometheus metric objects (Counters, Gauges, Histograms) for HTTP requests, database queries, authentication, and business data.
- **`app/services/metrics_collector.py`** — Background task that runs every 60 seconds, queries the database for current counts (total/active users by role, device inventory, distribution stats, login activity), and updates the corresponding Prometheus gauge/counter metrics.
- **Prometheus** scrapes the `/metrics` HTTP endpoint every 10 seconds (configured in `monitoring/prometheus/prometheus.yml`).
- **Grafana** uses Prometheus as a data source (configured in `monitoring/grafana/datasources/datasource.yml`) and loads dashboards from `monitoring/grafana/dashboards/`.

### Exported Business Metrics

| Metric | Type | Description |
|---|---|---|
| `total_users` | Gauge | Total registered users |
| `active_users` | Gauge | Users with status `active` |
| `new_users_created_total` | Counter | Cumulative new user creations |
| `total_operators` | Gauge | Users with role `operator` |
| `active_operators` | Gauge | Active operators |
| `total_clusters` | Gauge | Users with role `cluster` |
| `active_clusters` | Gauge | Active clusters |
| `total_sub_distributors` | Gauge | Users with role `sub_distributor` |
| `active_sub_distributors` | Gauge | Active sub-distributors |
| `inventory_items_total` | Gauge | Total devices registered |
| `low_stock_items_total` | Gauge | Devices below low-stock threshold |
| `distributions_created_total` | Counter | Cumulative distributions created |
| `distributions_completed_total` | Counter | Distributions marked delivered |
| `distributions_failed_total` | Counter | Distributions marked rejected |
| `device_distributions_total` | Counter | Per-status distribution count |
| `successful_logins_total` | Counter | Successful login events |
| `failed_logins_total` | Counter | Failed login attempts |
| `operator_logins_total` | Counter | Operator login events |
| `http_requests_total` | Counter | Total HTTP requests by method/endpoint/status |
| `http_request_duration_seconds` | Histogram | HTTP latency distribution |
| `http_requests_in_progress` | Gauge | Concurrent in-flight requests |
| `http_errors_total` | Counter | HTTP 4xx/5xx responses |
| `login_attempts_total` | Counter | Login attempts by status |
| `mysql_queries_total` | Counter | MySQL queries by operation type |
| `mysql_query_duration_seconds` | Histogram | MySQL query latency |
| `mysql_query_failures_total` | Counter | Failed MySQL queries |
| `mysql_active_connections` | Gauge | Active DB connections |

---

## 15. Testing

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
2. Login with any demo credential
3. Navigate through features
4. Check the browser console for errors

---

## 16. Building for Production

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
npm run preview     # Test the production build locally
```

The production build outputs to `frontend/dist/`.

---

## 17. Troubleshooting

### Backend Issues

**MongoDB Connection Error:**
- Verify your internet connection
- Confirm the MongoDB Atlas cluster is running
- Ensure your IP address is whitelisted in MongoDB Atlas

**Port 8080 Already in Use:**
```bash
# Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F

# Linux / macOS
lsof -i :8080
kill -9 <PID>
```

### Frontend Issues

**Port 5173 Already in Use:**
- Change the port in `frontend/vite.config.js`
- Update `CORS_ORIGINS` in `backend/.env` to match

**API Connection Error:**
- Ensure the backend is running on port 8080
- Verify `.env` has `VITE_API_URL=http://localhost:8080/api`
- Check CORS settings in the backend

**Module Not Found:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Monitoring Issues

**Grafana shows 0 for all business metrics:**
- Ensure the backend is running and Prometheus can reach `backend:8080/metrics`
- Check Prometheus targets at http://localhost:9090/targets — the `backend` job should be UP
- The metrics collector runs every 60s; wait at least one minute after startup for first sync
- Verify `monitoring/prometheus/prometheus.yml` has `targets: ["backend:8080"]`

**Grafana dashboards not appearing:**
- Check Grafana logs: `docker compose logs grafana`
- Verify dashboard JSON files exist in `monitoring/grafana/dashboards/`
- The provisioning directory is mounted at `/etc/grafana/provisioning/dashboards`
- Restart Grafana: `docker compose restart grafana`

**Prometheus target down:**
```bash
# From within the Docker network, test connectivity
docker compose exec backend wget -qO- http://localhost:8080/metrics | head -20
```

---

## 18. Development Notes

### Database Seeding

- Seed data is automatically created on first startup via `seed_initial_data()`
- Includes 5 demo users, 20 sample devices, and example records
- Tables are created automatically by `init_db()` on startup (see `backend/app/database.py`)
- To reset: drop and recreate the database, then restart the backend

### CORS Configuration

- Backend CORS is configured for `localhost:5173` and `localhost:3002`
- Update `backend/.env` if using different ports

---

## 19. Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/AmazingFeature`
3. Commit your changes: `git commit -m 'Add some AmazingFeature'`
4. Push to the branch: `git push origin feature/AmazingFeature`
5. Open a Pull Request

---

## 20. License

This project is licensed under the MIT License.

---

For issues and questions:
- Review the troubleshooting section above
- Check API documentation at http://localhost:8080/docs
- Inspect the browser console for frontend errors
- Review terminal output for backend errors

**Happy Coding! 🚀**
