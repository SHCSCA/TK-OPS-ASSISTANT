import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.core import SessionLocal, init_db
from db.models import Account, Comment

def test_crm_query():
    print("Testing DB Connection...")
    session = SessionLocal()
    try:
        count = session.query(Account).count()
        print(f"Account count: {count}")
        
        comments_count = session.query(Comment).count()
        print(f"Comments count: {comments_count}")
        
    except Exception as e:
        print(f"FAILED: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
    test_crm_query()
