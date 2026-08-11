# IBM i DB2 Remote Connection Guide - Python SDK
## Based on Official IBM i Access Client Solutions Documentation

This guide provides step-by-step instructions for connecting to IBM i DB2 database from remote Python applications, based on the official IBM i 7.3 documentation.

---

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [IBM i Server Configuration](#ibm-i-server-configuration)
4. [Python Client Setup](#python-client-setup)
5. [Connection Methods](#connection-methods)
6. [Code Examples](#code-examples)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### What is IBM i DB2 Access?

IBM i DB2 for i provides remote database access through:
- **DRDA (Distributed Relational Database Architecture)** - Industry standard protocol
- **ODBC, ADO, OLE DB, and .NET Data Provider interfaces**
- **Remote SQL access** via TCP/IP

### Key Components

**Server Side (IBM i):**
- `QZDASOINIT` - Main database server program (QSYS library)
- `QZDASON2` - Sockets setup program
- `QZDASRVSD` - Daemon program  
- `QZDASSINIT` - SSL server program

**Client Side:**
- `ibm_db` - Python driver for DB2 connectivity
- TCP/IP network connection

---

## Prerequisites

### IBM i Server Requirements
- **IBM i OS**: Version 7.1 or higher (7.3+ recommended)
- **DB2 for i**: Native to IBM i (pre-installed)
- **TCP/IP**: Configured and active
- **DRDA**: Enabled (default)
- **User Profile**: With appropriate database permissions

### Client Requirements
- **Python**: 3.6 or higher
- **Network**: TCP/IP connectivity to IBM i system
- **IBM Data Server Driver**: Installed with `ibm_db` package

---

## IBM i Server Configuration

### Step 1: Verify Database Server is Running

```bash
# On IBM i command line
WRKACTJOB SBS(QUSRWRK)
# Look for QZDASOINIT jobs
```

### Step 2: Check Service Table Entries

According to IBM documentation, IBM i uses specific ports for database services:

```bash
# Display service table entries
WRKSRVTBLE

# Key services and ports:
# as-database    - Port 8471 (non-secure)
# as-database-s  - Port 9471 (secure)
# ddm-ssl        - Port 448  (DRDA/DDM SSL)
```

**Important**: IBM i typically uses **port 446** or **448** for DRDA connections, NOT port 50000 (which is for LUW DB2).

### Step 3: Verify RDB (Relational Database) Name

```bash
# On IBM i
WRKRDBDIRE

# Or using SQL
SELECT * FROM QSYS2.ASP_INFO
```

Common RDB names:
- `*LOCAL` - Local database
- System name (e.g., `IBMIXMCP`)
- Custom RDB name

### Step 4: Configure User Permissions

```bash
# Grant database access to user
GRTOBJAUT OBJ(QSYS/QZDASOINIT) OBJTYPE(*PGM) USER(username) AUT(*USE)

# Grant access to specific library/schema
GRTOBJAUT OBJ(LIBNAME) OBJTYPE(*LIB) USER(username) AUT(*ALL)
```

---

## Python Client Setup

### Step 1: Install IBM DB2 Driver

```bash
# Install ibm_db package
pip install ibm_db

# Optional: Install SQLAlchemy adapter
pip install ibm_db_sa
```

### Step 2: Verify Installation

```python
import ibm_db
print("IBM DB2 driver installed successfully!")
```

---

## Connection Methods

### Method 1: Direct Connection String (Recommended)

Based on IBM i documentation, use this connection format:

```python
import ibm_db

# Connection string for IBM i
dsn = (
    "DATABASE=IBMIXMCP;"        # RDB name (use WRKRDBDIRE to find)
    "HOSTNAME=9.114.98.63;"     # IBM i hostname or IP
    "PORT=446;"                 # IBM i default port (446 or 448)
    "PROTOCOL=TCPIP;"
    "UID=username;"             # IBM i user profile
    "PWD=password;"             # User password
    "CURRENTSCHEMA=TECHMART;"   # Default library/schema (optional)
)

try:
    conn = ibm_db.connect(dsn, "", "")
    print("✓ Successfully connected to IBM i DB2!")
except Exception as e:
    print(f"✗ Connection failed: {e}")
finally:
    if conn:
        ibm_db.close(conn)
```

### Method 2: Using Environment Variables

```python
import ibm_db
import os

# Build connection string from environment
dsn = (
    f"DATABASE={os.getenv('DB2_DATABASE')};"
    f"HOSTNAME={os.getenv('DB2_HOSTNAME')};"
    f"PORT={os.getenv('DB2_PORT', '446')};"
    f"PROTOCOL=TCPIP;"
    f"UID={os.getenv('DB2_USERNAME')};"
    f"PWD={os.getenv('DB2_PASSWORD')};"
    f"CURRENTSCHEMA={os.getenv('DB2_SCHEMA', 'QGPL')};"
)

conn = ibm_db.connect(dsn, "", "")
```

### Method 3: SSL/TLS Secure Connection

For secure connections using port 448 or 9471:

```python
dsn = (
    "DATABASE=IBMIXMCP;"
    "HOSTNAME=9.114.98.63;"
    "PORT=448;"                 # SSL port
    "PROTOCOL=TCPIP;"
    "UID=username;"
    "PWD=password;"
    "SECURITY=SSL;"             # Enable SSL
    "CURRENTSCHEMA=TECHMART;"
)

conn = ibm_db.connect(dsn, "", "")
```

---

## Code Examples

### Example 1: Basic Query Execution

```python
import ibm_db

def connect_to_ibm_i():
    """Connect to IBM i DB2 database"""
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    
    try:
        conn = ibm_db.connect(dsn, "", "")
        print("✓ Connected to IBM i DB2!")
        return conn
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None

def execute_query(conn, sql):
    """Execute SQL query and return results"""
    try:
        stmt = ibm_db.exec_immediate(conn, sql)
        results = []
        
        row = ibm_db.fetch_assoc(stmt)
        while row:
            results.append(row)
            row = ibm_db.fetch_assoc(stmt)
        
        return results
    except Exception as e:
        print(f"✗ Query failed: {e}")
        return []

# Usage
conn = connect_to_ibm_i()
if conn:
    # Query with IBM i SQL syntax
    results = execute_query(
        conn, 
        "SELECT * FROM ORDERS FETCH FIRST 10 ROWS ONLY"
    )
    
    for row in results:
        print(row)
    
    ibm_db.close(conn)
```

### Example 2: Prepared Statements (Parameterized Queries)

```python
import ibm_db

def get_order_by_id(conn, order_id):
    """Get order using prepared statement"""
    sql = "SELECT * FROM ORDERS WHERE ORDER_ID = ?"
    
    try:
        # Prepare statement
        stmt = ibm_db.prepare(conn, sql)
        
        # Bind parameter
        ibm_db.bind_param(stmt, 1, order_id)
        
        # Execute
        ibm_db.execute(stmt)
        
        # Fetch result
        row = ibm_db.fetch_assoc(stmt)
        return row
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

# Usage
conn = connect_to_ibm_i()
if conn:
    order = get_order_by_id(conn, 'ORD-2024-001')
    if order:
        print(f"Order: {order['ORDER_ID']} - {order['PRODUCT_NAME']}")
    ibm_db.close(conn)
```

### Example 3: Insert Data

```python
import ibm_db

def insert_order(conn, order_data):
    """Insert new order record"""
    sql = """
        INSERT INTO ORDERS 
        (ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, PRICE, ORDER_DATE, STATUS)
        VALUES (?, ?, ?, ?, CURRENT DATE, ?)
    """
    
    try:
        stmt = ibm_db.prepare(conn, sql)
        
        # Bind parameters
        ibm_db.bind_param(stmt, 1, order_data['order_id'])
        ibm_db.bind_param(stmt, 2, order_data['email'])
        ibm_db.bind_param(stmt, 3, order_data['product'])
        ibm_db.bind_param(stmt, 4, order_data['price'])
        ibm_db.bind_param(stmt, 5, order_data['status'])
        
        # Execute
        ibm_db.execute(stmt)
        print("✓ Order inserted successfully!")
        return True
    except Exception as e:
        print(f"✗ Insert failed: {e}")
        return False

# Usage
conn = connect_to_ibm_i()
if conn:
    order = {
        'order_id': 'ORD-2024-100',
        'email': 'customer@example.com',
        'product': 'IBM i Cloud Service',
        'price': 999.99,
        'status': 'NEW'
    }
    insert_order(conn, order)
    ibm_db.close(conn)
```

### Example 4: Complete DB2 Adapter Class

```python
import ibm_db
import os
from typing import List, Dict, Any, Optional

class IBMiDB2Adapter:
    """
    Adapter for IBM i DB2 database connections
    Based on IBM i Access Client Solutions documentation
    """
    
    def __init__(self):
        """Initialize with environment variables"""
        self.database = os.getenv('DB2_DATABASE', 'SAMPLE')
        self.hostname = os.getenv('DB2_HOSTNAME', 'localhost')
        self.port = os.getenv('DB2_PORT', '446')  # IBM i default
        self.username = os.getenv('DB2_USERNAME')
        self.password = os.getenv('DB2_PASSWORD')
        self.schema = os.getenv('DB2_SCHEMA', 'QGPL')
        self.conn = None
    
    def connect(self) -> bool:
        """Establish connection to IBM i DB2"""
        try:
            dsn = (
                f"DATABASE={self.database};"
                f"HOSTNAME={self.hostname};"
                f"PORT={self.port};"
                f"PROTOCOL=TCPIP;"
                f"UID={self.username};"
                f"PWD={self.password};"
                f"CURRENTSCHEMA={self.schema};"
            )
            
            self.conn = ibm_db.connect(dsn, "", "")
            print(f"✓ Connected to IBM i DB2: {self.database}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection"""
        if self.conn:
            ibm_db.close(self.conn)
            self.conn = None
            print("✓ Disconnected from IBM i DB2")
    
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute SELECT query with optional parameters"""
        if not self.conn:
            if not self.connect():
                return []
        
        try:
            if params:
                stmt = ibm_db.prepare(self.conn, sql)
                for i, param in enumerate(params, start=1):
                    ibm_db.bind_param(stmt, i, param)
                ibm_db.execute(stmt)
            else:
                stmt = ibm_db.exec_immediate(self.conn, sql)
            
            results = []
            row = ibm_db.fetch_assoc(stmt)
            while row:
                # Convert to lowercase keys for consistency
                row_dict = {k.lower(): v for k, v in row.items()}
                results.append(row_dict)
                row = ibm_db.fetch_assoc(stmt)
            
            return results
        except Exception as e:
            print(f"✗ Query failed: {e}")
            return []
    
    def execute_update(self, sql: str, params: tuple = None) -> bool:
        """Execute INSERT/UPDATE/DELETE"""
        if not self.conn:
            if not self.connect():
                return False
        
        try:
            if params:
                stmt = ibm_db.prepare(self.conn, sql)
                for i, param in enumerate(params, start=1):
                    ibm_db.bind_param(stmt, i, param)
                ibm_db.execute(stmt)
            else:
                ibm_db.exec_immediate(self.conn, sql)
            
            return True
        except Exception as e:
            print(f"✗ Update failed: {e}")
            return False

# Usage Example
if __name__ == "__main__":
    # Set environment variables
    os.environ['DB2_DATABASE'] = 'IBMIXMCP'
    os.environ['DB2_HOSTNAME'] = '9.114.98.63'
    os.environ['DB2_PORT'] = '446'
    os.environ['DB2_USERNAME'] = 'aaruni'
    os.environ['DB2_PASSWORD'] = 'IBMIFORMCPODH33*()'
    os.environ['DB2_SCHEMA'] = 'TECHMART'
    
    # Create adapter and connect
    db = IBMiDB2Adapter()
    if db.connect():
        # Query data
        orders = db.execute_query(
            "SELECT * FROM ORDERS WHERE STATUS = ? FETCH FIRST 5 ROWS ONLY",
            ('Delivered',)
        )
        
        for order in orders:
            print(f"Order: {order['order_id']} - {order['product_name']}")
        
        db.disconnect()
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Connection Timeout (SQL30081N)

**Error**: `SQL30081N A communication error has been detected`

**Solutions**:
```bash
# Check IBM i system is reachable
ping <hostname>

# Check port is open (IBM i uses 446, not 50000)
telnet <hostname> 446

# Verify QZDASOINIT jobs are running
WRKACTJOB SBS(QUSRWRK)

# Check service table
WRKSRVTBLE
```

#### 2. Wrong Port Number

**Issue**: Using port 50000 (LUW DB2) instead of IBM i ports

**Solution**: IBM i uses different ports:
- **Port 446** - Standard DRDA (most common)
- **Port 448** - DRDA with SSL
- **Port 8471** - as-database (non-secure)
- **Port 9471** - as-database-s (secure)

```python
# Correct for IBM i
dsn = "...PORT=446;..."  # NOT 50000
```

#### 3. Database Not Found (SQL1013N)

**Error**: `SQL1013N The database alias name or database name could not be found`

**Solutions**:
```bash
# On IBM i, check RDB directory
WRKRDBDIRE

# Use correct RDB name
# For local: DATABASE=*LOCAL or DATABASE=<system_name>
```

```python
# Try with system name or *LOCAL
dsn = "DATABASE=*LOCAL;..."
# or
dsn = "DATABASE=IBMIXMCP;..."
```

#### 4. Schema/Library Not Found

**Error**: Table or view not found

**Solutions**:
```python
# Set schema in connection string
dsn = "...CURRENTSCHEMA=TECHMART;..."

# Or set after connection
ibm_db.exec_immediate(conn, "SET SCHEMA TECHMART")

# Or use fully qualified names
sql = "SELECT * FROM TECHMART.ORDERS"
```

#### 5. Authentication Failed (SQL30082N)

**Error**: `SQL30082N Security processing failed`

**Solutions**:
- Verify username and password are correct
- Check user profile: `DSPUSRPRF USRPRF(username)`
- Ensure user has database authority
- Check password hasn't expired

#### 6. QZDASOINIT Jobs Not Available

**Issue**: No prestart jobs available

**Solutions**:
```bash
# Check subsystem
WRKSBSJOB SBS(QUSRWRK)

# Add more prestart jobs if needed
CHGPJE SBSD(QUSRWRK) PGM(QZDASOINIT) INLJOBS(10)

# End and restart subsystem
ENDSBS SBS(QUSRWRK) OPTION(*IMMED)
STRSBS SBSD(QUSRWRK)
```

---

## Environment Variables Template

Create a `.env` file:

```bash
# IBM i DB2 Configuration
DB2_DATABASE=IBMIXMCP         # RDB name (use WRKRDBDIRE to find)
DB2_HOSTNAME=9.114.98.63      # IBM i hostname or IP
DB2_PORT=446                  # IBM i default port (446 or 448)
DB2_USERNAME=aaruni           # IBM i user profile
DB2_PASSWORD=IBMIFORMCPODH33*()  # User password
DB2_SCHEMA=TECHMART           # Default library/schema

# Optional Settings
DB2_SECURITY=SSL              # Enable SSL (optional)
DB2_TIMEOUT=30                # Connection timeout in seconds
```

Load in Python:
```python
from dotenv import load_dotenv
import os

load_dotenv()

# Access variables
database = os.getenv('DB2_DATABASE')
hostname = os.getenv('DB2_HOSTNAME')
```

---

## Key Differences: IBM i vs LUW DB2

| Feature | IBM i DB2 | LUW DB2 |
|---------|-----------|---------|
| **Default Port** | 446 or 448 | 50000 |
| **Schema Concept** | Libraries (QSYS2) | Schemas |
| **Database Name** | RDB name or *LOCAL | Database name |
| **System Tables** | QSYS2.* | SYSCAT.* |
| **Server Programs** | QZDASOINIT | db2sysc |
| **Case Sensitivity** | Uppercase default | Mixed case |
| **SQL Syntax** | IBM i SQL | DB2 LUW SQL |

---

## Testing Connection Script

```python
#!/usr/bin/env python3
"""Test IBM i DB2 connection based on official documentation"""

import ibm_db
import sys

def test_connection():
    """Test connection to IBM i DB2"""
    
    # Configuration (update with your values)
    config = {
        'database': 'IBMIXMCP',
        'hostname': '9.114.98.63',
        'port': '446',              # IBM i default
        'username': 'aaruni',
        'password': 'IBMIFORMCPODH33*()',
        'schema': 'TECHMART'
    }
    
    print("=" * 60)
    print("IBM i DB2 Connection Test")
    print("=" * 60)
    print(f"Database: {config['database']}")
    print(f"Hostname: {config['hostname']}")
    print(f"Port: {config['port']}")
    print(f"Username: {config['username']}")
    print(f"Schema: {config['schema']}")
    print("=" * 60)
    
    # Build connection string
    dsn = (
        f"DATABASE={config['database']};"
        f"HOSTNAME={config['hostname']};"
        f"PORT={config['port']};"
        f"PROTOCOL=TCPIP;"
        f"UID={config['username']};"
        f"PWD={config['password']};"
        f"CURRENTSCHEMA={config['schema']};"
    )
    
    try:
        # Attempt connection
        print("\nAttempting connection...")
        conn = ibm_db.connect(dsn, "", "")
        print("✓ Connection successful!")
        
        # Test query
        print("\nTesting query...")
        sql = "SELECT CURRENT DATE, CURRENT TIME FROM SYSIBM.SYSDUMMY1"
        stmt = ibm_db.exec_immediate(conn, sql)
        row = ibm_db.fetch_assoc(stmt)
        
        if row:
            print("✓ Query successful!")
            print(f"  Current Date: {row['1']}")
            print(f"  Current Time: {row['2']}")
        
        # Close connection
        ibm_db.close(conn)
        print("\n✓ Connection closed")
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Connection failed!")
        print(f"Error: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
```

---

## Additional Resources

- **IBM i Documentation**: https://www.ibm.com/docs/en/i
- **IBM i Access Client Solutions PDF**: https://www.ibm.com/docs/es/ssw_ibm_i_73/pdf/rzajrpdf.pdf
- **ibm_db Python Driver**: https://github.com/ibmdb/python-ibmdb
- **IBM Data Server Driver**: https://www.ibm.com/support/pages/download-initial-version-115-clients-and-drivers
- **IBM i SQL Reference**: https://www.ibm.com/docs/en/i/7.5?topic=reference-sql

---

**Document Version**: 1.0  
**Last Updated**: April 2026  
**Based on**: IBM i 7.3 Access Client Solutions Documentation