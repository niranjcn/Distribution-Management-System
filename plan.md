# Plan: Range-Based Filtering for Dashboards & Reports

## Objective

Add date range filtering to all dashboard and report views so users can filter metrics, charts, and data by a configurable time window instead of always seeing hardcoded or unfiltered data.

---

## Current State Summary

| Area | Current Behavior | Accepts Date Params? |
|------|-----------------|---------------------|
| **Reports** (inventory, distribution-summary, defect-summary, return-summary) | Frontend dropdown sends only `start_date`. Backend supports `start_date` & `end_date`. | Yes (partial) |
| **Reports** (user-activity, device-utilization) | No date support at all | No |
| **Dashboard Stats** (`/stats`) | All-time totals, hardcoded "this month" for defects | No |
| **Dashboard Advanced Metrics** (`/advanced-metrics`) | Hardcoded month/year/60-day windows | No |
| **Dashboard Charts** (`/charts/distributions`, `/charts/defects`) | Hardcoded trailing 12 months | No |
| **Dashboard User KPI** (`/user-kpi/{id}`) | Unfiltered totals + hardcoded 12-month trends | No |
| **Dashboard Activities** (`/activities`) | Full date range filtering (both start & end) | Yes |
| **Dashboard** (Admin Dashboard, Manager Dashboard, SubDistributor Dashboard, Operator Dashboard) | No date filter UI at all | N/A |

---

## Files Affected

### Backend (7 files)

| File | Change |
|------|--------|
| `backend/app/routes/dashboard.py` | Add `start_date` / `end_date` query params to 7 route handlers |
| `backend/app/services/dashboard_service.py` | Add `start_date` / `end_date` params to 6 service methods, modify SQL queries |
| `backend/app/routes/reports.py` | Add `start_date` / `end_date` query params to 2 route handlers (user-activity, device-utilization) |
| `backend/app/services/report_service.py` | Add `start_date` / `end_date` params to 2 service methods |
| `backend/app/utils/permissions.py` | No change needed |
| `backend/app/middleware/auth_middleware.py` | No change needed |
| `backend/app/database.py` | No change needed |

### Frontend (7 files)

| File | Change |
|------|--------|
| `frontend/src/services/api.js` | Add `start_date` / `end_date` params to dashboard API functions |
| `frontend/src/pages/dashboards/AdminDashboard.jsx` | Add date range selector, pass dates to API calls, reload on range change |
| `frontend/src/pages/dashboards/ManagerDashboard.jsx` | Add date range selector, pass dates to API calls, reload on range change |
| `frontend/src/pages/dashboards/SubDistributorDashboard.jsx` | Add date range selector, pass dates to API calls |
| `frontend/src/pages/dashboards/OperatorDashboard.jsx` | Add date range selector, pass dates to API calls |
| `frontend/src/pages/Reports.jsx` | Fix to send both `start_date` AND `end_date`, add date params to user-activity & device-utilization |
| `frontend/src/pages/Activities.jsx` | No change needed (already has full date filtering) |

**Total: 14 files modified**

---

## Detailed Changes

### Phase 1: Backend — Add Date Params to Dashboard Service

#### 1a. `get_dashboard_stats` — Add `start_date` / `end_date`

```python
async def get_dashboard_stats(user: Dict[str, Any], 
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> Dict[str, Any]:
```

- All SQL queries that count devices, distributions, defects, returns, users, approvals
  currently do full-table counts. Add `_build_date_filter` where applicable:
  - `created_at` for devices, distributions, defects, returns, users, approvals  
  - For "defects this month" — replace hardcoded `month_start` with `start_date` param
  - For lower roles (sub_distributor, operator) — keep role scoping, add date filter

**Queries affected:**
- Device counts → `WHERE created_at >= ? AND created_at <= ?`
- Distribution counts → `WHERE created_at >= ? AND created_at <= ?`
- Defect counts → `WHERE created_at >= ? AND created_at <= ?`
- Return counts → `WHERE created_at >= ? AND created_at <= ?`
- Approval counts → `WHERE created_at >= ? AND created_at <= ?`
- User counts → `WHERE created_at >= ? AND created_at <= ?`

