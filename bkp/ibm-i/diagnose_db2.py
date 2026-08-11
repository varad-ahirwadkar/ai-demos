#!/usr/bin/env python3
"""
DB2 Diagnostic Script
Helps diagnose DB2 connection and system issues
"""

import os
import sys
import subprocess


def run_command(cmd, description):
    """Run a shell command and display results"""
    print(f"\n{description}")
    print(f"Command: {cmd}")
    print("-" * 60)
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Error: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Command timed out")
        return False
    except Exception as e:
        print(f"Failed to run command: {e}")
        return False


def check_db2_environment():
    """Check DB2 environment variables"""
    print("\n" + "=" * 60)
    print("DB2 Environment Variables")
    print("=" * 60)
    
    env_vars = [
        'DB2_DATABASE', 'DB2_HOSTNAME', 'DB2_PORT', 
        'DB2_USERNAME', 'DB2_SCHEMA', 'DB2INSTANCE',
        'DB2_HOME', 'LD_LIBRARY_PATH', 'LIBPATH'
    ]
    
    for var in env_vars:
        value = os.getenv(var, '(not set)')
        if var in ['DB2_PASSWORD']:
            value = '***' if value != '(not set)' else value
        print(f"  {var}: {value}")


def check_db2_driver():
    """Check if DB2 driver is properly installed"""
    print("\n" + "=" * 60)
    print("DB2 Driver Check")
    print("=" * 60)
    
    try:
        import ibm_db
        print("✓ ibm_db module is installed")
        
        # Try to get version info
        try:
            print(f"  Version: {ibm_db.__version__ if hasattr(ibm_db, '__version__') else 'Unknown'}")
        except:
            pass
            
        return True
    except ImportError as e:
        print(f"✗ ibm_db module not installed: {e}")
        print("\nInstall with: pip install ibm_db")
        return False


def suggest_fixes_for_sql0902c():
    """Provide suggestions for SQL0902C error"""
    print("\n" + "=" * 60)
    print("SQL0902C Error - System Error")
    print("=" * 60)
    
    print("""
This error indicates a system-level problem with DB2. Common causes:

1. DATABASE NOT STARTED
   - Check if database is started
   - Run: db2 activate database <dbname>
   
2. INSUFFICIENT MEMORY
   - DB2 may not have enough memory allocated
   - Check database configuration
   - Run: db2 get db cfg for <dbname> | grep -i mem
   
3. CORRUPTED DATABASE
   - Database may need recovery
   - Run: db2 restart database <dbname>
   
4. WRONG DATABASE NAME
   - Verify database exists
   - Run: db2 list db directory
   
5. INSTANCE NOT STARTED
   - DB2 instance may not be running
   - Run: db2start
   
6. AUTHENTICATION ISSUES
   - Check user permissions
   - Verify user can connect: db2 connect to <dbname> user <username>
   
7. NETWORK/PROTOCOL ISSUES
   - For remote connections, verify TCPIP is configured
   - Check: db2 get dbm cfg | grep SVCENAME
   
8. FOR IBM i SYSTEMS
   - Ensure QZDASOINIT jobs are available
   - Check subsystem: WRKACTJOB SBS(QUSRWRK)
   - Verify SQL package: DSPLIB QSYS2
   
RECOMMENDED ACTIONS:
1. Connect directly using DB2 CLI to isolate the issue:
   db2 connect to <database> user <username>
   
2. Check DB2 diagnostic log:
   db2diag -H <hostname>
   
3. Verify database is active:
   db2 list active databases
   
4. Try restarting the instance:
   db2stop
   db2start
""")


def test_simple_connection():
    """Test a simple DB2 connection"""
    print("\n" + "=" * 60)
    print("Testing Simple DB2 Connection")
    print("=" * 60)
    
    try:
        import ibm_db
        
        db = os.getenv('DB2_DATABASE', 'SAMPLE')
        host = os.getenv('DB2_HOSTNAME', 'localhost')
        port = os.getenv('DB2_PORT', '50000')
        user = os.getenv('DB2_USERNAME', '')
        pwd = os.getenv('DB2_PASSWORD', '')
        
        if not user or not pwd:
            print("✗ DB2_USERNAME or DB2_PASSWORD not set")
            return False
        
        print(f"Attempting connection to:")
        print(f"  Database: {db}")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  User: {user}")
        
        # Try with minimal connection string first
        conn_str = f"DATABASE={db};HOSTNAME={host};PORT={port};PROTOCOL=TCPIP;UID={user};PWD={pwd};"
        
        print("\nConnecting...")
        conn = ibm_db.connect(conn_str, "", "")
        
        if conn:
            print("✓ Connection successful!")
            
            # Try a simple query
            try:
                stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")
                row = ibm_db.fetch_tuple(stmt)
                print(f"✓ Query successful: {row[0]}")
            except Exception as e:
                print(f"⚠ Query failed: {e}")
            
            ibm_db.close(conn)
            return True
        else:
            print("✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print(f"\nError type: {type(e).__name__}")
        
        # Check if it's the SQL0902C error
        if 'SQL0902C' in str(e):
            suggest_fixes_for_sql0902c()
        
        return False


def main():
    """Main diagnostic function"""
    print("=" * 60)
    print("DB2 Diagnostic Tool")
    print("=" * 60)
    
    # Check environment
    check_db2_environment()
    
    # Check driver
    if not check_db2_driver():
        sys.exit(1)
    
    # Test connection
    test_simple_connection()
    
    print("\n" + "=" * 60)
    print("Diagnostic Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()

# Made with Bob
