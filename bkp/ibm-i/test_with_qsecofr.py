import ibm_db as db2

print("=" * 60)
print("Testing IBM i DB2 Connection with QSECOFR")
print("=" * 60)

# Test with QSECOFR (has all authorities)
print("\nConnecting with QSECOFR and CURRENTSCHEMA=TECHMART...")
try:
    dsn = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=QSECOFR;"
        "PWD=IBMIFORMCPODH33*();"  # Use QSECOFR password
        "CURRENTSCHEMA=TECHMART;"
    )
    
    connexion = db2.connect(dsn, "", "")
    print("✓ Connection successful!")
    
    # Test a simple query
    stmt = db2.exec_immediate(connexion, "SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = db2.fetch_tuple(stmt)
    print(f"✓ Connected to server: {result[0]}")
    
    # List tables in TECHMART
    print("\nListing tables in TECHMART schema...")
    stmt = db2.exec_immediate(connexion, 
        "SELECT TABLE_NAME FROM QSYS2.SYSTABLES WHERE TABLE_SCHEMA='TECHMART' FETCH FIRST 10 ROWS ONLY")
    
    row = db2.fetch_tuple(stmt)
    if row:
        print("Tables found:")
        while row:
            print(f"  - {row[0]}")
            row = db2.fetch_tuple(stmt)
    else:
        print("  No tables found in TECHMART schema")
    
    db2.close(connexion)
    print("\n✓ Connection closed successfully")
    print("\n*** If this works, the issue is with AARUNI's authorities ***")
    
except Exception as e:
    print(f"✗ Failed: {e}")
    print("\n*** If QSECOFR also fails, there's a server configuration issue ***")

print("=" * 60)

# Made with Bob