If `start_date` is `None` — keep existing all-time behavior.

#### 1b. `get_advanced_dashboard_metrics` — Add `start_date` / `end_date`

```python
async def get_advanced_dashboard_metrics(user: Dict[str, Any],
                                          start_date: Optional[str] = None,
                                          end_date: Optional[str] = None) -> Dict[str, Any]:
```

- Replace hardcoded `month_start`, `year_start`, `sixty_days_ago` with `start_date` / `end_date`
- 12-month trends should remain 12-month but scoped to range if provided
- If `start_date` is `None` — keep existing year/month/60-day defaults

#### 1c. `get_distribution_chart_data` — Add `start_date` / `end_date`

```python
async def get_distribution_chart_data(start_date: Optional[str] = None,
                                      end_date: Optional[str] = None) -> list:
```

- Currently loops last 12 months with `timedelta(days=i*30)`
- If dates provided, use them as the window instead of 12-month default

#### 1d. `get_defect_chart_data` — Add `start_date` / `end_date`

```python
async def get_defect_chart_data(start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> list:
```

- Same pattern as distribution chart data
- If dates provided, use them as the window instead of 12-month default

#### 1e. `get_user_kpi` — Add `start_date` / `end_date`

```python
async def get_user_kpi(current_user: Dict[str, Any], target_user_id: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Dict[str, Any]:
```

- Add date filter to device, distribution, defect counts
- 12-month trends remain but scoped to range

#### 1f. `get_distribution_device_analytics` — Add `start_date` / `end_date`

```python
async def get_distribution_device_analytics(start_date: Optional[str] = None,
                                            end_date: Optional[str] = None) -> Dict[str, Any]:
```

- Add date filter to distribution device analytics queries

#### 1g. `get_system_alerts` — Consider date scope

- Critical defects count, pending approvals, low stock — these are current-state counters.
- Leave as is (no date filter makes sense for "pending approvals right now").

### Phase 2: Backend — Add Date Params to Dashboard Routes

In `backend/app/routes/dashboard.py`:

```python
@router.get("/stats")
async def get_dashboard_stats(
    start_date: str = Query(None), 
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
): ...

@router.get("/advanced-metrics")
async def get_advanced_dashboard_metrics(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
): ...

@router.get("/charts/distributions")
async def get_distribution_chart_data(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
): ...

@router.get("/charts/defects")
async def get_defect_chart_data(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
): ...

@router.get("/user-kpi/{user_id}")
async def get_user_kpi(
    user_id: str,
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(get_current_user)
): ...

@router.get("/distribution-device-analytics")
async def get_distribution_device_analytics(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_md)
): ...
```

### Phase 3: Backend — Add Date Params to Report Routes

In `backend/app/routes/reports.py`:

```python
@router.get("/user-activity")
async def get_user_activity_report(
    start_date: str = Query(None),
    end_date: str = Query(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
): ...

@router.get("/device-utilization")
async def get_device_utilization_report(
    start_date: str = Query(None),
    end_date: str = Depends(None),
    current_user: dict = Depends(require_admin_or_manager_or_md_or_staff)
): ...
```

### Phase 4: Frontend — API Layer

In `frontend/src/services/api.js`, update dashboard API functions to accept params:

```javascript
export const dashboardAPI = {
  getStats: async (params = {}) => api.get('/dashboard/stats', { params }),
  getAdvancedMetrics: async (params = {}) => api.get('/dashboard/advanced-metrics', { params }),
  getDistributionChartData: async (params = {}) => api.get('/dashboard/charts/distributions', { params }),
  getDefectChartData: async (params = {}) => api.get('/dashboard/charts/defects', { params }),
  getUserKpi: async (userId, params = {}) => api.get(`/dashboard/user-kpi/${userId}`, { params }),
  getDistributionDeviceAnalytics: async (params = {}) => api.get('/dashboard/distribution-device-analytics', { params }),
  // getRecentActivities, getSystemAlerts, getScopeUsers — no date filter needed
};
```

