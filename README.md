# SkyAgent – agentic flight booking (learning project)

| Layer | Tech |
|---|---|
| Agent workflow | **LangGraph** (`extract → route → search/select/status/cancel/chat → respond`) |
| LLM | **Ollama** `qwen3.5:4b` (change with `OLLAMA_MODEL`) |
| Backend | **FastAPI** + SQLAlchemy, **SQLite** |
| Frontend | **React** (Vite) |
| Flight data | **Duffel** test mode (free) – or the built-in offline demo provider when no key is set |
| Payments | **JazzCash** Hosted Checkout (sandbox) – or a built-in **mock** checkout |

## Run it

```bash
ollama pull qwen3.5:4b

cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then edit (see below)
.venv\Scripts\uvicorn app.main:app --reload     # http://localhost:8000/docs

cd frontend
npm install
npm run dev                                      # http://localhost:5173
```

Smoke tests: `python smoke_test.py` (API + payment, no LLM) · `python agent_demo.py` (chat in terminal).

## Pages

**Home** (`#/`) is one page: hero search form (city dropdowns, one-way/round-trip, dates, passengers, cabin) + the **AI assistant** chat + popular-destination photos. The booking flow is a row of tabs that unlock as you progress:

| Tab | Page | Route |
|---|---|---|
| 1 | Home – search + assistant | `#/` |
| 2 | Results – airline, times, duration, stops, price, filters + sorting | `#/results` |
| 3 | Details – itinerary, baggage, refund/change rules, fare comparison | `#/details` |
| 4 | Passengers – names, DOB, passport (international), contact, saved profiles | `#/passengers` |
| 5 | Review & pay – summary, live price re-check, taxes, JazzCash, approval checkbox | `#/review` |
| 6 | Confirmation – PNR, ticket status, email notice, ticket download | `#/confirmation/<ref>` |

Plus **My trips** (`#/trips`) in the header: upcoming/previous bookings, cancel, passenger profiles.
City photos are fetched from Wikipedia's public API (gradient fallback if offline).
Browsing and searching are public; **login is required from Passenger details onward** (and for agent trip lookups/cancels).

## Flight data: Duffel (recommended) or offline demo

1. Sign up at https://duffel.com (free), create a **test mode** token (`duffel_test_…`).
2. Put it in `backend/.env` as `DUFFEL_API_KEY=...` and restart the backend.

With a key: search = Duffel offer requests, the final price check = `GET /air/offers/{id}`,
issuing the ticket after JazzCash succeeds = `POST /air/orders` (paid from your Duffel test balance),
and cancellation = Duffel order cancellations. Without a key the app uses `services/local.py`, which fabricates
realistic offers (non-stop/1-stop, 3 fare brands, baggage, refund rules) so everything still works offline.
The header badge shows which source is active.

> The Duffel integration follows Duffel's v2 API docs but I could not run it without your key – if a call fails,
> the error from Duffel is shown in the UI; adjust `services/duffel.py` accordingly.

**Currency:** Duffel prices come in USD/GBP/etc. while JazzCash charges PKR, so totals are converted with
`FX_*_PKR` rates from `.env`. The price you approve is the PKR amount actually charged.

## Booking lifecycle

`search → select fare → passengers → review (re-verify price, approve) → booking created (pending_payment)
→ JazzCash → callback verified by secure hash → paid → ticket issued (PNR) → confirmation email → My trips`

* If the price changed between search and review, the booking is refused with a 409 and the UI shows the new total.
* If payment succeeds but ticketing fails, the booking stays `paid` with ticket status `failed` and a note.
* Email: SMTP if `SMTP_HOST` is set, otherwise saved to `backend/outbox/`.
* Ticket: printable HTML (Print → Save as PDF).

## JazzCash sandbox

Put Merchant ID / Password / Integrity Salt in `.env`. `services/jazzcash.py` builds the `pp_*` form with
`pp_SecureHash` (HMAC-SHA256 over `salt&sorted values`); the browser POSTs it to JazzCash; the return URL
`/api/payments/jazzcash/return` re-verifies the hash. Without credentials a mock checkout page is used
(same signing). Compare `build_checkout()` with your merchant doc if you get a hash mismatch.

## Limits
No email verification/password reset; JazzCash refunds aren't automated (cancelling a paid booking cancels the
ticket and records that the refund is manual); adults only; the demo provider uses naive local times; agent memory
is in-process (resets when the backend restarts). The OpenSky live-aircraft endpoint (`/api/flights/live`) is still
there but no longer shown in the UI.
