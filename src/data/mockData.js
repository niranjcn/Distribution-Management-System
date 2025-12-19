// Mock data for the Distribution Management System

// Users
export const users = [
  { id: '1', name: 'John Admin', email: 'admin@dms.com', role: 'admin', status: 'active', createdAt: '2024-01-15' },
  { id: '2', name: 'Sarah Manager', email: 'manager@dms.com', role: 'manager', status: 'active', createdAt: '2024-02-10' },
  { id: '3', name: 'Mike Distributor', email: 'distributor@dms.com', role: 'distributor', status: 'active', createdAt: '2024-02-20' },
  { id: '4', name: 'Lisa SubDist', email: 'subdist@dms.com', role: 'sub-distributor', status: 'active', createdAt: '2024-03-01' },
  { id: '5', name: 'Tom Operator', email: 'operator@dms.com', role: 'operator', status: 'active', createdAt: '2024-03-15' },
  { id: '6', name: 'Emma Wilson', email: 'emma@dms.com', role: 'operator', status: 'active', createdAt: '2024-04-01' },
  { id: '7', name: 'James Brown', email: 'james@dms.com', role: 'sub-distributor', status: 'inactive', createdAt: '2024-04-10' },
  { id: '8', name: 'Anna Smith', email: 'anna@dms.com', role: 'operator', status: 'active', createdAt: '2024-05-01' },
];

// Sub-distributors
export const subDistributors = [
  { id: 'sd1', name: 'Sub Distributor Alpha', location: 'New York', contactPerson: 'Lisa SubDist', email: 'alpha@subdist.com', phone: '+1-555-0101', status: 'active' },
  { id: 'sd2', name: 'Sub Distributor Beta', location: 'Los Angeles', contactPerson: 'James Brown', email: 'beta@subdist.com', phone: '+1-555-0102', status: 'active' },
  { id: 'sd3', name: 'Sub Distributor Gamma', location: 'Chicago', contactPerson: 'Robert Lee', email: 'gamma@subdist.com', phone: '+1-555-0103', status: 'active' },
  { id: 'sd4', name: 'Sub Distributor Delta', location: 'Houston', contactPerson: 'Maria Garcia', email: 'delta@subdist.com', phone: '+1-555-0104', status: 'inactive' },
];

// Operators
export const operators = [
  { id: 'op1', name: 'Tom Operator', email: 'tom@operator.com', subDistributor: 'sd1', assignedDevices: 12, status: 'active' },
  { id: 'op2', name: 'Emma Wilson', email: 'emma@operator.com', subDistributor: 'sd1', assignedDevices: 8, status: 'active' },
  { id: 'op3', name: 'Anna Smith', email: 'anna@operator.com', subDistributor: 'sd2', assignedDevices: 15, status: 'active' },
  { id: 'op4', name: 'David Johnson', email: 'david@operator.com', subDistributor: 'sd2', assignedDevices: 6, status: 'active' },
  { id: 'op5', name: 'Chris Martin', email: 'chris@operator.com', subDistributor: 'sd3', assignedDevices: 10, status: 'inactive' },
];

