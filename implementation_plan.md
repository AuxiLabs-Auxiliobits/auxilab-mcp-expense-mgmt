# Role-Based Access Control & Authentication Plan

This document outlines the architecture and implementation steps to introduce a secure authentication system with role-based access control (RBAC), OTP email verification, and a hierarchical account approval workflow into ExpenseOps.

## User Review Required

> [!IMPORTANT]
> Please review the updated plan. I have added the **OTP Email Verification** step to the signup flow. Since we do not have a real SMTP email server configured, the OTP code will be printed to the backend terminal console for development purposes. Let me know if you approve!

## Proposed Changes

### 1. Backend Database & Auth Models
We will add secure JWT-based authentication, OTP tracking, and a robust account state machine to the FastAPI backend.

#### [MODIFY] [backend/database.py](file:///d:/Downloads/ExpenseOPS/backend/database.py)
- **Update `Employee` model**:
  - Add `email` (unique index) and `hashed_password` columns.
  - Add `account_status` column (e.g., `PENDING_APPROVAL`, `APPROVED`, `REJECTED`).
  - Add `manager_id` (ForeignKey to `Employee.employee_id`) to track hierarchical reporting.
- **Add `AccountApproval` model**:
  - To track multi-signature approvals (e.g., VP requires CEO + Director).
  - Columns: `approval_id`, `pending_employee_id`, `approver_id`, `approver_role`, `status`.
- **Add `OTPVerification` model**:
  - To store transient OTP codes during signup.
  - Columns: `email`, `otp_code`, `expires_at`.
- **Update `seed_data`**: 
  - Manually provision the `CEO` and `Director` roles with default emails and passwords, as they cannot sign up via the UI.

#### [NEW] [backend/routers/auth.py](file:///d:/Downloads/ExpenseOPS/backend/routers/auth.py)
- Create new endpoints:
  - `POST /api/v1/auth/request-otp`: Accepts an email, generates a 6-digit OTP, saves it in the DB, and "sends" it (prints to console for dev).
  - `POST /api/v1/auth/signup`: Accepts user details + the OTP code. Validates the OTP. If valid, registers the user and assigns `account_status = PENDING_APPROVAL`. Rejects signup attempts for CEO/Director roles.
  - `POST /api/v1/auth/login`: Authenticates email/password. **Rejects login if `account_status != APPROVED`**.
  - `GET /api/v1/auth/me`: Returns the currently authenticated user's profile.
  - `GET /api/v1/auth/managers`: Returns a list of active Managers to populate the signup dropdown for Analysts.

#### [NEW] [backend/routers/users.py](file:///d:/Downloads/ExpenseOPS/backend/routers/users.py)
- Endpoints for the approval workflow:
  - `GET /api/v1/users/pending-approvals`: Returns a list of users waiting for the current user's approval based on their role.
  - `POST /api/v1/users/{employee_id}/approve`: Action to approve a pending user. Contains the logic to check if a VP has received both required approvals before fully activating the account.

### 2. Account Approval Workflow Logic
The core business logic for account activation will be implemented as follows:
- **Analyst Signup**: 
  1. Requests OTP -> Submits OTP with details and selected Manager.
  2. Account remains `PENDING_APPROVAL` until that specific Manager approves them.
- **Manager Signup**: 
  1. Requests OTP -> Submits OTP.
  2. Account remains `PENDING_APPROVAL` until *any* user with the `VP` role approves them.
- **VP Signup**: 
  1. Requests OTP -> Submits OTP.
  2. Account remains `PENDING_APPROVAL` until it receives an approval record from *both* a `CEO` and a `Director`.
- **Director / CEO**: Cannot sign up via the UI. Credentials will be manually seeded.

### 3. Frontend Routing & Auth Pages
We will transform the single-page app into a multi-page app with protected routes and RBAC layouts.

#### [NEW] [frontend/src/pages/Signup.jsx](file:///d:/Downloads/ExpenseOPS/frontend/src/pages/Signup.jsx)
- **Step 1**: Enter Name, Email, Password, Role.
- **Step 2 (If Analyst)**: Select a Manager from a dynamically populated dropdown.
- **Step 3 (OTP Verification)**: The user clicks "Send OTP". A modal/screen prompts for the 6-digit code. Upon submission of the valid OTP, the account is created and a "Pending Approval" success screen is shown.

#### [NEW] [frontend/src/pages/Login.jsx](file:///d:/Downloads/ExpenseOPS/frontend/src/pages/Login.jsx)
- Authenticates the user. If the backend returns a 403 Account Pending error, displays a corresponding alert to the user.

#### [MODIFY] [frontend/src/App.jsx](file:///d:/Downloads/ExpenseOPS/frontend/src/App.jsx) & Dashboard
- Implement UI rendering logic based on `user.role`:
  - **Analyst (Employee)**: Restrict the view to the `ReceiptUploader` and their own `TransactionGrid`. Hide global charts.
  - **Managers / VPs / Directors / CEO**: Show charts, metrics, and the full `TransactionGrid`. 
  - **Account Approvals Tab**: A new section in the dashboard visible to Managers+ where they can view and approve pending account registrations assigned to their purview.
  - **Expense Approvals**: Enforce that higher-ups can only review/approve expense claims that are flagged as `EXCEPTION_HOLD` or `PENDING`.

## Verification Plan

### Automated Verification
- No new automated unit tests, but existing pipelines will be tested to ensure the Auth layer doesn't break the submission flow.

### Manual Verification
1. Attempt to sign up as an Analyst. Verify the OTP is generated in the backend console. Submit the wrong OTP to verify it fails. Submit the correct OTP to verify it proceeds to `PENDING_APPROVAL`.
2. Log in as the selected Manager, go to the "Account Approvals" tab, and approve the Analyst. Verify the Analyst can now log in.
3. Attempt to sign up as a VP using the OTP flow. Log in as a Director and approve. Verify the VP still cannot log in. Log in as CEO and approve. Verify the VP can now log in.
