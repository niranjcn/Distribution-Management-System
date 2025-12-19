# Distribution Management System - Project Specification

## Technology Stack
- **Frontend Framework**: React (with React Router for navigation)
- **Styling**: Tailwind CSS
- **State Management**: React Context API or Redux
- **Authentication**: JWT-based authentication

## System Overview

Create a comprehensive distribution management system for tracking devices from the Network Operations Center (NOC) through the entire distribution chain to end operators.

## Device Flow

```
NOC → Main Distribution Center → Sub Distributors → Operators
```

## User Roles & Access Levels

### 1. Admin
- Full system access
- Manage all users (create, edit, delete)
- View all analytics and reports
- Override approvals
- Configure system settings

### 2. Manager
- View all distribution activities
- Generate reports
- Approve/reject returns
- Monitor sub-distributor and operator activities

### 3. Operator
- View assigned devices
- Report defects
- Initiate returns
- Track device status

### 4. Main Distributor
- Scan and register incoming devices from NOC
- Store device information (MAC address, serial number, model, etc.)
- Distribute devices to sub-distributors
- Track approval status from sub-distributors
- Manage returns and defects

### 5. Sub-Distributor
- Receive devices from main distribution center
- Approve/acknowledge device receipt
- Distribute devices to operators
- Review and approve/reject defect reports
- Process return requests

## Core Features & Pages

### 1. Authentication & Authorization
- Login page with role-based access
- Secure routes based on user roles
- Session management
- Password reset functionality

### 2. Dashboard (Role-specific)
- **Admin Dashboard**: System-wide metrics, user management, all activities
- **Manager Dashboard**: Distribution analytics, pending approvals, reports
- **Distributor Dashboard**: Inventory overview, pending distributions, return requests
- **Sub-Distributor Dashboard**: Received devices, pending approvals, operator assignments
- **Operator Dashboard**: Assigned devices, active devices, reported issues

### 3. Device Registration & Management

#### Main Distribution Center Page
- Scan device interface (barcode/QR code scanner)
- Device registration form with fields:
  - MAC Address (primary identifier)
  - Serial Number
  - Device Model
  - Manufacturer
  - Hardware Version
  - Firmware Version
  - Condition (New/Refurbished)
  - Date Received from NOC
  - Additional Notes
- Bulk import option (CSV/Excel)
- Search and filter registered devices
- Device inventory list with status indicators

### 4. Distribution Management

#### Distributor Page
- Create distribution batches
- Assign devices to sub-distributors
- Select sub-distributor from dropdown
- Add multiple devices to distribution
- Generate distribution receipt/invoice
- Track distribution status:
  - Pending (awaiting shipment)
  - In Transit
  - Delivered (awaiting approval)
  - Approved by sub-distributor
  - Rejected
- View distribution history
- Pending approvals list

#### Sub-Distributor Page
- View received distributions (pending approval)
- Approve/reject received devices with comments
- If rejected: specify reason and initiate return
- Assign devices to operators
- View operator assignments
- Track operator device status
- Distribution history to operators

#### Operator Page
- View assigned devices
- Device details view
- Mark devices as:
  - Active
  - Inactive
  - In Use
  - Stored

### 5. Device Tracking System

#### Track Device Page (Available to all roles)
- Search by:
  - MAC Address
  - Serial Number
  - Device Model
  - Distribution Batch ID
- Display complete device journey:
  - Registration date and details
  - Current location (Main Dist/Sub Dist/Operator)
  - Current status
  - Distribution history with timestamps
  - Current holder information
  - All status changes with timestamps
- Visual timeline/flowchart of device journey
- Export device history

### 6. Defect Reporting System

#### Report Defect Page (Operators & Sub-Distributors)
- Select device from assigned devices
- Defect reporting form:
  - Defect type (Hardware/Software/Cosmetic/Other)
  - Severity (Critical/High/Medium/Low)
  - Detailed description
  - Upload photos (multiple)
  - Date defect discovered
- Submit to sub-distributor for review
- Track defect report status

#### Defect Management (Sub-Distributors & Distributors)
- View all defect reports
- Filter by status, severity, date
- Review defect details and photos
- Approve/reject defect claims
- Add comments/feedback
- Initiate return if approved
- Request more information if needed

### 7. Return Management System

#### Return Initiation
- Operator or Sub-distributor initiates return
- Reasons:
  - Defective device (linked to defect report)
  - Wrong device received
  - Excess inventory
  - Customer cancellation
  - Other (specify)
- Return request form:
  - Device details (auto-populated)
  - Return reason
  - Linked defect report (if applicable)
  - Supporting documents/photos
  - Requested action (Replace/Refund/Repair)

#### Return Approval Workflow
1. **Operator** initiates return → sends to **Sub-Distributor**
2. **Sub-Distributor** reviews:
   - Approve: forward to Main Distributor
   - Reject: return denied with reason
   - Request Info: ask for more details
3. **Main Distributor** final review:
   - Approve: accept return, provide return shipping label
   - Reject: provide detailed reason
4. Track return shipment status
5. Upon receipt: update inventory, process refund/replacement

#### Return Tracking Page
- View all return requests with filters:
  - Status (Pending/Approved/Rejected/In Transit/Completed)
  - Date range
  - Initiator
  - Device type
- Detailed return timeline
- Comments/feedback history
- Approval chain visibility

