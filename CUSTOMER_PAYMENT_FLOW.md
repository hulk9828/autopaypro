# Customer Vehicle & Payment Flow – AutoLoanPro

This document describes the end-to-end flow of how a customer gets a vehicle and how payments work in the AutoLoanPro backend.

---

## 1. Overview

- **Admin** creates **customers** and assigns **vehicles on lease** with **loans** (lease amount, down payment, lease term, **lease_payment_type**: bi_weekly, monthly, or semi_monthly). No interest; flat payment per due. Vehicles are **leased**, not sold; after lease end they can be reassigned.
- **Customer** receives login credentials by email, logs in, and can view vehicles/loans, make payments, and see history.
- **Payments** are either:
  - **Customer-authenticated**: customer calls `POST /payments/` with `loan_id`, `card_token`, and optional `due_date_iso`.
  - **Public/link**: admin creates a checkout → customer pays with `payment_intent_id` + `card_token` via `POST /payments/pay` (no login required).

---

## 2. High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ADMIN: Vehicle & Customer Setup                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. Vehicles exist in system (added via /vehicles)                                │
│  2. Admin creates customer + assigns vehicles on lease → POST /customers/         │
│     • basic_info, address_docs, vehicles_to_lease[] (vehicle_id, lease_amount,   │
│       down_payment, lease_payment_type, loan_term_months)                        │
│     • System: creates Customer, marks Vehicle(s) leased, creates Loan(s),       │
│       sets lease_start_date/lease_end_date on CustomerVehicle, emails credentials │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CUSTOMER: Onboarding                                                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│  3. Customer receives email: login (email) + auto-generated password               │
│  4. Customer logs in → POST /customers/login (email, password)                    │
│     • Returns JWT (Bearer token) for customer-only endpoints                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CUSTOMER: View Vehicles & Loans                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  5. GET /customers/home (Bearer) → vehicles, loans, remaining balance,            │
│     next payment due dates, loan_status (open/closed)                             │
│  6. GET /customers/profile (Bearer) → profile; PATCH /customers/profile → update  │
│  7. GET /payments/summary (Bearer) → single list of paid_dues, unpaid_dues,       │
│     overdue_payments with payment_status enum                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│  PAYMENT PATH A: Customer logged in  │  │  PAYMENT PATH B: Public / link flow   │
├──────────────────────────────────────┤  ├──────────────────────────────────────┤
│  POST /payments/                      │  │  Admin: POST /payments/checkout       │
│  Body: loan_id, payment_type          │  │  (loan_id, payment_type, due_date_iso,│
│  (next | due), due_date_iso? ,        │  │  email or customer_id) → client_     │
│  card_token                           │  │  secret, payment_intent_id, amount  │
│  → Stripe charge, Payment record,     │  │  Customer: GET /payments/checkout/     │
│  loan balance updated, loan closed    │  │  {payment_intent_id} (optional)       │
│  when amount_financed = 0             │  │  Customer: POST /payments/pay          │
│                                       │  │  (payment_intent_id, card_token)      │
│                                       │  │  → same: record payment, update loan  │
└──────────────────────────────────────┘  └──────────────────────────────────────┘
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  AFTER PAYMENT                                                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Payment record created (due_date, amount, status completed/failed)             │
│  • Loan amount_financed reduced; if 0 → loan status = closed                     │
│  • Notifications: payment received / payment confirmed (email + FCM if configured)│
│  • Customer: GET /payments/history, GET /payments/my-receipt/{payment_id}         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Flows

### 3.1 Admin Creates Customer and Assigns Vehicles

1. **Prerequisites**
   - Vehicles must exist (e.g. created via admin/vehicles).
   - Admin is authenticated (e.g. `POST /admins/login` → use Bearer token).

2. **Request**
   - **Endpoint:** `POST /api/v1/customers/`
   - **Auth:** Admin Bearer token.
   - **Body (JSON):** `CreateCustomerRequest`:
     - `basic_info`: first_name, last_name, phone, email
     - `address_docs`: address, driver_license_number, employer_name
     - `vehicles_to_lease`: array of:
       - `vehicle_id`, `lease_amount`, `down_payment`, `lease_payment_type` (bi_weekly | monthly | semi_monthly), `loan_term_months`

