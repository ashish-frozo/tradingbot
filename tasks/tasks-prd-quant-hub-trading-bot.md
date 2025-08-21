# Tasks for Quant Hub Trading Bot

Based on PRD: `prd-quant-hub-trading-bot.md`

## Relevant Files

### Backend Core
- `backend/app/__init__.py` - Application package initialization
- `backend/app/core/config.py` - Configuration management and environment variables
- `backend/app/core/logging.py` - Centralized logging configuration
- `backend/app/core/utils.py` - Common utility functions
- `backend/app/core/security.py` - Security utilities and token management
- `backend/main.py` - FastAPI application factory and Socket.IO setup
- `backend/requirements.txt` - Python dependencies including Dhan-Tradehull==3.*

### Database & Models
- `backend/app/db/database.py` - SQLModel database connection and session management
- `backend/app/db/models/trade.py` - Trade model with fills, P&L, and audit fields
- `backend/app/db/models/position.py` - Position model with Greeks and risk metrics
- `backend/app/db/models/strategy.py` - Strategy configuration and state model
- `backend/app/db/models/config.py` - System configuration and risk parameters model
- `backend/app/db/models/audit.py` - Audit log model for decision-hash and compliance
- `backend/app/db/crud/` - CRUD operations for all models

### Broker Integration
- `backend/app/broker/tradehull_client.py` - Async wrapper for Dhan-Tradehull API
- `backend/app/broker/enums.py` - Trading enums (transaction types, segments, etc.)
- `backend/app/broker/rate_limiter.py` - Rate limiting for 20 orders/sec, 20 mods/order
- `backend/app/broker/token_manager.py` - Automatic token refresh at 08:50 IST
- `backend/app/broker/exceptions.py` - Custom broker-specific exceptions

### Strategy Engine
- `backend/app/strategies/__init__.py` - Strategy module exports and initialization
- `backend/app/strategies/base.py` - Abstract Strategy base class with pluggable interface and comprehensive lifecycle management
- `backend/app/strategies/registry.py` - Strategy registry and dynamic loading system with hot-reload capabilities
- `backend/app/strategies/vol_oi/__init__.py` - Volume-OI strategy module initialization and exports
- `backend/app/strategies/vol_oi/models.py` - Comprehensive data models for signals, trade phases, and performance tracking
- `backend/app/strategies/vol_oi/config.py` - Strategy configuration with validation and trading parameters
- `backend/app/strategies/vol_oi/detector.py` - Volume spike detection (>3σ+5x), price jump detection (0.15%), and OI confirmation (1.5σ)
- `backend/app/strategies/vol_oi/trader.py` - Complete Volume-OI strategy implementation with probe/scale trading and risk management

### Risk & Order Management
- `backend/app/risk/manager.py` - Risk management with daily P&L caps and position limits
- `backend/app/risk/circuit_breaker.py` - Circuit breaker logic for VIX and market events
- `backend/app/risk/calculator.py` - Dynamic margin calculation and lot sizing
- `backend/app/risk/position_limits.py` - Position limits management (10 lots/signal, 50 lots total/strategy)
- `backend/app/orders/manager.py` - Order management system with slippage controls
- `backend/app/orders/executor.py` - Order execution with latency auditing (<150ms target)
- `backend/app/orders/requote.py` - Re-quote system (max 3 retries, ≤₹0.10 price chase)
- `backend/app/orders/kill_switch.py` - Emergency "Kill All" functionality with 2-second flatten target
- `backend/app/orders/tracking.py` - Order status tracking and fill notifications
- `backend/app/orders/models.py` - Order state and execution models
- `backend/app/audit/compliance.py` - Decision-hash and feature snapshot storage for audit compliance

### Market Data
- `backend/app/data/__init__.py` - Data module exports and initialization
- `backend/app/data/feed.py` - Live option chain data feed (3s intervals) with circuit breaker
- `backend/app/data/ltp_feed.py` - Real-time LTP data feed for futures (1s intervals) with health monitoring
- `backend/app/data/storage.py` - Comprehensive market data storage system with retention policies (7d raw, 2y metrics, 90d bars)
- `backend/app/db/models/market_data.py` - Database models for multi-tier market data storage
- `backend/app/worker/data_retention.py` - Automated data retention and cleanup worker (6-hour cycles)
- `backend/app/data/processor.py` - Statistical baseline processor for volume and OI anomaly detection with rolling statistics
- `backend/app/data/validator.py` - Comprehensive data validation and error handling with circuit breakers, quality scoring, and health monitoring
- Note: Greeks (delta, gamma, theta, vega) are provided directly by Tradehull API in option chain responses