// Devices
export const devices = [
  { id: 'd1', macAddress: 'AA:BB:CC:DD:EE:01', serialNumber: 'SN-2024-001', model: 'Router X500', manufacturer: 'NetGear', hardwareVersion: '2.0', firmwareVersion: '5.1.2', condition: 'new', status: 'active', currentLocation: 'sub-distributor', currentHolder: 'Sub Distributor Alpha', registeredAt: '2024-01-15', registeredBy: 'Mike Distributor' },
  { id: 'd2', macAddress: 'AA:BB:CC:DD:EE:02', serialNumber: 'SN-2024-002', model: 'Router X500', manufacturer: 'NetGear', hardwareVersion: '2.0', firmwareVersion: '5.1.2', condition: 'new', status: 'in-use', currentLocation: 'operator', currentHolder: 'Tom Operator', registeredAt: '2024-01-16', registeredBy: 'Mike Distributor' },
  { id: 'd3', macAddress: 'AA:BB:CC:DD:EE:03', serialNumber: 'SN-2024-003', model: 'Switch S200', manufacturer: 'Cisco', hardwareVersion: '1.5', firmwareVersion: '3.2.1', condition: 'refurbished', status: 'stored', currentLocation: 'main-distribution', currentHolder: 'Main Distribution', registeredAt: '2024-01-17', registeredBy: 'Mike Distributor' },
  { id: 'd4', macAddress: 'AA:BB:CC:DD:EE:04', serialNumber: 'SN-2024-004', model: 'Modem M100', manufacturer: 'TP-Link', hardwareVersion: '3.0', firmwareVersion: '2.0.5', condition: 'new', status: 'defective', currentLocation: 'sub-distributor', currentHolder: 'Sub Distributor Beta', registeredAt: '2024-01-18', registeredBy: 'Mike Distributor' },
  { id: 'd5', macAddress: 'AA:BB:CC:DD:EE:05', serialNumber: 'SN-2024-005', model: 'Router X700', manufacturer: 'NetGear', hardwareVersion: '2.1', firmwareVersion: '5.2.0', condition: 'new', status: 'active', currentLocation: 'operator', currentHolder: 'Emma Wilson', registeredAt: '2024-01-19', registeredBy: 'Mike Distributor' },
  { id: 'd6', macAddress: 'AA:BB:CC:DD:EE:06', serialNumber: 'SN-2024-006', model: 'Switch S300', manufacturer: 'Cisco', hardwareVersion: '2.0', firmwareVersion: '4.0.0', condition: 'new', status: 'in-transit', currentLocation: 'in-transit', currentHolder: 'In Transit to SD Beta', registeredAt: '2024-02-01', registeredBy: 'Mike Distributor' },
  { id: 'd7', macAddress: 'AA:BB:CC:DD:EE:07', serialNumber: 'SN-2024-007', model: 'Router X500', manufacturer: 'NetGear', hardwareVersion: '2.0', firmwareVersion: '5.1.2', condition: 'new', status: 'pending', currentLocation: 'main-distribution', currentHolder: 'Main Distribution', registeredAt: '2024-02-05', registeredBy: 'Mike Distributor' },
  { id: 'd8', macAddress: 'AA:BB:CC:DD:EE:08', serialNumber: 'SN-2024-008', model: 'Modem M200', manufacturer: 'TP-Link', hardwareVersion: '3.1', firmwareVersion: '2.1.0', condition: 'refurbished', status: 'returned', currentLocation: 'main-distribution', currentHolder: 'Main Distribution', registeredAt: '2024-02-10', registeredBy: 'Mike Distributor' },
  { id: 'd9', macAddress: 'AA:BB:CC:DD:EE:09', serialNumber: 'SN-2024-009', model: 'Router X700', manufacturer: 'NetGear', hardwareVersion: '2.1', firmwareVersion: '5.2.0', condition: 'new', status: 'active', currentLocation: 'operator', currentHolder: 'Anna Smith', registeredAt: '2024-02-15', registeredBy: 'Mike Distributor' },
  { id: 'd10', macAddress: 'AA:BB:CC:DD:EE:10', serialNumber: 'SN-2024-010', model: 'Switch S200', manufacturer: 'Cisco', hardwareVersion: '1.5', firmwareVersion: '3.2.1', condition: 'new', status: 'active', currentLocation: 'sub-distributor', currentHolder: 'Sub Distributor Gamma', registeredAt: '2024-02-20', registeredBy: 'Mike Distributor' },
  { id: 'd11', macAddress: 'AA:BB:CC:DD:EE:11', serialNumber: 'SN-2024-011', model: 'Router X500', manufacturer: 'NetGear', hardwareVersion: '2.0', firmwareVersion: '5.1.2', condition: 'new', status: 'in-use', currentLocation: 'operator', currentHolder: 'David Johnson', registeredAt: '2024-03-01', registeredBy: 'Mike Distributor' },
  { id: 'd12', macAddress: 'AA:BB:CC:DD:EE:12', serialNumber: 'SN-2024-012', model: 'Modem M100', manufacturer: 'TP-Link', hardwareVersion: '3.0', firmwareVersion: '2.0.5', condition: 'new', status: 'stored', currentLocation: 'main-distribution', currentHolder: 'Main Distribution', registeredAt: '2024-03-05', registeredBy: 'Mike Distributor' },
];

