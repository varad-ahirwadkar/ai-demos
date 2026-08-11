#!/usr/bin/env python3
"""
Database Setup Script
Creates database schema and inserts sample data
Supports both PostgreSQL and IBM DB2 databases
"""

import os
import sys
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

# Database type selection
DB_TYPE = os.getenv('DB_TYPE', 'postgresql')  # 'postgresql' or 'db2'


class DatabaseSetup:
    """Base class for database setup operations"""
    
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection"""
        raise NotImplementedError
    
    def disconnect(self):
        """Close database connection"""
        raise NotImplementedError
    
    def create_schema(self):
        """Create database schema"""
        raise NotImplementedError
    
    def insert_data(self, data: List[Dict[str, Any]]):
        """Insert data into database"""
        raise NotImplementedError
    
    def verify_data(self):
        """Verify inserted data"""
        raise NotImplementedError


class PostgreSQLSetup(DatabaseSetup):
    """PostgreSQL database setup"""
    
    def __init__(self):
        super().__init__()
        self.db_name = os.getenv('POSTGRES_DB', 'techmart')
        self.user = os.getenv('POSTGRES_USER', 'postgres')
        self.password = os.getenv('POSTGRES_PASSWORD', 'postgres')
        self.host = os.getenv('POSTGRES_HOST', 'localhost')
        self.port = os.getenv('POSTGRES_PORT', '5432')
        
    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            import psycopg2
            self.conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to PostgreSQL database: {self.db_name}")
            return True
        except Exception as e:
            print(f"✗ Error connecting to PostgreSQL: {e}")
            return False
    
    def disconnect(self):
        """Close PostgreSQL connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✓ Disconnected from PostgreSQL")
    
    def create_schema(self):
        """Create PostgreSQL schema and tables"""
        try:
            # Create orders table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS orders (
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
            """
            self.cursor.execute(create_table_sql)
            
            # Create indexes
            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_customer_email 
                ON orders(customer_email);
            """)
            
            self.conn.commit()
            print("✓ Created PostgreSQL schema and tables")
            return True
        except Exception as e:
            print(f"✗ Error creating schema: {e}")
            self.conn.rollback()
            return False
    
    def insert_data(self, data: List[Dict[str, Any]]):
        """Insert data into PostgreSQL"""
        try:
            insert_sql = """
            INSERT INTO orders (
                order_id, customer_email, product_name, category,
                price, order_date, delivery_date, status, is_opened
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_id) DO NOTHING;
            """
            
            inserted_count = 0
            for row in data:
                self.cursor.execute(insert_sql, (
                    row['order_id'],
                    row['customer_email'],
                    row['product_name'],
                    row['category'],
                    row['price'],
                    row['order_date'],
                    row['delivery_date'],
                    row['status'],
                    row['is_opened']
                ))
                inserted_count += self.cursor.rowcount
            
            self.conn.commit()
            print(f"✓ Inserted {inserted_count} records into PostgreSQL")
            return True
        except Exception as e:
            print(f"✗ Error inserting data: {e}")
            self.conn.rollback()
            return False
    
    def verify_data(self):
        """Verify data in PostgreSQL"""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM orders;")
            count = self.cursor.fetchone()[0]
            print(f"✓ Total orders in database: {count}")
            
            self.cursor.execute("""
                SELECT order_id, customer_email, product_name, status, price 
                FROM orders 
                ORDER BY order_date DESC 
                LIMIT 5;
            """)
            rows = self.cursor.fetchall()
            print("\nSample orders:")
            for row in rows:
                print(f"  - {row[0]}: {row[2]} ({row[3]}) - ${row[4]}")
            return True
        except Exception as e:
            print(f"✗ Error verifying data: {e}")
            return False


