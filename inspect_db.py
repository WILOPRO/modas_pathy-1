import sqlite3

def check_column(table_name, column_name):
    conn = sqlite3.connect('modas_pathy.db')
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        found = False
        for col in columns:
            if col[1] == column_name:
                found = True
                break
        
        status = "FOUND" if found else "MISSING"
        print(f"Table '{table_name}', Column '{column_name}': {status}")
        
        # Print all columns for context if missing
        if not found:
            print(f"  Existing columns in {table_name}: {[c[1] for c in columns]}")
            
    except Exception as e:
        print(f"Error checking {table_name}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("--- Database Inspection ---")
    check_column('clients', 'measurements')
    check_column('custom_orders', 'measurements')
    check_column('site_settings', 'exchange_rate')
    check_column('site_settings', 'qr_image')