// Distributions
export const distributions = [
  { id: 'dist1', batchId: 'BATCH-2024-001', fromDistributor: 'Main Distribution', toDistributor: 'Sub Distributor Alpha', devices: ['d1', 'd2'], deviceCount: 2, status: 'approved', createdAt: '2024-01-20', approvedAt: '2024-01-21', approvedBy: 'Lisa SubDist', notes: 'First batch of routers' },
  { id: 'dist2', batchId: 'BATCH-2024-002', fromDistributor: 'Main Distribution', toDistributor: 'Sub Distributor Beta', devices: ['d4', 'd6'], deviceCount: 2, status: 'pending', createdAt: '2024-02-01', approvedAt: null, approvedBy: null, notes: 'Mixed device batch' },
  { id: 'dist3', batchId: 'BATCH-2024-003', fromDistributor: 'Main Distribution', toDistributor: 'Sub Distributor Gamma', devices: ['d10'], deviceCount: 1, status: 'approved', createdAt: '2024-02-20', approvedAt: '2024-02-21', approvedBy: 'Robert Lee', notes: 'Single switch delivery' },
  { id: 'dist4', batchId: 'BATCH-2024-004', fromDistributor: 'Sub Distributor Alpha', toDistributor: 'Tom Operator', devices: ['d2'], deviceCount: 1, status: 'approved', createdAt: '2024-01-25', approvedAt: '2024-01-25', approvedBy: 'Tom Operator', notes: 'Assigned to operator' },
  { id: 'dist5', batchId: 'BATCH-2024-005', fromDistributor: 'Sub Distributor Alpha', toDistributor: 'Emma Wilson', devices: ['d5'], deviceCount: 1, status: 'approved', createdAt: '2024-01-28', approvedAt: '2024-01-28', approvedBy: 'Emma Wilson', notes: 'Router assignment' },
  { id: 'dist6', batchId: 'BATCH-2024-006', fromDistributor: 'Sub Distributor Beta', toDistributor: 'Anna Smith', devices: ['d9'], deviceCount: 1, status: 'pending', createdAt: '2024-02-25', approvedAt: null, approvedBy: null, notes: 'Awaiting operator confirmation' },
  { id: 'dist7', batchId: 'BATCH-2024-007', fromDistributor: 'Main Distribution', toDistributor: 'Sub Distributor Alpha', devices: ['d7'], deviceCount: 1, status: 'in-transit', createdAt: '2024-03-01', approvedAt: null, approvedBy: null, notes: 'In transit' },
  { id: 'dist8', batchId: 'BATCH-2024-008', fromDistributor: 'Sub Distributor Beta', toDistributor: 'David Johnson', devices: ['d11'], deviceCount: 1, status: 'approved', createdAt: '2024-03-05', approvedAt: '2024-03-06', approvedBy: 'David Johnson', notes: 'Router for field use' },
];