### WebSocket & Real-time
- `backend/app/websocket/live_feed.py` - Socket.IO handlers for real-time updates
- `backend/app/websocket/events.py` - WebSocket event definitions and handlers
- `backend/app/websocket/manager.py` - WebSocket connection management

### API Routes
- `backend/app/api/deps.py` - API dependencies and authentication
- `backend/app/api/routes_dashboard.py` - Dashboard data endpoints
- `backend/app/api/routes_positions.py` - Position and portfolio endpoints
- `backend/app/api/routes_admin.py` - Admin endpoints for strategy control
- `backend/app/api/routes_risk.py` - Risk monitoring and control endpoints
- `backend/app/api/routes_health.py` - Health check and system status endpoints

### Background Tasks
- `backend/app/worker/tasks.py` - Celery tasks for data processing and maintenance
- `backend/app/worker/scheduler.py` - Task scheduling and cron jobs
- `backend/app/worker/retrain.py` - Nightly model retraining (Isolation Forest)

### Frontend Core
- `frontend/src/main.tsx` - React application entry point
- `frontend/src/App.tsx` - Main application component with routing
- `frontend/src/lib/socket.ts` - Socket.IO client configuration
- `frontend/src/lib/api.ts` - API client with TypeScript types
- `frontend/src/lib/utils.ts` - Utility functions and helpers
- `frontend/src/hooks/useRealtime.ts` - Custom hook for real-time data
- `frontend/src/stores/useAppStore.ts` - Zustand store for application state

### Frontend Components
- `frontend/src/components/Dashboard.tsx` - Main dashboard layout with integrated equity curve
- `frontend/src/components/PositionsGrid.tsx` - Positions grid with Greeks display
- `frontend/src/components/EquityCurve.tsx` - Real-time equity curve chart with P&L visualization, drawdown tracking, and performance metrics
- `frontend/src/components/RiskPanel.tsx` - Risk metrics and margin usage display
- `frontend/src/components/LatencyChart.tsx` - Latency histogram visualization
- `frontend/src/components/AlphaDecayPlot.tsx` - Alpha decay visualization
- `frontend/src/components/KillButton.tsx` - Emergency flatten-all button
- `frontend/src/components/StrategyCard.tsx` - Strategy performance scorecard
- `frontend/src/components/AlertsPanel.tsx` - Alerts and notifications display

### Infrastructure
- `docker-compose.yml` - Local development environment setup
- `backend/Dockerfile` - Backend container configuration
- `frontend/Dockerfile` - Frontend container configuration
- `.github/workflows/ci.yml` - GitHub Actions CI/CD pipeline
- `backend/alembic/` - Database migration scripts
- `deployment/railway.json` - Railway deployment configuration
- `monitoring/prometheus.yml` - Prometheus monitoring configuration
- `monitoring/grafana-dashboard.json` - Grafana dashboard configuration

### Testing
- `backend/tests/test_tradehull_client.py` - Broker integration tests
- `backend/tests/test_vol_oi_strategy.py` - Strategy implementation tests
- `backend/tests/test_risk_manager.py` - Risk management tests
- `backend/tests/test_order_manager.py` - Order management tests
- `frontend/src/components/__tests__/` - Frontend component tests

### Notes

- All backend tests use pytest-asyncio for async testing and respx for mocking HTTP calls
- Frontend tests use React Testing Library and Jest
- Use `pytest backend/tests/` to run all backend tests
- Use `npm test` in frontend directory to run frontend tests
- Database migrations handled via Alembic
- Redis used for caching and real-time data buffering
- Socket.IO for real-time communication between backend and frontend

## Tasks

- [ ] 1.0 Backend Infrastructure & Core Setup
  - [x] 1.1 Initialize FastAPI project structure with Python 3.12
  - [ ] 1.2 Configure SQLModel with PostgreSQL database connection
  - [ ] 1.3 Set up Redis connection for caching and real-time data
  - [ ] 1.4 Configure centralized logging with structured JSON output
  - [ ] 1.5 Implement configuration management with environment variables
  - [ ] 1.6 Set up Celery for background tasks and scheduling
  - [ ] 1.7 Create database models for trades, positions, strategies, and audit logs
  - [ ] 1.8 Implement Alembic for database migrations
  - [ ] 1.9 Set up pytest framework with async testing capabilities