class DB2Setup(DatabaseSetup):
    """IBM DB2 database setup"""
    
    def __init__(self):
        super().__init__()
        self.db_name = os.getenv('DB2_DATABASE', 'SAMPLE')
        self.schema = os.getenv('DB2_SCHEMA', 'TECHMART')
        self.hostname = os.getenv('DB2_HOSTNAME', 'localhost')
        self.port = os.getenv('DB2_PORT', '50000')
        self.username = os.getenv('DB2_USERNAME', '')
        self.password = os.getenv('DB2_PASSWORD', '')
    
    def connect(self):
        """Connect to DB2 database"""
        try:
            import ibm_db
            
            print(f"Attempting to connect to DB2...")
            print(f"  Host: {self.hostname}")
            print(f"  Port: {self.port}")
            print(f"  Database: {self.db_name}")
            print(f"  Schema: {self.schema}")
            print(f"  Username: {self.username}")
            
            conn_str = (
                f"DATABASE={self.db_name};"
                f"HOSTNAME={self.hostname};"
                f"PORT={self.port};"
                f"PROTOCOL=TCPIP;"
                f"UID={self.username};"
                f"PWD={self.password};"
            )
            self.conn = ibm_db.connect(conn_str, "", "")
            print(f"✓ Connected to DB2 database: {self.db_name}")
            return True
        except Exception as e:
            print(f"\n✗ Error connecting to DB2: {e}")
            print("\nTroubleshooting tips:")
            print("1. Verify DB2 server is running")
            print("2. Check hostname/IP address is correct")
            print("3. Verify port number (default: 50000)")
            print("4. Ensure firewall allows connections on the DB2 port")
            print("5. Check DB2 instance is started: db2start")
            print("6. Verify database exists: db2 list db directory")
            print("7. Test network connectivity: telnet <hostname> <port>")
            print(f"8. For IBM i, ensure QZDASOINIT jobs are available")
            return False
    
    def disconnect(self):
        """Close DB2 connection"""
        if self.conn:
            import ibm_db
            ibm_db.close(self.conn)
        print("✓ Disconnected from DB2")
    
    def create_schema(self):
        """Create DB2 schema and tables"""
        try:
            import ibm_db
            
            # Create schema
            try:
                ibm_db.exec_immediate(self.conn, f"CREATE SCHEMA {self.schema}")
            except:
                pass  # Schema might already exist
            
            # Create orders table
            create_table_sql = f"""
            CREATE TABLE {self.schema}.ORDERS (
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
            ibm_db.exec_immediate(self.conn, create_table_sql)
            
            # Create indexes
            ibm_db.exec_immediate(self.conn, 
                f"CREATE UNIQUE INDEX {self.schema}.IDX_ORDER_ID ON {self.schema}.ORDERS(ORDER_ID)")
            ibm_db.exec_immediate(self.conn,
                f"CREATE INDEX {self.schema}.IDX_CUSTOMER_EMAIL ON {self.schema}.ORDERS(CUSTOMER_EMAIL)")
            
            print("✓ Created DB2 schema and tables")
            return True
        except Exception as e:
            print(f"✗ Error creating schema: {e}")
            return False
    
    def insert_data(self, data: List[Dict[str, Any]]):
        """Insert data into DB2"""
        try:
            import ibm_db
            
            insert_sql = f"""
            INSERT INTO {self.schema}.ORDERS (
                ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, CATEGORY,
                PRICE, ORDER_DATE, DELIVERY_DATE, STATUS, IS_OPENED
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            stmt = ibm_db.prepare(self.conn, insert_sql)
            inserted_count = 0
            
            for row in data:
                ibm_db.bind_param(stmt, 1, row['order_id'])
                ibm_db.bind_param(stmt, 2, row['customer_email'])
                ibm_db.bind_param(stmt, 3, row['product_name'])
                ibm_db.bind_param(stmt, 4, row['category'])
                ibm_db.bind_param(stmt, 5, row['price'])
                ibm_db.bind_param(stmt, 6, row['order_date'])
                ibm_db.bind_param(stmt, 7, row['delivery_date'])
                ibm_db.bind_param(stmt, 8, row['status'])
                ibm_db.bind_param(stmt, 9, row['is_opened'])
                
                if ibm_db.execute(stmt):
                    inserted_count += 1
            
            print(f"✓ Inserted {inserted_count} records into DB2")
            return True
        except Exception as e:
            print(f"✗ Error inserting data: {e}")
            return False
    
    def verify_data(self):
        """Verify data in DB2"""
        try:
            import ibm_db
            
            stmt = ibm_db.exec_immediate(self.conn, 
                f"SELECT COUNT(*) FROM {self.schema}.ORDERS")
            row = ibm_db.fetch_tuple(stmt)
            print(f"✓ Total orders in database: {row[0]}")
            
            stmt = ibm_db.exec_immediate(self.conn, f"""
                SELECT ORDER_ID, CUSTOMER_EMAIL, PRODUCT_NAME, STATUS, PRICE 
                FROM {self.schema}.ORDERS 
                ORDER BY ORDER_DATE DESC 
                FETCH FIRST 5 ROWS ONLY
            """)
            
            print("\nSample orders:")
            row = ibm_db.fetch_tuple(stmt)
            while row:
                print(f"  - {row[0]}: {row[2]} ({row[3]}) - ${row[4]}")
                row = ibm_db.fetch_tuple(stmt)
            return True
        except Exception as e:
            print(f"✗ Error verifying data: {e}")
            return False


def load_csv_data(csv_file: str) -> List[Dict[str, Any]]:
    """Load data from CSV file"""
    data = []
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert is_opened to boolean/int
                is_opened = 1 if row['is_opened'].lower() in ['yes', 'true', '1'] else 0
                
                data.append({
                    'order_id': row['order_id'],
                    'customer_email': row['customer_email'],
                    'product_name': row['product_name'],
                    'category': row['category'],
                    'price': float(row['price']),
                    'order_date': row['order_date'],
                    'delivery_date': row['delivery_date'] if row['delivery_date'] else None,
                    'status': row['status'],
                    'is_opened': is_opened
                })
        print(f"✓ Loaded {len(data)} records from {csv_file}")
        return data
    except Exception as e:
        print(f"✗ Error loading CSV: {e}")
        return []


def main():
    """Main execution function"""
    print("=" * 60)
    print("Database Setup Script")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}")
    print()
    
    # Create appropriate database setup instance
    if DB_TYPE.lower() == 'postgresql':
        db_setup = PostgreSQLSetup()
    elif DB_TYPE.lower() == 'db2':
        db_setup = DB2Setup()
    else:
        print(f"✗ Unsupported database type: {DB_TYPE}")
        print("Supported types: postgresql, db2")
        sys.exit(1)
    
    # Connect to database
    if not db_setup.connect():
        sys.exit(1)
    
    try:
        # Create schema
        print("\n1. Creating database schema...")
        if not db_setup.create_schema():
            sys.exit(1)
        
        # Load data from CSV
        print("\n2. Loading data from CSV...")
        csv_file = os.getenv('CSV_FILE', 'data/orders.csv')
        data = load_csv_data(csv_file)
        
        if not data:
            print("✗ No data to insert")
            sys.exit(1)
        
        # Insert data
        print("\n3. Inserting data into database...")
        if not db_setup.insert_data(data):
            sys.exit(1)
        
        # Verify data
        print("\n4. Verifying inserted data...")
        db_setup.verify_data()
        
        print("\n" + "=" * 60)
        print("✓ Database setup completed successfully!")
        print("=" * 60)
        
    finally:
        db_setup.disconnect()


if __name__ == "__main__":
    main()

# Made with Bob