### Phase 5: Frontend — Date Range Filter Component

Create a reusable `DateRangeFilter` component at:
`frontend/src/components/ui/DateRangeFilter.jsx`

Options: `Today`, `Last 7 Days`, `Last 30 Days`, `Last 90 Days`, `This Year`, `All Time`, `Custom Range`

When "Custom Range" is selected, show two date pickers (start / end).

Props:
- `value`: current range string
- `onChange`: callback with `{ range, startDate, endDate }`
- `showCustom`: boolean (default true)

### Phase 6: Frontend — Admin Dashboard

Add state:
```javascript
const [dateRange, setDateRange] = useState({ range: 'all', startDate: null, endDate: null });
```

Add `buildDateParams`:
```javascript
const buildDateParams = (range) => {
  const params = {};
  if (range.startDate || range.endDate) {
    if (range.startDate) params.start_date = range.startDate.toISOString();
    if (range.endDate) params.end_date = range.endDate.toISOString();
  }
  return params;
};
```

Add `DateRangeFilter` component above stat cards.

Pass `buildDateParams(dateRange)` to all dashboard API calls:
- `dashboardAPI.getStats(params)`
- `dashboardAPI.getAdvancedMetrics(params)`
- `dashboardAPI.getDistributionChartData(params)`
- `dashboardAPI.getDefectChartData(params)`
- `dashboardAPI.getDistributionDeviceAnalytics(params)`

Re-fetch when `dateRange` changes via `useEffect` dependency.

**Charts affected:**
- Active/Inactive Doughnut — will reflect filtered range
- Device Status Pie — will reflect filtered range
- 12-Month Defect Trend Line — will reflect filtered range
- Distribution device analytics tables

**Stat cards affected:**
- Total Devices, Active Devices, Inactive Devices — filtered
- Defects (Month), Defects (Year) — replaced by filtered values
- Replacements — filtered
- Reliability cards (Defect Incidence %, 60-Day Repair Rate) — filtered
- Role counts (Operators, Sub Distributors, Clusters, Staff) — filtered

**Not filtered (current-state data, keep as is):**
- Recent Activities (always shows latest)
- Critical Ops Alerts (current state)
- Recent Users (always shows latest)
- Recent Defect Reports (always shows latest)
- HierarchySelector / UserKpiSection — should also get date params

### Phase 7: Frontend — Manager Dashboard

Same pattern as Admin Dashboard:
- Add `DateRangeFilter`
- Pass date params to all API calls
- Re-fetch on range change

**Charts affected:**
- Device Health Doughnut
- Replacement Confirmation Pipeline Doughnut
- Defect Trend Line
- Distribution analytics cards/tables

**Stat cards affected:**
- Total Devices, Active Devices, Defects, Awaiting Receipt, Replacements

**Not filtered:**
- Alerts (current state)
- Quick Stats (Approved/Pending/InTransit/Rejected) — these are derived from all distributions fetched

### Phase 8: Frontend — SubDistributor Dashboard

- Add `DateRangeFilter` (simpler, maybe just 4 options: 30d/90d/Year/All)
- Pass date params to `dashboardAPI.getStats(params)` and `dashboardAPI.getAdvancedMetrics(params)`

**Stat cards affected:**
- Received Devices, Pending Confirmations, My Operators, Defect Reports, Returns, Assigned

**Charts affected:**
- My Device Active vs Inactive Doughnut
- Cluster/Operator Account Active vs Inactive Doughnut

**Not filtered:**
- My Devices list, Pending Confirmations list, My Operators list (current state)
- Defect Reports to Review, Return Requests lists (current state)

### Phase 9: Frontend — Operator Dashboard

- Add `DateRangeFilter` (simpler, 4 options)
- Pass date params to `dashboardAPI.getStats(params)` and `dashboardAPI.getAdvancedMetrics(params)`

**Stat cards affected:**
- Assigned Devices, Active, In Use, My Defect Reports (filtered)

**Charts affected:**
- My Device Active vs Inactive Doughnut

