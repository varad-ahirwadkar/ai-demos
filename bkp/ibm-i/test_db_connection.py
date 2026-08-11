#!/usr/bin/env python3
"""
Database Connection Testing Utility
Tests connectivity to PostgreSQL and DB2 databases
"""

import os
import sys
import socket


def test_network_connectivity(host, port):
    """Test basic network connectivity to host:port"""
    print(f"\nTesting network connectivity to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        
        if result == 0:
            print(f"✓ Port {port} is open on {host}")
            return True
        else:
            print(f"✗ Port {port} is closed or unreachable on {host}")
            print(f"  Error code: {result}")
            return False
    except socket.gaierror:
        print(f"✗ Hostname {host} could not be resolved")
        return False
    except Exception as e:
        print(f"✗ Network test failed: {e}")
        return False


def test_postgresql_connection():
    """Test PostgreSQL connection"""
    print("\n" + "=" * 60)
    print("Testing PostgreSQL Connection")
    print("=" * 60)
    
    # Get configuration
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'techmart')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')
    
    print(f"\nConfiguration:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Database: {db}")
    print(f"  User: {user}")
    print(f"  Password: {'*' * len(password)}")
    
    # Test network connectivity
    if not test_network_connectivity(host, port):
        print("\n⚠ Network connectivity test failed")
        print("Possible issues:")
        print("  - PostgreSQL server is not running")
        print("  - Firewall is blocking the connection")
        print("  - Wrong hostname or port")
        return False
    
    # Test database connection
    try:
        import psycopg2
        print("\n✓ psycopg2 module is installed")
        
        print(f"\nAttempting to connect to PostgreSQL...")
        conn = psycopg2.connect(
            dbname=db,
            user=user,
            password=password,
            host=host,
            port=port,
            connect_timeout=10
        )
        
        print("✓ Successfully connected to PostgreSQL!")
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\nPostgreSQL version:")
        print(f"  {version}")
        
        cursor.close()
        conn.close()
        
        print("\n✓ PostgreSQL connection test PASSED")
        return True
        
    except ImportError:
        print("\n✗ psycopg2 module not installed")
        print("Install it with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Verify PostgreSQL is running: sudo systemctl status postgresql")
        print("  2. Check pg_hba.conf for access rules")
        print("  3. Verify database exists: psql -l")
        print("  4. Check credentials are correct")
        return False


def test_db2_connection():
    """Test DB2 connection"""
    print("\n" + "=" * 60)
    print("Testing DB2 Connection")
    print("=" * 60)
    
    # Get configuration
    host = os.getenv('DB2_HOSTNAME', 'localhost')
    port = os.getenv('DB2_PORT', '50000')
    db = os.getenv('DB2_DATABASE', 'SAMPLE')
    schema = os.getenv('DB2_SCHEMA', 'TECHMART')
    user = os.getenv('DB2_USERNAME', '')
    password = os.getenv('DB2_PASSWORD', '')
    
    print(f"\nConfiguration:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Database: {db}")
    print(f"  Schema: {schema}")
    print(f"  Username: {user}")
    print(f"  Password: {'*' * len(password) if password else '(not set)'}")
    
    if not user or not password:
        print("\n✗ DB2 username or password not set")
        print("Set them with:")
        print("  export DB2_USERNAME=your_username")
        print("  export DB2_PASSWORD=your_password")
        return False
    
    # Test network connectivity
    if not test_network_connectivity(host, port):
        print("\n⚠ Network connectivity test failed")
        print("Possible issues:")
        print("  - DB2 server is not running")
        print("  - Firewall is blocking the connection")
        print("  - Wrong hostname or port")
        print("  - DB2 instance not started (run: db2start)")
        return False
    
    # Test database connection
    try:
        import ibm_db
        print("\n✓ ibm_db module is installed")
        
        print(f"\nAttempting to connect to DB2...")
        conn_str = (
            f"DATABASE={db};"
            f"HOSTNAME={host};"
            f"PORT={port};"
            f"PROTOCOL=TCPIP;"
            f"UID={user};"
            f"PWD={password};"
        )
        
        conn = ibm_db.connect(conn_str, "", "")
        print("✓ Successfully connected to DB2!")
        
        # Test query
        stmt = ibm_db.exec_immediate(conn, "SELECT * FROM SYSIBM.SYSDUMMY1")
        row = ibm_db.fetch_tuple(stmt)
        print(f"\nTest query result: {row}")
        
        # Check if schema exists
        try:
            stmt = ibm_db.exec_immediate(conn, 
                f"SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = '{schema}'")
            row = ibm_db.fetch_tuple(stmt)
            if row:
                print(f"\n✓ Schema '{schema}' exists")
            else:
                print(f"\n⚠ Schema '{schema}' does not exist (will be created)")
        except:
            print(f"\n⚠ Could not check schema existence")
        
        ibm_db.close(conn)
        
        print("\n✓ DB2 connection test PASSED")
        return True
        
    except ImportError:
        print("\n✗ ibm_db module not installed")
        print("Install it with: pip install ibm_db")
        print("\nNote: You may need IBM Data Server Driver installed first")
        print("Download from: https://www.ibm.com/support/pages/download-initial-version-115-clients-and-drivers")
        return False
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Verify DB2 instance is started: db2start")
        print("  2. Check database exists: db2 list db directory")
        print("  3. Verify user has access: db2 connect to <database>")
        print("  4. Check DB2 is listening: netstat -an | grep <port>")
        print("  5. For IBM i, ensure QZDASOINIT jobs are available")
        print("  6. Check firewall rules allow connections")
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("Database Connection Testing Utility")
    print("=" * 60)
    
    db_type = os.getenv('DB_TYPE', 'postgresql').lower()
    
    if db_type == 'postgresql':
        success = test_postgresql_connection()
    elif db_type == 'db2':
        success = test_db2_connection()
    else:
        print(f"\n✗ Unknown database type: {db_type}")
        print("Set DB_TYPE to 'postgresql' or 'db2'")
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All tests PASSED - Ready to run database_setup.py")
    else:
        print("✗ Tests FAILED - Fix issues before running database_setup.py")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

# Made with Bob
