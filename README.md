# Multi-Agent RevOps Orchestrator

**A complete, production-grade AI system that automatically watches the market, analyses your revenue data, and sends you a professional weekly intelligence briefing on WhatsApp + Email — all powered by four AI agents working together.**

It uses LangGraph to orchestrate real multi-agent workflows with conditional logic, observability, and production delivery.

---

## Can a Complete Beginner Use This?

**Yes.**

This README is written specifically for people who are learning. Every single step is explained in plain language. You do **not** need to be an expert in AI, Python, or databases to get this running.

There are two paths:

- **Path A (Easiest – Recommended for Beginners)**: Use Docker. You will copy-paste commands. The whole system runs in containers.
- **Path B (Manual)**: Install everything on your laptop directly (for people who already know some Python).

We strongly recommend **Path A** if you are new.

---

## What Does This System Actually Do?

Every week (or whenever you trigger it), four specialised AI agents work together:

1. **Signal Scraper Agent** → Goes on the internet and finds news about your competitors (pricing changes, new dealers, big orders, etc.).
2. **Analyst Agent** → Looks at your internal sales numbers (stored in a database) and compares them with the competitor news. It finds problems and opportunities.
3. **Writer Agent** → Writes a clean, professional 1-page report in proper business English.
4. **Router Agent** → Sends the report to you on **WhatsApp** (short version) and **Email** (full beautiful version).

All of this happens automatically.

---

## Prerequisites (What You Must Install First)

You need these four things before starting. Install them in order.

### 1. Git (for downloading the code)

- **Mac**: Open Terminal and run: `git --version`. If it says "command not found", install Xcode Command Line Tools: `xcode-select --install`
- **Windows**: Download from https://git-scm.com/download/win
- **Linux**: `sudo apt install git`

After installing, open a new terminal and type:
```bash
git --version
```
You should see something like `git version 2.40.0`

### 2. Docker Desktop (Strongly Recommended for Beginners)

This is the magic tool that lets you run the entire system with almost zero configuration.

**Download here**:
- Mac (Apple Silicon M1/M2/M3/M4): https://docs.docker.com/desktop/install/mac-install/
- Mac (Intel): Same link above
- Windows: https://docs.docker.com/desktop/install/windows-install/
- Linux: https://docs.docker.com/desktop/install/linux-install/

**After installing Docker Desktop**:
1. Open Docker Desktop application
2. Wait until it says "Docker Desktop is running" (green light)
3. Open Terminal and test:
   ```bash
   docker --version
   ```
   You should see `Docker version 26.x.x`

**Important**: Keep Docker Desktop running in the background while you work.

### 3. (Optional but Recommended) A Code Editor

- Download **VS Code**: https://code.visualstudio.com/
- After installing, you can open the project folder easily.

### 4. Anthropic API Key (Required – This is the Brain)

This project uses Claude (made by Anthropic) as the intelligence for all four agents.

**Step-by-step to get your free API key**:

1. Go to https://console.anthropic.com/
2. Click **"Sign up"** (use your Google account or email)
3. Verify your email if asked
4. After logging in, you will be taken to the dashboard
5. On the left sidebar, click **"API keys"**
6. Click the big **"Create Key"** button (top right)
7. Give it any name, for example: `revops-orchestrator-local`
8. Click **Create**
9. **Copy the key immediately** (it starts with `sk-ant-...`). You will only see it once.
10. Paste it somewhere safe (we will put it in the `.env` file later)

> **Note**: You will need to add a small amount of credit ($5–10) to your Anthropic account to actually run the agents. The first few runs will cost very little (usually under $0.50).

---

## Installation – Path A: The Easy Way (Using Docker)

This is the recommended path for most people.

### Step 1: Download the Project

Open your Terminal and run these commands one by one:

```bash
# Go to your home folder
cd ~

# Download the entire project from GitHub
git clone https://github.com/YOUR_USERNAME/multi-agent-revops-orchestrator.git

# Enter the project folder
cd multi-agent-revops-orchestrator
```

> Replace `YOUR_USERNAME` with your actual GitHub username.

### Step 2: Create Your Personal Settings File

```bash
# Copy the example file
cp .env.example .env
```

Now open the `.env` file in your editor (or use this command on Mac):

```bash
# On Mac
open .env

# On Windows (in VS Code)
code .env
```

You will see many lines. You **only need to change these two** for your first run:

1. Find this line:
   ```
   ANTHROPIC_API_KEY=sk-ant-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```
   Replace the `sk-ant-...` part with the real key you copied earlier.

2. (Optional) If you want the system to send messages to you, also fill WhatsApp and Email sections. For now, you can leave them as they are.

Save the file and close it.

### Step 3: Start Everything with One Command