### 8. Approval Management

#### Approvals Dashboard (Distributors)
- Pending approvals from sub-distributors list
- Filter by:
  - Sub-distributor
  - Distribution date
  - Status
- Bulk view of distributed devices
- For each distribution:
  - Show approval status
  - Approved by (name and timestamp)
  - Pending count
  - Rejected count (with reasons)
- Send reminders for pending approvals
- View approval history

#### Approval Actions (Sub-Distributors)
- Approve device receipt:
  - Verify quantity
  - Verify device condition
  - Check against distribution list
  - Add notes
  - Digital signature/confirmation
- Reject with mandatory reason:
  - Damaged in transit
  - Wrong device
  - Incorrect quantity
  - Other (specify)
- Partial approval option (approve some, reject others in same batch)

### 9. Reports & Analytics

#### Generate Reports
- Device inventory report
- Distribution history report
- Return analytics
- Defect analytics by device model
- Sub-distributor performance
- Operator device assignments
- Pending approvals summary
- Export options (PDF, Excel, CSV)
- Date range filters
- Custom report builder

### 10. User Management (Admin)
- Create/edit/delete users
- Assign roles
- Manage permissions
- View user activity logs
- Deactivate/reactivate accounts

### 11. Notifications System
- Real-time notifications for:
  - New device distribution
  - Pending approvals
  - Defect reports
  - Return requests
  - Approval/rejection notifications
  - Status changes
- Notification center/bell icon
- Email notifications (optional)

## UI/UX Requirements

### Design Principles
- Clean, modern interface using Tailwind CSS
- Responsive design (mobile, tablet, desktop)
- Intuitive navigation with sidebar menu
- Role-based menu items
- Breadcrumb navigation
- Loading states and skeleton screens
- Error handling with user-friendly messages
- Success/failure toast notifications

### Color Scheme (Suggested)
- Primary: Blue (#3B82F6)
- Success: Green (#10B981)
- Warning: Yellow (#F59E0B)
- Danger: Red (#EF4444)
- Neutral: Gray shades

### Key Components Needed
1. **Navigation**
   - Top navbar with user profile, notifications, logout
   - Sidebar with role-based menu items
   - Breadcrumbs

2. **Data Tables**
   - Sortable columns
   - Pagination
   - Search/filter
   - Bulk actions
   - Export options

3. **Forms**
   - Input validation
   - Error messages
   - Required field indicators
   - Auto-save drafts (for long forms)

4. **Cards**
   - Device cards
   - Summary cards for dashboard
   - Status cards

5. **Modals**
   - Confirmation dialogs
   - Quick view details
   - Approval/rejection forms

6. **Status Badges**
   - Color-coded status indicators
   - Consistent across the app

7. **Timeline Components**
   - Visual device journey
   - Approval workflow timeline
   - Return process timeline

## Technical Requirements

### State Management
- Global state for:
  - User authentication
  - User role and permissions
  - Notifications
- Component-level state for forms and UI interactions

### API Integration (Mock for now)
- RESTful API structure
- Endpoints for:
  - Authentication
  - Device CRUD operations
  - Distribution management
  - Defect reporting
  - Returns
  - Approvals
  - Reports
  - User management

### Data Models

#### Device
```javascript
{
  id: string,
  macAddress: string,
  serialNumber: string,
  model: string,
  manufacturer: string,
  hardwareVersion: string,
  firmwareVersion: string,
  condition: string,
  status: string,
  currentLocation: string,
  currentHolder: string,
  registeredAt: timestamp,
  registeredBy: string
}
```

#### Distribution
```javascript
{
  id: string,
  fromDistributor: string,
  toDistributor: string,
  devices: array,
  status: string,
  createdAt: timestamp,
  approvedAt: timestamp,
  approvedBy: string,
  rejectionReason: string
}
```

#### DefectReport
```javascript
{
  id: string,
  deviceId: string,
  reportedBy: string,
  defectType: string,
  severity: string,
  description: string,
  photos: array,
  status: string,
  reviewedBy: string,
  reviewComments: string,
  reportedAt: timestamp
}
```

#### ReturnRequest
```javascript
{
  id: string,
  deviceId: string,
  initiatedBy: string,
  reason: string,
  defectReportId: string,
  status: string,
  approvalChain: array,
  currentApprover: string,
  createdAt: timestamp,
  completedAt: timestamp
}
```

## Development Phases

### Phase 1: Foundation
- Project setup (React + Tailwind)
- Authentication system
- Role-based routing
- Basic layouts and navigation

### Phase 2: Core Features
- Device registration
- Distribution management
- Approval workflow
- User dashboards

### Phase 3: Advanced Features
- Device tracking
- Defect reporting
- Return management
- Notifications

### Phase 4: Polish
- Reports and analytics
- User management
- Testing and bug fixes
- Performance optimization

## Success Criteria
- All user roles can access appropriate features
- Complete device lifecycle tracking
- Efficient approval workflow
- Easy-to-use defect and return management
- Real-time status updates
- Comprehensive reporting
- Responsive and intuitive UI
- Secure authentication and authorization

## Future Enhancements (Optional)
- Barcode/QR code scanning via camera
- Mobile app version
- Real-time chat support
- Automated notifications via SMS/Email
- Integration with inventory management systems
- Analytics dashboard with charts
- Geolocation tracking for device shipments
- API documentation for third-party integrations
