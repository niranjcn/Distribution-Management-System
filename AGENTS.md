# AGENTS.md

# Distribution Management System (DMS)

This repository contains the Distribution Management System consisting of:

- Frontend: React + Vite
- Backend: FastAPI
- Database: MySQL
- Authentication: JWT
- Deployment: Docker

---

# Goal

Your primary responsibility is to implement requested changes **without introducing regressions**.

Every change must preserve existing functionality unless explicitly instructed otherwise.

---

# General Rules

- Understand the complete feature before modifying it.
- Never assume a file is isolated.
- Search for all references before renaming, deleting, or modifying.
- Prefer minimal, targeted changes over large refactors.
- Preserve coding style and architecture.
- Do not remove existing functionality unless explicitly requested.

---

# Before Making Any Change

Always determine:

- Which frontend pages use this feature?
- Which backend APIs are affected?
- Which database models are involved?
- Which user roles use this functionality?
- Whether reports, dashboards, or notifications depend on it.
- Whether authentication or permissions are impacted.

---

# Regression Checklist

After every code modification verify that:

## Backend

- API starts successfully.
- No import errors.
- No syntax errors.
- Existing endpoints continue working.
- Response formats remain compatible.
- JWT authentication still works.
- Role permissions remain unchanged.
- Database migrations (if any) are correct.

---

## Frontend

Verify:

- Application builds successfully.
- No console errors.
- No broken routes.
- Forms still submit correctly.
- Existing components render properly.
- Navigation still works.
- Role-based menus remain correct.
- Responsive layout is preserved.

---

## Database

If schema changes:

- Existing data remains valid.
- Foreign keys remain intact.
- No orphan records.
- Existing queries continue working.
- Indexes are preserved where appropriate.

---

## Business Logic

Ensure that changes do NOT break:

- User Management
- Authentication
- Device Management
- Distribution Workflow
- Approval Workflow
- Notifications
- Reports
- Dashboard
- Inventory Management

---

# Cross-Feature Validation

Whenever changing:

## Authentication

Verify:

- Login
- Logout
- Token refresh (if applicable)
- Protected routes
- User session
- Role permissions

---

## User Management

Verify:

- Create User
- Edit User
- Delete User
- Role Assignment
- User Listing

---

## Device Management

Verify:

- Add Device
- Edit Device
- Delete Device
- Search
- Status Updates

---

## Distribution

Verify:

- Create Distribution
- Approval
- Allocation
- Tracking
- Completion

---

## Reports

Verify:

- Reports load
- Filters work
- Export functions (if available)
- Statistics remain accurate

---

# API Rules

Never:

- Rename API endpoints unnecessarily.
- Change request payloads without updating every consumer.
- Change response structures without checking frontend compatibility.

If an API changes:

- Update frontend.
- Update validation.
- Update documentation.
- Update tests.

---

# UI Rules

Maintain:

- Existing design language.
- Consistent spacing.
- Typography.
- Colors.
- Responsive behavior.
- Accessibility.

Avoid introducing inconsistent UI patterns.

---

# Error Handling

All new code must:

- Handle failures gracefully.
- Return meaningful error messages.
- Avoid exposing internal exceptions.
- Log unexpected failures.

---

# Performance

Avoid:

- Duplicate API calls.
- N+1 database queries.
- Unnecessary re-renders.
- Blocking operations.
- Large unnecessary bundle increases.

---

# Security

Never:

- Expose secrets.
- Hardcode credentials.
- Bypass authentication.
- Bypass authorization.
- Trust client input.

Always validate:

- User input
- Permissions
- Authentication
- Database operations

---

# Testing Requirements

After implementing a change, verify:

Frontend

- Build succeeds.
- No console errors.
- Feature works.
- Existing pages still work.

Backend

- Server starts.
- APIs return expected responses.
- Existing endpoints remain functional.

Integration

- Frontend communicates correctly with backend.
- Database operations succeed.
- Authentication still functions.

---

# Code Quality

Write code that is:

- Readable
- Modular
- Well commented where necessary
- Consistent with existing architecture

Avoid unnecessary abstraction.

---

# Pull Request Checklist

Before considering a task complete:

- Change implemented.
- Existing functionality preserved.
- No regression introduced.
- No unused imports.
- No dead code.
- No lint errors.
- No build errors.
- No runtime errors.
- Documentation updated if required.

---

# Golden Rule

Every modification should leave the application in a deployable state.

Never fix one feature by silently breaking another.

When uncertain, inspect the complete dependency chain before making changes.