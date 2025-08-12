from sqlmodel import SQLModel, create_engine, Session
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def check_and_create_tables():
    """检查表是否存在，如果不存在则创建"""
    try:
        # 检查是否存在project表
        conn = sqlite3.connect("./database.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='project';
        """)
        
        if not cursor.fetchone():
            logger.info("Database tables not found, creating...")
            SQLModel.metadata.create_all(engine)
            logger.info("Database tables created successfully")
        else:
            logger.info("Database tables already exist")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Error checking/creating database tables: {e}")
        # 如果检查失败，尝试创建表
        try:
            SQLModel.metadata.create_all(engine)
            logger.info("Database tables created as fallback")
        except Exception as create_error:
            logger.error(f"Failed to create tables: {create_error}")
            raise

def get_session():
    with Session(engine) as session:
        yield session