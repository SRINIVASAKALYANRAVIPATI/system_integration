
import sqlalchemy
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/interview_db"

def check_connection():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            row = result.fetchone()
            print(f"PostgreSQL Connection Successful! Version: {row[0]}")
            return True
    except Exception as e:
        print(f"PostgreSQL Connection Failed: {e}")
        return False

if __name__ == "__main__":
    check_connection()
