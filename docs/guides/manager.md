# Manager Guide

**Who you are:** The Manager runs day-to-day operations. You manage users and the team
structure, register and manage devices, create and approve distributions, handle defects
and returns, review approvals, view reports, and keep an eye on team activity. You work
from the **Management Ops Console** (Manager Dashboard). This guide walks you through
each function step by step.

Your role is deliberately broad: almost every management function is available to you —
devices, distribution, defects, returns, approvals, reports, external inventory, backups,
viewing a user's dashboard, team activity, and managing your team's accounts.

Read **[getting-started.md](getting-started.md)** first for the login basics and the
layout (sidebar on the left, profile menu and notification bell top-right).

---

## Contents

1. [Managing your profile](#1-managing-your-profile)
   - [Step-by-step: change your details later (Profile)](#step-by-step-change-your-details-later-profile)
2. [Finding an intended device (Track Device)](#2-finding-an-intended-device-track-device)
   - [Step-by-step: search for a specific device](#step-by-step-search-for-a-specific-device)
   - [What you see in the result](#what-you-see-in-the-result)
   - [Step-by-step: find a device when you don't know its serial](#step-by-step-find-a-device-when-you-dont-know-its-serial)
   - [Useful tricks](#useful-tricks)
3. [Using reports efficiently](#3-using-reports-efficiently)
   - [The shared controls](#the-shared-controls)
   - [How to use each report](#how-to-use-each-report)
   - [Efficiency tips](#efficiency-tips)
4. [Using the Activities section](#4-using-the-activities-section)
   - [Step-by-step: find activity](#step-by-step-find-activity)
   - [Step-by-step: filter the log](#step-by-step-filter-the-log)
   - [How to use it efficiently](#how-to-use-it-efficiently)
5. [Viewing a user's dashboard](#5-viewing-a-users-dashboard)
   - [Step-by-step: find and open a user's dashboard](#step-by-step-find-and-open-a-users-dashboard)
   - [Why this is useful](#why-this-is-useful)
6. [User management](#6-user-management)
   - [6.1 The user hierarchy (why it matters)](#61-the-user-hierarchy-why-it-matters)
   - [6.2 The roles you can assign](#62-the-roles-you-can-assign)
   - [6.3 Step-by-step: create a single user](#63-step-by-step-create-a-single-user)
   - [6.4 Step-by-step: edit, deactivate, or delete a user](#64-step-by-step-edit-deactivate-or-delete-a-user)
   - [6.5 Step-by-step: bulk upload users](#65-step-by-step-bulk-upload-users)
   - [6.6 Change requests (reviewing staff requests)](#66-change-requests-reviewing-staff-requests)
   - [6.7 Step-by-step: reassign a user (move a cluster or operator)](#67-step-by-step-reassign-a-user-move-a-cluster-or-operator)
7. [Device management](#7-device-management)
   - [7.1 Step-by-step: register a device individually](#71-step-by-step-register-a-device-individually)
   - [7.2 Step-by-step: bulk import devices](#72-step-by-step-bulk-import-devices)
   - [7.3 Step-by-step: find and filter devices](#73-step-by-step-find-and-filter-devices)
   - [7.4 Step-by-step: edit a device](#74-step-by-step-edit-a-device)
   - [7.5 Step-by-step: delete a device](#75-step-by-step-delete-a-device)
   - [7.6 Step-by-step: handle edit requests from staff](#76-step-by-step-handle-edit-requests-from-staff)
8. [Sub distributions & the approval workflow](#8-sub-distributions--the-approval-workflow)
   - [8.1 How the workflow works (read this first)](#81-how-the-workflow-works-read-this-first)
   - [8.2 Step-by-step: create a distribution individually](#82-step-by-step-create-a-distribution-individually)
   - [8.3 Step-by-step: bulk upload a distribution](#83-step-by-step-bulk-upload-a-distribution)
   - [8.4 Step-by-step: view and search distributions](#84-step-by-step-view-and-search-distributions)
   - [8.5 Downloading the device list of a distribution](#85-downloading-the-device-list-of-a-distribution)
   - [8.6 The statuses, explained](#86-the-statuses-explained)
   - [8.7 Handling disputes and the confirmation flow](#87-handling-disputes-and-the-confirmation-flow)
   - [8.8 Where distributions appear in Approvals](#88-where-distributions-appear-in-approvals)
9. [Defects, replacements & returns](#9-defects-replacements--returns)
   - [9.1 The defect workflow (read this first)](#91-the-defect-workflow-read-this-first)
   - [9.2 The Defect Reports page (how to check it)](#92-the-defect-reports-page-how-to-check-it)
   - [9.3 Step-by-step: review and handle a defect report](#93-step-by-step-review-and-handle-a-defect-report)
   - [9.4 Step-by-step: replace a defective device (in detail)](#94-step-by-step-replace-a-defective-device-in-detail)
   - [9.5 The Return Requests page, in detail](#95-the-return-requests-page-in-detail)
   - [9.6 The Pending Dues page, in detail](#96-the-pending-dues-page-in-detail)
   - [9.7 The Approvals page, in detail](#97-the-approvals-page-in-detail)
10. [Backup](#10-backup)
    - [10.1 What's on the Backup page](#101-whats-on-the-backup-page)
    - [10.2 Step-by-step: download a device backup](#102-step-by-step-download-a-device-backup)
    - [10.3 Step-by-step: download the returns & defects backup](#103-step-by-step-download-the-returns--defects-backup)
    - [10.4 Step-by-step: schedule the MySQL database backup](#104-step-by-step-schedule-the-mysql-database-backup)
    - [10.5 Step-by-step: use the backup document vault](#105-step-by-step-use-the-backup-document-vault)
11. [External inventory (items & distribution)](#11-external-inventory-items--distribution)
    - [11.1 What external inventory is (read this first)](#111-what-external-inventory-is-read-this-first)
    - [11.2 The page layout](#112-the-page-layout)
    - [11.3 Step-by-step: register an item individually](#113-step-by-step-register-an-item-individually)
    - [11.4 Step-by-step: edit an item](#114-step-by-step-edit-an-item)
    - [11.5 Step-by-step: delete an item](#115-step-by-step-delete-an-item)
    - [11.6 Step-by-step: bulk upload items from a file](#116-step-by-step-bulk-upload-items-from-a-file)
    - [11.7 Step-by-step: distribute a single item](#117-step-by-step-distribute-a-single-item)
    - [11.8 Step-by-step: bulk distribution from a file](#118-step-by-step-bulk-distribution-from-a-file)
    - [11.9 The Distributed Items page (history)](#119-the-distributed-items-page-history)
    - [11.10 Warranty status, explained](#1110-warranty-status-explained)
    - [11.11 What you can do](#1111-what-you-can-do)

---

## 1. Managing your profile

### Step-by-step: change your details later (Profile)

You can change your name, email, phone, password, and address any time.

1. Click the **profile menu** in the **top-right corner** of the screen.
2. Click **Profile** from the dropdown.
3. You will see two tabs at the top of the page: **Profile Information** and **Security**.

**Edit your profile details (name, designation, address, pincode):**

1. Stay on the **Profile Information** tab (or click it if you are on Security).
2. Edit the **Full Name**, **Designation**, **Address**, and **Pincode** fields.
3. Click **Save Changes** at the bottom right. A green "Profile updated successfully"
   message confirms it.

**Change your email:**

1. Click the **Security** tab.
2. Find the **Email Address** card.
3. See your **Current Email** (greyed out) and type the **New Email** in the box.
4. Click **Change Email**. The email updates immediately.

**Change your phone number:**

1. On the **Security** tab, find the **Phone Number** card.
2. Type the new number (min 10 digits) in the **New Phone Number** box.
3. Click **Change Phone**.

**Change your password:**

1. On the **Security** tab, find the **Password** card.
2. Enter **Current Password** (your existing password).
3. Enter **New Password** (at least 6 characters) and **Confirm New Password**.
4. Click **Update Password**. A green message confirms it.

---

## 2. Finding an intended device (Track Device)

**Purpose:** The **Track Device** page is where you look up a device and see exactly
where it is and everywhere it has been. It appears in your sidebar for every role; as
Manager you see **all devices** in the system.

### Step-by-step: search for a specific device

1. Open **Track Device** from the sidebar.
2. In the search box at the top, type the device's **serial number**, **NUID**, or
   **MAC address**.
3. Click **Track Device** (or press Enter).

### What you see in the result

- **Device Info card** — manufacturer, MAC, serial, device type, and device ID.
- **Current Location** — shows the holder type and who holds it now (for example
  "Sub Distributor — Ajay Traders"). Colours help: PDIC (blue), Sub Distributor
  (purple), Cluster (indigo), Operator (green).
- **Availability Status** — the current status (available, distributed, in use,
  defective, returned, etc.).
- **Device Journey** — a timeline of every action on the device (registered, distributed
  from person A → person B, status changes). The most recent entry is marked **current**.
- **Distribution Flow** — a visual chain: **PDIC → Sub Distributor → Cluster → Operator**.
  The step that is highlighted shows where the device currently sits.

### Step-by-step: find a device when you don't know its serial

Before you search, the page lists **All Devices** (active devices first, replaced devices
in a separate section at the bottom). To narrow this list efficiently:

1. Click **Show Filters** (top of the All Devices list).
2. Use the dropdowns to filter by:
   - **Device Type** (e.g. SB, ONT)
   - **Vendor / manufacturer**
   - **Status** (e.g. "defective" to find problem devices)
   - **Sub Distribution** and **Cluster** (to narrow to a region)
3. Click a device card to open its full journey.

### Useful tricks

- **Finding a replacement:** if a device was replaced, its card is in the red "Replaced
  Devices" section. When you open a replaced device you get a banner with an
  **Open Replacement Device** button — click it to jump straight to the replacement.
- **Fix a broken holder:** if a device shows the wrong holder, open it and click
  **Fix Holder** (re-applies the most recent distribution).
- **Change status directly:** as Manager you can click **Change Status**, pick the
  new status, add optional notes, and **Save**.
- **Refresh:** after a distribution, click **Refresh** on the device page to pull the
  latest journey.

---

## 3. Using reports efficiently

You have four reporting pages. They all share the same idea: **pick a time range, then
drill down**. The three hierarchy reports (Sub Distribution, Cluster, Operator) are
increasingly narrow levels of the same tree, so you can work from the top down.

### The shared controls

- **Date range filter** (top-right): Today, Last 7 / 30 / 60 / 90 days, This Year,
  All Time, or **Custom Range** (pick start and end dates, then **Apply**). Set this
  first — every number on the page updates to match.
- **Refresh** button: re-pulls the report data.
- **Filter Report** bar: choose which field to search (**All Fields, Name, Email,
  Phone, Digital ID, Broadband ID**), type a value, and click **Search**. Use **Reset**
  to clear.
- **View tabs: Total / SB / ONT** — switch between all devices, SB devices, and ONT
  devices. In Total you see combined counts; in SB and ONT you see a per-vendor
  breakdown.

### How to use each report

**Reports & Analytics (overview)** — a one-screen health check:

1. Pick a **date range**.
2. Read the four headline cards: **Total Devices, Distributions, Defect Reports,
   Return Requests**.
3. Look at **Devices by Location** (bar chart) and **Devices by Condition** (donut).
4. The **Monthly Activity** bar chart shows distributions vs returns vs defects per month.
5. Scroll to **Summary Statistics** for completion/pending/rate per metric.
6. Use **Export PDF** (top right) to save a copy, or **Download Report** to get the
   data file.

**Sub Distribution Report** — "what does each sub distribution hold?"

1. Set your date range.
2. Read the columns per sub distribution: **Total Operators, Total Clusters,
   Device Count, and the SB / ONT / Other split**.
3. Use the **SB / ONT** tabs to see per-vendor numbers for that type.
4. Use **Filter Report** to jump to one sub distribution by name or ID.
5. Best used when you want a region-by-region snapshot of device holdings.

**Cluster Report** — "which clusters sit under which sub distribution?"

1. Set your date range.
2. Use the **Sub Distribution** dropdown (top) to look at just one region — the table
   then shows only that region's clusters.
3. Read each cluster's **Total Operators** and **Device Count / SB / ONT / Other**.
4. **Tip:** this report is the bridge between Sub Distribution and Operator — pick a
   region here, then open the Operator report and pick the same region to go one level
   deeper.

**Operator Report** — "who holds what, down to the last operator?"

1. Set your date range.
2. Optionally pick a **Sub Distribution**, then a **Cluster** (the Cluster dropdown
   only becomes active once you pick a Sub Distribution — this keeps the list tidy).
3. Each row shows the operator, their digital/broadband IDs, their parent
   sub distribution and cluster, and their device counts.
4. Use **Filter Report** to search an individual operator by name or digital ID.

### Efficiency tips

- **Always set the date range first** — otherwise you are looking at All Time and the
  tables are large.
- **Work top-down:** Sub Distribution → Cluster → Operator. Keep the same region
  selected in each to drill down without guessing.
- **Use tabs to isolate SB vs ONT** when investigating a vendor complaint.
- **Search beats scrolling** — for a single person or entity, use the Filter Report
  search rather than paging through 15-row pages.

---

## 4. Using the Activities section

**Purpose:** Activities is the **audit log** — a timeline of meaningful actions by
users, such as device movements, registrations, and inventory changes. As Manager you
see the actions performed by your **team and staff**, so you can answer "who did what,
and when" for your operations. Activity performed at the **executive level** is not
shown to you.

### Step-by-step: find activity

1. Open **Activities** from the sidebar.
2. The table shows four columns: **Actor** (who), **Type** (category), **Description**
   (what happened), **Date** (when).
3. If a row is linked to something (e.g. a device), clicking it takes you to that record.

### Step-by-step: filter the log

1. In the **Filters** card use the five controls:
   - **Actor name** — type a person's name to see only their actions.
   - **Type** dropdown — **All**, **Device**, **Inventory**, or **API**.
   - **Search description/action** — type a keyword (e.g. "registered") to match the
     description.
   - **Start date** and **End date** — pick a time window.
2. Click **Apply** to run the filters.
3. Click **Reset** to clear everything and see all activity again.

### How to use it efficiently

- **Audit one person:** type their name in Actor and Apply. You get their complete
  history — useful before changing their role or when investigating a mistake.
- **Audit one type of event:** choose **Device** (or Inventory/API) and add a keyword
  like "deleted" or "transferred".
- **Narrow by time:** set start/end dates for the period you care about instead of
  scrolling.
- **Export:** the table has an export option — use it to pull the filtered log into a
  spreadsheet for records or a report.
- **Combine:** actor + type + date together give you a precise slice (e.g. "what did
  X do to devices in the last 7 days").

---

## 5. Viewing a user's dashboard

**Purpose:** The **View User Dashboard** page lets you look at *someone else's view*
without leaving your session — you pick a Sub Distributor, Cluster, or Operator and see
their dashboard exactly as they see it. It is a read-only look; your own login is not
affected.

### Step-by-step: find and open a user's dashboard

1. Open **View User Dashboard** from the sidebar.
2. In the search box, type the person's **name, digital ID, broadband ID, or email**
   (or click **Search** with a term).
3. From the results, click the person you want. You are taken to their dashboard,
   scoped to their role and their chain.
4. Use the page normally to inspect their numbers, then navigate away (e.g. open your
   own **Dashboard**) to return to your own view.

> You can open the dashboards of **Sub Distributors, Clusters, Operators, and Sub
> Distribution Managers**.

### Why this is useful

- **Support:** an operator says a number looks wrong — open their dashboard and see
  exactly what they see.
- **Onboarding / coaching:** check a new Cluster's dashboard to confirm their device and
  distribution figures look right.
- **Troubleshooting scope:** verify whether a problem is a data issue or a permission
  issue by looking at what the field user is actually shown.

---

## 6. User management

### 6.1 The user hierarchy (why it matters)

Users belong to a **tree**: Sub Distributors sit under the company, Clusters under a Sub
Distributor, Operators under a Cluster (or a Sub Distributor). A **Sub Distribution
Manager** or **Sub Distribution Employee** can be attached under a Sub Distributor too.
When you create a user you must place them correctly in this tree, because it controls
what devices/data they can see and who approves their work.

### 6.2 The roles you can assign

You can create accounts for every role **below manager level**.

| Role | What the person does | Typical placement |
|------|----------------------|-------------------|
| **PDIC Staff** | HQ operational team: devices, distribution, defects, external inventory | Top of the tree |
| **Sub Distribution Manager** | Runs a field region, approves field requests | Under a Sub Distributor |
| **Sub Distributor** | Runs distribution in the field, confirms deliveries, creates team users | Under the company |
| **Cluster** | Field support: deliveries, defects, returns | Under a Sub Distributor (or Sub Dist. Manager) |
| **Operator** | Direct device work: own devices, defect reports, confirmations | Under a Cluster or Sub Distributor |
| **Sub Distribution Employee** | Field work, submits approval requests | Under a Sub Distributor |

**Rule of thumb:** create people at the lowest role that covers their job. A field
person who only handles devices is an **Operator**, not a Manager.

### 6.3 Step-by-step: create a single user

1. Open **User Management** (or **Assign Users**) from the sidebar.
2. Click the **Add User** button (top right).
3. In the pop-up form fill in:
   - **Name** — the person's full name.
   - **Email** — their login email.
   - **Password** — their initial password (tell them to change it on first login).
   - **Role** — pick from the role table above.
   - **Phone** (optional), **Designation** (optional), **Address** (optional),
     **Pincode** (optional).
   - **Parent** — only appears when the role needs a parent:
     - Creating a **Cluster** → select its parent **Sub Distributor**.
     - Creating an **Operator** → select **Sub Distributor** or **Cluster** (choose
       which it sits under), and optionally a **Network Name**.
     - Creating a **Sub Distribution Manager** or **Sub Distribution Employee** →
       select the parent **Sub Distributor**.
   - **Digital ID / Broadband ID** — add these if the person holds them (you can add
     multiple rows).
4. Confirm the password in the confirmation field.
5. Click **Create** (the button may read **Save** / **Add User**).
6. You get a green "User created successfully" message and the user appears in the list.

### 6.4 Step-by-step: edit, deactivate, or delete a user

1. In **User Management**, find the user (use the search bar or the **Role** /
   region filters at the top).
2. Click the **pencil (Edit)** icon on their row.
3. Change their details and **Save**.
4. To stop a person temporarily, use the **deactivate/status** action instead of
   deleting — the account stays but they cannot log in.
5. To remove someone entirely, click the **trash (Delete)** icon and confirm. Deleting a
   **Sub Distributor or Cluster** who has people under them leaves those users orphaned;
   a **Reassignment Request** is created for the administrator to resolve.

> **Your boundary:** you can edit, deactivate, and delete any account **below manager
> level**. Accounts at or above your level are managed by the administrator.

### 6.5 Step-by-step: bulk upload users

Use this when you have **many users at once** (e.g. a new region's entire team).

1. Open **Bulk Upload Users** from the sidebar.
2. Choose what you are uploading:
   - **Upload Subdistributors** — create sub distributor accounts.
   - **Upload Clusters** — create clusters; you must then pick the parent
     **Sub Distributor**.
   - **Operators (under Subdistributor)** — create operators assigned to a sub
     distributor.
   - **Operators (under Cluster)** — create operators under a specific cluster
     (pick the sub distribution first, then the cluster).
3. Click **Download Template** to get the CSV template. Its columns are:
   `email, password, name, digital_id, broadband_id, phone, network_name`.
   - Use a pipe (`|`) in `digital_id` to add multiple IDs, e.g. `SD001|DIG002`.
   - `network_name` is optional and only applies to operators.
4. Fill the file (one row per user) and save.
5. **Drag and drop** the file into the upload box, or click to browse.
   Supported: `.csv`, `.xlsx`, `.xls`.
6. Click **Upload**.
7. Review the result screen:
   - **Created** (green) — how many accounts were made, with the list.
   - **Skipped** (yellow) — rows ignored (e.g. duplicate email), with the reason.
   - **Errors** (red) — rows that failed, with the row number and message.
8. Fix any error rows in the file and re-upload only those.

### 6.6 Change requests (reviewing staff requests)

**What they are:** change requests are edits your team submits to have a change applied
for them — **credential changes** (new email / password), **device status changes**, and
**replacement transfer-fix requests** (when a replacement device went to the wrong
place).

**What you review:** as Manager, your **Change Requests** list is scoped to:

- **Team credential and device status changes** submitted by your staff.
- **Replacement transfer-fix requests** from the field.

#### Step-by-step: approve or reject a request

1. Open **Change Requests** from the sidebar (under User Management) — or **Edit
   Requests** (under Devices) for device edit requests.
2. Find the pending request. It shows who submitted it and what change they want.
3. Choose:
   - **Approve** — the change is applied (email/password set, device status changed,
     transfer performed).
   - **Reject** — nothing changes. You can add a note explaining why.
4. The requester is notified of your decision either way.

### 6.7 Step-by-step: reassign a user (move a cluster or operator)

**When to do it:** reassignment moves a person to a new parent **without deleting
anything**. Use it when the team structure needs to change — a **Cluster** should report
to a different **Sub Distributor**, or an **Operator** should report to a different
**Sub Distributor** or **Cluster**. Typical times: reorganising a region, a parent
leaves or changes role, or a team's work moves under another branch.

**What it does:** the person keeps their account, their devices, and their data — only
their **parent** changes, so their scoped devices, distributions, and reports follow the
new chain. Do this before deleting a parent so the people under them never end up with no
one to report to.

#### Step-by-step: reassign

1. Open **User Management** (All Users).
2. On a **Cluster** or **Operator** row, click the **reassign (network) icon**.
3. In the **Reassign** pop-up, pick the new parent from the dropdown:
   - A **Cluster** moves to a **Sub Distributor**.
   - An **Operator** moves to a **Sub Distributor** or a **Cluster**.
4. Click **Reassign**. A green "User reassigned successfully" message confirms it and the
   user appears under their new parent from then on.

---

## 7. Device management

**Purpose:** This is where every device in the system is created, edited, and removed.
As Manager you can register devices one at a time, upload hundreds at once, edit any
device, and delete devices directly (no approval needed — only staff edits and
deletes require your approval).

### 7.1 Step-by-step: register a device individually

1. Open **Devices** from the sidebar.
2. Click the **Register Device** button (top right). This takes you to
   **Register New Device**.
3. **Scan the barcode** (recommended): click the large dashed "Click to scan device
   barcode/QR code" box and allow camera access. Position the code in the frame —
   it reads MAC addresses, serial numbers, and models. Or click **"Or enter details
   manually"** and type the fields instead.
4. Fill in the form:
   - **Device Type** — ONT, ONU, OLT, Router, Switch, Modem, Access Point, **SB**
     (set-top box), or Other.
   - **Band Type / Box Type** — for non-SB devices pick **Single Band** or
     **Dual Band**; for SB devices pick **HD** or **OTT**.
   - **MAC Address** and **Serial Number** — required for non-SB devices.
   - **Device Model** and **Vendor** — required for every device.
   - **NUID** — required for SB devices only.
   - **Hardware Version**, **Firmware Version** — optional, for reference.
   - **Condition** — **New** or **Refurbished**.
   - **Additional Notes** — anything worth recording.
5. Click **Register Device**. A green "Device registered successfully!" message
   confirms it and you land back on the Devices list.

> **SB vs other devices:** set-top boxes are tracked by **NUID**, not by MAC/serial.
> If you pick **SB**, the form switches to show Box Type and NUID and hides the
> MAC/Serial fields. Every other type needs MAC + Serial.

### 7.2 Step-by-step: bulk import devices

Use this when adding many devices at once (a new shipment, a warehouse transfer).

1. Open **Devices** from the sidebar.
2. Click **Bulk Import** (top right).
3. Click **Download Template** to get the CSV template. Two formats are supported:
   - **Regular:** `Vendor, device_type, model, mac_address, serial_number, band_type`
     (serial required; MAC and band_type optional).
   - **SB:** `vendor, device_type, model, nuid, box_type` (for set-top boxes;
     box_type must be **HD** or **OTT**).
   - Valid `device_type` values: ONU, ONT, OLT, Router, Switch, Modem, Access Point,
     SB, Other. Valid `band_type` values: `single_band`, `dual_band`.
4. Fill the file (one row per device) and save. Supported: `.xlsx`, `.xls`, `.csv`.
5. **Drag and drop** the file into the upload box, or click to browse.
6. Click **Upload**. The result screen shows:
   - **Created** (green) — devices registered.
   - **Warnings** (yellow) — rows accepted with issues.
   - **Errors** (red) — rows that failed, with the row number and message.
7. Fix any error rows in the file and re-upload only those.

### 7.3 Step-by-step: find and filter devices

1. Open **Devices**. As Manager the page shows **"All registered devices in the
   system"** with summary cards at the top: **Total, Available, Distributed,
   Defective, Returned**.
2. Use the **Table Filters (ALL Devices)** card:
   - **Date range** — narrow the list to devices added in a period.
   - **Show Filters** — reveal dropdowns for **Device Type, Vendor, Sub Distribution,
     Cluster, Status** (available / distributed / in_use / defective / replaced /
     returned / maintenance).
3. Use **Search Devices** for a precise lookup: pick a field (**All Fields, NUID,
   MAC Address, Serial Number, Vendor, Type, Model, Device ID**), type the value, and
   click **Search**. Pattern search runs on the **complete dataset**, not just the
   loaded rows.
4. Row colours mean something:
   - **Green row / border** — this device is a **replacement** device.
   - **Red row / border** — this device is **defective**.
5. Click any row (or the **eye** icon) to open **Device Details** — status, holder,
   location, full field list, and any replacement/defect mapping.
6. From Device Details you can **Edit Device**, **Track Device** (jumps to the Track
   page with this device pre-filled), or see the **Replacement Mapping** box linking a
   defective device to its replacement.

### 7.4 Step-by-step: edit a device

1. In **Devices**, find the device (search or filter).
2. Click the **amber pencil (Edit)** icon on its row — or open Device Details and click
   **Edit Device**.
3. In the **Edit Device** modal you can change: **Device Type, Band/Box Type, Serial
   Number, MAC Address, Model, NUID, Vendor,** and **Location**.
4. Click **Save Changes**. Because you are a Manager your changes are applied
   **immediately** (the modal notes "As manager, your changes will be applied
   immediately without approval").
5. A green "Device updated successfully!" message confirms it.

> **If the row doesn't let you edit:** your edits apply immediately. Requests to edit
> devices that arrive from staff are submitted for approval instead — those show up for
> you to review (see below).

### 7.5 Step-by-step: delete a device

1. In **Devices**, find the device.
2. Click the **red trash (Delete)** icon on its row.
3. The confirmation asks: *"Are you sure you want to delete device …? This action
   cannot be undone."* Click **Delete**.
4. A green "Device … deleted successfully" message confirms it.

**Delete several at once:**

1. Tick the **checkboxes** on the rows you want to remove (or the box in the header to
   select the whole page).
2. A blue panel appears at the bottom: "*N device(s) selected*" with a
   **Delete Selected** button.
3. Click **Delete Selected**, optionally add a **Reason**, then confirm.
4. As Manager the deletion applies immediately. (Staff deletions are submitted as
   approval requests — you are the one who approves or rejects those in the Approvals
   page.)

**Where staff edit/delete requests land:** when a staff member requests an edit
or a delete, it becomes a **change request** for you to review. You'll find these in
the **Approvals** page (the bell icon shows new pending items). You can **approve** (the
edit/delete runs) or **reject** (nothing changes).

### 7.6 Step-by-step: handle edit requests from staff

**Who sends them:** when staff try to **edit**, **delete**, or **change the status** of a
device, the system
submits a **change request** instead of applying it. These are the request types you
will see:

| Request | What it asks | What happens when you approve |
|---------|--------------|-------------------------------|
| **Edit** (`device_edit_change`) | The proposed field changes (type, serial, MAC, model, NUID, vendor, etc.) | The device is updated with the proposed values |
| **Delete** (`device_delete_change`) | One or more device IDs plus a reason | The listed devices are deleted |
| **Status change** (`device_status_change`) | A device ID, the requested new status, and a reason | The device status is changed |

**Where to handle them:**

1. Open **Approvals** from the bell icon (top right). A badge shows how many items are
   pending.
2. Find the request. It shows who submitted it, what device(s) it concerns, and the
   proposed change.
3. Choose:
   - **Approve** — the change is applied exactly as proposed (edit runs, delete runs,
     status is set). The requester gets a notification.
   - **Reject** — nothing changes; the device stays as it was.

> **Why this matters:** approving a staff edit is a real action on a real device, so
> check the requested change against the device before you approve. For delete
> requests the confirmation shows the count of devices — a mistaken approval is
> irreversible (bulk delete has no undo).

---

## 8. Sub distributions & the approval workflow

**Purpose:** Distributions are how devices move down the chain —
**PDIC (you) → Sub Distributor → Cluster → Operator**. Every time you send devices, the
recipient gets a **Delivery Confirmation** task: they must confirm the device(s)
physically arrived before the transfer becomes final. This section covers creating
distributions, viewing them, the statuses, and the confirmation/approval workflow.

### 8.1 How the workflow works (read this first)

1. **You create a distribution** — pick the recipient and the devices, click submit.
   The distribution starts in **Awaiting Receipt** (`pending_receipt`).
2. **The recipient is notified** — a **warning notification** "Action Required: Confirm
   Device Receipt" points them to the **Delivery Confirmations** page. If the recipient
   is a Sub Distributor, the sub distribution's staff/manager also get pinged so a
   delivery into their branch is never missed.
3. **The recipient confirms or disputes**:
   - **Received** → distribution becomes **Confirmed** (`approved`); the devices are
     now owned by the recipient and they can redistribute them further down the chain.
   - **Not Received** → distribution becomes **Disputed**; you, the management team,
     and the sender are alerted immediately.
4. **You resolve disputes** — when the devices are physically back with the sender,
   you click **Confirm devices are back** to unlock redistribution.

> **The golden rule:** the recipient **cannot redistribute** the devices until they
> confirm receipt. Until then the devices stay with the sender. This is what makes the
> "disputed" state safe — nothing moves twice by accident.

### 8.2 Step-by-step: create a distribution individually

1. Open **Distributions** from the sidebar.
2. Click **Create Distribution** (top right).
3. On the left, **select the devices** to send. Use the **Selection Mode** buttons:
   - **Manual** — click devices one by one.
   - **Registered Date** — pick one date; the matching devices appear.
   - **Date Range** — pick a from/to window.
   - **Serial Range** — enter a serial start and end (e.g. SN-000100 to SN-000500).
   - **Search box** — type MAC, model, or serial to filter the list.
   - **Select Filtered (N)** — grabs every device matching your current filter at once.
4. Check the **Selected Devices** panel on the right; remove any by clicking the trash
   icon on the row.
5. Under **Select Recipient**:
   - Pick the **Recipient Type** — as Manager you can send to a **Sub Distributor**,
     **Cluster**, or **Operator**.
   - Narrow with the optional **Filter by Sub-Distributor / Cluster** dropdowns, then
     pick the **final recipient**. A breadcrumb shows the hierarchy path (e.g.
     `Sub Distributor → Cluster → Recipient`) so you always know who you're sending to.
6. Set the **Date of Distribution** (leave blank for today) and add **Notes** if needed.
7. Click **Create Distribution**. Review the summary in the confirm dialog and click
   **Confirm Transfer**.
8. A green "Distribution created successfully!" message appears and you return to the
   Distributions list, where the new row shows **Awaiting Receipt**.

### 8.3 Step-by-step: bulk upload a distribution

Use this when sending a large, known set of devices (you have their IDs in a list).

1. Open **Distributions** from the sidebar.
2. Click **Bulk Upload** (top right).
3. Click **Download CSV Template**. Columns: `mac_address, serial_number, nuid` —
   provide **any one** per row (a row can also have more than one).
4. Fill the file and save. Supported: `.xlsx`, `.xls`, `.csv`.
5. **Select Recipient** the same way as in a single create (type → filters → recipient).
6. **Drop the file** into the upload box (or click to browse). Add optional **Notes**
   and a **Date of Distribution**.
7. Click **Upload & Create Distribution**.
8. Read the result: **Rows Processed, Valid Devices, Errors**.
   - If all rows are valid the distribution is created and sent to the recipient.
   - Invalid/unregistered rows block the whole upload — fix the listed rows and
     re-upload. **A single date** is applied to the whole upload; if your file contains
     more than one `date_of_distribution`, you'll be asked to provide a single date.

### 8.4 Step-by-step: view and search distributions

1. Open **Distributions**. The four cards at the top give a snapshot:
   **Total, Awaiting Receipt, Confirmed, Disputed**.
2. Set the **date range** (top right) to focus on a period.
3. Use **Search Distributions**: pick a field (**All Fields, Distribution ID, From,
   To, Digital ID, Broadband ID, Status, Confirmed By**), type, and **Search**.
4. The table columns: **Distribution ID, From, To, Devices, Status, Created,
   Confirmed By**. Click a row (or the **eye** icon) to open **Distribution Details**:
   - Sender → recipient, status badge, and the **By Device Type / By Vendor**
     breakdowns.
   - **Total Sent, SB count, Total Devices** summary boxes.
   - Confirmed By, transfer date, and any notes.

### 8.5 Downloading the device list of a distribution

1. Open the **Distribution Details** of the row you care about.
2. Click **Download CSV** or **Download Excel** (top-right of the details header).
   This exports the distribution's devices as **MAC / NUID** data in the chosen format.
3. The file downloads with a name like `<distribution-id>-mac-nuid.csv`.
4. You can download this for **any** distribution — every one in the system. Each
   table also has a general **Export** button that saves the
   on-screen columns to CSV.

### 8.6 The statuses, explained

| Status | What it means | Who acts |
|--------|---------------|----------|
| **Awaiting Receipt** (`pending_receipt`) | You sent it; the recipient hasn't confirmed yet. Devices are still effectively the sender's. | Recipient confirms or disputes |
| **Confirmed** (`approved`) | Recipient confirmed receipt. Devices now belong to them and can be redistributed. | Recipient (already done) |
| **Disputed** (`disputed`) | Recipient says the devices did **not** arrive. You, the management team, and the sender are all notified. | You / the management team |
| Cancelled | The creator cancelled the request before it was resolved. | Creator |
| Rejected | Management closed the distribution without accepting it (e.g. after a dispute is resolved). | Management |

### 8.7 Handling disputes and the confirmation flow

- **See what's waiting:** open **Distributions** filtered to **Awaiting Receipt** or
  **Disputed**. Rows needing your attention show the relevant action icon, and the
  **Approvals** feed (bell icon) counts them.
- **Resolve a dispute:** when the devices are physically back with the sender, open the
  Disputed distribution and click the green **Confirm devices are back** icon.
  This records the return and **unlocks the devices** for redistribution.
- **Confirmations are handled by the recipient** — your job is to act when something is
  disputed or stuck.

### 8.8 Where distributions appear in Approvals

The **Approvals** page (bell icon) merges everything waiting for action into one feed
with badges: **Distribution, Return Confirmation, Defect**. Pending distributions in
that feed are the ones awaiting receipt confirmation. As Manager you can open any
of them and jump straight to the distribution to confirm a return, review a dispute,
or check its details — one place to keep every open thread moving.

---

## 9. Defects, replacements & returns

**Purpose:** When a device fails, the cycle is: someone **reports the defect** → you
**review** it → the device is **returned** to PDIC → you **replace** it (or it is
serviced) → the user **confirms** the replacement. Money owed for the defective device
is tracked as a **pending due**, and every pending action also appears in the
**Approvals** feed. This section covers each of those pages.

### 9.1 The defect workflow (read this first)

1. **A field user reports a defect** (Operator, Cluster, Sub Distributor, or Sub
   Distribution Employee). The device is automatically marked **defective**. You, the
   management team, and the reporter's sub distributor are notified.
2. **You review the report** — approve or reject it.
   - **Approve** → a **return request is automatically created** and the reporter is
     told to return the defective device to PDIC.
   - **Reject** → the report is closed; nothing else changes.
3. **The device comes back** — staff (or you) confirm receipt on the **Returns**
   page. The return becomes **received** and ownership transfers back to PDIC.
4. **You assign a replacement** (only once the defect is approved **and** the device is
   received at PDIC). You pick an existing device, reuse the same (serviced) device,
   or register a brand-new one.
5. **The user confirms the replacement** physically — the replacement only becomes
   active in their account after they click **Confirm Receipt**.
6. **Payment (optional)** — if the replacement carries a due amount, it appears as a
   **pending due** until you confirm the payment.

> **The golden rule:** a replacement is **only assigned after** the defective device is
> approved and physically received at PDIC. The system blocks assigning earlier — the
> defective device must be returned first.

### 9.2 The Defect Reports page (how to check it)

Open **Defect Reports** from the sidebar. As Manager you see **every** report in
the system.

- **Summary cards:** **Total, Open, Under Review, Resolved, Critical** — a quick pulse
  on how many problems are outstanding.
- **Defect Attention Center** (red/amber/purple panels, for management roles):
  - **Urgent & needs review** — critical/high reports still open. Click **Review Now**
    to jump straight in.
  - **Defective Device Return Pending** — approved defects waiting for the device to
    arrive at PDIC.
  - **Replacement Assignment Queue** — approved + returned defects that still need a
    replacement device. Click **Open Pending Replacement Page**.
- **Search:** pick a field (**All Fields, Report ID, Device Serial, NUID, Description,
  Defect Type, Severity, Status, Reported By, Digital ID, Broadband ID, Device Type**),
  type, and **Search**. Use **Reset** to clear.
- **Table columns:** Device, Type, Severity, Reported By, Date, Status, **Payment
  Status** (Confirmed / Pending Payment), Actions.
- **View filters:** **All / Pending Replacement / Replaced** buttons above the table
  narrow the list to defect–replacement work.
- **Row actions** (per your permission):
  - **Eye** — open the full details.
  - **MessageSquare** — review a `reported` defect (approve/reject).
  - **RefreshCw** — replace a device (only when the defect is approved and the return
    is received).
  - **DollarSign** — confirm a pending payment (once the return is received).

**What a report's detail shows:** the device, its status badge, defect type, severity,
reported-by and date, the description, **Defective Device** vs **Replacement Device**
boxes, any auto-created return request ID, a **Payment Due** box (amount, who owes,
bill link), the replacement mapping note, and any **photos**.

### 9.3 Step-by-step: review and handle a defect report

1. Open **Defect Reports**.
2. Find a report with status **reported** (the Attention Center lists the urgent ones).
3. Click the **message (Review)** icon — or open the report and click **Review Defect**.
4. Read the details, then choose:
   - **Approve & Initiate Return** — the report is approved, a **return request is
     automatically created**, and the reporter is told to return the device to PDIC.
   - **Reject** — the report is closed and the reporter is notified.
5. The review modal reminds you that approving **automatically creates the return
   request** — you don't need to create one manually.

**After approval:** the report's status shows **approved**, a linked return request ID
appears on the report, and staff get a "Defective Device Return — Pending Receipt"
notification pointing to the **Returns** page.

### 9.4 Step-by-step: replace a defective device (in detail)

**Prerequisite:** the defect must be **approved** and the defective device must be
marked **received** at PDIC (you'll see the green **Replace Device** action only then).

1. Open **Defect Reports** and find the approved defect with a received return.
2. Click the **RefreshCw (Replace Device)** icon.
3. In the **Replace Defective Device** modal, choose one of three modes:
   - **Select Existing Device** — filter by device type (ONU, ONT, SB, ...), search by
     ID / serial / MAC / model, and pick a device from stock (only **available** or
     **returned** devices are offered).
   - **Use Same Device (Serviced)** — keep the same device; after the user confirms,
     it is marked serviced and handed back. Use when the device was repaired rather
     than replaced.
   - **Register New Device** — fill the fields (type, band/box type, model, vendor,
     serial + MAC for non-SB; NUID + box type for SB) to register and assign a brand
     new replacement in one go.
4. Optionally set **Due Amount** (what the user must pay) and **Upload Bill** (proof,
   e.g. a bill or receipt file).
5. Click **Assign Replacement**.
   - The defect moves to **replacement_pending_confirmation** and the user is alerted:
     "Replacement Device Ready — Confirmation Required", with a warning to **confirm
     only after physically receiving the device**.
   - The defective device is marked **replaced** (or **maintenance** if serviced in
     place). The **Replacements** page records the mapping: defective device →
     replacement device.
6. **The user confirms receipt** (on their Defect Reports page or the **Replacement
   Confirmation** page). Only then:
   - The defect becomes **resolved**.
   - The replacement device is **activated in the user's account** (in use for an
     operator, distributed for other roles).
   - You get a "Replacement Receipt Confirmed" notification.

**If the replacement can't ship immediately:** management can mark it **waiting for
PDIC shipment** (the user is told "Device is being shipped, please wait"), **resend
the confirmation reminder** to the user, and the user can send a **replacement
enquiry** to management. Use **Pending Replacements** (`/replacements/pending`) to see
approved defects that still need a replacement device, split into **awaiting / ready /
waiting** counts.

### 9.5 The Return Requests page, in detail

**Purpose:** Return Requests tracks devices coming **back** to PDIC. When a defect is
approved, the system **automatically creates a return request** for that device; you
and staff act on these in the **Returns** page (from the sidebar).

1. Open **Returns**. Summary cards show **Total, Pending, Under Review, Approved,
   Rejected**.
2. If any return is waiting for the device to physically arrive, an amber banner says
   **"N return requests are waiting for device reached confirmation at PDIC"**.
3. **Search Returns:** pick a field (**All Fields, Return ID, Device Serial, NUID,
   Initiated By, Digital ID, Broadband ID, Reason, Status**), type, and **Search**.
4. The table shows: **Device, Reason, Initiated By, Date, Status, Actions**.
5. Click a row (or the **eye**) to open **Return Request Details**:
   - The device, status badge, reason, who initiated it, and when.
   - **Return Approved By** (who approved, when), **Received At PDIC** date (once
     confirmed), description, and the **linked Defect Report ID** if this return came
     from a defect.
   - An **Approval Timeline** (Return Initiated → Reviews → Return Completed).
6. **Confirm the device reached PDIC** — for a return that is **Pending** or
   **Approved**, click the **PackageCheck** icon (or the button in details). The
   confirmation lists what it does: marks the return **received**, **transfers device
   ownership back to PDIC**, and **notifies the user the return is complete**. Add an
   optional comment and click **Confirm Received**.

> **Why confirming receipt matters:** only a **received** return unlocks the next
> steps — the defect's **replacement** can be assigned, and any **pending due
> payment** can be confirmed.

### 9.6 The Pending Dues page, in detail

**Purpose:** Pending Dues shows **money owed** by field users for returned defective
devices (the **Due Amount** you set when approving/replacing a defect). A due exists
when a return is **received** at PDIC, has a **return amount above zero**, and the
**payment is not yet confirmed**.

1. Open **Pending Dues** from the sidebar.
2. Summary cards: **Users (count), Total Due, Total Items** — the full outstanding
   picture across everyone.
3. The table groups dues **per user**: each row shows the **user name, role, parent,
   digital/broadband IDs, number of due items, and total due** (highest first).
4. **Search** by **user name, user role, parent name, digital ID, broadband ID, or
   total due**.
5. Click a user row to open a **details drawer**: the list of that user's defects with
   report ID, device, return ID, return status, amount, and received date.

**How a due gets cleared:**

1. The defective device must be **received** at PDIC (see Returns).
2. Open **Defect Reports**, find the defect, and click the **DollarSign (Confirm
   Payment)** action.
3. Once confirmed, the payment status shows **Confirmed — By <name>**, and the user
   gets a "Defect Return Payment Confirmed" notification.

> **Who owes:** the reported user (the operator/reporter who held the device). Note
> that a **sub distribution employee**'s dues are shown under their branch's **sub
> distributor**.

### 9.7 The Approvals page, in detail

**Purpose:** Approvals is the **single merged feed** of everything waiting for your
action. It combines distributions, return confirmations, defect items, and device
change requests so you don't have to chase each page separately.

1. Open **Approvals** from the bell icon (top right). Pending counts show as **badges**.
2. The feed is organised by **type** (each with its own icon):
   - **Distribution** — distributions awaiting receipt confirmation or a dispute
     decision.
   - **Return Confirmation** — returns waiting for the "device reached PDIC"
     confirmation (pending + approved returns).
   - **Defect** — defect reports waiting to be reviewed.
3. Click any item to open its details, then **Approve** or **Reject** (rejecting
   requires a **reason**). Approving/deciding here is the same as doing it on the
   page itself — the item leaves the feed and the affected record updates.
4. Device **change requests** from staff (edits, deletes, status changes) are also
   handled from this feed — approve to apply, reject to leave unchanged.

> **Using it well:** the Approvals feed is your daily inbox. Work it top-to-bottom
> each morning — anything still pending there is something a field user or another
> role is waiting on.

---

## 10. Backup

**Purpose:** The **Backup** page protects your data in three ways: you can **download
snapshots** of your devices and your returns/defects, you can **schedule automatic
MySQL database dumps** that get uploaded to Google Drive, and you can store **extra
backup files** in a document vault for later download. Everything happens from one
page in the sidebar.

### 10.1 What's on the Backup page

The page is a set of cards, top to bottom:

1. **Device Backup** — download a full export of every device, including its journey
   path from its starting point through the hierarchy to its current location.
2. **Returns and Defects Tracking Backup** — download a separate file of all return
   records and defect reports, for audit and tracking.
3. **MySQL Database Backup** — set an automatic schedule for full database dumps,
   which are uploaded to Google Drive via rclone. (Time uses the **backend container
   clock**.)
4. **Backup Document Vault** — upload important backup files and download them later.
   Available to you and the management team.

### 10.2 Step-by-step: download a device backup

1. Open **Backup** from the sidebar.
2. Read the "Included in backup" note: device details, starting point, path traversed
   through the hierarchy levels, and current location.
3. Under **File format**, pick **XLSX** (spreadsheet) or **CSV** (plain table).
4. Click **Download Device Backup**. A file downloads (named like
   `device-backup.xlsx` or `device-backup.csv`).
5. Open it in Excel or a spreadsheet app. Each row is one device with its journey
   path (started from → passed through → current location).

> **What's in the file:** per device you get the device ID, serial, MAC, NUID, type,
> model, manufacturer, status, current holder (name and type), the journey path
> (started_from / passed_through / current_at), and created/updated timestamps.

### 10.3 Step-by-step: download the returns & defects backup

1. On **Backup**, go to the **Returns and Defects Tracking Backup** card.
2. Use the same **File format** toggle (XLSX or CSV) chosen at the top.
3. Click **Download Returns + Defects Backup**. A file downloads (named like
   `returns-defects-backup.xlsx` / `.csv`).
4. Open it to review:
   - **XLSX:** two sheets — **Returned Devices** and **Defect Reports** — with the
     full record details (return/report IDs, device identifiers, requester/reporter,
     reason/type, status, approval and received dates).
   - **CSV:** one combined table where each row is tagged `return` or `defect`.

### 10.4 Step-by-step: schedule the MySQL database backup

1. On **Backup**, find the **MySQL database backup** card. When it loads it shows the
   current schedule (default **Daily** at **02:00**, no last run yet).
2. Set **Frequency**:
   - **Daily** — runs every day at the chosen time.
   - **Weekly** — pick the **Day of week** (Monday–Sunday) and the time.
   - **Monthly** — pick the **Day of month** (1–31; days past the month's end use the
     last day) and the time.
3. Set **Time of day** (24-hour, e.g. `02:00`). Remember this is the **backend
   container clock**, not necessarily your computer's time.
4. Click **Save Schedule**. A green "Database backup schedule updated" message
   confirms it, and the card shows **Last run** once one has happened.
5. To change it later, just adjust the fields and **Save Schedule** again.

> **How it works:** at the scheduled time the backend runs a full database dump
> (`mysqldump --single-transaction --quick`), compresses it to a `.sql.gz` file named
> like `mysql-backup-YYYYMMDD-HHMMSS.sql.gz`, uploads it to Google Drive with rclone,
> then deletes the local copy. The **Last run** timestamp tells you when the most
> recent dump actually ran. If a run fails (database down, drive unreachable), the
> error is logged and it tries again on the next scheduled occasion.

### 10.5 Step-by-step: use the backup document vault

**Purpose:** a safe place to park important backup files (e.g. manually saved exports,
or files from outside the system) so they are not lost, and to download them later.

1. On **Backup**, find the **Backup document vault** card.
2. **Upload a file:** click **Choose file**, pick a file (max **25 MB**), then click
   **Upload to Vault**. A green "File uploaded successfully" message confirms it.
3. **Refresh the list:** click **Refresh List** to reload the stored files.
4. The **Stored files** list shows each file's name, size (e.g. `1.2 MB`), and upload
   date. Click **Download** on a row to fetch that file back to your computer.

> **Restriction:** the vault is available to you and the management team.

---

## 11. External inventory (items & distribution)

### 11.1 What external inventory is (read this first)

External inventory is a **separate catalog from the main Devices section**. Where the
Devices section (section 7) tracks every individual PDIC device with its serial, MAC and
journey, external inventory tracks **stock items you buy to hand out** — OTT boxes, OLTs,
remotes, set-top boxes (SB), adapters — each with a **quantity on hand**, an optional
price, and an optional warranty.

The key difference is how distribution works:

- Main-device distributions go through the **approval workflow** (section 8).
- External inventory distributions are **instant**. As soon as you click **Distribute**,
  the item's available quantity drops, a history entry is recorded, and the recipient is
  notified. There is no pending or approval step.

You can manage items and distribute them. Everyone else can only look at the catalog
(name and price).

### 11.2 The page layout

Open **External Inventory** from the sidebar. Management gets a dropdown with five
pages:

- **Items** — the stock catalog.
- **Bulk Import** — add many items at once from a CSV/Excel file.
- **Distribution** — give one item to one recipient.
- **Bulk Distribution** — give many items to one recipient from a file.
- **Distributed Items** — history of every distribution made.

**Items**, **Distribution** and **Distributed Items** are tabs on the External Inventory
page itself; **Bulk Import** and **Bulk Distribution** open as their own pages. The header
has a **Refresh** button and an **Add Item** button. On the **Items** tab, a **Search Items**
card above the table lets you search by name, identifier, type, supplier, or location, and
filter by **Warranty**, **Identifier Type**, and **Type**. The table also has a **Bulk
Import** button in its top-right.

The table lists the available items. Depleted items (quantity zero) drop out of the
catalog automatically.

### 11.3 Step-by-step: register an item individually

1. Go to **External Inventory → Items** and click **Add Item**.
2. Fill in the form:
   - **Name** — required.
   - **Identifier Type** and **Identifier** — optional, but you must fill both together.
     Valid identifier types: **NU ID, IMEI, Serial Ref, MAC ID, Asset Tag, Other**. The
     combination of identifier type + identifier must be unique across items.
   - **Type** — the kind of item: **OTT Box, OLT, Remote, SB, Adapter, Others**.
   - **Quantity** (minimum 1) and **Price** (in ₹, minimum 0).
   - **Supplier**, **Location**, **Warranty Start Date**, **Warranty Duration (months)**,
     and **Notes** — all optional.
3. Click **Create Item**. A green "External inventory item created" message confirms it,
   and the item appears with status **active**.

### 11.4 Step-by-step: edit an item

1. On **Items**, click **Edit** on a row (or click the row itself).
2. Change the fields you need. You can also set **Status** to `inactive` to stop the item
   being distributed, or back to `active` to re-enable it.
3. Click **Save Changes**.

> Each item must have a unique identifier type + identifier combination.

### 11.5 Step-by-step: delete an item

1. On **Items**, click **Delete** on a row.
2. Confirm the prompt. The item is removed from the catalog permanently.

> Already-made distributions stay in the **Distributed Items** history — deleting the
> item does not remove the record of what was given away.

### 11.6 Step-by-step: bulk upload items from a file

1. On **External Inventory → Items**, click the **Bulk Import** button (top-right of the
   table) — or open **External Inventory → Bulk Import** from the sidebar.
2. Read the **File Requirements** card: `.csv`, `.xlsx`, and `.xls` files up to **10 MB**,
   and at most **300,000** data rows. The required column is `name`; all other columns are
   optional.
3. Click **Download CSV Model** to get a ready-made template
   (`external-inventory-import-model.csv`) with the header row and two sample rows.
4. Open it, replace the samples with your items, and keep the header. The optional columns
   are `identifier_type`, `identifier`, `device_type`, `price`, `quantity`, `supplier_name`,
   `location`, `warranty_start_date` (format `YYYY-MM-DD`), `warranty_duration` (months),
   and `notes`. The same rules as 11.3 apply: an identifier needs its identifier type, and
   identifier pairs must be unique.
5. **Drag and drop** your file onto the upload box (or click to browse), then click
   **Import Items**.
6. The **Import Result** card reports **Rows Processed**, **Created**, and
   **Skipped / Errors**. Problem rows (missing name, bad quantity/price/date, duplicate or
   already-existing identifier pair, quantity below 1) are listed by row number with the
   reason, so you can fix and re-import them.

### 11.7 Step-by-step: distribute a single item

1. Go to **External Inventory → Distribution**.
2. **Item** — pick what to give away. The dropdown shows each item's name, type and current
   quantity, e.g. `OTT Box Pro (OTT Box) | Qty 20`.
3. **Select Recipient Type** — choose **Sub Distributor**, **Cluster**, or **Operator**.
4. **Recipient** — choose the specific person. The count next to the label shows how many
   of that type are available (only **active** accounts are listed). If none exist you get
   a warning and cannot continue.
5. **Quantity** (minimum 1) and optional **Notes**.
6. Click **Distribute**.

The distribution completes immediately: the item's quantity is reduced, a history entry
is created, and the recipient gets a notification
("You have been assigned 3 x OTT Box Pro from external inventory."). There is no
confirmation step.

> The system blocks distributing more than the available quantity, distributing an
> `inactive` or out-of-stock item, or distributing to an inactive account.

### 11.8 Step-by-step: bulk distribution from a file

This sends **many items to a single recipient** in one go.

1. Go to **External Inventory → Bulk Distribution**.
2. Click **Download CSV Template** to get
   `external-inventory-bulk-distribution-template.csv`. Required columns:
   **identifier_type**, **identifier**. Optional: **quantity** (defaults to 1). Each row
   must reference an item that exists, and each identifier pair must be unique in the file.
3. **Select Recipient Type** (Sub Distributor / Cluster / Operator), then the specific
   **Recipient**. The card confirms who you are sending to.
4. **Upload File** — drag your `.xlsx`, `.xls`, or `.csv` file onto the dashed box (or
   click to browse). Add optional **Notes**.
5. Click **Upload & Distribute**.

The **Distribution Result** card shows **Rows Processed**, **Distributed**, and **Errors**.
Rows that fail (item not found, out of stock, quantity too large, inactive item, duplicate
row, inactive recipient) are listed with their row number and reason. Only the valid rows
are distributed, and the recipient gets one combined notification for the whole batch.

### 11.9 The Distributed Items page (history)

Open **External Inventory → Distributed Items** to audit everything that has been given
out. Each row shows:

- **History ID**, **Item**, **Recipient**
- **Qty**, **Previous** (stock before), **Remaining** (stock after)
- **Warranty** badge (see 11.10)
- **Distributed By**, **Distributed At**, **Status**

You can **search** (by history ID, item, recipient, or distributor) and **filter** by
warranty status, identifier type, and device type.

### 11.10 Warranty status, explained

The system computes a warranty status from **Warranty Start Date + Warranty Duration
(months)** compared with today:

| Status | Meaning |
|--------|---------|
| **Warranty Active** (green) | The expiry date is today or in the future. |
| **Warranty Expired** (red) | The expiry date has passed. |
| **No Warranty** (gray) | No start date was entered. |

The badge appears in the Distributed Items list, and both lists have an
**All Warranty / Warranty Active / Warranty Expired** filter.

### 11.11 What you can do

| Action | Available |
|--------|-----------|
| Browse the Items catalog (name & price only) | Yes |
| Add, Edit, Delete items | Yes |
| Bulk upload items from a CSV/Excel file | Yes |
| Distribute a single item | Yes |
| Bulk distribution from a file | Yes |
| View the Distributed Items history | Yes |

*Continue to the other role guides from the [README](README.md) when you need to know
what a different role can do.*
