# Rozana OMS – FastAPI Microservice

Simple FastAPI service for order creation and status updates using PostgreSQL and Firebase token authentication.

## Quick Start
```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:password@localhost:5432/oms_db"
uvicorn application.app.main:app --reload
```

## Main Endpoints
| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | /create_order | Create order with items |
| GET  | /get_order_details?order_id= | Retrieve order and items |
| PUT/PATCH | /update_order_status | Update overall order status |
| PUT/PATCH | /update_item_status | Update specific item status |
| GET | /health | Health check |

## Database Migrations
See `ALEMBIC.md` for the two-command cheat-sheet.

---
## Legacy documentation (outdated)


A production-ready FastAPI microservice implementing CQRS pattern with PostgreSQL database, Redis caching, and Apache Kafka event streaming.

## Architecture Overview

This OMS microservice implements a sophisticated CQRS (Command Query Responsibility Segregation) pattern with the following components:

- **FastAPI Application**: RESTful API with async/await support
- **PostgreSQL Database**: Single master database with future read replica support
- **Redis Cache**: High-performance caching for command operations
- **Apache Kafka**: Event streaming for asynchronous processing
- **Docker Containerization**: Complete microservice stack

## Key Features

### CQRS Implementation
- **Commands (POST/PUT)**: Cache in Redis → Publish to Kafka → Async DB write
- **Queries (GET)**: Direct read from database
- **Cancel Operation**: Synchronous write to master database
- **Event Sourcing**: Order journey tracking with status changes

### Infrastructure
- **PostgreSQL Database**: Single master database with configurable read replica support
- **Redis Caching**: Order data caching with TTL
- **Kafka Event Streaming**: Reliable message delivery with consumer groups
- **Connection Pooling**: Optimized database connections using psycopg

## API Endpoints

### Order Management

| Method | Endpoint | Description | Data Flow |
|--------|----------|-------------|-----------|
| `POST` | `/orders` | Create order | Redis Cache → Kafka → Async DB |
| `PUT` | `/orders/{order_id}` | Update order | Redis Cache → Kafka → Async DB |
| `GET` | `/orders` | List orders | Database |
| `GET` | `/orders/{order_id}` | Get order details (with returns & refunds) | Database |
| `GET` | `/orders/{order_id}/journey` | Get order journey | Database |
| `PUT` | `/orders/{order_id}/cancel` | Cancel order | Master DB (Sync) |

## Database Schema

### Orders Table
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    facility_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    order_datetime TIMESTAMP NOT NULL,
    eta TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Order Items Table
```sql
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES orders(order_id),
    sku VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    sale_price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Order Journey Table
```sql
CREATE TABLE order_journey (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES orders(order_id),
    current_status VARCHAR(20) NOT NULL,
    previous_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- 6GB+ RAM recommended for full stack

### 1. Start the Microservice Stack

```bash
# Clone and navigate to project
git clone <repository-url>
cd oms-fastapi

# Start all services
docker-compose up --build
```

### 2. Services Access

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL DB**: localhost:5432
- **Redis**: localhost:6379
- **Kafka**: localhost:9092

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Create an order (Redis + Kafka flow)
curl -X POST "http://localhost:8000/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "ORD-001",
    "customer_id": "CUST-001",
    "facility_id": "FAC-001",
    "status": "pending",
    "total_amount": 99.99,
    "order_datetime": "2024-01-01T10:00:00",
    "eta": "2024-01-01T15:00:00",
    "items": [
      {
        "sku": "ITEM-001",
        "quantity": 2,
        "unit_price": 45.00,
        "sale_price": 49.99
      }
    ]
  }'

# List orders
curl "http://localhost:8000/orders?limit=10"

# Get order details
# Includes payments with refund history and return requests
curl "http://localhost:8000/orders/ORD-001"

# Get order journey
curl "http://localhost:8000/orders/ORD-001/journey"

