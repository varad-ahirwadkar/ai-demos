# Database Setup Script

A comprehensive Python script to create database schemas and insert sample data. Supports both **PostgreSQL** and **IBM DB2** databases.

## Features

- ✅ Supports PostgreSQL and IBM DB2
- ✅ Creates database schema with proper indexes
- ✅ Loads data from CSV files
- ✅ Handles duplicate records gracefully
- ✅ Verifies data insertion
- ✅ Environment variable configuration

## Prerequisites

### For PostgreSQL
```bash
pip install psycopg2-binary
```

### For IBM DB2
```bash
pip install ibm_db
```

## Configuration

Set environment variables to configure the database connection:

### PostgreSQL Configuration
```bash
export DB_TYPE=postgresql
export POSTGRES_DB=techmart
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export CSV_FILE=data/orders.csv
```

### DB2 Configuration
```bash
export DB_TYPE=db2
export DB2_DATABASE=SAMPLE
export DB2_SCHEMA=TECHMART
export DB2_HOSTNAME=localhost
export DB2_PORT=50000
export DB2_USERNAME=your_username
export DB2_PASSWORD=your_password
export CSV_FILE=data/orders.csv
```

## Usage

### Basic Usage
```bash
# For PostgreSQL
python database_setup.py

# For DB2
DB_TYPE=db2 python database_setup.py
```

### With Custom CSV File
```bash
CSV_FILE=/path/to/your/orders.csv python database_setup.py
```

### Complete Example (PostgreSQL)
```bash
export DB_TYPE=postgresql
export POSTGRES_DB=techmart
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=secret123
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export CSV_FILE=data/orders.csv

python database_setup.py
```

### Complete Example (DB2)
```bash
export DB_TYPE=db2
export DB2_DATABASE=SAMPLE
export DB2_SCHEMA=TECHMART
export DB2_HOSTNAME=192.168.1.100
export DB2_PORT=50000
export DB2_USERNAME=db2admin
export DB2_PASSWORD=db2pass
export CSV_FILE=data/orders.csv

python database_setup.py
```

## CSV File Format

The CSV file should have the following columns:

```csv
order_id,customer_email,product_name,category,order_date,delivery_date,price,status,is_opened
ORD-2024-001,john.doe@email.com,Laptop Pro 15,Electronics,2024-03-15,2024-03-20,1299.99,Delivered,yes
ORD-2024-002,jane.smith@email.com,Wireless Mouse,Electronics,2024-04-01,2024-04-05,29.99,Delivered,no
```

### Column Descriptions
- **order_id**: Unique order identifier (e.g., ORD-2024-001)
- **customer_email**: Customer's email address
- **product_name**: Name of the product
- **category**: Product category
- **order_date**: Date when order was placed (YYYY-MM-DD)
- **delivery_date**: Date when order was delivered (YYYY-MM-DD or empty)
- **price**: Product price (decimal)
- **status**: Order status (e.g., Delivered, Processing, In Transit)
- **is_opened**: Whether product was opened (yes/no, true/false, 1/0)

## Database Schema

### PostgreSQL Schema
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2) NOT NULL,
    order_date DATE NOT NULL,
    delivery_date DATE,
    status VARCHAR(50) NOT NULL,
    is_opened BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### DB2 Schema
```sql
CREATE TABLE TECHMART.ORDERS (
    ID INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ORDER_ID VARCHAR(50) NOT NULL,
    CUSTOMER_EMAIL VARCHAR(255) NOT NULL,
    PRODUCT_NAME VARCHAR(255) NOT NULL,
    CATEGORY VARCHAR(100),
    PRICE DECIMAL(10,2) NOT NULL,
    ORDER_DATE DATE NOT NULL,
    DELIVERY_DATE DATE,
    STATUS VARCHAR(50) NOT NULL,
    IS_OPENED SMALLINT DEFAULT 0,
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Output Example

```
============================================================
Database Setup Script
============================================================
Database Type: postgresql

✓ Connected to PostgreSQL database: techmart

1. Creating database schema...
✓ Created PostgreSQL schema and tables

2. Loading data from CSV...
✓ Loaded 10 records from data/orders.csv

3. Inserting data into database...
✓ Inserted 10 records into PostgreSQL

4. Verifying inserted data...
✓ Total orders in database: 10

Sample orders:
  - ORD-2024-010: USB-C Hub (Processing) - $49.99
  - ORD-2024-009: Ergonomic Mouse Pad (Processing) - $19.99
  - ORD-2024-008: Webcam HD (Processing) - $79.99
  - ORD-2024-007: Standing Desk (In Transit) - $599.99
  - ORD-2024-006: Monitor 27 inch (Delivered) - $399.99

============================================================
✓ Database setup completed successfully!
============================================================
✓ Disconnected from PostgreSQL
```

## Troubleshooting

### Test Connection First
Before running the setup script, test your database connection:

```bash
# Test PostgreSQL connection
DB_TYPE=postgresql python test_db_connection.py

# Test DB2 connection
DB_TYPE=db2 python test_db_connection.py
```

### DB2 Connection Error (SQL30081N)
If you see error: `SQL30081N A communication error has been detected`

**Common Causes:**
1. **DB2 server not running**
   ```bash
   # Start DB2 instance
   db2start
   ```

2. **Wrong hostname or port**
   - Verify hostname: `ping <hostname>`
   - Check port is open: `telnet <hostname> <port>`
   - Default DB2 port is 50000

3. **Firewall blocking connection**
   ```bash
   # Check if port is accessible
   nc -zv <hostname> <port>
   # or
   telnet <hostname> <port>
   ```

4. **DB2 instance not configured for TCP/IP**
   ```bash
   # Check DB2 configuration
   db2 get dbm cfg | grep SVCENAME
   ```

5. **For IBM i systems**
   - Ensure QZDASOINIT jobs are available
   - Check subsystem is active: `WRKACTJOB SBS(QUSRWRK)`
   - Verify DB2 Connect license if required

### PostgreSQL Connection Issues
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check `pg_hba.conf` for access rules
- Ensure database exists: `psql -l`
- Test connection: `psql -h <host> -p <port> -U <user> -d <database>`

### Import Errors
- Install required packages: `pip install psycopg2-binary` or `pip install ibm_db`
- For DB2, ensure IBM Data Server Driver is installed
- Download from: https://www.ibm.com/support/pages/download-initial-version-115-clients-and-drivers

### CSV File Issues
- Verify CSV file path is correct
- Check CSV format matches expected columns
- Ensure dates are in YYYY-MM-DD format
- Verify price values are valid decimals

### Network Connectivity Test
```bash
# Test if port is reachable
telnet <hostname> <port>

# Or using nc (netcat)
nc -zv <hostname> <port>

# Or using Python
python -c "import socket; s=socket.socket(); s.settimeout(5); print('Open' if s.connect_ex(('<hostname>', <port>))==0 else 'Closed')"
```

## License

This script is part of the TechMart Customer Service Demo project.