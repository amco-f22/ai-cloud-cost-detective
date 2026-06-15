# 🕵️ AI Cloud Cost Detective

An AI-powered preventative tool that automatically investigates your cloud infrastructure, identifies misconfigurations and over-provisioned resources, and instantly provides actionable commands to significantly reduce your cloud bill.

## 📖 The Problem Statement

Organizations today rely heavily on cloud platforms (AWS, Azure, GCP). However, when junior DevOps engineers or developers misconfigure or over-provision resources, companies expect a $20,000 monthly bill but receive a $50,000 one. 

Usually, companies treat cloud optimization as an **afterthought**. At the end of the quarter, they generate a "Cloud Visibility Report" to figure out what went wrong. 

**AI Cloud Cost Detective acts as a prevention mechanism.** Instead of waiting for the bill, this tool proactively scans your active resources, compares their configurations against cloud best practices, and immediately flags areas where you can save money—giving you the exact CLI commands needed to fix them.

## 🌟 Why build your own AI Cost Tool?

There are open-source projects like *Carpenter*, but they are restricted to specific services (like Kubernetes). Building this custom AI tool means **unlimited flexibility**. It works with EC2, S3 buckets, databases, volumes, and networks. If your organization adopts a new service tomorrow, you can simply update the AI prompt or add a detector function, and the tool is updated in minutes without waiting for open-source support tickets.

---

## 🚀 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React (Vite + TypeScript + Tailwind) |
| **Backend** | Python (FastAPI) |
| **Auth** | Custom JWT Auth (bcrypt + PyJWT) |
| **Cloud Data** | AWS CLI (subprocess integration) |
| **Cloud Target** | Amazon Web Services (AWS) |
| **AI Analysis** | Google Gemini (Primary) / Groq Llama 3 (Secondary) |
| **Database** | PostgreSQL (Docker) |
| **Live Updates** | FastAPI WebSockets |

---

## 🏗️ Architecture & Request Flow

```
                               ┌──────────────┐
                               │     USER     │
                               └──────┬───────┘
                                      │
                                      ▼
                            ┌───────────────────┐
                            │  REACT FRONTEND   │
                            │  (Vite + TS)      │
                            └────────┬──────────┘
                                     :
                                     : Login / Run Scan
                                     ▼
                            ┌───────────────────┐
                            │  PYTHON BACKEND   │
                            │    (FastAPI)      │
                            │                   │
                            │  · JWT Auth       │
                            │  · Thread Pool    │
                            └───┬───────┬───┬───┘
                                :       :   :
                 ┌──────────────┘       :   └──────────────┐
                 :                      :                  :
                 ▼                      ▼                  ▼
          ┌─────────────┐     ┌──────────────┐    ┌──────────────┐
          │   AWS CLI   │     │   FASTAPI    │    │   GEMINI /   │
          │             │     │  WEBSOCKET   │    │    GROQ      │
          │ aws ec2 ... │     │  (Progress)  │    │              │
          │ aws s3 ...  │     └──────┬───────┘    │ Cost Analysis│
          └──────┬──────┘            :            └──────┬───────┘
                 :                   : Live logs         :
                 ▼                   ▼                   :
          ┌─────────────┐   ┌───────────────┐            :
          │    AWS      │   │    REACT      │            :
          │  (us-east-1)│   │  (Live Timer &│            :
          │             │   │   Progress)   │            :
          └─────────────┘   └───────────────┘            :
                                                         ▼
                                                  ┌──────────────┐
                                                  │  POSTGRESQL  │
                                                  │   (Docker)   │
                                                  │              │
                                                  │ · users      │
                                                  │ · analyses   │
                                                  └──────┬───────┘
                                                         :
                                                         : Stored results
                                                         ▼
                                                  ┌───────────────┐
                                                  │    REACT      │
                                                  │ (Final Report │
                                                  │  + Suggestions│
                                                  │  + Fixes)     │
                                                  └───────────────┘
```

1. User authenticates via custom JWT stored in PostgreSQL.
2. User triggers an analysis via the React Dashboard.
3. FastAPI backend executes multi-threaded AWS CLI commands to fetch infrastructure data.
4. Real-time progress updates and a live timer are streamed via WebSockets.
5. The raw AWS resource JSON and pre-computed detection flags are sent to the AI Model.
6. AI returns a verified, human-readable summary with fix commands.
7. Results are cached in PostgreSQL to save API tokens and enable history viewing.

