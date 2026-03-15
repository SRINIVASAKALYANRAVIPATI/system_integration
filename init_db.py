
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_db():
    try:
        # Connect to default postgres DB to create the new one
        conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            host='localhost',
            password='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if DB exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname='interview_db'")
        exists = cur.fetchone()
        
        if not exists:
            cur.execute("CREATE DATABASE interview_db")
            print("Database 'interview_db' created successfully.")
        else:
            print("Database 'interview_db' already exists.")
            
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    create_db()
