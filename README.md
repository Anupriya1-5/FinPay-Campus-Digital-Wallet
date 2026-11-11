# FinPay – Smart Campus Digital Wallet

A multi-role academic demo application with Student, Merchant, Admin and Support Officer portals.

## Stack
- Frontend: React + Vite
- Backend: FastAPI + SQLAlchemy
- Database: SQLite (local demo)
- Authentication: JWT bearer tokens, role-based API authorization
- Tests: pytest

## Important scope note
This is a simulated campus wallet. It does **not** connect to real UPI, banks, cards or payment gateways. Top-ups are simulated and must be treated as demo funds. The application is an academic prototype, not a production financial system.

## Windows / VS Code setup

### 1. Backend
Open a terminal in `backend`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks `Activate.ps1`, keep using `.venv\Scripts\python.exe` as shown; activation is not required.

API documentation: http://127.0.0.1:8000/docs

### 2. Frontend
Open a second terminal in `frontend`:

```powershell
npm.cmd install
npm.cmd run dev
```

Open the Vite URL shown in the terminal (normally http://localhost:5173).

### Demo accounts
All passwords: `password123`

| Role | Email |
|---|---|
| Student | rahul@student.finpay.edu |
| Student | priya@student.finpay.edu |
| Merchant | canteen@finpay.edu |
| Merchant | stationery@finpay.edu |
| Admin | admin@finpay.edu |
| Support Officer | support@finpay.edu |

Seed data creates a Canteen, Stationery Shop, Campus Transport and Hostel Office.

## Included workflows
- Student wallet, simulated top-up, merchant payments, QR payload display, transaction history, spending summary and notifications.
- Merchant registration/approval, merchant dashboard, QR payload and sales history.
- Admin user/merchant management, merchant approvals, cashback policy visibility, transaction monitoring, fraud alerts and monthly reconciliation.
- Support complaint queue, investigation status and refund decision workflow.
- Integer-paise cashback, tier multipliers, monthly category caps, idempotency key enforcement and wallet ledger entries.
- Refunds reverse the original merchant payment and create compensating ledger entries.
- Rule-based fraud flags for repeated rapid payments and repeated failures.
- Audit events for important actions.

## Tests
From `backend`:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Project structure
```text
FinPay/
  backend/
    app/
      api/
      core/
      models/
      repositories/
      schemas/
      services/
      main.py
      seed.py
    tests/
  frontend/
    src/
  README.md
```

## Security / production limitations
- Demo JWT secret in `.env.example` must be replaced outside local development.
- SQLite is suitable for a local academic demo. A concurrent production wallet needs a database with appropriate row locking, isolation and operational controls.
- QR codes in this demo carry a signed-in-app merchant identifier payload; they are not payment-network QR codes.
- Refund approvals, top-ups and settlement are simulated academic workflows.
- Before production use, add formal KYC, payment-provider integration, stronger fraud controls, rate limiting, secrets management, monitoring, backups and security review.