# Cancel order (Direct DB write)
curl -X PUT "http://localhost:8000/orders/ORD-001/cancel"
```

## Environment Configuration

```env
# Database Configuration
# Currently using single master database for both read and write operations
# In future, you can change READ_DATABASE_URL to point to a read replica
WRITE_DATABASE_URL=postgresql://user:password@postgres-db:5432/oms_db
READ_DATABASE_URL=postgresql://user:password@postgres-db:5432/oms_db

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_ORDER_TOPIC=order-events
KAFKA_CONSUMER_GROUP=order-processor

# Application Configuration
LOG_LEVEL=INFO
```

## Future Read Replica Support

The system is designed to easily support read replicas in the future:

1. **Setup Read Replica**: Deploy a PostgreSQL read replica
2. **Update Environment**: Change `READ_DATABASE_URL` in `.env` file
3. **No Code Changes**: The application will automatically use the read replica for queries

Example for future read replica:
```env
WRITE_DATABASE_URL=postgresql://user:password@master-db:5432/oms_db
READ_DATABASE_URL=postgresql://user:password@replica-db:5432/oms_db
```

## Architecture Components

### 1. FastAPI Application (`main.py`)
- RESTful API endpoints
- Pydantic models for request/response validation
- Async/await for non-blocking operations
- Comprehensive error handling

### 2. CQRS Services (`services.py`)
- **OrderService**: Handles create/update operations
- **OrderQueryService**: Handles read operations
- Separation of concerns for scalability

### 3. Infrastructure Layer (`infrastructure.py`)
- **RedisManager**: Connection pooling and caching operations
- **KafkaManager**: Producer/consumer management
- Connection lifecycle management

### 4. Event Consumer (`consumer.py`)
- **OrderEventProcessor**: Processes Kafka events
- **OrderEventConsumer**: Kafka consumer with error handling
- Async event processing with database writes

### 5. Database Layer (`database.py`)
- Connection pooling for write and read operations
- Context managers for connection lifecycle
- Health checks and monitoring
- Future-ready for read replica support

## Monitoring and Observability

### Logs
```bash
# Application logs
docker-compose logs -f app

# Consumer logs
docker-compose logs -f consumer

# Database logs
docker-compose logs -f postgres-db

# Infrastructure logs
docker-compose logs -f redis kafka
```

### Health Checks
- Database connection health checks
- Redis connectivity monitoring
- Kafka broker health verification

## Production Deployment

### Scaling Considerations
- **Horizontal Scaling**: Multiple API instances behind load balancer
- **Database Scaling**: Easy to add read replicas by updating environment variables
- **Kafka Partitioning**: Configure topic partitions for parallel processing
- **Redis Clustering**: For high availability caching

### Security
- Database connection encryption
- API rate limiting
- Input validation and sanitization
- Environment variable security

### Performance Optimization
- Connection pooling tuning
- Redis cache TTL optimization
- Kafka batch processing
- Database query optimization

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires external services)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run consumer separately for testing
python app/consumer.py

# Monitor Kafka topics
docker exec -it oms-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --from-beginning
```

## Troubleshooting

### Common Issues
1. **Services not starting**: Check Docker resources and port conflicts
2. **Database connection errors**: Verify connection strings and network
3. **Kafka connection issues**: Ensure Zookeeper is healthy
4. **Redis connection problems**: Check Redis service status

### Debug Commands
```bash
# Check service status
docker-compose ps

# View service logs
docker-compose logs [service-name]

# Connect to database
docker exec -it oms-postgres psql -U user -d oms_db

# Connect to Redis
docker exec -it oms-redis redis-cli

# List Kafka topics
docker exec -it oms-kafka kafka-topics --list --bootstrap-server localhost:9092
```

This microservice provides a robust foundation for order management with modern architectural patterns, ensuring scalability, reliability, and maintainability. The single database approach simplifies deployment while maintaining the flexibility to add read replicas in the future.