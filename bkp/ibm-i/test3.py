import pyodbc

print("=" * 60)
print("Testing IBM i ODBC Connection")
print("=" * 60)

conn_str = (
    "DRIVER={IBM i Access ODBC Driver};"
    "SYSTEM=9.114.98.63;"
    "UID=AARUNI;"
    "PWD=IBMIFORMCPODH33*();"
    "DBQ=TECHMART;"
)

try:
    print("\n[1] Connecting to IBM i...")
    conn = pyodbc.connect(conn_str)
    print("✓ Connection successful!")
    
    print("\n[2] Testing simple query...")
    cursor = conn.cursor()
    cursor.execute("SELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1")
    result = cursor.fetchone()
    print(f"✓ Connected to server: {result[0]}")
    
    print("\n[3] Querying ORDERS table...")
    cursor.execute("SELECT * FROM TECHMART.ORDERS FETCH FIRST 5 ROWS ONLY")
    
    # Get column names
    columns = [column[0] for column in cursor.description]
    print(f"✓ Columns: {', '.join(columns)}")
    
    # Fetch rows
    rows = cursor.fetchall()
    print(f"✓ Found {len(rows)} rows")
    
    if rows:
        print("\nFirst few rows:")
        for i, row in enumerate(rows, 1):
            print(f"  Row {i}: {row}")
    
    cursor.close()
    conn.close()
    print("\n✓ Connection closed successfully")
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS! ODBC connection works perfectly!")
    print("=" * 60)
    
except pyodbc.Error as e:
    print(f"\n✗ Connection failed!")
    print(f"Error: {e}")
    print("\nTroubleshooting:")
    print("1. Verify IBM i Access ODBC Driver is installed")
    print("2. Check credentials are correct")
    print("3. Verify network connectivity")
    
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