---

## 🔍 What Resources It Scans & Detects

The application runs a 10-point inspection on your AWS environment before passing the data to the AI:

1. **Oversized EC2 Instances:** Flags instances running with large resource profiles (e.g., `t3.2xlarge`) that could be downsized.
2. **Unattached / Orphaned EBS Volumes:** Finds expensive `gp3` or `io1` disks that are not attached to any virtual machine but are still billing you.
3. **Old EBS Snapshots:** Detects snapshots older than 30-90 days that are unnecessarily hoarding storage space.
4. **S3 Buckets w/o Lifecycle Policies:** Identifies S3 buckets lacking transition policies to cheaper storage (like Glacier).
5. **Unused Elastic IPs:** Flags static IPs that are unattached but still costing an hourly rate.
6. **Permissive Security Groups:** Security risk + potential DDoS cost risk (e.g., ports open to `0.0.0.0/0`).
7. **Idle RDS Databases:** Detects databases without recent connections.
8. **Load Balancers without Targets:** Finds ELBs that are running and billing but have no healthy backend instances.
9. **NAT Gateways:** Flags expensive NAT gateways, suggesting cheaper alternatives where applicable.
10. **Oversized EBS Volumes:** Detects disks that are massively provisioned but barely utilized.

---

## 🧠 AI Models & Reasoning

Cloud architectures are incredibly dense. Analyzing raw JSON dumps from the AWS CLI requires LLMs with massive context windows and strong reasoning capabilities. The choice of model heavily depends on your budget, environment size, and required speed.

1. **OpenAI (GPT-4o) & Anthropic (Claude 3.5 Sonnet)** — *Ideal / Primary Choices*
   - **Why use them:** For enterprise-grade production environments, these are the industry leaders in reasoning and logic. They are highly reliable at parsing complex JSON structures and generating accurate, hallucination-free AWS commands.
   - **Caveat:** They are premium models and can be expensive when analyzing massive AWS accounts with thousands of resources.

2. **Google Gemini (gemini-3.5-flash)** — *Used in this project for cost savings*
   - **Why we used it:** Cloud environments can have thousands of resources. Gemini's massive context window (up to 1M tokens) and generous output limits make it perfect for ingesting entire AWS accounts without data truncation. Most importantly, it is highly cost-effective (often free tier) while maintaining solid JSON-parsing capabilities.

3. **Groq (llama-3.3-70b-versatile)** — *Used for lightning-fast sandbox analysis*
   - **Why we used it:** Groq's LPU inference engine is insanely fast (~300+ tokens/sec), and Llama 3 70B is an open-source powerhouse.
   - **Caveat:** Groq's free tier has strict TPM (Tokens Per Minute) limits. It is best used for smaller accounts or single-region sandbox scans.

**Which should you use?** It depends! If you are building this for an enterprise and want the highest fidelity, integrate **OpenAI or Claude**. If you want a massive context window on a budget, use **Gemini**. If you want lightning-fast analysis on a small sandbox account, use **Groq**. You can switch providers instantly in the `.env` file.

---

## ✨ Standout Features

- **Multi-threaded Scanning:** Fetches data across AWS services concurrently without blocking the server event loop.
- **Live WebSocket Progress:** Keeps the user engaged by streaming fine-grained logs (e.g., "Scanning EC2 instances...") to the frontend in real-time.
- **Analysis Timer:** Live UI timer tracking the duration of the scan and AI inference.
- **History Tracking:** Saves investigations to PostgreSQL so team members don't waste AI tokens re-running scans.

---

## ⚙️ Prerequisites

- AWS CLI installed and configured (`aws configure`)
- Docker (for PostgreSQL database)
- Google Gemini API Key or Groq API Key
- Python 3.10+
- Node.js 18+

## 🚀 How to Run

### 1. Database
```bash
# Start the PostgreSQL container
docker run -d --name cost-detective-db -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15
```

### 2. Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Copy env and add your API keys
cp .env.example .env

# Run the server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to start preventing those massive cloud bills!