3. **Validations**
   - Email, phone, driver_license_number must be unique.
   - Down payment &lt; lease amount (else error).
   - If lease_amount == down_payment: loan is created with amount_financed = 0, status **closed**, no schedule.
   - Each vehicle must exist, not already leased, not already assigned.

4. **What the system does**
   - Creates **Customer** (with hashed auto-generated password).
   - For each vehicle:
     - Marks vehicle as **leased** (status = leased).
     - Creates **CustomerVehicle** with `lease_start_date`, `lease_end_date` (for reassignment after lease end).
     - Computes `amount_financed = lease_amount - down_payment`; **flat payment per due** = amount_financed ÷ num_payments (no interest). Num payments: **monthly** = term_months, **bi_weekly** / **semi_monthly** = term_months × 2.
     - Creates **Loan** with `lease_payment_type`, `bi_weekly_payment_amount` (amount per due), active or closed if amount_financed == 0.
   - Sends **email** to customer with login credentials (email + generated password).

5. **Response**
   - `CustomerResponse` (customer id, name, email, etc.).

---

### 3.2 Customer Login and Identity

1. **Endpoint:** `POST /api/v1/customers/login`
2. **Body:** `email`, `password`, optional `device_token` (for push).
3. **Response:** JWT access token (use as `Authorization: Bearer <token>` for customer endpoints).

Customer can then:
- **GET /api/v1/customers/home** – vehicles, loans, next dues, balances.
- **GET /api/v1/customers/profile** – profile; **PATCH /api/v1/customers/profile** – update (including optional profile image).
- **GET /api/v1/payments/summary** – single list of payment/due entries (paid, unpaid, overdue).
- **GET /api/v1/payments/history** – transaction history.
- **GET /api/v1/payments/my-receipt/{payment_id}** – receipt for a payment.

---

### 3.3 Payment Schedule (lease_payment_type)

- Each **Loan** has:
  - `amount_financed`, `bi_weekly_payment_amount` (amount per due, any frequency), `loan_term_months`, **`lease_payment_type`** (bi_weekly | monthly | semi_monthly), `created_at`.
- **Due dates** depend on `lease_payment_type`:
  - **bi_weekly:** first due = `created_at` + 14 days, then every 14 days.
  - **monthly:** same calendar day each month (or last day if shorter).
  - **semi_monthly:** 1st and 15th of each month (on or after loan start).
- Number of installments: **monthly** = term_months; **bi_weekly** / **semi_monthly** = term_months × 2.
- A **Payment** row is created when a due is paid; it stores the **due_date** that this payment satisfies.
- **CustomerVehicle** stores `lease_start_date` and `lease_end_date`; after lease end the vehicle is eligible for reassignment (future use).

---

### 3.4 Payment Flow A – Customer Logged In

1. Customer has a Bearer token.
2. **Endpoint:** `POST /api/v1/payments/`
3. **Body:** `loan_id`, `payment_type` (`"next"` or `"due"`), optional `due_date_iso` (required when `payment_type == "due"`), `card_token` (Stripe payment method/token).
4. **Behaviour:**
   - **next**: system finds the next unpaid due for that loan and charges that amount.
   - **due**: system validates `due_date_iso` as an unpaid due for that loan and charges that installment.
5. Backend charges via Stripe, creates **Payment** (due_date, amount, status), reduces loan `amount_financed`. If `amount_financed` becomes 0, loan is marked **closed**.
6. Response includes success and transaction details; customer can fetch receipt via `GET /payments/my-receipt/{payment_id}`.

---

### 3.5 Payment Flow B – Public / Link (No Login)

Used when admin sends a payment link or the customer pays without logging in.

1. **Admin creates checkout**
   - **Endpoint:** `POST /api/v1/payments/checkout` (Admin Bearer).
   - **Body:** `loan_id`, `payment_type` (`"next"` or `"due"`), optional `due_date_iso` (if "due"), and **either** `email` or `customer_id` to identify the customer.
   - **Response:** `client_secret` (Stripe PaymentIntent), `payment_intent_id`, amount, and other checkout details.

2. **Optional: get checkout by ID**
   - **Endpoint:** `GET /api/v1/payments/checkout/{payment_intent_id}` (no auth).
   - Returns same kind of checkout info (e.g. to show amount or re-use client_secret).

