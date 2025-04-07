# ORY Hydra Database Performance Benchmarking

This project sets up ORY Hydra with both MySQL and PostgreSQL databases for performance comparison. Each database is configured with specific tuning parameters and monitored using Prometheus and Grafana.

## Project Structure

```
.
├── postgres/
│   ├── docker-compose.postgres.yml
│   ├── postgresql.conf
│   └── pg_hba.conf
├── mysql/
│   ├── docker-compose.mysql.yml
│   ├── my.cnf
│   ├── .my.cnf
│   └── Dockerfile.exporter
└── shared-monitoring/
    ├── docker-compose.monitoring.yml
    ├── prometheus/
    │   └── prometheus.yml
    └── grafana/
        └── provisioning/
            ├── datasources/
            └── dashboards/
```

## Network Configuration

All services use a single shared Docker network (`hydra_benchmark_network`) to ensure proper communication between:
- Monitoring services (Prometheus, Grafana)
- Database servers (PostgreSQL, MySQL)
- Exporters (postgres_exporter, mysqld_exporter)
- ORY Hydra instances

This unified network approach simplifies service discovery and ensures metrics collection works properly.

## Database Configurations

### PostgreSQL (2 CPU, 4GB RAM)
- Tuned for OLTP workload
- Optimized buffer and memory settings
- Configured autovacuum for maintenance
- Monitoring via postgres_exporter

### MySQL (2 CPU, 4GB RAM)
- InnoDB optimizations
- Buffer pool and log settings
- Performance schema enabled
- Custom mysqld_exporter configuration:
  - Built from prom/mysqld-exporter:v0.15.0
  - Configured with root access for complete metrics collection
  - Enhanced metrics collection (tables, innodb, global status)
  - Proper container naming for Prometheus service discovery

## Running the Experiments

The experiments are designed to be run sequentially to ensure accurate benchmarking:

### 0. Create Shared Network
```bash
docker network create hydra_benchmark_network
```

### 1. Start Monitoring Stack
```bash
cd shared-monitoring
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Run PostgreSQL Experiment
```bash
cd ../postgres
docker-compose -f docker-compose.postgres.yml up -d
# Run experiments, then when complete:
docker-compose -f docker-compose.postgres.yml down
```

### 3. Run MySQL Experiment
```bash
cd ../mysql
docker-compose -f docker-compose.mysql.yml up -d
# Run experiments, then when complete:
docker-compose -f docker-compose.mysql.yml down
```

### 4. Cleanup
```bash
cd ../shared-monitoring
docker-compose -f docker-compose.monitoring.yml down
docker network rm hydra_benchmark_network
```

## Monitoring

### Accessing Metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- PostgreSQL Metrics: http://localhost:9187/metrics
- MySQL Metrics: http://localhost:9104/metrics

### Key Metrics Monitored
1. CPU & RAM Usage
2. Buffer/Cache Usage
3. Connection Stats
4. Database-specific metrics:
   - PostgreSQL: Autovacuum activity
   - MySQL: InnoDB purge threads and buffer pool

### Prometheus Configuration
- Single shared network for all services
- Streamlined job configuration with one job per component
- Hydra metrics collected via `/admin/metrics/prometheus` endpoint
- Container names used for direct service discovery

## Database Access

### PostgreSQL
- Database: oauth2-oidc
- Port: 5432
- Default Credentials:
  - Username: postgres
  - Password: secret

### MySQL
- Database: oauth2-oidc
- Port: 3306
- Default Credentials:
  - Username: root
  - Password: secret

## Hydra Configuration
- Public API: http://localhost:4444
- Admin API: http://localhost:4445
- Resource Limits:
  - CPU: 1 unit
  - Memory: 2GB

## Load Testing

The project includes a `hydra-tester` tool for simulating OAuth2 flows and benchmarking Hydra's performance:

```bash
cd hydra-tester
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Example with 10 clients, 5 concurrent threads per client (50 total concurrent flows), 15s timeout
./run.py --clients 10 --threads-per-client 5 --refresh-count 10 --refresh-interval 60 --timeout 15 --verbose
```

See [hydra-tester/README.md](hydra-tester/README.md) for detailed configuration options and usage instructions.

## Notes
- Each database is configured with appropriate resource limits (2 CPU, 4GB RAM)
- Hydra instances are configured with 1 CPU and 2GB RAM
- Monitoring is set up to track key performance metrics
- Both setups use the same database name 'oauth2-oidc'
