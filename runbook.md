# ORY Hydra Database Performance Benchmarking Runbook

This runbook provides detailed instructions for setting up, running, and monitoring the ORY Hydra database performance benchmarking experiments.

## Prerequisites

- Docker and Docker Compose installed
- At least 8GB of free RAM
- At least 4 CPU cores available
- Ports 3306, 4444, 4445, 5432, 9090, 9104, 9187, and 3000 available

## Network Setup

### 1. Create Shared Network
```bash
# Create the shared network that all services will use
docker network create hydra_benchmark_network

# Verify network creation
docker network ls | grep hydra_benchmark_network
```

### 2. Network Verification
Before starting experiments, verify network configuration:
```bash
# List all networks
docker network ls

# Inspect the benchmark network
docker network inspect hydra_benchmark_network
```

## Sequential Experiment Setup

### 1. Start Monitoring Stack First
```bash
# Navigate to monitoring directory
cd shared-monitoring

# Start monitoring services
docker-compose -f docker-compose.monitoring.yml up -d

# Verify monitoring services are running
docker-compose -f docker-compose.monitoring.yml ps

# Check logs for any issues
docker-compose -f docker-compose.monitoring.yml logs -f

# Verify Prometheus targets
curl -s http://localhost:9090/api/v1/targets | grep "health"

# Access monitoring interfaces
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (default credentials: admin/admin)

# Verify Prometheus can reach its targets
# Open http://localhost:9090/targets and check all targets are UP
```

### 2. PostgreSQL Experiment
```bash
# Navigate to PostgreSQL directory
cd ../postgres

# Start PostgreSQL stack
docker-compose -f docker-compose.postgres.yml up -d

# Verify services are running
docker-compose -f docker-compose.postgres.yml ps

# Monitor logs
docker-compose -f docker-compose.postgres.yml logs -f

# Verify metrics are being collected
curl -s http://localhost:9187/metrics | grep "pg_up"

# Run your experiments...

# When experiment is complete, bring down PostgreSQL stack
docker-compose -f docker-compose.postgres.yml down
```

### 3. MySQL Experiment
```bash
# Navigate to MySQL directory
cd ../mysql

# Start MySQL stack
docker-compose -f docker-compose.mysql.yml up -d

# Verify services are running
docker-compose -f docker-compose.mysql.yml ps

# Monitor logs
docker-compose -f docker-compose.mysql.yml logs -f

# Verify metrics are being collected
curl -s http://localhost:9104/metrics | grep "mysql_up"

# If the MySQL exporter is not working, check the container logs
docker logs mysql-mysqld_exporter-1

# Verify the MySQL exporter container name matches what Prometheus expects
docker ps | grep mysqld_exporter

# Run load tests with hydra-tester
cd ../hydra-tester
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run with default settings
./run.py

# Or with custom configuration
./run.py \
  --clients 10 \
  --refresh-count 10 \
  --refresh-interval 60 \
  --hydra-admin-url http://localhost:4445 \
  --hydra-public-url http://localhost:4444 \
  --verbose

# Monitor results:
# - Check output/clients.json for client credentials
# - Check output/tokens.json for token history
# - Monitor metrics in Grafana dashboard

# When experiment is complete, bring down MySQL stack
docker-compose -f docker-compose.mysql.yml down
```

### 4. Running Load Tests

The hydra-tester tool simulates complete OAuth2 flows to benchmark Hydra's performance:

1. Setup:
```bash
cd hydra-tester
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configuration:
- Default settings in config/default_config.json
- Override via CLI flags or environment variables
- Supports both MySQL and PostgreSQL setups

3. Key Features:
- Client creation and management
- Authorization code flow with PKCE
- Automated login/consent handling
- Token refresh cycles
- Detailed logging and metrics

4. Monitoring:
- Check output/clients.json for client data
- Check output/tokens.json for token history
- Monitor in Grafana:
  - Request rates and latencies
  - Success/failure counts
  - Database performance impact

5. Example Commands:
```bash
# Basic test
./run.py