Make sure Docker Desktop is running.

In the same terminal, run:

```bash
docker compose up --build
```

This single command will:
- Download PostgreSQL (database)
- Download Redis (caching)
- Build the AI application
- Start everything
- Automatically create the demo data (10 dealers + 6 months of sales)

**First time will take 5–12 minutes.** You will see lots of text. This is normal.

When you see this line, the system is ready:
```
INFO:     Application startup complete.
```

Keep this terminal window open.

### Step 4: Trigger Your First Weekly Briefing

Open a **new** terminal window (keep the first one running).

Run this command:

```bash
curl -X POST http://localhost:8000/run
```

You should get back something like:
```json
{"run_id": "550e8400-e29b-41d4-a716-446655440000", "status": "accepted", "message": "..."}
```

This means the four AI agents have started working in the background.

### Step 5: Watch the Magic Happen

Go back to the first terminal window (where `docker compose` is running).

You will see logs like:
```
[signal_scraper_node] Starting...
[analyst_node] Starting...
[writer_node] Generating briefing...
[router_node] Delivering briefing...
```

After 60–180 seconds, you will see the full markdown report printed in the logs (or errors if something is missing).

### Step 6: Check What Happened

In any terminal, run:

```bash
curl http://localhost:8000/status/latest
```

This will show you the complete audit trail of all four agents, how long each one took, and whether WhatsApp/Email was sent.

---

## Installation – Path B: Manual (Without Docker)

Only do this if you are comfortable with Python and already have PostgreSQL + Redis installed.

```bash
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# or .venv\Scripts\activate        # Windows

pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

python -m src.database.seed_data
uvicorn src.api.main:app --reload
```

Then use the same `curl -X POST http://localhost:8000/run` command.

---

## Getting WhatsApp + Email Working (Optional but Impressive)

For a real portfolio demo, you should make the delivery channels work.

### WhatsApp (takes ~15 minutes)

1. Go to https://developers.facebook.com/
2. Create a new app → Business → WhatsApp
3. Get a **Test Phone Number** (free)
4. Add your personal number as a test recipient
5. Copy the **Access Token** and **Phone Number ID**
6. Paste them into `.env`:
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WHATSAPP_RECIPIENT_PHONE=+91xxxxxxxxxx` (your number in international format)

### Email (SendGrid – Free tier available)

1. Create account at https://sendgrid.com/
2. Go to Settings → API Keys → Create
3. Copy the key
4. In `.env`:
   - `SMTP_PASSWORD=SG.xxxxxxxxxx` (the key)
   - `SMTP_TO_EMAILS=yourname@gmail.com`

After changing `.env`, restart the containers:
```bash
docker compose down
docker compose up
```

---

## What Should Happen on a Successful Run?

You will get:

1. A short, professional message on WhatsApp with the top 4–5 insights
2. A beautiful email in your inbox with the full 5-section report (Executive Summary, Market Signals, Internal Performance, Anomalies & Risks, Recommended Actions)
3. A complete audit trail at `/status/latest` showing exactly how long each agent took and what it did

This is extremely strong interview material because it proves you can build **real, observable, multi-channel autonomous AI systems**.

---

## Troubleshooting (Common Problems)

**"docker compose up" fails with "port 5432 already in use"**
→ You already have PostgreSQL running on your laptop. Stop it or change the port in `docker-compose.yml`.

**"ANTHROPIC_API_KEY not found"**
→ You forgot to edit the `.env` file or the key has extra spaces. Delete the line and paste again carefully.

**Playwright errors**
→ Run `playwright install chromium` again.

**No output / agents do nothing**
→ Check that you have credit in your Anthropic account. Go to https://console.anthropic.com/settings/billing

**"Module not found" errors (manual install)**
→ Make sure you activated the virtual environment (`source .venv/bin/activate`)

---

## Project Structure (Simplified)

```
multi-agent-revops-orchestrator/
├── src/
│   ├── agents/          ← The 4 AI agents (scraper, analyst, writer, router)
│   ├── graph/           ← The LangGraph StateGraph + conditional logic
│   ├── tools/           ← Reusable tools (web search, safe database queries, WhatsApp, email)
│   ├── api/             ← FastAPI endpoints (/run and /status)
│   ├── scheduler/       ← APScheduler weekly cron
│   └── database/        ← PostgreSQL models + realistic demo data
├── tests/               ← Unit tests
├── docker-compose.yml   ← The magic "one command" file
└── README.md            ← This file
```

---

## After You Get It Running – Next Steps

1. Take screenshots of:
   - The terminal logs during a run
   - The WhatsApp message you received
   - The email in your inbox
   - The `/status/latest` JSON

---

## License

MIT License – feel free to use this project.

---
