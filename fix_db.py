import sqlite3

def add_column_if_missing(table, column, type_def):
    conn = sqlite3.connect('modas_pathy.db')
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [c[1] for c in cursor.fetchall()]
        
        if column not in columns:
            print(f"Adding column {column} to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
            conn.commit()
            print(f"Column {column} added successfully.")
        else:
            print(f"Column {column} already exists in {table}.")
            
    except Exception as e:
        print(f"Error processing {table}.{column}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting database repair...")
    
    # Fix clients table
    add_column_if_missing('clients', 'measurements', 'TEXT')
    
    # Fix custom_orders table
    add_column_if_missing('custom_orders', 'measurements', 'TEXT')
    
    # Fix site_settings table
    add_column_if_missing('site_settings', 'exchange_rate', 'FLOAT DEFAULT 6.96')
    add_column_if_missing('site_settings', 'qr_image', 'VARCHAR(256)')
    
    print("Database repair completed.")
