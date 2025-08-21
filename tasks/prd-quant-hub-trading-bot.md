Product Requirements Document (PRD) — Quant Hub Trading Bot

Revision 2 · Trader-Vetted · Markdown

⸻

1. Introduction / Overview

Quant Hub is a scalable, low-latency options-trading system that automates pattern-driven strategies while enforcing strict risk-controls and providing millisecond-level visibility.
Initial release targets NIFTY weekly options with the “Volume + Delayed-OI Confirm” edge; the plug-in architecture lets future assets/strategies slot in without downtime.

Primary goal: capture alpha that survives real-world slippage, margin swings, and exchange outages—turning discretionary trades into systematic, auditable workflows.

⸻

2. Goals

#	Objective	Target
1	Automation	Sub-150 ms round-trip from signal → order ACK
2	Emotion Control	All entries/exits/risk caps hard-coded; manual override = flatten only
3	Scalability	50-100 micro-trades / day; auto-scale when CPU > 70 % or WS lag > 200 ms
4	Dynamic Risk	Lot & hedge sizing float with live margin (≤ 40 % utilisation)
5	Performance	Win-rate ≥ 65 % or CAGR ≥ 15 % net; Sharpe ≥ 1.2 preferred
6	Reliability	99.9 % uptime (09:00–15:45 IST); DR RTO ≤ 2 min, RPO = current session


⸻

3. User Stories (key excerpts)
	•	Trader – “Start the bot at 09:15, see fills/P & L/live risk; override only to kill-all.”
	•	Admin – “Toggle any strategy on/off mid-session without restart.”
	•	Risk Manager – “Enforce ₹25 k daily loss cap; auto-flatten and lock entries when hit.”

⸻

4. Functional Requirements

4.1 Core Trading Engine
	•	Pluggable strategies via abstract Strategy base.
	•	Slippage filter – reject fills if slippage per leg > ₹0.30 or spread > 0.3 %.
	•	Latency audit – stamp outbound time; store ACK RTT for every order.

4.2 “Volume + Delayed-OI Confirm” Strategy

Phase	Rule
Trigger	After 09:30 IST warm-up: volume > 3 σ and > 5× 1-min avg and mid-price jump ≥ 0.15 % in ≤ 2 s
Probe	Buy 2 lots option + delta-hedge via futures or deep-ITM option (≈ 30 % SPAN cut)
Confirm	OI Δ > 1.5 σ within ≤ 240 s (worst-case exchange lag)
Scale	Add 8 lots (total 10) if confirm hits & slippage filter passes
Partial-fill	< 80 % filled after 1 s → cancel remainder & scratch
Exit	+40 % premium, −25 % SL, or 10-min timeout
Event filter	Auto-disable on RBI, Budget, US-CPI, or exchange halt days

4.3 Order Management
	•	Burst cap 20 orders / sec, 20 mods / order.
	•	Re-quote: max 3 retries, price-chase ≤ ₹0.10 each.

4.4 Risk Management
	•	Dynamic lot cap: ≤ 40 % free margin, hard ceiling 50 lots.
	•	Daily P & L stop ₹25 k → flatten + lock.
	•	Circuit breakers: India VIX > +3 σ, auction, or halt.
	•	Decision-hash + feature snapshot stored per order (audit).

4.5 Data Management
	•	Live option chain every ≤ 3 s (Trade-hull).
	•	Accept OI refresh up to 5 s.
	•	Store: raw WS 7 d; derived metrics 2 y; minute bars 90 d.

4.6 User Interface & Monitoring
	•	Dashboard additions
	•	Alpha-decay plot (P & L vs age)
	•	Latency histogram, slippage tracker
	•	Prominent 2-s “Kill All” button
	•	Parameter governance – UI can toggle strategies; numeric thresholds require code merge + approval.

4.7 Alerts
	•	Slack/Telegram on fills, exits, risk.
	•	Extra alert if latency > 200 ms or ≥ 3 trades blocked by slippage filter in 5 min.

⸻

5. Technical Infrastructure

Layer	Detail
Broker	Dhan-Tradehull v3.x async wrapper; token refresh daily 08:50 IST
Backend	FastAPI 3.12 · SQLModel/Postgres · Redis · Celery
Realtime	Socket.IO
Frontend	React 18 TS · shadcn/ui · Tailwind · Recharts
Deployment	Primary: Railway (Singapore); Mumbai VPS fallback for ≤ 10 ms RTT
Scaling	Auto-spawn replicas when CPU > 70 % (5-min) or WS lag > 200 ms
Disaster Recovery	Hot-standby Postgres + Redis (AOF 60 s); RTO ≤ 2 min


⸻

6. Success Metrics

Category	KPI
Execution	≥ 99.5 % order ACKs < 150 ms (median); 95-th ≤ 250 ms
Cost Control	Avg slippage ≤ ₹0.30 / leg
Trading	Win-rate ≥ 65 % or CAGR ≥ 15 %; Sharpe ≥ 1.2
Risk	Max drawdown ≤ 6 % equity; loss cap never breached
Uptime	99.9 % market-hours; RTO ≤ 2 min


⸻

7. Non-Goals (Phase 1)
	•	BANKNIFTY integration deferred to Phase 2 (before FINNIFTY).
	•	Manual order entry, back-testing engine, mobile app, multi-broker, market-making, crypto/commodity remain out-of-scope.

⸻

8. Design & UX Highlights
	•	Modern, responsive dashboard; framer-motion fade-ins.
	•	Color-coded risk (green / yellow / red).
	•	Navigation: Dashboard · Positions · Admin.
	•	Latency & alpha-decay visuals added.

⸻

9. Open Questions
	1.	Confirm any Trade-hull burst limits beyond 20 orders / sec
	2.	Add sector/correlation caps?
	3.	NSE audit JSON spec for decision-hash field?
	4.	Handling holiday-short weeks in 90-day history?
	5.	VPS spec for Mumbai fallback (target RTT < 10 ms)?
	6.	Are CPU 70 % + WS 200 ms good auto-scale triggers?
	7.	Default to deep-ITM option hedge to cut margin?

⸻

Revision 2 integrates slippage controls, latency audits, dynamic margin limits, event filters, compliance logging, and scalability paths—ready for stakeholder sign-off.