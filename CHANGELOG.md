# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Dashboard loading skeleton components
- ErrorBoundary wrappers across all dashboard sections
- Shared chartOptions in `src/utils/chartConfig.js`
- Frontend test suite with 24 passing tests (StatCard, Card, DataTable)
- OpenAPI `summary` annotations on all 144 backend routes
- 12 backend contract test suites (389 route tests)
- Backend test infrastructure with mock fixtures for all routess

### Changed
- Notification pagination from "Show All" to 20/page with prev/next navigation
- Dashboard service split into submodules
- Silent error catch handlers replaced with user-visible error toasts
- `batch_service.py` rewritten from MongoDB to MySQL
- Fixed `status` query param shadowing `fastapi.status` in 4 route files
- Updated CHANGELOG.md, TODO.md, ENGINEERING_AUDIT.md

### Removed
- Unused `DistributorDashboard.jsx` component
- Unfinished batch management feature (service, routes, models, tests, frontend)

## [1.0.0] - 2026-07-22

### Added
- Dashboard Updates & Report Generation
- Password change request flow
- PWA setup with favicon and app icons
- New update stages workflow
- Rclone backup integration for bills and defects
- Grafana monitoring dashboard
- User bulk upload with file preview
- Email and password update flows
- Reassignment request system with activity logging
- External inventory management
- Operator dashboard
- Sub-distributor dashboard
- Defect report with selection filters
- IST timezone support for dates

### Changed
- Navbar and Sidebar UI fixes
- User reassignment system improvements
- Refresh state fixes for user page
- Reports page fixes for date and items
- Page cap updates
- Removed notes from replacement and defect flow

### Security
- Final security fixes for production
- Reverse proxy configuration
- IAM implementation
- CSRF middleware
- Security headers middleware
- Rate limiting
- JWT authentication hardening

## [0.9.0] - 2026-06-10

### Added
- Updated folder structure reorganization
- Dashboard with user KPI
- User reassignment functionality
- Monitoring tool setup (Grafana)
- Activity logging system
- External inventory module
- Backup system for entire database
- Export table functionality
- Receipt generation
- Flow diagrams for distribution lifecycle

### Changed
- Bulk upload corrections
- User role updates
- MD role updates
- Sub-distributor management fixes

## [0.8.0] - 2026-05-15

### Added
- Approval workflow with role routing
- Distribution tracking system
- Device replacement flow
- Repair holder management
- Device history tracking
- Change request system

## [0.7.0] - 2026-04-20

### Added
- Notification system
- Batch management
- Operator management
- Returns management
- Defect tracking with photo uploads

## [0.6.0] - 2026-04-01

### Added
- External inventory dashboard
- Purchase order management
- Inventory adjustments tracking
- Payment processing for returned devices

## [0.5.0] - 2026-03-15

### Added
- Reports module (inventory, distribution, defect, return summaries)
- Report export functionality
- User activity tracking
- Device utilization reports

## [0.4.0] - 2026-03-01

### Added
- Device management CRUD
- Device search and filtering
- Device status tracking
- Bulk device upload

## [0.3.0] - 2026-02-15

### Added
- User management CRUD
- Role-based access control with 8 user roles
- User bulk upload
- User status management

## [0.2.0] - 2026-02-01

### Added
- JWT authentication (login, logout, token refresh)
- Session management
- Password management
- Basic security middleware

## [0.1.0] - 2026-01-15

### Added
- Initial project setup
- FastAPI backend scaffolding
- MySQL database schema
- Project directory structure
- Docker and Docker Compose configuration