**Not filtered:**
- My Devices cards, My Defect Reports list, My Return Requests list (current state)

### Phase 10: Frontend — Fix Reports Page

In `frontend/src/pages/Reports.jsx`:

1. **Send both `start_date` AND `end_date`** to the API:
```javascript
const buildDateParams = (range) => {
  const now = new Date();
  const params = {};
  if (range === 'all') return params;
  
  const start = buildRangeStart(range);
  if (start) params.start_date = start.toISOString();
  
  // Add end_date = end of today
  const end = new Date();
  end.setHours(23, 59, 59, 999);
  params.end_date = end.toISOString();
  
  return params;
};
```

2. **Add date params to user-activity report** and device-utilization report (if they become available)

3. **Add Custom Range option** to the dropdown (optional enhancement)

---

## Database Columns Used for Date Filtering

| Table | Date Column | Used In |
|-------|------------|---------|
| `devices` | `created_at` | Dashboard stats, inventory report, advanced metrics |
| `distributions` | `created_at` | Dashboard stats, distribution summary, chart data, advanced metrics |
| `defect_reports` | `created_at` | Dashboard stats, defect summary, chart data, advanced metrics |
| `return_requests` | `created_at` | Dashboard stats, return summary, advanced metrics |
| `users` | `created_at` | Dashboard stats (role counts filtered by creation date) |
| `approvals` | `created_at` | Dashboard stats (approval counts) |
| `device_history` | `timestamp` | Activities (already filtered correctly) |
| `inventory_stock_movements` | `created_at` | Activities (already filtered correctly) |
| `api_activity_logs` | `created_at` | Activities (already filtered correctly) |

---

## What Will Be Affected

### User Experience Changes

| Role | Dashboard | What Changes |
|------|-----------|-------------|
| `super_admin`, `md_director` | Admin Dashboard | Date filter appears on top. All stat cards, charts, and tables become time-scoped. |
| `manager`, `pdic_staff` | Manager Dashboard | Same as above. |
| `sub_distribution_manager`, `sub_distributor`, `cluster` | SubDistributor Dashboard | Date filter appears. Stats and charts become time-scoped. |
| `operator` | Operator Dashboard | Date filter appears. Stats and charts become time-scoped. |
| All (admin/mgr/staff) | Reports page | Fix: now sends `end_date` properly. Optional: custom range. |

### API Response Changes

All modified endpoints will return the same structure `{ success: true, message, data }`. The `data` contents will reflect the filtered time range instead of all-time or hardcoded windows.

**No breaking changes** — if `start_date` / `end_date` are omitted, all endpoints fall back to current behavior (all-time or hardcoded defaults).

### What Will NOT Be Affected

- Authentication / JWT — no changes
- User management — no changes
- Device management CRUD — no changes
- Distribution workflow — no changes
- Approval workflow — no changes
- Notification system — no changes
- Backup/export endpoints — no changes
- Activities page — no changes (already works)
- Recent activities, alerts (current-state lists on dashboards) — no changes
- All other pages (Devices, Distributions, Defects, Returns, Users) — no changes
- Database schema — no changes
- Nginx / Docker config — no changes

---

## Implementation Order

1. Backend: Add `start_date`/`end_date` to dashboard service methods
2. Backend: Add `start_date`/`end_date` to dashboard route handlers
3. Backend: Add `start_date`/`end_date` to report service methods (user-activity, device-utilization)
4. Backend: Add `start_date`/`end_date` to report route handlers
5. Frontend: Create `DateRangeFilter` component
6. Frontend: Update API service with params
7. Frontend: Update AdminDashboard
8. Frontend: Update ManagerDashboard
9. Frontend: Update SubDistributorDashboard
10. Frontend: Update OperatorDashboard
11. Frontend: Fix Reports page
12. Test: Verify each role dashboard renders with filtered data
13. Test: Verify no regressions when no date params sent

---

## Revert Strategy

If any issue arises:
1. Each backend change is optional — omit params → old behavior
2. Each frontend component can be reverted individually
3. No database migrations → zero risk to existing data
