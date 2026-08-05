# Monitoring — Distribution Management System

This document describes the Prometheus + Grafana monitoring stack instrumented into the backend.

## Architecture

```
┌──────────────────┐     scrape (15s)     ┌──────────────┐     dashboard      ┌────────┐
│  Backend (:8080) │ ◄─────────────────── │  Prometheus  │ ◄───────────────── │ Grafana │
│  /metrics         │                     │  (:9090)     │                   │(:3000)  │
└──────────────────┘                     └──────────────┘                   └────────┘
                                                  │                              │
                                           ┌───────┴───────┐                     │
                                           │  alert.rules   │                     │
                                           │  (7 rules)     │                     │
                                           └───────────────┘                     │
                                                                                │
                                                    nginx reverse proxy (:443) ◄┘
                                                    /grafana/* ──────────────────┘
```

- Backend exposes Prometheus metrics at `/metrics` (raw text, `Content-Type: text/plain`).
- Prometheus scrapes the backend every 10s, stores 30 days of history.
- Grafana is provisioned with a Prometheus datasource and 2 dashboards (HTTP + database performance only).
- Grafana is accessible via nginx at `https://localhost/grafana/`.

## Services

| Service      | Container       | IP           | Port          |
|-------------|----------------|--------------|---------------|
| Prometheus  | `dms-prometheus` | 172.20.0.10 | 9090          |
| Grafana     | `dms-grafana`    | 172.20.0.11 | 3000 (HTTPS)  |

## Getting Started

### 1. Build & Start

```bash
docker compose up -d
```

This starts the two new containers alongside the existing stack.

### 2. Verify Metrics Endpoint

```bash
curl -s http://localhost:8080/metrics | head -20
```

If behind the reverse proxy:

```bash
curl -sk https://localhost/api/../metrics | head -20
# Or from within Docker:
docker compose exec backend curl -s http://localhost:8080/metrics | head -20
```

Expected output (first lines):

```
# HELP python_info Python implementation information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="11",patch="...",version="3.11.?"} 1.0
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/docs",method="GET",status_code="200"} 2.0
```

### 3. Access Grafana

- URL: **https://localhost/grafana/** (HTTPS via nginx)
- Default credentials: `admin` / `admin` (change on first login)
- Set a custom password via `GRAFANA_ADMIN_PASSWORD` in your `.env` file:
  ```
  GRAFANA_ADMIN_PASSWORD=your-secure-password
  ```

The Prometheus datasource and 2 dashboards are auto-provisioned.

## Dashboards

### Backend API (`uid: backend-api`)
| Panel | Description |
|-------|-------------|
| HTTP Request Rate | Rate per second, split by method + endpoint |
| HTTP Request Duration (P95) | 95th percentile latency |
| HTTP Error Rate | Errors per second by endpoint + status |
| In-Flight Requests | Concurrent requests by method |
| Error Ratio (%) | Error % with thresholds (5% orange, 10% red) |
| Uptime | Seconds since last restart |

### Database (`uid: database-metrics`)
| Panel | Description |
|-------|-------------|
| Query Rate by Operation | SELECT / INSERT / UPDATE / DELETE per second |
| Query Latency P95 | 95th percentile by operation |
| Query Failure Rate | Failures per second by operation |
| Active Connections | Connection pool size (thresholds at 10 / 20) |

## Metrics Reference

