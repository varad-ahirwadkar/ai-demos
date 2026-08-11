# Source - https://stackoverflow.com/a/48977705
# Posted by Hassan Abedi
# Retrieved 2026-04-23, License - CC BY-SA 3.0

import ibm_db as db2

def make_connexion_with_schema():
    """Try connection with CURRENTSCHEMA"""
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=AARUNI;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    return db2.connect(dsn, "", "")

def make_connexion_without_schema():
    """Try connection without CURRENTSCHEMA"""
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=AARUNI;"
        "PWD=IBMIFORMCPODH33*();"
    )
    return db2.connect(dsn, "", "")

def make_connexion_with_aaruni_schema():
    """Try connection with AARUNI as schema"""
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=AARUNI;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=AARUNI;"
    )
    return db2.connect(dsn, "", "")

# Test different connection methods
print("=" * 60)
print("Testing IBM i DB2 Connection Methods")
print("=" * 60)

# Test 1: Without CURRENTSCHEMA
print("\n[Test 1] Connecting WITHOUT CURRENTSCHEMA...")
try:
    connexion = make_connexion_without_schema()
    print("✓ Connection successful!")
    
    # Test a simple query
    stmt = db2.exec_immediate(connexion, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Connected to server: {result[0]}")
    
    db2.close(connexion)
    print("✓ Connection closed successfully")
    print("\n*** SUCCESS: Connection works WITHOUT CURRENTSCHEMA ***\n")
except Exception as e:
    print(f"✗ Failed: {e}\n")

# Test 2: With CURRENTSCHEMA=TECHMART
print("[Test 2] Connecting WITH CURRENTSCHEMA=TECHMART...")
try:
    connexion = make_connexion_with_schema()
    print("✓ Connection successful!")
    
    # Test a simple query
    stmt = db2.exec_immediate(connexion, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Connected to server: {result[0]}")
    
    db2.close(connexion)
    print("✓ Connection closed successfully")
    print("\n*** SUCCESS: Connection works WITH CURRENTSCHEMA=TECHMART ***\n")
except Exception as e:
    print(f"✗ Failed: {e}\n")

# Test 3: With CURRENTSCHEMA=AARUNI
print("[Test 3] Connecting WITH CURRENTSCHEMA=AARUNI...")
try:
    connexion = make_connexion_with_aaruni_schema()
    print("✓ Connection successful!")
    
    # Test a simple query
    stmt = db2.exec_immediate(connexion, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Connected to server: {result[0]}")
    
    db2.close(connexion)
    print("✓ Connection closed successfully")
    print("\n*** SUCCESS: Connection works WITH CURRENTSCHEMA=AARUNI ***\n")
except Exception as e:
    print(f"✗ Failed: {e}\n")

print("=" * 60)


# conn_str = (
#     "DATABASE=IBMIXMCP;"
#     "HOSTNAME=localhost;"
#     "PORT=50000;"
#     "PROTOCOL=TCPIP;"
#     "AUTHENTICATION=SERVER;"
#     "SECURITY=NONE;"
#     "UID=aaruni;"
#     "PWD=IBMIFORMCPODH33*();" # replace with your actual password
# )