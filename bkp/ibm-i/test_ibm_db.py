import ibm_db

# NOTE: Hostname is now 'localhost' and port is '50000'
# The tunnel handles the journey to the IBM i
conn_str = (
    "DATABASE=IBMIXMCP;"
    "HOSTNAME=9.114.98.63;"
    "PORT=446;"
    "PROTOCOL=TCPIP;"
    "AUTHENTICATION=SERVER_ENCRYPT;"
    "UID=aaruni;"
    "PWD=IBMIFORMCPODH33*();" # replace with your actual password
)

try:
    conn = ibm_db.connect(conn_str, "", "")
    print("✓ SUCCESS: Connected to IBM i via SSH Tunnel!")
    
    # Let's verify the data you inserted earlier
    sql = "SELECT COUNT(*) FROM TECHMART.ORDERS"
    stmt = ibm_db.exec_immediate(conn, sql)
    res = ibm_db.fetch_both(stmt)
    print(f"✓ MCP Check: Found {res[0]} orders in the database.")

except Exception as e:
    print(f"✗ Tunnel Connection Failed: {e}")