### HTTP
| Metric | Type | Labels |
|--------|------|--------|
| `http_requests_total` | Counter | `method`, `endpoint`, `status_code` |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint`, `status_code` |
| `http_requests_in_progress` | Gauge | `method` |
| `http_errors_total` | Counter | `method`, `endpoint`, `status_code` |

### Database
| Metric | Type | Labels |
|--------|------|--------|
| `mysql_queries_total` | Counter | `operation` (select/insert/update/delete) |
| `mysql_query_duration_seconds` | Histogram | `operation` |
| `mysql_query_failures_total` | Counter | `operation` |
| `mysql_active_connections` | Gauge | — |

### System
| Metric | Type | Labels |
|--------|------|--------|
| `app_info` | Info | `name`, `framework`, `python_version` |
| `app_uptime_seconds` | Gauge | — |

## Alert Rules

| Alert | Severity | Condition | For |
|-------|----------|-----------|-----|
| BackendDown | critical | `up == 0` | 30s |
| HighErrorRate | warning | error rate > 5% | 2m |
| HighLatency | warning | P95 latency > 2s | 2m |
| ManyInProgressRequests | warning | in-flight > 50 | 1m |
| SlowQueries | warning | P95 query > 1s | 2m |
| QueryFailures | critical | failure rate > 0.1/s | 2m |
| AppRestarted | info | uptime < 60s | 0s |

Rules are defined in `monitoring/prometheus/alert.rules.yml`.

## Adding a New Metric

1. Define the metric in `backend/app/core/metrics.py`:
   ```python
   my_metric = Counter("my_metric_total", "Description", labelnames=["label1"])
   ```
2. Increment/observe it where appropriate in the codebase:
   ```python
   from app.core.metrics import my_metric
   my_metric.labels(label1="value").inc()
   ```
3. The new metric appears at `/metrics` and in Prometheus automatically.
4. Add a panel to the appropriate dashboard JSON in `monitoring/grafana/dashboards/`.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `/metrics` returns 404 | CSRF blocking | `/metrics` is exempt in `CSRFMiddleware` — verify `exempt_urls` |
| Prometheus targets show "down" | Backend not reachable on `dms_net` | Verify IP (172.20.0.3) and port (8080) — run `docker compose ps` |
| Grafana shows "datasource not found" | Provisioning failed | Check `monitoring/grafana/datasources/datasource.yml` syntax |
| Dashboards not appearing | Provisioning path mismatch | Ensure JSON files are in the path specified in `dashboard.yml` |
| High cardinality explosion | Endpoint label has dynamic values | Use `path_template` or strip dynamic segments from the label |
| Prometheus OOM | Retention too long | Reduce `--storage.tsdb.retention.time` in docker-compose |
| `prometheus-client` import error | Dependency not installed | Run `pip install prometheus-client>=0.19.0` and rebuild |
| Scraping `/metrics` causes slow responses | Too many metrics | Keep label cardinality low; use Histogram buckets sparingly |

## File Layout

```
monitoring/
├── prometheus/
│   ├── prometheus.yml        # Scrape config
│   └── alert.rules.yml       # Alert rules (7 alerts)
└── grafana/
    ├── datasources/
    │   └── datasource.yml    # Prometheus datasource
    └── dashboards/
        ├── dashboard.yml     # Dashboard provisioning config
        ├── backend-api-dashboard.json
        └── database-dashboard.json
backend/app/
├── core/
│   └── metrics.py            # All metric definitions + middleware + /metrics handler
├── middleware/
│   └── metrics_middleware.py  # (metrics defined in core/metrics.py instead)
├── database_sqlalchemy.py     # Engine event listeners record live MySQL metrics
└── main.py                    # Registers middleware, /metrics route, CSRF exemption
```

## How Metrics Are Collected

- **HTTP metrics** are recorded per request by `MetricsMiddleware` in `app/core/metrics.py`.
- **MySQL metrics** are recorded live by SQLAlchemy engine event listeners registered in `app/database_sqlalchemy.py` (`before_cursor_execute` / `after_cursor_execute` / `handle_error` / pool `checkout` / `checkin`). No background collector is required — there is no polling loop, and the DB metrics appear in Prometheus as soon as queries run.
- **Uptime / app metadata** are set on each `/metrics` scrape.
- No business-domain metrics are exported (users, operators, distributions, inventory, logins, etc.). Monitoring is scoped to performance signals used when investigating issues.
