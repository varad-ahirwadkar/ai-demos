#!/usr/bin/env python3
"""
Simple Database Setup Script
Creates table and inserts sample data directly (no CSV required)
Supports PostgreSQL and IBM DB2
"""

import os
import sys
from datetime import datetime, timedelta

# Database type
DB_TYPE = os.getenv('DB_TYPE', 'postgresql')  # 'postgresql' or 'db2'


def setup_postgresql():
    """Setup PostgreSQL database with table and data"""
    try:
        import psycopg2
        
        # Connection parameters
        conn = psycopg2.connect(
            dbname=os.getenv('POSTGRES_DB', 'techmart'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
        cursor = conn.cursor()
        
        print("✓ Connected to PostgreSQL")
        
        # Drop table if exists (for clean setup)
        print("\nDropping existing table (if any)...")
        cursor.execute("DROP TABLE IF EXISTS orders CASCADE;")
        
        # Create table
        print("Creating orders table...")
        cursor.execute("""
            CREATE TABLE orders (
                id SERIAL PRIMARY KEY,
                order_id VARCHAR(50) UNIQUE NOT NULL,
                customer_email VARCHAR(255) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                category VARCHAR(100),
                price DECIMAL(10,2) NOT NULL,
                order_date DATE NOT NULL,
                delivery_date DATE,
                status VARCHAR(50) NOT NULL,
                is_opened BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX idx_customer_email ON orders(customer_email);")
        cursor.execute("CREATE INDEX idx_order_date ON orders(order_date);")
        
        # Insert sample data
        print("Inserting sample data...")
        sample_data = [
            ('ORD-2024-001', 'john.doe@email.com', 'Laptop Pro 15', 'Electronics', 1299.99, '2024-03-15', '2024-03-20', 'Delivered', True),
            ('ORD-2024-002', 'jane.smith@email.com', 'Wireless Mouse', 'Electronics', 29.99, '2024-04-01', '2024-04-05', 'Delivered', False),
            ('ORD-2024-003', 'bob.wilson@email.com', 'Office Chair', 'Furniture', 249.99, '2024-03-25', '2024-04-02', 'Delivered', True),
            ('ORD-2024-004', 'alice.brown@email.com', 'Desk Lamp', 'Home & Office', 45.99, '2024-04-10', '2024-04-15', 'Delivered', False),
            ('ORD-2024-005', 'charlie.davis@email.com', 'Mechanical Keyboard', 'Electronics', 89.99, '2024-04-05', '2024-04-12', 'Delivered', True),
            ('ORD-2024-006', 'diana.miller@email.com', 'Monitor 27 inch', 'Electronics', 399.99, '2024-03-20', '2024-03-28', 'Delivered', False),
            ('ORD-2024-007', 'evan.garcia@email.com', 'Standing Desk', 'Furniture', 599.99, '2024-04-08', '2024-04-18', 'In Transit', False),
            ('ORD-2024-008', 'fiona.martinez@email.com', 'Webcam HD', 'Electronics', 79.99, '2024-04-12', None, 'Processing', False),
            ('ORD-2024-009', 'george.lopez@email.com', 'Ergonomic Mouse Pad', 'Home & Office', 19.99, '2024-04-14', None, 'Processing', False),
            ('ORD-2024-010', 'hannah.lee@email.com', 'USB-C Hub', 'Electronics', 49.99, '2024-04-16', None, 'Processing', False),
        ]
        
        insert_sql = """
            INSERT INTO orders (order_id, customer_email, product_name, category, price, 
                              order_date, delivery_date, status, is_opened)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.executemany(insert_sql, sample_data)
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM orders;")
        count = cursor.fetchone()[0]
        print(f"\n✓ Successfully inserted {count} orders")
        
        # Show sample
        cursor.execute("""
            SELECT order_id, customer_email, product_name, status, price 
            FROM orders 
            ORDER BY order_date DESC 
            LIMIT 5;
        """)
        
        print("\nSample orders:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[2]} ({row[3]}) - ${row[4]}")
        
        cursor.close()
        conn.close()
        print("\n✓ PostgreSQL setup completed successfully!")
        return True
        
    except ImportError:
        print("✗ psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def setup_db2():
    """Setup DB2 database with table and data"""
    try:
        import ibm_db
        
        # Connection parameters
        schema = os.getenv('DB2_SCHEMA', 'TECHMART')
        conn_str = (
            f"DATABASE={os.getenv('DB2_DATABASE', 'SAMPLE')};"
            f"HOSTNAME={os.getenv('DB2_HOSTNAME', 'localhost')};"
            f"PORT={os.getenv('DB2_PORT', '50000')};"
            f"PROTOCOL=TCPIP;"
            f"UID={os.getenv('DB2_USERNAME', '')};"
            f"PWD={os.getenv('DB2_PASSWORD', '')};"
        )
        
        print(f"Connecting to DB2...")
        print(f"  Host: {os.getenv('DB2_HOSTNAME', 'localhost')}")
        print(f"  Port: {os.getenv('DB2_PORT', '50000')}")
        print(f"  Database: {os.getenv('DB2_DATABASE', 'SAMPLE')}")
        print(f"  Schema: {schema}")
        
        conn = ibm_db.connect(conn_str, "", "")
        print("✓ Connected to DB2")
        
        # Create schema if not exists
        try:
            print(f"\nCreating schema {schema}...")
            ibm_db.exec_immediate(conn, f"CREATE SCHEMA {schema}")
            print(f"✓ Schema {schema} created")
        except:
            print(f"✓ Schema {schema} already exists")
        
        # Drop table if exists
        try:
            print("Dropping existing table (if any)...")
            ibm_db.exec_immediate(conn, f"DROP TABLE {schema}.ORDERS")
            print("✓ Existing table dropped")
        except:
            print("✓ No existing table to drop")
        
        # Create table
        print("Creating ORDERS table...")
        create_table_sql = f"""
        CREATE TABLE {schema}.ORDERS (
            ID INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            ORDER_ID VARCHAR(50) NOT NULL,
            CUSTOMER_EMAIL VARCHAR(255) NOT NULL,
            PRODUCT_NAME VARCHAR(255) NOT NULL,
            CATEGORY VARCHAR(100),
            PRICE DECIMAL(10,2) NOT NULL,
            ORDER_DATE DATE NOT NULL,
            DELIVERY_DATE DATE,
            STATUS VARCHAR(50) NOT NULL,
            IS_OPENED SMALLINT DEFAULT 0,
            CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        ibm_db.exec_immediate(conn, create_table_sql)
        print("✓ Table created")
        
        # Create indexes
        print("Creating indexes...")
        ibm_db.exec_immediate(conn, 
            f"CREATE UNIQUE INDEX {schema}.IDX_ORDER_ID ON {schema}.ORDERS(ORDER_ID)")
        ibm_db.exec_immediate(conn,
            f"CREATE INDEX {schema}.IDX_CUSTOMER_EMAIL ON {schema}.ORDERS(CUSTOMER_EMAIL)")
        print("✓ Indexes created")
        
        # Insert sample data
        print("Inserting sample data...")
        sample_data = [
            ('ORD-2024-001', 'john.doe@email.com', 'Laptop Pro 15', 'Electronics', 1299.99, '2024-03-15', '2024-03-20', 'Delivered', 1),
            ('ORD-2024-002', 'jane.smith@email.com', 'Wireless Mouse', 'Electronics', 29.99, '2024-04-01', '2024-04-05', 'Delivered', 0),
            ('ORD-2024-003', 'bob.wilson@email.com', 'Office Chair', 'Furniture', 249.99, '2024-03-25', '2024-04-02', 'Delivered', 1),
            ('ORD-2024-004', 'alice.brown@email.com', 'Desk Lamp', 'Home & Office', 45.99, '2024-04-10', '2024-04-15', 'Delivered', 0),
            ('ORD-2024-005', 'charlie.davis@email.com', 'Mechanical Keyboard', 'Electronics', 89.99, '2024-04-05', '2024-04-12', 'Delivered', 1),
            ('ORD-2024-006', 'diana.miller@email.com', 'Monitor 27 inch', 'Electronics', 399.99, '2024-03-20', '2024-03-28', 'Delivered', 0),
            ('ORD-2024-007', 'evan.garcia@email.com', 'Standing Desk', 'Furniture', 599.99, '2024-04-08', '2024-04-18', 'In Transit', 0),
            ('ORD-2024-008', 'fiona.martinez@email.com', 'Webcam HD', 'Electronics', 79.99, '2024-04-12', None, 'Processing', 0),
            ('ORD-2024-009', 'george.lopez@email.com', 'Ergonomic Mouse Pad', 'Home & Office', 19.99, '2024-04-14', None, 'Processing', 0),
            ('ORD-2024-010', 'hannah.lee@email.com', 'USB-C Hub', 'Electronics', 49.99, '2024-04-16', None, 'Processing', 0),
        ]
        
        insert_sql = f"""
        INSERT INTO {schema}.ORDERS (
            ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, CATEGORY,
            PRICE, ORDER_DATE, DELIVERY_DATE, STATUS, IS_OPENED
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        stmt = ibm_db.prepare(conn, insert_sql)
        inserted = 0
        
        for row in sample_data:
            for i, val in enumerate(row, 1):
                ibm_db.bind_param(stmt, i, val)
            if ibm_db.execute(stmt):
                inserted += 1
        
        print(f"\n✓ Successfully inserted {inserted} orders")
        
        # Verify
        stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {schema}.ORDERS")
        row = ibm_db.fetch_tuple(stmt)
        print(f"✓ Total orders in database: {row[0]}")
        
        # Show sample
        stmt = ibm_db.exec_immediate(conn, f"""
            SELECT ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, STATUS, PRICE 
            FROM {schema}.ORDERS 
            ORDER BY ORDER_DATE DESC 
            FETCH FIRST 5 ROWS ONLY
        """)
        
        print("\nSample orders:")
        row = ibm_db.fetch_tuple(stmt)
        while row:
            print(f"  - {row[0]}: {row[2]} ({row[3]}) - ${row[4]}")
            row = ibm_db.fetch_tuple(stmt)
        
        ibm_db.close(conn)
        print("\n✓ DB2 setup completed successfully!")
        return True
        
    except ImportError:
        print("✗ ibm_db not installed. Install with: pip install ibm_db")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("Simple Database Setup Script")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}\n")
    
    if DB_TYPE.lower() == 'postgresql':
        success = setup_postgresql()
    elif DB_TYPE.lower() == 'db2':
        success = setup_db2()
    else:
        print(f"✗ Unsupported database type: {DB_TYPE}")
        print("Set DB_TYPE to 'postgresql' or 'db2'")
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ Database setup completed successfully!")
    else:
        print("✗ Database setup failed!")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

# Made with Bob