3. **Customer completes payment**
   - **Endpoint:** `POST /api/v1/payments/pay` (no auth).
   - **Body:** `payment_intent_id` (from checkout), `card_token`.
   - Backend confirms the Stripe PaymentIntent, then creates **Payment**, updates loan (and closes loan if paid off). Same notifications as Flow A.

---

### 3.6 Other Payment-Related Actions

| Action | Endpoint | Who | Description |
|--------|----------|-----|-------------|
| Record manual payment | `POST /api/v1/payments/record-manual` | Admin | Record cash/check/other; select customer, loan, due date, amount, method, note. |
| Waive one overdue | `POST /api/v1/payments/waive-overdue` | Admin | Waive by `loan_id` + `due_date_iso`. |
| Waive earliest overdue by customer/loan | `POST /api/v1/payments/waive-overdue-by-customer` | Admin | Body: `customer_id`, `loan_id`, optional note. |
| Bulk overdue reminder | `POST /api/v1/payments/bulk-overdue-reminder` | Admin | Sends default overdue email + push to all with overdue installments. |
| Update payment status | `PATCH /api/v1/payments/{payment_id}/status` | Admin | Set completed/failed; “completed” triggers Payment Confirmed notification. |
| Due customers list | `GET /api/v1/payments/due-customers` | Admin | Customers with unpaid dues (for creating checkouts). |
| Due installments list | `GET /api/v1/payments/due-installments` | Admin | All unpaid dues with loan_id, due_date_iso, amount. |
| Payment summary | `GET /api/v1/payments/summary` | Admin | Single list of paid/unpaid/overdue items with totals. |

---

## 4. Notifications

- **Customer credentials:** Email with login and password when customer is created.
- **Payment received / Payment confirmed:** Sent when payments are recorded or status set to completed (email + FCM if configured).
- **Due reminder / Overdue:** Cron and bulk overdue reminder can send emails and push (e.g. “due tomorrow”, “overdue alert”).
- Device token can be set at login or via `PATCH /api/v1/auth/device-token`.

---

## 5. Key API Endpoints Summary

| Purpose | Method | Endpoint | Auth |
|--------|--------|----------|------|
| Create customer + assign vehicles on lease | POST | `/api/v1/customers/` | Admin |
| Create lease (existing customer) | POST | `/api/v1/leases/` | Admin |
| List leases | GET | `/api/v1/leases/` | Admin |
| Export leases to Excel | GET | `/api/v1/leases/export` | Admin |
| Customer login | POST | `/api/v1/customers/login` | None |
| Customer home (vehicles, loans, next due) | GET | `/api/v1/customers/home` | Customer |
| Customer profile | GET / PATCH | `/api/v1/customers/profile` | Customer |
| Payment summary (paid/unpaid/overdue) | GET | `/api/v1/payments/summary` | Customer |
| Make payment (logged-in) | POST | `/api/v1/payments/` | Customer |
| Create checkout (for link) | POST | `/api/v1/payments/checkout` | Admin |
| Get checkout | GET | `/api/v1/payments/checkout/{payment_intent_id}` | None |
| Confirm payment (link) | POST | `/api/v1/payments/pay` | None |
| My transaction history | GET | `/api/v1/payments/history` | Customer |
| My receipt | GET | `/api/v1/payments/my-receipt/{payment_id}` | Customer |

---

## 6. Loan Status and Amounts

- **Loan status:** Stored as `active` or `closed`. Exposed to customer as **open** / **completed** (or “closed”) in APIs.
- **lease_payment_type:** One of **bi_weekly**, **monthly**, **semi_monthly**. Determines due-date schedule; no interest is applied—payment per due is flat (amount_financed ÷ num_payments).
- **Closing a loan:** When `amount_financed` reaches 0 (e.g. after payments or full down payment), the loan is set to **closed**. Closed loans are excluded from “next due”, unpaid/overdue lists, and payment actions.
- **Amounts:** All displayed amounts (e.g. next_payment_amount, amount_financed, bi_weekly_payment_amount) are kept non-negative across the app.

This completes the flow from vehicle assignment and customer creation through login, viewing vehicles/loans, and making payments (either logged-in or via payment link).