// Defect Reports
export const defectReports = [
  { id: 'def1', deviceId: 'd4', device: devices[3], reportedBy: 'James Brown', defectType: 'Hardware', severity: 'critical', description: 'Device not powering on. No LED indicators light up when connected to power.', photos: ['photo1.jpg', 'photo2.jpg'], status: 'open', reviewedBy: null, reviewComments: null, reportedAt: '2024-02-15', subDistributor: 'Sub Distributor Beta' },
  { id: 'def2', deviceId: 'd2', device: devices[1], reportedBy: 'Tom Operator', defectType: 'Software', severity: 'medium', description: 'Firmware update fails repeatedly. Device becomes unresponsive during update.', photos: ['photo3.jpg'], status: 'under-review', reviewedBy: 'Lisa SubDist', reviewComments: 'Investigating firmware compatibility', reportedAt: '2024-02-20', subDistributor: 'Sub Distributor Alpha' },
  { id: 'def3', deviceId: 'd8', device: devices[7], reportedBy: 'Anna Smith', defectType: 'Cosmetic', severity: 'low', description: 'Scratches on the casing, does not affect functionality.', photos: [], status: 'resolved', reviewedBy: 'Mike Distributor', reviewComments: 'Accepted as minor cosmetic issue', reportedAt: '2024-02-25', subDistributor: 'Sub Distributor Beta' },
  { id: 'def4', deviceId: 'd5', device: devices[4], reportedBy: 'Emma Wilson', defectType: 'Hardware', severity: 'high', description: 'Ethernet ports 3 and 4 not functioning. Traffic not passing through.', photos: ['photo4.jpg', 'photo5.jpg'], status: 'open', reviewedBy: null, reviewComments: null, reportedAt: '2024-03-01', subDistributor: 'Sub Distributor Alpha' },
  { id: 'def5', deviceId: 'd11', device: devices[10], reportedBy: 'David Johnson', defectType: 'Software', severity: 'medium', description: 'WiFi signal drops intermittently. Requires restart to fix.', photos: [], status: 'under-review', reviewedBy: 'James Brown', reviewComments: 'Checking for firmware updates', reportedAt: '2024-03-10', subDistributor: 'Sub Distributor Beta' },
];

// Return Requests
export const returnRequests = [
  { id: 'ret1', deviceId: 'd4', device: devices[3], initiatedBy: 'James Brown', initiatorRole: 'sub-distributor', reason: 'Defective device', defectReportId: 'def1', requestedAction: 'Replace', status: 'pending', approvalChain: [{ role: 'sub-distributor', status: 'approved', by: 'James Brown', at: '2024-02-16' }, { role: 'distributor', status: 'pending', by: null, at: null }], currentApprover: 'distributor', createdAt: '2024-02-16', completedAt: null, notes: 'Critical hardware failure' },
  { id: 'ret2', deviceId: 'd8', device: devices[7], initiatedBy: 'Anna Smith', initiatorRole: 'operator', reason: 'Wrong device received', defectReportId: null, requestedAction: 'Replace', status: 'approved', approvalChain: [{ role: 'sub-distributor', status: 'approved', by: 'James Brown', at: '2024-02-26' }, { role: 'distributor', status: 'approved', by: 'Mike Distributor', at: '2024-02-27' }], currentApprover: null, createdAt: '2024-02-25', completedAt: '2024-02-28', notes: 'Device model mismatch' },
  { id: 'ret3', deviceId: 'd2', device: devices[1], initiatedBy: 'Tom Operator', initiatorRole: 'operator', reason: 'Defective device', defectReportId: 'def2', requestedAction: 'Repair', status: 'under-review', approvalChain: [{ role: 'sub-distributor', status: 'under-review', by: 'Lisa SubDist', at: null }], currentApprover: 'sub-distributor', createdAt: '2024-02-22', completedAt: null, notes: 'Pending investigation of firmware issue' },
  { id: 'ret4', deviceId: 'd5', device: devices[4], initiatedBy: 'Emma Wilson', initiatorRole: 'operator', reason: 'Defective device', defectReportId: 'def4', requestedAction: 'Replace', status: 'pending', approvalChain: [{ role: 'sub-distributor', status: 'pending', by: null, at: null }], currentApprover: 'sub-distributor', createdAt: '2024-03-02', completedAt: null, notes: 'Hardware ports not working' },
];

