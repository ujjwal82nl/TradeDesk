# 🚀 TradeDesk — Multi-Broker Portfolio, Trading & Algorithmic Platform

**TradeDesk** is an enterprise-grade, unified multi-broker trading, portfolio management, and algorithmic execution platform. It aggregates equities, F&O derivatives, US stocks, and crypto portfolios across multiple brokers into a single command center with native Indian Rupee (₹) valuation, real-time indicator monitoring, and instant Telegram bot signal alerts.

---

## 🌟 Key Features

### 1. Multi-Broker Unified Portfolio & Execution
- **DhanHQ**: Holdings, open positions, orders, executed trades, funds, FIFO trade lot reconstruction, and automated TOTP 24-hour token refresh (`DHAN_CLIENT_ID` + `DHAN_PIN` + `DHAN_TOTP_SECRET`).
- **INDMoney (INDstocks)**: Indian equities and US stocks, trade lots, margin funds, and automated 24-hour token refresh via official API.
- **Zerodha Kite**: Holdings, positions, orders, trades, and headless automated login.
- **CoinDCX**: Crypto spot balances (with real-time USD/USDT to INR conversion), futures/derivatives, and options contracts with native & Black-Scholes Greeks (Delta, Gamma, Theta, Vega) and live INR valuation.
- **Universal Dividend & Statement Importer**: Import statements (.csv and .xlsx OpenXML) from Dhan, Zerodha, Groww, Upstox, INDMoney, Angel One, and CAMS/KFintech CAS.
- **Automated Broker Sync**: Automatically links Dhan, Zerodha, INDMoney, and CoinDCX accounts from `.env` to your admin user on startup.

### 2. URL & Navigation Hierarchy
- **Reporting & Analytics (`/dashboard/*`)**:
  - `/dashboard`: Consolidated net worth and asset/broker allocation.
  - `/dashboard/holdings`: Consolidated holdings with drill-down trade lots.
  - `/dashboard/positions`: Open F&O, crypto, and equity positions with P&L.
  - `/dashboard/options`: Options portfolio with strike breakdown and portfolio Greeks.
  - `/dashboard/strategies`: Multi-leg strategy builder and payoff analyzer.
  - `/dashboard/orders`: Multi-broker order book.
  - `/dashboard/trades`: Executed trade book and trade journal.
  - `/dashboard/margin`: Available cash, collateral, and margin utilization.
  - `/dashboard/dividends`: Dividend income calendar and monthly projections.
  - `/dashboard/analytics`: XIRR, benchmark comparisons, and performance metrics.
  - `/dashboard/algo`: Algo engine strategy runners and kill-switch.
  - `/dashboard/brokers`: Connected broker credentials and live token expiration status.
- **Trading & Execution (`/trading/*`)**:
  - `/trading/screener`: Market screener and scanner across NSE, BSE, F&O, and CoinDCX crypto pairs.
  - `/trading/signals`: Real-time indicator monitoring, signal flip alerts, and Telegram bot control.
  - `/trading/order-pad`: Unified multi-broker order placement terminal with margin estimates and safety guardrails.

### 3. Real-Time Indicator & Telegram Bot Alert Engine
- **Multi-Timeframe Indicator Engine**: Continuous calculation of technical indicators (e.g. **SuperTrend** with Period=16, Multiplier=1.5 on 90-minute resampled candles).
- **Automated Signal Flip Detection**: Detects bullish flips (🔴 RED ➔ 🟢 GREEN) and bearish flips (🟢 GREEN ➔ 🔴 RED) on completed candles.
- **Instant Telegram Delivery**: Formatted HTML alert cards sent directly to your phone with current spot price, indicator band value, and trigger timestamps.
- **Auto-Detect Chat ID**: Automatically detects your personal Telegram Chat ID via bot webhook/updates with one click.
- **Background Worker**: Standalone async worker running in the backend lifecycle every 60 seconds without requiring browser tabs to remain open.

---

## 🏛 System Architecture

