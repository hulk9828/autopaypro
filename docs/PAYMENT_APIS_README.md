# Payment-Related APIs – Overview & How They Work

This document lists all payment-related API endpoints in the AutoLoanPro Payment App and explains how the payment flows work.

**Base URL:** `/api/v1` (e.g. payments prefix → `/api/v1/payments`)

**Authentication:**
- **Customer:** Bearer token (customer login). Use for customer-only endpoints.
- **Admin:** Bearer token (admin login). Use for admin-only endpoints.
- **No auth:** Used for external payment recording (`POST /payments/update-payment`) and for checkout: fetch (`GET /payments/checkout/{token}`) and complete (`POST /payments/checkout/{token}/complete`).

---

## Table of Contents

1. [Payments router (`/payments`)](#1-payments-router-payments)
2. [Customer router – payment-related (`/customers`)](#2-customer-router--payment-related-customers)
3. [Calendar router – payment (`/calendar`)](#3-calendar-router--payment-calendar)
4. [Dashboard router – payment-related (`/dashboard`)](#4-dashboard-router--payment-related-dashboard)
5. [How the payment flows work](#5-how-the-payment-flows-work)

---

## 1. Payments router (`/payments`)

All endpoints below are under **`GET/POST/PATCH /api/v1/payments/...`**.

### External payment (no auth)

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `POST` | `/payments/update-payment` | None | Record a payment from an external payment system. Body: `customer_id`, `loan_id`, `amount`. Validates customer and loan ownership; applies amount to earliest unpaid installments; creates payment with `payment_method="external"`, `status="completed"`. Returns `payment_id` and `remaining_balance`. No authentication required. |

**Flow:** External system calls `POST /payments/update-payment` with the three required fields. Backend validates customer exists, loan exists, loan belongs to customer; rejects zero/negative amount and amount exceeding remaining balance; applies payment to earliest unpaid EMIs (supports partial); updates loan `total_paid` and closes loan if fully paid.

---

### Checkout (payment link by email)

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `POST` | `/payments/checkout` | Admin | Create a checkout: pass `customer_id`, `loan_id`, and optional `amount` (if omitted, full remaining balance is used). Backend creates a unique payment link, **sends it to the customer’s email**, and returns `checkout_id`, `token`, `payment_link`, `amount`, `expires_at`, `email_sent_to`. Link expires in 7 days. |
| `GET` | `/payments/checkout/{token}` | None | **Fetch checkout by token** (no auth). Used when the user opens the link from the email. Returns checkout details: `customer_name`, `loan_id`, `vehicle_display`, `amount`, `remaining_balance`, `status`, `expires_at`. 404 if token invalid or expired. |
| `POST` | `/payments/checkout/{token}/complete` | None | **Complete checkout** after the user has paid on the frontend. Optional body: `{ "amount": 500 }` (if omitted, checkout amount is used). Records the payment (same as update-payment), marks checkout as completed, returns `payment_id` and `remaining_balance`. 400 if checkout not found, expired, or already completed. |

**Flow:** Admin creates checkout → customer receives email with payment link (`PAYMENT_LINK_BASE_URL?token=...`) → user opens link → frontend calls `GET /payments/checkout/{token}` to show amount and details → user pays (e.g. on your frontend/gateway) → frontend calls `POST /payments/checkout/{token}/complete` (optionally with `amount`) to record the payment and update the loan.

---

### Customer: history, receipt, notifications

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `GET` | `/payments/history` | Customer | Paginated “my transaction history”. Query params: `skip`, `limit`. |
| `GET` | `/payments/my-receipt/{payment_id}` | Customer | Get receipt for one of the customer’s payments. 404 if not owner. |
| `GET` | `/payments/my-notifications` | Customer | All notifications for the logged-in customer (payment received, confirmed, due tomorrow, overdue). Query params: `skip`, `limit`. |

---

### Admin: manual payment, waive, reminders, status, receipt

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `POST` | `/payments/record-manual` | Admin | Record a manual payment (cash, check, etc.): `customer_id`, `loan_id`, `due_date_iso`, `amount`, `payment_method` (cash/card/online/check), optional `note`. Due date must be an unpaid scheduled installment. |
| `POST` | `/payments/waive-overdue` | Admin | Waive one unpaid installment: `loan_id`, `due_date_iso`, optional `note`. Creates a zero-amount completed payment (waived); that due is considered satisfied. |
| `POST` | `/payments/waive-overdue-by-customer` | Admin | Waive the **earliest** overdue installment for a customer’s loan: `customer_id`, `loan_id`, optional `note`. |
| `POST` | `/payments/bulk-overdue-reminder` | Admin | Send default overdue alert email and push notification to **all** customers who have at least one overdue payment. No body. |
| `PATCH` | `/payments/{payment_id}/status` | Admin | Set payment status to `completed` or `failed`. When set to `completed`, a “Payment Confirmed” notification is sent. |
| `GET` | `/payments/{payment_id}/receipt` | Admin | Get receipt data for any payment (for display/print). |

---

### Admin: due lists, summary, overdue, notifications, transactions

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `GET` | `/payments/due-customers` | Admin | List customers who have at least one unpaid due. Each item has loan_id, email, next due, etc. Query: `customer_id`, `loan_id`, `search`, `skip`, `limit`. |
| `GET` | `/payments/due-installments` | Admin | List every unpaid due installment: loan_id, customer, `due_date_iso`, amount. Query: `customer_id`, `loan_id`, `search`, `skip`, `limit`. |
| `GET` | `/payments/summary` | Admin | Payment summary: paid/unpaid/overdue breakdown, total collected, pending amount, overdue amount, total payment left. Query: `customer_id`, `loan_id`, `search`. |
| `GET` | `/payments/overdue` | Admin | Overdue accounts: list of overdue installments, total count, total outstanding amount, average overdue days. Query: `skip`, `limit`. |
| `GET` | `/payments/notifications` | Admin | All notifications (all customers). Optional filter: `customer_id`. Query: `customer_id`, `skip`, `limit`. |
| `GET` | `/payments/transactions` | Admin | Paginated transaction history with summary: total, total_amount, completed_count, failed_count. Query: `customer_id`, `loan_id`, `from_date`, `to_date`, `skip`, `limit`. |
| `GET` | `/payments/transactions/export` | Admin | Export transactions to Excel (.xlsx). Same filters: `customer_id`, `loan_id`, `from_date`, `to_date`. Returns file download. |

---

## 2. Customer router – payment-related (`/customers`)

Under **`/api/v1/customers/...`**. Customer auth required.

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `GET` | `/customers/home` | Customer | Customer home: vehicles, loan info, **remaining balance**, **next payment due** dates. Single call for dashboard-style view. |
| `GET` | `/customers/payment-schedule` | Customer | Full payment schedule: for each loan, list of due dates with **amount** and **status** (paid / upcoming / overdue). Optional query: `from_date`, `to_date` to filter the date range. |

These are the main “when to pay and how much” and “what’s left to pay” APIs for the logged-in customer.

---

## 3. Calendar router – payment (`/calendar`)

Under **`/api/v1/calendar/...`**. Admin only.

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `GET` | `/calendar/payment` | Admin | Payment calendar for a **single date**. Query: `date` (YYYY-MM-DD). Returns paid (due on that date and paid), pending (due on that date not paid), and overdue (due before that date not paid) with counts and lists. |

Use this to build an admin calendar view (e.g. “what’s due on this day?”).

---

## 4. Dashboard router – payment-related (`/dashboard`)

Under **`/api/v1/dashboard/...`**. Admin only.

| Method | Endpoint | Auth | Description |
|--------|----------|------|--------------|
| `GET` | `/dashboard/` | Admin | Full dashboard: summary stats (e.g. total customers, active loans, overdue accounts, monthly revenue), **recent payments**, overdue accounts, upcoming payments. |
| `GET` | `/dashboard/recent-payments` | Admin | Recent payments only. Query: `limit` (default 10, max 50). |
| `GET` | `/dashboard/pending-loans` | Admin | Customers who have **pending loan amount** (remaining balance > 0). Each item: customer details, `loan_id`, `pending_loan_amount`, and **pending_emis** (list of due date + amount the user has to pay). |

---

## 5. How the payment flows work

### A. Checkout (payment link by email)

1. **Admin** creates a checkout: `POST /api/v1/payments/checkout` with `customer_id`, `loan_id`, and optional `amount`.
2. Backend creates a checkout record with a unique `token`, builds the payment URL from `PAYMENT_LINK_BASE_URL` (e.g. `https://app.example.com/pay?token=xxx`), and **sends an email** to the customer with that link.
3. **Customer** opens the link; the frontend reads `token` from the URL and calls `GET /api/v1/payments/checkout/{token}` to get amount, vehicle, and customer info for the payment page.
4. **User pays** on the frontend (your own payment UI/gateway).
5. **Frontend** calls `POST /api/v1/payments/checkout/{token}/complete` (with optional `amount` in body) to record the payment. Backend applies the amount to the loan (earliest unpaid installments), creates a payment with `payment_method="external"`, and marks the checkout as completed.
6. Response includes `payment_id` and `remaining_balance`.

Set `PAYMENT_LINK_BASE_URL` in config (e.g. `https://yourapp.com/pay`) so the email contains the full payment page URL.

### B. External payment (no auth)

1. **External payment system** (e.g. gateway or partner) has already collected the payment from the customer.
2. It calls `POST /api/v1/payments/update-payment` with JSON: `{"customer_id": "<uuid>", "loan_id": "<uuid>", "amount": 500}`.
3. Backend validates: customer exists, loan exists, loan belongs to customer; amount &gt; 0; amount ≤ remaining balance.
4. Backend applies the amount to the **earliest unpaid installments** (overdue first, then upcoming). Partial EMIs are supported (one due can be partially paid).
5. Backend creates a payment record with `payment_method="external"`, `status="completed"`, and `applied_installments` breakdown; updates loan `total_paid` (and reduces `amount_financed` for remaining balance); closes loan if fully paid.
6. Response: `{"success": true, "message": "Payment recorded successfully", "payment_id": "<uuid>", "remaining_balance": <number>}`. On error: 400 with `{"success": false, "message": "Customer not found"}` (or Loan not found / Invalid amount / etc.).

### C. Manual payment (admin)

1. Admin receives cash/check/other from customer.
2. `POST /payments/record-manual` with `customer_id`, `loan_id`, `due_date_iso`, `amount`, `payment_method`, optional `note`.
3. Backend validates that the due date is a scheduled unpaid installment for that loan and that the customer owns the loan; then creates a completed payment and updates loan `total_paid`.

### D. Waiving an installment (admin)

- **One specific due:** `POST /payments/waive-overdue` with `loan_id`, `due_date_iso`. Backend creates a zero-amount “waived” payment so that due is considered satisfied.
- **Earliest overdue for a customer’s loan:** `POST /payments/waive-overdue-by-customer` with `customer_id`, `loan_id`. Backend finds the earliest overdue unpaid due for that loan and waives it.

### E. Applying payments to dues (logic)

- **Flexible payment:** Any positive amount can be paid. The system applies it to the **earliest** unpaid dues first (overdue, then upcoming/future). Partial payments can satisfy part of a due; full due is marked paid when applied amount ≥ EMI for that date.
- **Manual:** Can target a specific due (e.g. `due_date_iso` in record-manual). **External (update-payment):** Always applies to earliest unpaid dues for the given amount.

### F. Key concepts

- **EMI / installment:** Each loan has a schedule of due dates (bi-weekly, monthly, or semi-monthly). Each due date has an amount (“EMI amount”). A payment can cover one or more dues depending on amount.
- **Overdue:** A due date that is in the past and not fully paid.
- **Pending loan amount:** `amount_financed - total_paid`; reported in dashboard and in `/dashboard/pending-loans` with customer details and list of pending EMIs (due date + amount).

For exact request/response shapes, use the OpenAPI schema at `/openapi.json` or the interactive docs at `/docs`.
