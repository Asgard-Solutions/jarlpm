# JarlPM - AI-Agnostic Product Management

JarlPM helps Product Managers lead with clarity and discipline. Capture problems, lock decisions, and deliver implementation-ready epics — using any LLM you choose.

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL (or use Neon for cloud)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env template and configure
cp .env.example .env
# Edit .env with your values (see Environment Variables below)

# Run the server
uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
yarn install

# Copy env template
cp .env.example .env
# Set VITE_BACKEND_URL to your backend URL

# Run dev server
yarn dev
```

App runs at `http://localhost:3000`

---

## Environment Variables

### Backend (`backend/.env`)

```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require

# Security
JWT_SECRET=your-256-bit-secret-key
ENCRYPTION_SECRET_KEY=your-32-byte-hex-key

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Stripe Billing
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...      # Optional: for webhook verification
STRIPE_PRICE_ID=price_...            # Optional: auto-creates if not set

# Email (Microsoft Graph) - Optional
MICROSOFT_GRAPH_CLIENT_ID=...
MICROSOFT_GRAPH_CLIENT_SECRET=...
MICROSOFT_GRAPH_TENANT_ID=...
```

### Frontend (`frontend/.env`)

```bash
VITE_BACKEND_URL=http://localhost:8001
```

---

## Authentication

JarlPM uses **JWT tokens stored in httpOnly cookies** for authentication.

### How it works locally:

1. **Signup/Login** → Backend validates credentials, creates JWT
2. **Set-Cookie** → JWT returned as httpOnly cookie (not accessible to JS)
3. **Subsequent requests** → Browser auto-sends cookie, backend validates
4. **Logout** → Cookie cleared

### Cookie settings (for local dev):

```python
# In routes/auth.py
response.set_cookie(
    key="session_token",
    value=token,
    httponly=True,
    secure=False,      # Set True in production (HTTPS)
    samesite="lax",
    max_age=86400 * 7  # 7 days
)
```

### Testing auth locally:

```bash
# Signup
curl -X POST http://localhost:8001/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234","name":"Test User"}'

# Login (saves cookie)
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email":"test@example.com","password":"Test1234"}'

# Authenticated request (uses cookie)
curl http://localhost:8001/api/auth/me -b cookies.txt
```

---

## Database & Migrations

JarlPM uses **PostgreSQL** with **SQLAlchemy ORM**. Tables are auto-created on startup.

### Local PostgreSQL:

```bash
# Create database
createdb jarlpm

# Set DATABASE_URL
DATABASE_URL=postgresql://localhost/jarlpm
```

### Using Neon (cloud PostgreSQL):

1. Create project at [neon.tech](https://neon.tech)
2. Copy connection string to `DATABASE_URL`
3. Append `?sslmode=require` if not present

### Schema auto-migration:

Tables are created automatically when the server starts via:

```python
# In db/database.py
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

### Manual migration (if needed):

```bash
cd backend
python -c "
from db.database import engine, Base
from db.models import *
import asyncio

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migration complete')

asyncio.run(migrate())
"
```

---

## Testing Stripe Webhooks Locally

Stripe webhooks need to reach your local server. Use the **Stripe CLI**:

### 1. Install Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows
scoop install stripe

# Linux
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.dev/stripe-cli-debian-local stable main" | sudo tee /etc/apt/sources.list.d/stripe.list
sudo apt update && sudo apt install stripe
```

### 2. Login to Stripe

```bash
stripe login
```

### 3. Forward webhooks to localhost

```bash
stripe listen --forward-to localhost:8001/api/webhook/stripe
```

This outputs a webhook signing secret like `whsec_...`. Add it to your `.env`:

```bash
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 4. Test webhook events

```bash
# Trigger a test event
stripe trigger checkout.session.completed

# Or trigger subscription events
stripe trigger customer.subscription.created
stripe trigger invoice.paid
stripe trigger invoice.payment_failed
```

### Key webhook events handled:

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Logs completion |
| `customer.subscription.created` | Activates subscription |
| `customer.subscription.updated` | Updates period dates |
| `customer.subscription.deleted` | Marks as canceled |
| `invoice.paid` | Confirms renewal |
| `invoice.payment_failed` | Sets status to past_due |

---

## Project Structure

```
/app
├── backend/
│   ├── db/
│   │   ├── database.py      # Async SQLAlchemy setup
│   │   ├── models.py        # Core models (User, Epic, Subscription)
│   │   ├── feature_models.py
│   │   └── user_story_models.py
│   ├── routes/
│   │   ├── auth.py          # Signup, login, password reset
│   │   ├── subscription.py  # Stripe billing
│   │   ├── epic.py          # Epic CRUD + AI chat
│   │   ├── feature.py       # Feature planning
│   │   ├── user_story.py    # User stories
│   │   ├── poker.py         # AI estimation
│   │   └── ...
│   ├── services/
│   │   ├── llm_service.py   # LLM abstraction layer
│   │   ├── prompt_service.py
│   │   └── email_service.py
│   ├── server.py            # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/index.js     # API client
│   │   ├── components/      # Reusable UI (shadcn/ui)
│   │   ├── pages/           # Route components
│   │   └── store/           # Zustand stores
│   ├── vite.config.js
│   └── package.json
└── memory/
    └── PRD.md               # Product requirements doc
```

---

## API Overview

| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/signup` | Create account |
| `POST /api/auth/login` | Login (returns cookie) |
| `GET /api/auth/me` | Current user |
| `GET /api/subscription/status` | Subscription status |
| `POST /api/subscription/create-checkout` | Start Stripe checkout |
| `POST /api/subscription/cancel` | Cancel subscription |
| `GET /api/epics` | List user's epics |
| `POST /api/epics/{id}/chat` | Chat with AI (SSE stream) |
| `GET /api/features/epic/{id}` | List features |
| `POST /api/poker/estimate` | AI story estimation |

---

## Tech Stack

- **Frontend**: React 19, Vite, Tailwind CSS, shadcn/ui, Zustand
- **Backend**: FastAPI, SQLAlchemy (async), PostgreSQL
- **Auth**: JWT in httpOnly cookies, bcrypt password hashing
- **Payments**: Stripe Subscriptions
- **Email**: Microsoft Graph API
- **LLM**: User-provided keys (OpenAI, Anthropic, or local)

---

## License

MIT