```
                                  ┌──────────────────────────┐
                                  │      Client Browser      │
                                  └─────────────┬────────────┘
                                                │
                                                ▼
                                  ┌──────────────────────────┐
                                  │       Nginx Reverse      │
                                  │       Proxy (Port 80)    │
                                  └──────┬────────────┬──────┘
                                         │            │
                     /                   │            │   /api/
                     ┌───────────────────┘            └────────────────────┐
                     ▼                                                     ▼
        ┌─────────────────────────┐                           ┌─────────────────────────┐
        │   React Frontend (MUI)  │                           │   FastAPI Backend API   │
        │   Port 3000 (Internal)  │                           │   Port 8000 (Internal)  │
        └─────────────────────────┘                           └────────────┬────────────┘
                                                                           │
                               ┌────────────────────────┬──────────────────┴──────────────────┐
                               ▼                        ▼                                     ▼
                  ┌─────────────────────────┐ ┌───────────────────┐               ┌───────────────────────┐
                  │   PostgreSQL Database   │ │    Redis Cache    │               │  Background Indicator │
                  │   Port 5432 (Internal)  │ │    Port 6379      │               │  & Alert Monitor Loop │
                  └─────────────────────────┘ └───────────────────┘               └───────────┬───────────┘
                                                                                              │
                               ┌──────────────────────────────────────────────────────────────┴──────────┐
                               │                               Broker APIs & External Webhooks           │
                               ▼                               ▼                     ▼                   ▼
                         ┌───────────┐                   ┌───────────┐         ┌───────────┐       ┌───────────┐
                         │   Dhan    │                   │  Zerodha  │         │  CoinDCX  │       │ Telegram  │
                         │   REST    │                   │   Kite    │         │  Options  │       │  Bot API  │
                         └───────────┘                   └───────────┘         └───────────┘       └───────────┘
```

---

## 📁 Repository Structure

```
TradeDesk/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── router.py               # Main API router
│   │   │   └── endpoints/
│   │   │       ├── alerts.py           # Telegram bot & indicator alerts
│   │   │       ├── brokers.py          # Broker accounts & sync
│   │   │       ├── portfolio.py        # NAV rollup & allocations
│   │   │       ├── holdings.py         # Holdings & FIFO trade lots
│   │   │       ├── positions.py        # Positions & Option Greeks
│   │   │       ├── orders.py           # Order management
│   │   │       ├── trades.py           # Trades & journal
│   │   │       ├── margin.py           # Margin & fund utilization
│   │   │       ├── dividends.py        # Dividend calendar & CSV/XLSX import
│   │   │       ├── strategies.py       # Multi-leg options strategies
│   │   │       ├── analytics.py        # Performance & XIRR
│   │   │       └── algo.py             # Algo runs & execution
│   │   ├── brokers/
│   │   │   ├── base.py                 # Abstract broker interface
│   │   │   ├── aggregator.py           # Multi-broker rollup
│   │   │   └── adapters/
│   │   │       ├── dhan_adapter.py     # Dhan auto-TOTP & holdings/lots
│   │   │       ├── zerodha_adapter.py  # Zerodha Kite Connect
│   │   │       ├── indmoney_adapter.py # INDstocks REST API
│   │   │       └── coindcx_adapter.py  # Spot, Futures & Options + Greeks
│   │   ├── core/
│   │   │   ├── config.py               # Application settings
│   │   │   ├── security.py             # JWT token handling
│   │   │   └── dependencies.py         # FastAPI dependency injection
│   │   ├── models/                     # SQLAlchemy ORM models
│   │   │   ├── alert.py                # AlertRule & AlertNotification
│   │   │   ├── broker.py               # BrokerProvider & BrokerAccount
│   │   │   ├── holding.py              # Holding & HoldingLot
│   │   │   ├── position.py             # Position & Greeks
│   │   │   └── user.py                 # User authentication
│   │   ├── services/
│   │   │   ├── alert_service.py        # Candle resampling & SuperTrend
│   │   │   ├── telegram_service.py     # Telegram Bot API integration
│   │   │   └── broker_service.py       # Broker synchronization
│   │   └── main.py                     # App entry point & background worker
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/layout/
│   │   │   └── MainLayout.tsx          # Dual-section sidebar & topbar
│   │   ├── pages/
│   │   │   ├── Dashboard / Portfolio   # Portfolio overview
│   │   │   ├── Holdings / Positions    # Holdings, lots, positions, Greeks
│   │   │   ├── Trading / Screener      # Market screener
│   │   │   ├── Trading / Signals       # Indicator monitor & Telegram bot
│   │   │   └── Trading / OrderPad      # Multi-broker order execution
│   │   ├── api/                        # Axios HTTP client
│   │   └── store/                      # Redux state slices
│   ├── package.json
│   └── Dockerfile
│
├── nginx/
│   └── nginx.conf                      # Production reverse proxy config
├── docker-compose.yml                  # Multi-container orchestration
├── .env.example                        # Safe template for environment variables
└── README.md
```

