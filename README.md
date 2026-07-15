# DS Office — Client Status Tracker

A simple web app for a Divisional Secretariat front office:
- Front desk enters a client's details, purpose, and which sections they need.
- Each section officer (Land / Planning / Account / Administration / Registration / Field) opens
  their own queue on any phone/PC browser and marks a client's step **In Progress** → **Done**.
- A public screen in the waiting area shows live tokens and progress bars.
- A staff dashboard shows full client details for internal monitoring.

No app installation needed — everything runs in a normal web browser.

## Pages

| Page | URL | Who uses it |
|---|---|---|
| Home | `/` | Menu linking to all screens |
| Front Desk Entry | `/entry` | Reception officer registers a new client |
| Section Officer | `/section` | Officer picks their section, updates client progress |
| Public Display | `/display` | Big screen / TV in waiting area (auto-refreshes) |
| Staff Dashboard | `/staff` | Full internal view, filter by section, see completed |

Data updates every 5–8 seconds automatically (no page reload needed).

## 1. Run it locally (to test before going live)

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in a browser. On the same WiFi, other devices can
reach it at `http://<your-computer's-LAN-IP>:8000`.

## 2. Put it on the internet — fully free

Since you need it reachable over the internet (not just office WiFi), and want to stay
on free tiers, use **two free services together**:

- **Render.com (free web service)** — runs the app itself
- **Neon.tech (free Postgres database)** — stores the client data permanently

Why two services? Render's free tier wipes its own disk on every restart/redeploy — so
if the data lived only there, it could vanish. Neon's free database is separate and
persistent, so your data survives even when Render restarts.

### Step 1 — Create the free database (Neon)
1. Go to neon.tech → sign up free → **Create a project**.
2. Once created, copy the **connection string** shown (starts with `postgresql://...`).

### Step 2 — Deploy the app (Render)
1. Push this folder to a new GitHub repository.
2. On render.com → **New → Web Service** → connect that repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment**, add a variable:
   - Key: `DATABASE_URL`
   - Value: the Neon connection string you copied
6. Deploy. Render gives you a public link like `https://ds-office.onrender.com`.

That's it — the app automatically detects `DATABASE_URL` and uses Neon's Postgres
instead of a local file, so client data is never lost even if Render restarts or you
redeploy an update.

**One thing to know about free tiers:** both Render's free web service and Neon's free
database "sleep" after a period of no use, and take 10-30 seconds to wake up on the
next visit. Fine for a front office — the very first click of the day might be a bit
slow, then it's normal speed. If that becomes annoying, a paid Render tier (~$7/month)
keeps the app always-on; Neon's free database usually doesn't need upgrading for an
office this size.

### Option — your own server instead
If you'd rather not depend on third-party free tiers for a government system, the same
app can run on a local office server or cheap VPS with the built-in SQLite file — no
Neon needed, since your own server's disk won't get wiped. Ask me if you'd like the
steps for that instead.

## 3. Admin login

The Admin Dashboard (`/admin`) now requires a login — anyone else can still use
Front Desk, Section Officer, Public Display, and Feedback without logging in.

**Default local test credentials** (only for running on your own computer):
- Username: `admin`
- Password: `changeme123`

**Before deploying for real**, set these as environment variables (on Render, under
your service's **Environment** tab, same place as `DATABASE_URL`):

| Variable | Purpose |
|---|---|
| `ADMIN_USERNAME` | Your chosen admin username |
| `ADMIN_PASSWORD` | Your chosen admin password — pick something strong |
| `SESSION_SECRET` | A long random string (e.g. generate one at random.org) — keeps login sessions secure |

If you don't set these, the app falls back to the default credentials above, which
is **not safe** for a real deployment — anyone who reads the code could log in.

**Note on scope:** this protects the `/admin` page and the feedback data behind it.
The `/api/clients` data (used by the public display and section officer pages) is
intentionally still open, since those screens need to work without anyone logging in.
If you'd like stronger protection — e.g. separate logins per section officer — that
can be added next.

## 4. Feedback data storage

Client feedback submitted through the `/feedback` form is stored in the same
database as client records (Neon Postgres in production, or the local SQLite file
when testing on your computer) — no separate setup needed.

## 5. Still open — before real use
- **No login/password yet** — anyone with the link could enter clients or mark sections
  done. Worth adding a simple password per section before going live.


## 4. Things you may want next
- Simple login per section officer (so Land officer can't accidentally mark Registration done)
- SMS/WhatsApp token notification to the client's phone
- Daily/monthly report export (e.g. how many clients per section, average wait time)
- Sinhala/Tamil language toggle on the public display and entry form

Just ask — these can be added incrementally without rebuilding what's here.