# Extended test with more clients
./run.py --clients 20 --refresh-count 15 --refresh-interval 30

# Verbose mode with custom URLs
./run.py \
  --clients 10 \
  --refresh-count 10 \
  --refresh-interval 60 \
  --hydra-admin-url http://localhost:4445 \
  --hydra-public-url http://localhost:4444 \
  --verbose
```

### 5. Final Cleanup
```bash
# Stop monitoring stack
cd ../shared-monitoring
docker-compose -f docker-compose.monitoring.yml down

# Remove shared network
docker network rm hydra_benchmark_network

# Verify cleanup
docker network ls | grep hydra_benchmark_network
docker ps -a | grep -E "mysql|postgres|prometheus|grafana"
```

### 5. Monitoring Stack Management

The monitoring stack runs continuously during experiments. Access the monitoring interfaces at:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (default credentials: admin/admin)

Key monitoring tasks:
1. Check Prometheus targets status
2. Monitor metrics collection
3. View Grafana dashboards
4. Check for any connection issues between services

## Verification Steps

### 1. Network Connectivity
```bash
# Check if containers can reach each other
docker exec -it shared-monitoring-prometheus-1 ping postgres-postgres-1
docker exec -it shared-monitoring-prometheus-1 ping mysql-mysql-1

# Verify Prometheus can scrape metrics
curl -s http://localhost:9090/api/v1/targets | jq .
```

### 2. Database Connectivity

#### PostgreSQL
```bash
# Connect to PostgreSQL
docker exec -it postgres_postgres_1 psql -U postgres -d oauth2-oidc

# Check if Hydra tables are created
\dt

# Check database size
SELECT pg_size_pretty(pg_database_size('oauth2-oidc'));

# Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'oauth2-oidc';
```

#### MySQL
```bash
# Connect to MySQL
docker exec -it mysql_mysql_1 mysql -u root -psecret oauth2-oidc

# Check if Hydra tables are created
SHOW TABLES;

# Check database size
SELECT table_schema "oauth2-oidc", 
       ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) "Size (MB)" 
FROM information_schema.TABLES 
WHERE table_schema = "oauth2-oidc"
GROUP BY table_schema;

# Check active connections
SHOW STATUS WHERE Variable_name = 'Threads_connected';
```

### 2. Verify Hydra API

```bash
# Check Hydra health status (PostgreSQL setup)
curl http://localhost:4445/health/ready