---

## ⚙️ Configuration (`.env`)

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Key | Description | Example / Default |
| :--- | :--- | :--- |
| `POSTGRES_USER` | PostgreSQL database user | `trading` |
| `POSTGRES_PASSWORD` | PostgreSQL database password | `your_secure_password` |
| `POSTGRES_DB` | PostgreSQL database name | `trading_platform` |
| `SECRET_KEY` | JWT encryption secret key (min 32 chars) | `openssl rand -hex 32` |
| `DHAN_CLIENT_ID` | Dhan 10-digit Client ID | `1000000000` |
| `DHAN_PIN` | Dhan 6-digit numeric login PIN | `123456` |
| `DHAN_TOTP_SECRET` | Dhan Base32 Authenticator secret key | `JBSWY3DPEHPK3PXP` |
| `ZERODHA_USER_ID` | Zerodha Kite 6-character user ID | `AB1234` |
| `ZERODHA_PASSWORD` | Zerodha Kite account password | `your_kite_password` |
| `ZERODHA_TOTP_SECRET`| Zerodha Base32 Authenticator secret | `JBSWY3DPEHPK3PXP` |
| `INDMONEY_CLIENT_ID` | INDstocks Client ID / UCC | `IND123456` |
| `INDMONEY_API_KEY` | INDstocks TOTP Client ID | `your_totp_client_id` |
| `INDMONEY_MPIN` | INDstocks 4-digit MPIN | `1234` |
| `INDMONEY_TOTP_SECRET`| INDstocks Base32 Authenticator secret | `JBSWY3DPEHPK3PXP` |
| `COINDCX_API_KEY` | CoinDCX API Key | `your_coindcx_api_key` |
| `COINDCX_API_SECRET` | CoinDCX API Secret HMAC key | `your_coindcx_secret` |
| `COINDCX_AUTH_TOKEN` | CoinDCX Web Bearer token (for Options) | `Bearer eyJhbGci...` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token from @BotFather | `8960073576:AAFt_...` |
| `TELEGRAM_CHAT_ID` | Personal or group Telegram Chat ID | `5726199080` |

---

## 💻 Local Quickstart

Ensure [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) are installed.

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/TradeDesk.git
cd TradeDesk

# 2. Configure environment
cp .env.example .env
# Edit .env with your broker and Telegram credentials

# 3. Start all services
docker compose up -d --build

# 4. View service status
docker compose ps
```

- **Frontend App**: [http://localhost](http://localhost) (or [http://localhost:3000](http://localhost:3000))
- **Backend API Docs**: [http://localhost/api/docs](http://localhost/api/docs) (or [http://localhost:8000/api/docs](http://localhost:8000/api/docs))

---

## 🌐 Deploying to a VPS (Ubuntu / Debian)

Follow these steps to deploy TradeDesk to a remote VPS (DigitalOcean, Hetzner, AWS EC2, Linode, Contabo, etc.) and keep it running 24/7.

### Step 1: Connect & Prepare VPS

```bash
# SSH into your VPS
ssh root@your_vps_ip

# Update packages
apt update && apt upgrade -y

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
apt install -y docker-compose-plugin git curl ufw

# (Optional) Setup UFW Firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### Step 2: Clone Repository

```bash
cd /opt
git clone https://github.com/<your-username>/TradeDesk.git
cd TradeDesk
```

### Step 3: Setup Environment Variables

```bash
cp .env.example .env
nano .env
```
Paste your production database passwords, JWT secret, broker credentials, and Telegram tokens.

### Step 4: Launch Containers

```bash
docker compose up -d --build
```

Verify that all containers are healthy:
```bash
docker compose ps
```
You should see:
- `trading_db` (Healthy)
- `trading_redis` (Healthy)
- `trading_backend` (Up / Healthy)
- `trading_frontend` (Up)
- `trading_nginx` (Up / Port 80, 443)

