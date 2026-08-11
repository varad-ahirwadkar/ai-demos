#!/usr/bin/env python3
"""
Diagnostic script for IBM i DB2 connection issues
Tests multiple connection configurations
"""

import ibm_db
import sys

def test_connection(config_name, dsn):
    """Test a specific connection configuration"""
    print(f"\n{'='*60}")
    print(f"Testing: {config_name}")
    print(f"{'='*60}")
    print(f"DSN: {dsn}")
    
    conn = None
    try:
        conn = ibm_db.connect(dsn, "", "")
        print("✓ Connection successful!")
        
        # Test a simple query
        sql = "SELECT CURRENT DATE, CURRENT TIME FROM SYSIBM.SYSDUMMY1"
        stmt = ibm_db.exec_immediate(conn, sql)
        row = ibm_db.fetch_assoc(stmt)
        
        if row:
            print("✓ Query successful!")
            print(f"  Current Date: {row['1']}")
            print(f"  Current Time: {row['2']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Connection failed!")
        print(f"  Error: {e}")
        return False
        
    finally:
        if conn:
            ibm_db.close(conn)
            print("✓ Connection closed")

def main():
    """Test multiple connection configurations"""
    
    print("="*60)
    print("IBM i DB2 Connection Diagnostic Tool")
    print("="*60)
    
    # Configuration 1: Port 446 (IBM i standard DRDA)
    dsn1 = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    
    # Configuration 2: Port 448 (IBM i DRDA with SSL)
    dsn2 = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=448;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    
    # Configuration 3: Port 8471 (as-database non-secure)
    dsn3 = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=8471;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    
    # Configuration 4: Port 50000 (LUW DB2 - for comparison)
    dsn4 = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=50000;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    
    # Configuration 5: Using *LOCAL as database
    dsn5 = (
        "DATABASE=*LOCAL;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
        "CURRENTSCHEMA=TECHMART;"
    )
    
    # Configuration 6: Without CURRENTSCHEMA
    dsn6 = (
        "DATABASE=IBMIXMCP;"
        "HOSTNAME=9.114.98.63;"
        "PORT=446;"
        "PROTOCOL=TCPIP;"
        "UID=aaruni;"
        "PWD=IBMIFORMCPODH33*();"
    )
    
    configs = [
        ("Port 446 (IBM i standard DRDA)", dsn1),
        ("Port 448 (IBM i DRDA with SSL)", dsn2),
        ("Port 8471 (as-database non-secure)", dsn3),
        ("Port 50000 (LUW DB2 style)", dsn4),
        ("Using *LOCAL database", dsn5),
        ("Without CURRENTSCHEMA", dsn6),
    ]
    
    results = []
    for name, dsn in configs:
        success = test_connection(name, dsn)
        results.append((name, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, success in results:
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{status}: {name}")
    
    print(f"{'='*60}")
    
    # Return exit code
    any_success = any(success for _, success in results)
    return 0 if any_success else 1

if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
