# TechMart Customer Service Demo - IBM i VM Setup Guide

This guide provides step-by-step instructions for deploying the TechMart Customer Service Assistant demo on an IBM i VM using DB2 database.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Running the Demo](#running-the-demo)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- **IBM i OS**: Version 7.3 or higher
- **DB2 for i**: Native to IBM i (already installed)
- **Python**: 3.9 or higher
- **Git**: For cloning the repository
- **SSH Access**: To the IBM i VM

### Network Requirements
- Outbound internet access for downloading packages
- Open ports:
  - `5000` - Flask web application
  - `8321` - MCP server
  - `5050` - Llama Stack distribution (if using)
  - `50000` - DB2 default port (if remote access needed)

---

## System Requirements

### Minimum Hardware
- **CPU**: 4 cores
- **RAM**: 16 GB
- **Storage**: 50 GB free space
- **Network**: 100 Mbps

### Recommended Hardware
- **CPU**: 8+ cores
- **RAM**: 32 GB+
- **Storage**: 100 GB+ SSD
- **Network**: 1 Gbps

---

## Installation Steps

### Step 1: Connect to IBM i VM

```bash
# SSH into your IBM i VM
ssh your-username@your-ibm-i-vm-hostname

# Switch to bash shell (if not default)
bash
```

### Step 2: Install System Dependencies

```bash
# Update package manager (if using yum on PASE)
yum update -y

# Install Python 3.9+ and development tools
yum install -y python39 python39-devel python39-pip

# Install Git
yum install -y git

# Install build tools
yum install -y gcc gcc-c++ make

# Install DB2 client libraries (if not already available)
# These are typically pre-installed on IBM i
```

### Step 3: Verify DB2 Installation

```bash
# Check DB2 version
db2level

# Check DB2 instance
db2 get instance

# List databases
db2 list db directory
```

### Step 4: Create DB2 Database and Schema

```bash
# Connect to DB2 as admin user
db2

# Create database for TechMart
CREATE DATABASE TECHMART USING CODESET UTF-8 TERRITORY US;

# Connect to the database
CONNECT TO TECHMART;

# Create schema
CREATE SCHEMA TECHMART;

# Set current schema
SET SCHEMA TECHMART;

# Create orders table
CREATE TABLE ORDERS (
    ID INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
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
    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID)
);

# Create index on order_id for faster lookups
CREATE UNIQUE INDEX IDX_ORDER_ID ON ORDERS(ORDER_ID);

# Create index on customer_email
CREATE INDEX IDX_CUSTOMER_EMAIL ON ORDERS(CUSTOMER_EMAIL);

# Grant permissions (replace YOUR_USERNAME with actual username)
GRANT ALL ON ORDERS TO USER YOUR_USERNAME;

# Verify table creation
DESCRIBE TABLE ORDERS;

# Exit DB2
QUIT;
```

### Step 5: Insert Sample Data

```bash
# Create SQL file with sample data
cat > ~/insert_sample_orders.sql << 'EOF'
CONNECT TO TECHMART;
SET SCHEMA TECHMART;

INSERT INTO ORDERS (ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, CATEGORY, PRICE, ORDER_DATE, DELIVERY_DATE, STATUS, IS_OPENED)
VALUES 
('ORD-2024-001', 'john.doe@email.com', 'Wireless Bluetooth Headphones', 'Electronics', 79.99, '2024-03-15', '2024-03-18', 'Delivered', 1),
('ORD-2024-002', 'jane.smith@email.com', 'Stainless Steel Water Bottle', 'Home & Kitchen', 24.99, '2024-03-20', '2024-03-23', 'Delivered', 0),
('ORD-2024-003', 'bob.johnson@email.com', 'Running Shoes - Size 10', 'Sports & Outdoors', 89.99, '2024-03-25', '2024-03-28', 'Delivered', 1),
('ORD-2024-004', 'alice.williams@email.com', 'Organic Cotton T-Shirt', 'Clothing', 29.99, '2024-04-01', '2024-04-04', 'Delivered', 0),
('ORD-2024-005', 'charlie.brown@email.com', 'Laptop Backpack', 'Accessories', 49.99, '2024-04-10', NULL, 'Processing', 0);

COMMIT;
QUIT;
EOF

# Execute SQL file
db2 -tvf ~/insert_sample_orders.sql

# Verify data
db2 "CONNECT TO TECHMART; SELECT COUNT(*) FROM TECHMART.ORDERS;"
```

### Step 6: Clone the Repository

```bash
# Create working directory
mkdir -p ~/ai-demos
cd ~/ai-demos

# Clone the repository
git clone https://github.com/your-org/ai-demos.git
cd ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo
```

### Step 7: Set Up Python Virtual Environment

```bash
# Create virtual environment
python3.9 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Install DB2 Python driver
pip install ibm_db ibm_db_sa

# Install additional dependencies
pip install gunicorn python-dotenv
```

### Step 8: Create DB2 Database Adapter

Create a new file to handle DB2 connections:

```bash
cat > ~/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/database/db2_adapter.py << 'EOF'
"""
DB2 Database Adapter for TechMart Demo
Provides connection and query utilities for IBM DB2
"""

import ibm_db
import ibm_db_dbi
from typing import List, Dict, Any, Optional
import os
from datetime import datetime

class DB2Adapter:
    def __init__(self):
        self.db_name = os.getenv('DB2_DATABASE', 'TECHMART')
        self.schema = os.getenv('DB2_SCHEMA', 'TECHMART')
        self.hostname = os.getenv('DB2_HOSTNAME', 'localhost')
        self.port = os.getenv('DB2_PORT', '50000')
        self.username = os.getenv('DB2_USERNAME')
        self.password = os.getenv('DB2_PASSWORD')
        self.conn = None
        
    def connect(self):
        """Establish connection to DB2 database"""
        try:
            conn_str = (
                f"DATABASE={self.db_name};"
                f"HOSTNAME={self.hostname};"
                f"PORT={self.port};"
                f"PROTOCOL=TCPIP;"
                f"UID={self.username};"
                f"PWD={self.password};"
            )
            self.conn = ibm_db.connect(conn_str, "", "")
            print(f"Connected to DB2 database: {self.db_name}")
            return True
        except Exception as e:
            print(f"Error connecting to DB2: {e}")
            return False
    
    def disconnect(self):
        """Close DB2 connection"""
        if self.conn:
            ibm_db.close(self.conn)
            self.conn = None
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results as list of dictionaries"""
        if not self.conn:
            self.connect()
        
        try:
            # Prepare statement
            stmt = ibm_db.prepare(self.conn, query)
            
            # Bind parameters if provided
            if params:
                for i, param in enumerate(params, start=1):
                    ibm_db.bind_param(stmt, i, param)
            
            # Execute query
            ibm_db.execute(stmt)
            
            # Fetch results
            results = []
            row = ibm_db.fetch_assoc(stmt)
            while row:
                # Convert keys to lowercase for consistency
                row_dict = {k.lower(): v for k, v in row.items()}
                results.append(row_dict)
                row = ibm_db.fetch_assoc(stmt)
            
            return results
        except Exception as e:
            print(f"Error executing query: {e}")
            return []
    
    def execute_update(self, query: str, params: tuple = None) -> bool:
        """Execute INSERT/UPDATE/DELETE query"""
        if not self.conn:
            self.connect()
        
        try:
            stmt = ibm_db.prepare(self.conn, query)
            
            if params:
                for i, param in enumerate(params, start=1):
                    ibm_db.bind_param(stmt, i, param)
            
            ibm_db.execute(stmt)
            return True
        except Exception as e:
            print(f"Error executing update: {e}")
            return False
    
    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order details by order ID"""
        query = f"""
            SELECT * FROM {self.schema}.ORDERS 
            WHERE ORDER_ID = ?
        """
        results = self.execute_query(query, (order_id,))
        return results[0] if results else None
    
    def get_orders_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Get all orders for a customer email"""
        query = f"""
            SELECT * FROM {self.schema}.ORDERS 
            WHERE CUSTOMER_EMAIL = ?
            ORDER BY ORDER_DATE DESC
        """
        return self.execute_query(query, (email,))
    
    def check_return_eligibility(self, order_id: str) -> Dict[str, Any]:
        """Check if order is eligible for return"""
        order = self.get_order_by_id(order_id)
        
        if not order:
            return {
                "eligible": False,
                "reason": "Order not found"
            }
        
        # Check if delivered
        if order['status'] != 'Delivered':
            return {
                "eligible": False,
                "reason": "Order must be delivered to be eligible for return"
            }
        
        # Check if opened
        if order['is_opened'] == 1:
            return {
                "eligible": False,
                "reason": "Opened items cannot be returned"
            }
        
        # Check 30-day window
        if order['delivery_date']:
            delivery_date = order['delivery_date']
            days_since_delivery = (datetime.now().date() - delivery_date).days
            
            if days_since_delivery > 30:
                return {
                    "eligible": False,
                    "reason": f"Return window expired ({days_since_delivery} days since delivery)"
                }
        
        return {
            "eligible": True,
            "reason": "Order is eligible for return",
            "order": order
        }
    
    def get_all_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all orders with optional limit"""
        query = f"""
            SELECT * FROM {self.schema}.ORDERS 
            ORDER BY ORDER_DATE DESC
            FETCH FIRST {limit} ROWS ONLY
        """
        return self.execute_query(query)

# Singleton instance
_db_adapter = None

def get_db_adapter() -> DB2Adapter:
    """Get or create DB2 adapter instance"""
    global _db_adapter
    if _db_adapter is None:
        _db_adapter = DB2Adapter()
        _db_adapter.connect()
    return _db_adapter
EOF
```

### Step 9: Update MCP Server for DB2

```bash
# Backup original MCP server
cp scripts/orders_mcp_server.py scripts/orders_mcp_server.py.postgres.bak

# Create DB2-compatible MCP server
cat > scripts/orders_mcp_server_db2.py << 'EOF'
"""
TechMart Orders MCP Server - DB2 Version
Provides order lookup and return eligibility checking tools
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from database.db2_adapter import get_db_adapter

# Initialize FastMCP server
mcp = FastMCP("TechMart Orders")

@mcp.tool()
def get_order(order_id: str) -> dict:
    """
    Get order details by order ID
    
    Args:
        order_id: The order ID (e.g., 'ORD-2024-001')
    
    Returns:
        Order details including customer email, product, price, dates, and status
    """
    db = get_db_adapter()
    order = db.get_order_by_id(order_id)
    
    if not order:
        return {"error": f"Order {order_id} not found"}
    
    return {
        "order_id": order['order_id'],
        "customer_email": order['customer_email'],
        "product_name": order['product_name'],
        "category": order['category'],
        "price": float(order['price']),
        "order_date": str(order['order_date']),
        "delivery_date": str(order['delivery_date']) if order['delivery_date'] else None,
        "status": order['status'],
        "is_opened": bool(order['is_opened'])
    }

@mcp.tool()
def check_return_eligibility(order_id: str) -> dict:
    """
    Check if an order is eligible for return
    
    Args:
        order_id: The order ID to check
    
    Returns:
        Eligibility status and reason
    """
    db = get_db_adapter()
    result = db.check_return_eligibility(order_id)
    return result

@mcp.tool()
def reload_orders() -> dict:
    """
    Reload sample orders into the database
    
    Returns:
        Status message
    """
    return {
        "message": "Please run the SQL script to reload orders",
        "script": "db2 -tvf ~/insert_sample_orders.sql"
    }

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
EOF
```

### Step 10: Configure Environment Variables

```bash
# Create .env file
cat > .env << 'EOF'
# DB2 Configuration
DB2_DATABASE=TECHMART
DB2_SCHEMA=TECHMART
DB2_HOSTNAME=localhost
DB2_PORT=50000
DB2_USERNAME=your_username
DB2_PASSWORD=your_password

# Llama Stack Configuration (if using remote)
LLAMA_STACK_URL=http://localhost:5050

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8321

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-change-this

# Application Configuration
APP_HOST=0.0.0.0
APP_PORT=5000

# Ollama Configuration (if using local)
OLLAMA_URL=http://localhost:11434
USE_OLLAMA=true
EOF

# Update with your actual DB2 credentials
vi .env

# Load environment variables
source .env
```

---

## Configuration

### Option 1: Using Local Ollama (Recommended for IBM i VM)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve &

# Pull required models
ollama pull llama3.2:1b
ollama pull llama3.2:3b
ollama pull llama3.1:8b

# Verify models
ollama list
```

### Option 2: Using Remote Llama Stack

```bash
# Update .env with remote Llama Stack URL
echo "LLAMA_STACK_URL=http://your-llama-stack-host:5050" >> .env
echo "USE_OLLAMA=false" >> .env
```

---

## Running the Demo

### Step 1: Start MCP Server

```bash
# Open a new terminal
cd ~/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo

# Activate virtual environment
source venv/bin/activate

# Load environment variables
source .env

# Start DB2-compatible MCP server
cd scripts
python orders_mcp_server_db2.py

# Server should start on port 8321
```

### Step 2: Start Flask Application

```bash
# Open another terminal
cd ~/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo

# Activate virtual environment
source venv/bin/activate

# Load environment variables
source .env

# Start Flask application
cd app
python app.py

# Application should start on port 5000
```

### Step 3: Access the Application

```bash
# From your local machine, create SSH tunnel
ssh -L 5000:localhost:5000 your-username@your-ibm-i-vm-hostname

# Open browser:
http://localhost:5000
```

### Step 4: Test the Demo

Try these queries:

1. **Simple**: "Hello, how can you help me?"
2. **Policy**: "What is your return policy?"
3. **Order Lookup**: "Check status of order ORD-2024-001"
4. **Return Check**: "Can I return order ORD-2024-002?"
5. **Shipping**: "How long does shipping take?"

---

## Running as System Services

### MCP Server Service

```bash
sudo tee /etc/systemd/system/techmart-mcp.service > /dev/null << 'EOF'
[Unit]
Description=TechMart MCP Server (DB2)
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/scripts
Environment="PATH=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/venv/bin"
EnvironmentFile=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/.env
ExecStart=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/venv/bin/python orders_mcp_server_db2.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Flask Application Service

```bash
sudo tee /etc/systemd/system/techmart-app.service > /dev/null << 'EOF'
[Unit]
Description=TechMart Flask Application
After=network.target techmart-mcp.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/app
Environment="PATH=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/venv/bin"
EnvironmentFile=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/.env
ExecStart=/home/your-username/ai-demos/ai-demos/openshift-ai/llama-stack-demos/techmart-customer-service-demo/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable techmart-mcp techmart-app
sudo systemctl start techmart-mcp techmart-app
sudo systemctl status techmart-mcp techmart-app
```

---

## Troubleshooting

### DB2 Connection Issues

```bash
# Check DB2 instance
db2 get instance

# Test connection
db2 connect to TECHMART

# Check table
db2 "SELECT COUNT(*) FROM TECHMART.ORDERS"

# Check DB2 logs
db2diag -A
```

### MCP Server Issues

```bash
# Check if running
ps aux | grep orders_mcp_server_db2

# Test MCP server
curl http://localhost:8321/health

# Check logs
tail -f ~/techmart-mcp.log
```

### Python DB2 Driver Issues

```bash
# Reinstall ibm_db
pip uninstall ibm_db ibm_db_sa
pip install ibm_db ibm_db_sa

# Check installation
python -c "import ibm_db; print('DB2 driver OK')"
```

---

## Monitoring

```bash
# Create monitoring script
cat > ~/monitor-techmart.sh << 'EOF'
#!/bin/bash
echo "=== TechMart Demo Health Check ==="

# Check DB2
echo "DB2 Status:"
db2 connect to TECHMART > /dev/null 2>&1 && echo "Connected" || echo "Failed"

# Check MCP Server
echo "MCP Server:"
curl -s http://localhost:8321/health || echo "Not responding"

# Check Flask App
echo "Flask App:"
curl -s http://localhost:5000/health || echo "Not responding"

# Check resources
echo "Memory:"
free -h | grep Mem

echo "Disk:"
df -h | grep -E "/$"
EOF

chmod +x ~/monitor-techmart.sh
~/monitor-techmart.sh
```

---

## Backup and Recovery

```bash
# Backup DB2 database
db2 backup database TECHMART to ~/techmart-backups

# Restore DB2 database
db2 restore database TECHMART from ~/techmart-backups
```

---

## Quick Reference

```bash
# Start services
sudo systemctl start techmart-mcp techmart-app

# Stop services
sudo systemctl stop techmart-app techmart-mcp

# Check DB2
db2 connect to TECHMART
db2 "SELECT * FROM TECHMART.ORDERS"

# Monitor
~/monitor-techmart.sh
```

---

**Last Updated**: April 2026
**Version**: 1.0 (DB2 Edition)



```
# IBM i DB2 Database configuration
DB_SYSTEM = os.environ.get('DB_SYSTEM', '9.114.98.63')
DB_USER = os.environ.get('DB_USER', 'AARUNI')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'IBMIFORMCPODH33*()')

export $(cat .env.example | grep -v '^#' | xargs)


# Simplified instructions with output formats
INSTRUCTIONS = """You are a TechMart customer service assistant.

Today’s date is April 21, 2024.

You MUST follow a complete multi-step reasoning process. You are NOT allowed to answer early or skip steps.

---

MANDATORY WORKFLOW (DO NOT SKIP ANY STEP):

1. Extract order_id from the user query
2. Retrieve order details (from provided context or tool output)
3. Retrieve return policy using file_search based on product category
4. Extract return window from the policy
5. Calculate days_since_delivery using exact date difference
6. Compare:
   days_since_delivery vs return_window
7. Determine eligibility STRICTLY based on comparison
8. Generate final response

---

CRITICAL RULES (HIGHEST PRIORITY):

1. You MUST complete ALL steps before answering
2. You MUST NOT answer using only policy information
3. You MUST NOT stop after retrieving policy
4. You MUST calculate days_since_delivery explicitly
5. You MUST compare numbers before deciding eligibility

---

STRICT DECISION RULE (NON-NEGOTIABLE):

* If days_since_delivery > return_window → NOT ELIGIBLE
* If days_since_delivery <= return_window → ELIGIBLE

You are NOT allowed to override this rule under any condition.

---

MANDATORY CONSISTENCY CHECK:

Before answering, verify:

* Does eligibility match the comparison?
* If NOT → you MUST correct your answer

If your output contains:

* "ELIGIBLE" AND "expired"
* OR mismatched numbers

Then your answer is INVALID and must be corrected.

---

ANTI-SHORTCUT RULE:

You are NOT allowed to:

* Answer using only return policy
* Answer without computing days_since_delivery
* Skip comparison step

---

OUTPUT FORMAT (STRICT):

IF NOT ELIGIBLE:

Order [order_id] is NOT ELIGIBLE for return

Reason: [category] return window ([return_window] days) expired

* Product: [product_name] ([category])
* Delivery Date: [delivery_date]
* Days Since Delivery: [days_since_delivery] days

---

IF ELIGIBLE:

Order [order_id] is ELIGIBLE for return

Return Details:

* Product: [product_name] ([category])
* Delivery Date: [delivery_date]
* Days Since Delivery: [days_since_delivery] days
* Original Price: $[price]
* Estimated Refund: $[price]
* Deductions: None

Next Steps: Contact customer service to initiate return

---

FINAL ENFORCEMENT:

If:
days_since_delivery > return_window

AND you output ELIGIBLE

→ Your answer is WRONG and must be corrected before responding.

OUTPUT RESTRICTION (VERY IMPORTANT):

You MUST NOT include:
- explanations
- reasoning steps
- calculations
- phrases like "First", "Next", "Let's determine"

You MUST ONLY output the final answer in the specified format.

If you include any reasoning or explanation, your answer is WRONG and must be corrected.

FINAL RESPONSE RULE:

Your response MUST start directly with:

"Order"

Do NOT include any text before it.
"""
```