### Step 5: (Recommended) Add SSL / HTTPS with Let's Encrypt

Install Certbot to secure your domain with free automated HTTPS:
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

### Step 6: User & Admin Management CLI

TradeDesk provides a dedicated administrative CLI tool inside the backend container to manage accounts securely without exposing public registration to the web.

```bash
# 1. Wipe demo accounts and create a fresh personal Admin user as ID 1
sudo docker exec trading_backend python scripts/manage_users.py reset \
  --email "your_email@example.com" \
  --password "YourStrongPassword123!" \
  --name "Your Name"

# 2. List all users and verify access privileges
sudo docker exec trading_backend python scripts/manage_users.py list

# 3. Add or update another user
sudo docker exec trading_backend python scripts/manage_users.py add \
  --email "trader@example.com" \
  --password "TraderPass123!" \
  --name "Trader" \
  --admin

# 4. Delete demo accounts (admin@trading.com, admin@trading.local)
sudo docker exec trading_backend python scripts/manage_users.py delete-defaults

# 5. Automatically link broker accounts from .env to active users
sudo docker exec trading_backend python scripts/manage_users.py sync-brokers

# 6. Test Dhan automated TOTP login and 24-hr token generation
sudo docker exec trading_backend python scripts/manage_users.py test-dhan
```

---

### Step 7: Multi-Server Reverse Proxy (e.g. CloudPanel / Nginx under `/opt/`)

If you host TradeDesk on a dedicated Docker server (e.g., `187.127.138.189`) and access it through an existing domain or panel on another server (e.g., `https://iamatwork.cloud/opt/*`), configure your upstream Vhost with high-priority prefix blocks (`^~`):

```nginx
# --- Redirect /opt to /opt/ if trailing slash is omitted ---
location = /opt {
    return 301 /opt/;
}

# --- TradeDesk Backend API (routes to Docker host) ---
location ^~ /opt/api/ {
    proxy_pass http://187.127.138.189:3080/opt/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
}

# --- TradeDesk Frontend & Dashboard Routes ---
location ^~ /opt/ {
    proxy_pass http://187.127.138.189:3080/opt/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# --- Static Assets (JS / CSS / Media) ---
location ^~ /static/ {
    proxy_pass http://187.127.138.189:3080/static/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# --- WebSockets ---
location /ws {
    proxy_pass http://187.127.138.189:3080/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

> **Note on `^~`:** CloudPanel contains regular expression blocks for static assets (`.js`, `.css`, etc.). The `^~` modifier guarantees that requests under `/opt/` and `/static/` bypass host regexes and proxy directly to TradeDesk.

---

### Step 8: Database Migrations (Greeks & Options)

If upgrading an existing database, ensure Black-Scholes Greeks columns are applied to the `positions` table:

```bash
sudo docker exec trading_db psql -U trading -d trading_platform -c "
ALTER TABLE positions ADD COLUMN IF NOT EXISTS delta NUMERIC(15, 6);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS gamma NUMERIC(15, 8);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS theta NUMERIC(15, 6);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS vega NUMERIC(15, 6);
"
```

---

### Step 9: Managing the VPS Application

```bash
# View live backend logs (including Telegram alert triggers)
docker compose logs -f backend

# Restart services after updating code or .env
docker compose down
docker compose up -d --build

# Check database backups
docker exec -t trading_db pg_dump -U trading trading_platform > backup_$(date +%Y%m%d).sql
```

---

## 🔒 Security Best Practices

- **Never commit `.env` or credentials**: The root `.gitignore` excludes `.env`, `backend/.env`, logs, and temporary caches.
- **Token Encryption**: Sensitive broker access tokens in PostgreSQL are encrypted using Fernet symmetric cryptography (`FERNET_KEY`).
- **TOTP Resiliency**: Dhan, INDMoney, and Zerodha authentication pipelines compute dynamic time-based OTPs, preventing expired session lockouts.
- **Telegram Safety**: Telegram alerts validate recipient IDs to prevent sending to unauthorized channels.

---

## 📜 License

This project is licensed under the MIT License — feel free to customize and extend for your trading requirements.
