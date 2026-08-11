import ibm_db as db2

print("=" * 60)
print("Testing Alternative IBM i DB2 Connection Methods")
print("=" * 60)

# Method 1: Minimal connection (no CURRENTSCHEMA, no AUTHENTICATION)
print("\n[Method 1] Minimal connection (no extras)...")
try:
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=QSECOFR;"
        "PWD=IBMIFORMCPODH33*();"
    )
    conn = db2.connect(dsn, "", "")
    print("✓ SUCCESS! Minimal connection works!")
    
    stmt = db2.exec_immediate(conn, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Server: {result[0]}")
    
    db2.close(conn)
except Exception as e:
    print(f"✗ Failed: {e}")

# Method 2: With SERVER authentication
print("\n[Method 2] With AUTHENTICATION=SERVER...")
try:
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=QSECOFR;"
        "PWD=IBMIFORMCPODH33*();"
        "AUTHENTICATION=SERVER;"
    )
    conn = db2.connect(dsn, "", "")
    print("✓ SUCCESS! SERVER authentication works!")
    
    stmt = db2.exec_immediate(conn, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Server: {result[0]}")
    
    db2.close(conn)
except Exception as e:
    print(f"✗ Failed: {e}")

# Method 3: With SERVER_ENCRYPT authentication
print("\n[Method 3] With AUTHENTICATION=SERVER_ENCRYPT...")
try:
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=QSECOFR;"
        "PWD=IBMIFORMCPODH33*();"
        "AUTHENTICATION=SERVER_ENCRYPT;"
    )
    conn = db2.connect(dsn, "", "")
    print("✓ SUCCESS! SERVER_ENCRYPT authentication works!")
    
    stmt = db2.exec_immediate(conn, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Server: {result[0]}")
    
    db2.close(conn)
except Exception as e:
    print(f"✗ Failed: {e}")

# Method 4: Using *LOCAL as database name
print("\n[Method 4] Using *LOCAL as database...")
try:
    dsn = (
        "DATABASE=*LOCAL;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=QSECOFR;"
        "PWD=IBMIFORMCPODH33*();"
    )
    conn = db2.connect(dsn, "", "")
    print("✓ SUCCESS! *LOCAL database works!")
    
    stmt = db2.exec_immediate(conn, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Server: {result[0]}")
    
    db2.close(conn)
except Exception as e:
    print(f"✗ Failed: {e}")

# Method 5: Using system name as database
print("\n[Method 5] Using IBMIXMCP as system...")
try:
    dsn = (
        "SYSTEM=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=QSECOFR;"
        "PWD=IBMIFORMCPODH33*();"
    )
    conn = db2.connect(dsn, "", "")
    print("✓ SUCCESS! SYSTEM parameter works!")
    
    stmt = db2.exec_immediate(conn, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Server: {result[0]}")
    
    db2.close(conn)
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n" + "=" * 60)

# Made with Bob
