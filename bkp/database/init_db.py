#!/usr/bin/env python3
"""
Database initialization script
Loads sample orders from CSV into PostgreSQL
"""

import os
import csv
import psycopg2
from psycopg2.extras import execute_values

# Database connection parameters
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'techmart')
DB_USER = os.getenv('DB_USER', 'techmart')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'techmart123')

def init_database():
    """Initialize database with schema and sample data"""
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("📊 Initializing TechMart database...")
    
    # Read and execute schema (with DROP IF EXISTS for idempotency)
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
        try:
            cursor.execute(schema_sql)
            conn.commit()
            print("✅ Database schema created")
        except Exception as e:
            conn.rollback()
            if "already exists" in str(e):
                print("✅ Database schema already exists (skipping)")
            else:
                raise
    
    # Load sample data from CSV
    # Try multiple possible paths
    csv_paths = [
        '/tmp/orders.csv',  # When copied to container
        os.path.join(os.path.dirname(__file__), '..', 'data', 'orders.csv'),  # Relative path
        'orders.csv',  # Current directory
    ]
    
    csv_path = None
    for path in csv_paths:
        if os.path.exists(path):
            csv_path = path
            break
    
    if csv_path:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            orders = []
            for row in reader:
                orders.append((
                    row['order_id'],
                    row['customer_email'],
                    row['product_name'],
                    row['category'],
                    float(row['price']),
                    row['order_date'],
                    row['delivery_date'],
                    row['status'],
                    row['is_opened']
                ))
            
            # Insert orders
            insert_query = """
                INSERT INTO orders (
                    order_id, customer_email, product_name,
                    category, price, order_date, delivery_date, status, is_opened
                ) VALUES %s
                ON CONFLICT (order_id) DO UPDATE SET
                    customer_email = EXCLUDED.customer_email,
                    product_name = EXCLUDED.product_name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    order_date = EXCLUDED.order_date,
                    delivery_date = EXCLUDED.delivery_date,
                    status = EXCLUDED.status,
                    is_opened = EXCLUDED.is_opened
            """
            execute_values(cursor, insert_query, orders)
            print(f"✅ Loaded {len(orders)} orders from CSV")
    else:
        print("⚠️  No orders.csv found, skipping sample data")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("🎉 Database initialization complete!")

if __name__ == '__main__':
    init_database()

# Made with Bob