- [ ] 2.0 Dhan-Tradehull Integration & Market Data Pipeline
  - [ ] 2.1 Create async wrapper for Dhan-Tradehull API client
  - [ ] 2.2 Implement rate limiting (20 orders/sec, 20 mods/order)
  - [ ] 2.3 Set up automatic token refresh at 08:50 IST daily
  - [x] 2.4 Build live option chain data feed with 3-second intervals
  - [x] 2.5 Implement real-time LTP data capture for underlying futures
  - [x] 2.6 Create data storage system (7d raw WS, 2y derived metrics, 90d minute bars)
  - [x] 2.7 Build Greeks calculation engine (delta, gamma, theta, vega) ⚡ SKIPPED: Tradehull API already provides Greeks data
  - [x] 2.8 Implement statistical baseline calculations for volume and OI detection
  - [x] 2.9 Create data validation and error handling for market data feeds

- [x] 3.0 Strategy Engine & Volume-OI Confirm Implementation
  - [x] 3.1 Design and implement abstract Strategy base class
      - [x] 3.2 Create strategy registry and dynamic loading system
    - [x] 3.3 Implement volume spike detection (>3σ AND >5× 1-min average)
    - [x] 3.4 Build mid-price jump detection (≥0.15% within 2 seconds)
    - [x] 3.5 Create OI change confirmation logic (>1.5σ within 240 seconds)
    - [x] 3.6 Implement probe trade execution (2 lots with delta hedge)
    - [x] 3.7 Build position scaling logic (add 8 lots on confirmation)
    - [x] 3.8 Create exit conditions (+40% profit, -25% SL, 10-min timeout)
    - [x] 3.9 Implement event filters for RBI, Budget, US-CPI, and exchange halt days
    - [x] 3.10 Add partial fill handling (<80% filled after 1s → cancel remainder)

- [x] 4.0 Risk Management & Order Management System
  - [x] 4.1 Implement dynamic lot sizing based on 40% margin utilization
  - [x] 4.2 Create daily P&L stop loss system (₹25k hard cap with auto-flatten)
  - [x] 4.3 Build circuit breaker system for India VIX >+3σ and market events
  - [x] 4.4 Implement slippage filter (reject if >₹0.30/leg or spread >0.3%)
  - [x] 4.5 Create order execution with latency auditing (<150ms target)
  - [x] 4.6 Build re-quote system (max 3 retries, ≤₹0.10 price chase)
  - [x] 4.7 Implement position limits (10 lots/signal, 50 lots total/strategy)
  - [x] 4.8 Create decision-hash and feature snapshot storage for audit compliance
  - [x] 4.9 Build manual "Kill All" functionality with 2-second flatten target
  - [x] 4.10 Implement order status tracking and fill notifications

- [x] 5.0 Frontend Dashboard & Real-time Monitoring
  - [x] 5.1 Initialize React 18 project with TypeScript and Vite
  - [x] 5.2 Set up Tailwind CSS and shadcn/ui component library
  - [x] 5.3 Configure Socket.IO client for real-time updates
  - [x] 5.4 Implement Zustand store for application state management
  - [x] 5.5 Create main dashboard layout with navigation
  - [x] 5.6 Build real-time P&L and equity curve visualization
  - [x] 5.7 Implement positions grid with Greeks, SL/PT, and TTL countdown
  - [x] 5.8 Create strategy performance scorecards (win-rate, R:R, drawdown)
  - [x] 5.9 Build risk panel with margin usage and daily loss tracking
  - [x] 5.10 Implement latency histogram and slippage tracking charts
  - [x] 5.11 Create alpha-decay plot (P&L vs position age)
  - [x] 5.12 Build prominent "Kill All" button with 2-second confirmation
  - [x] 5.13 Implement admin panel for strategy toggle controls
  - [x] 5.14 Create alerts panel with Slack/Telegram integration
  - [x] 5.15 Add framer-motion animations and responsive design

- [ ] 6.0 Deployment, Scaling & Production Infrastructure
  - [ ] 6.1 Create Docker Compose setup for local development
  - [ ] 6.2 Build production Dockerfiles for backend and frontend
  - [ ] 6.3 Configure Railway deployment for Singapore region
  - [ ] 6.4 Set up Mumbai VPS fallback for <10ms RTT
  - [ ] 6.5 Implement health checks and auto-restart mechanisms
  - [ ] 6.6 Configure auto-scaling triggers (CPU >70%, WS lag >200ms)
  - [ ] 6.7 Set up Prometheus monitoring and metrics collection
  - [ ] 6.8 Create Grafana dashboards for system monitoring
  - [ ] 6.9 Implement PagerDuty alerts for system failures
  - [ ] 6.10 Configure hot-standby Postgres and Redis with AOF
  - [ ] 6.11 Set up GitHub Actions CI/CD pipeline with automated testing
  - [ ] 6.12 Create disaster recovery procedures (RTO ≤2 min target)
  - [ ] 6.13 Implement daily S3 backups and point-in-time recovery 