// Device history/journey for tracking
export const deviceHistory = {
  'd1': [
    { action: 'Registered', location: 'NOC', timestamp: '2024-01-15 09:00', user: 'Mike Distributor', notes: 'Received from NOC' },
    { action: 'Stored', location: 'Main Distribution', timestamp: '2024-01-15 10:00', user: 'Mike Distributor', notes: 'Added to inventory' },
    { action: 'Distributed', location: 'Main Distribution', timestamp: '2024-01-20 14:00', user: 'Mike Distributor', notes: 'Sent to Sub Distributor Alpha' },
    { action: 'Received', location: 'Sub Distributor Alpha', timestamp: '2024-01-21 11:00', user: 'Lisa SubDist', notes: 'Approved and received' },
  ],
  'd2': [
    { action: 'Registered', location: 'NOC', timestamp: '2024-01-16 09:00', user: 'Mike Distributor', notes: 'Received from NOC' },
    { action: 'Distributed', location: 'Main Distribution', timestamp: '2024-01-20 14:00', user: 'Mike Distributor', notes: 'Sent to Sub Distributor Alpha' },
    { action: 'Received', location: 'Sub Distributor Alpha', timestamp: '2024-01-21 11:00', user: 'Lisa SubDist', notes: 'Approved' },
    { action: 'Assigned', location: 'Sub Distributor Alpha', timestamp: '2024-01-25 10:00', user: 'Lisa SubDist', notes: 'Assigned to operator' },
    { action: 'Activated', location: 'Tom Operator', timestamp: '2024-01-25 15:00', user: 'Tom Operator', notes: 'Device in use' },
    { action: 'Defect Reported', location: 'Tom Operator', timestamp: '2024-02-20 09:00', user: 'Tom Operator', notes: 'Firmware update issue' },
  ],
};

// Dashboard statistics
export const dashboardStats = {
  admin: {
    totalDevices: 12,
    activeDevices: 6,
    totalUsers: 8,
    pendingApprovals: 3,
    defectReports: 5,
    returnRequests: 4,
  },
  manager: {
    totalDevices: 12,
    pendingApprovals: 3,
    defectReports: 5,
    returnRequests: 4,
    distributionThisMonth: 8,
    resolvedDefects: 1,
  },
  distributor: {
    totalInventory: 4,
    pendingDistributions: 2,
    awaitingApproval: 2,
    defectReports: 5,
    returnRequests: 4,
    distributedThisMonth: 6,
  },
  'sub-distributor': {
    receivedDevices: 3,
    pendingApprovals: 1,
    operatorCount: 2,
    defectReports: 2,
    returnRequests: 2,
    assignedToOperators: 2,
  },
  operator: {
    assignedDevices: 2,
    activeDevices: 1,
    defectReports: 1,
    pendingReturns: 1,
    inUseDevices: 1,
  },
};

// Recent activities
export const recentActivities = [
  { id: 1, action: 'Device registered', description: 'Router X500 (SN-2024-012) registered', user: 'Mike Distributor', timestamp: '2024-03-05 10:30' },
  { id: 2, action: 'Distribution created', description: 'Batch BATCH-2024-007 sent to Sub Distributor Alpha', user: 'Mike Distributor', timestamp: '2024-03-01 14:00' },
  { id: 3, action: 'Defect reported', description: 'WiFi issue reported for device d11', user: 'David Johnson', timestamp: '2024-03-10 09:15' },
  { id: 4, action: 'Return approved', description: 'Return request ret2 approved', user: 'Mike Distributor', timestamp: '2024-02-27 16:00' },
  { id: 5, action: 'Device approved', description: 'Sub Distributor Gamma approved batch BATCH-2024-003', user: 'Robert Lee', timestamp: '2024-02-21 11:30' },
];