# Check Hydra health status (MySQL setup)
curl http://localhost:4445/health/ready
```

### 3. Verify Metrics Collection

1. Open Prometheus (http://localhost:9090)
2. Go to Status > Targets to verify all exporters are up
3. Try some test queries:
   - Database metrics:
     ```
     rate(process_cpu_seconds_total{job="postgres"}[1m])
     mysql_global_status_threads_connected
     ```
   - Hydra metrics (via admin API):
     ```
     rate(http_request_duration_seconds_count{job=~"hydra-.*"}[5m])
     ```

4. Open Grafana (http://localhost:3000)
5. Navigate to the "Database Performance Metrics" dashboard
6. Verify metrics are being displayed

Note: Hydra metrics are now collected via the `/admin/metrics/prometheus` endpoint, which is the correct endpoint for accessing Hydra's Prometheus metrics through its admin API.

## Monitoring Key Metrics

### PostgreSQL Metrics
- Container name: `postgres-postgres_exporter-1:9187`
1. **Autovacuum Activity**
   - Prometheus query: `pg_stat_activity_count{state="autovacuum"}`
   - Check for regular autovacuum runs

2. **Buffer Usage**
   - Prometheus query: `pg_stat_bgwriter_buffers_backend_fsync`

3. **Transaction Throughput**
   - Prometheus query: `rate(pg_stat_database_xact_commit[5m])`

### MySQL Metrics
- Container name: `mysql-mysqld_exporter-1:9104` (configured in docker-compose.mysql.yml)
1. **InnoDB Purge Threads**
   - Prometheus query: `mysql_global_status_innodb_purge_threads`

2. **Buffer Pool Usage**
   - Prometheus query: `mysql_global_status_innodb_buffer_pool_pages_total - mysql_global_status_innodb_buffer_pool_pages_free`

3. **Transaction Throughput**
   - Prometheus query: `rate(mysql_global_status_com_commit[5m])`

### Hydra Metrics
- PostgreSQL setup: `postgres-hydra-1:4445/admin/metrics/prometheus`
- MySQL setup: `mysql-hydra-1:4445/admin/metrics/prometheus`
1. **Request Duration**
   - Prometheus query: `rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])`

2. **Request Rate**
   - Prometheus query: `rate(http_request_duration_seconds_count{job=~"hydra-.*"}[5m])`

3. **Error Rate**
   - Prometheus query: `sum(rate(http_request_duration_seconds_count{job=~"hydra-.*",code=~"5.*"}[5m]))`

## Troubleshooting

### MySQL Exporter Issues

1. **MySQL exporter container naming**
   - Ensure the container name in docker-compose.mysql.yml matches what Prometheus expects:
     ```yaml
     mysql_exporter:
       build:
         context: .
         dockerfile: Dockerfile.exporter
       container_name: mysql-mysqld_exporter-1
     ```

2. **MySQL exporter connection issues**
   - Check the Dockerfile.exporter configuration:
     ```
     FROM prom/mysqld-exporter:v0.15.0
     
     USER root
     RUN echo -e "[client]\nuser=root\npassword=secret\nhost=mysql\nport=3306" > /etc/.my.cnf && \
         chmod 644 /etc/.my.cnf
     USER nobody
     
     ENTRYPOINT [ "/bin/mysqld_exporter" ]
     CMD [ "--config.my-cnf=/etc/.my.cnf", "--collect.info_schema.tables", "--collect.info_schema.innodb_metrics", 
           "--collect.global_status", "--collect.global_variables", "--collect.perf_schema.tableiowaits", 
           "--collect.perf_schema.indexiowaits", "--collect.perf_schema.tablelocks" ]
     ```

3. **Verifying MySQL exporter metrics**
   - Check if the exporter is running: `docker ps | grep mysqld_exporter`
   - Check if metrics are available: `curl -s http://localhost:9104/metrics | grep mysql_up`
   - Check Prometheus targets: `curl -s http://localhost:9090/api/v1/targets | grep mysql`

### Common Issues

1. **Services fail to start**
   - Check for port conflicts
   - Ensure enough system resources are available
   - Review logs: `docker-compose -f docker-compose.<db>.yml logs`

2. **Database connection issues**
   - Verify network connectivity between containers
   - Check database logs for authentication errors
   - Ensure database initialization completed successfully

3. **Metrics not appearing**
   - Check exporter connectivity in Prometheus targets
   - Verify exporter is running: `docker ps | grep exporter`
   - Check exporter logs: `docker logs <exporter-container-id>`

4. **Hydra migration failures**
   - Check Hydra logs: `docker logs <hydra-container-id>`
   - Verify database credentials and permissions
   - Ensure database is accessible from Hydra container

## Cleanup

To stop and remove all containers, networks, and volumes:

```bash
# PostgreSQL stack
cd postgres
docker-compose -f docker-compose.postgres.yml down -v

# MySQL stack
cd ../mysql
docker-compose -f docker-compose.mysql.yml down -v

# Finally, stop monitoring stack when all experiments are complete
cd ../shared-monitoring
docker-compose -f docker-compose.monitoring.yml down -v
```

Note: Using `down -v` will remove the volumes. If you want to preserve the metrics data for later analysis, omit the `-v` flag.
