# IBM i DB2 Connection - Privilege Issue Solution

## Problem Identified

**Error**: `SQL30060N "AARUNI" does not have the privilege to perform operation "EXCSAT"`

This means the user `aaruni` doesn't have the necessary privileges to connect to the database server via DRDA.

## Solution Steps

### On IBM i System (Run these commands as QSECOFR or admin)

#### Step 1: Grant Database Server Access

```bash
# Grant authority to use QZDASOINIT program
GRTOBJAUT OBJ(QSYS/QZDASOINIT) OBJTYPE(*PGM) USER(AARUNI) AUT(*USE)

# Grant authority to QSYS library
GRTOBJAUT OBJ(QSYS) OBJTYPE(*LIB) USER(AARUNI) AUT(*USE)
```

#### Step 2: Grant Library/Schema Access

```bash
# Grant access to TECHMART library
GRTOBJAUT OBJ(TECHMART) OBJTYPE(*LIB) USER(AARUNI) AUT(*ALL)

# Grant access to ORDERS table
GRTOBJAUT OBJ(TECHMART/ORDERS) OBJTYPE(*FILE) USER(AARUNI) AUT(*ALL)
```

#### Step 3: Verify User Profile Settings

```bash
# Display user profile
DSPUSRPRF USRPRF(AARUNI)

# Check these settings:
# - Status: *ENABLED
# - User class: Should have appropriate class
# - Special authority: May need *JOBCTL or *IOSYSCFG
```

#### Step 4: Check DRDA Server Jobs

```bash
# Check if QZDASOINIT jobs are available
WRKACTJOB SBS(QUSRWRK)

# If no jobs, add prestart jobs
CHGPJE SBSD(QUSRWRK) PGM(QZDASOINIT) INLJOBS(10)

# Restart subsystem
ENDSBS SBS(QUSRWRK) OPTION(*IMMED)
STRSBS SBSD(QUSRWRK)
```

#### Step 5: Verify Service Ports

```bash
# Check service table
WRKSRVTBLE

# Look for these services:
# - as-database (port 8471)
# - as-database-s (port 9471)  
# - drda (port 446)
# - ddm-ssl (port 448)
```

### Alternative: Use Different Authentication

If you can't modify user privileges, try these alternatives:

#### Option 1: Use a Different User

Create or use a user with proper authorities:

```python
dsn = (
    "DATABASE=IBMIXMCP;"
    "HOSTNAME=9.114.98.63;"
    "PORT=446;"
    "PROTOCOL=TCPIP;"
    "UID=QSECOFR;"  # Or another admin user
    "PWD=password;"
    "CURRENTSCHEMA=TECHMART;"
)
```

#### Option 2: Use System Naming Convention

```python
dsn = (
    "DATABASE=IBMIXMCP;"
    "HOSTNAME=9.114.98.63;"
    "PORT=446;"
    "PROTOCOL=TCPIP;"
    "UID=aaruni;"
    "PWD=IBMIFORMCPODH33*();"
    "NAMING=1;"  # 0=SQL naming, 1=System naming
    "CURRENTSCHEMA=TECHMART;"
)
```

## Quick Test After Fixing Privileges

```python
import ibm_db

dsn = (
    "DATABASE=IBMIXMCP;"
    "HOSTNAME=9.114.98.63;"
    "PORT=446;"
    "PROTOCOL=TCPIP;"
    "UID=aaruni;"
    "PWD=IBMIFORMCPODH33*();"
    "CURRENTSCHEMA=TECHMART;"
)

conn = None
try:
    print("Attempting connection...")
    conn = ibm_db.connect(dsn, "", "")
    print("✓ Connection successful!")
    
    # Test query
    sql = "SELECT CURRENT DATE FROM SYSIBM.SYSDUMMY1"
    stmt = ibm_db.exec_immediate(conn, sql)
    row = ibm_db.fetch_assoc(stmt)
    print(f"✓ Query successful! Current date: {row['1']}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    
finally:
    if conn:
        ibm_db.close(conn)
```

## Common SQL Codes

- **SQL30060N**: User lacks EXCSAT privilege → Grant QZDASOINIT access
- **SQL30081N**: Communication error → Check port/firewall
- **SQL30082N**: Authentication failed → Check username/password
- **SQL1013N**: Database not found → Check RDB name
- **SQL0902C**: System error → Check QZDASOINIT jobs

## Contact IBM i Administrator

If you don't have admin access, provide this information to your IBM i administrator:

```
User: AARUNI
Issue: Cannot connect to DB2 via DRDA (SQL30060N)
Required: Grant authority to QZDASOINIT program and TECHMART library

Commands needed:
GRTOBJAUT OBJ(QSYS/QZDASOINIT) OBJTYPE(*PGM) USER(AARUNI) AUT(*USE)
GRTOBJAUT OBJ(TECHMART) OBJTYPE(*LIB) USER(AARUNI) AUT(*ALL)