import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

load_dotenv()

database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("API_DB_USER", "calc_ro"),
    password=os.getenv("API_DB_PASSWORD"),
    host=os.getenv("API_DB_HOST", "localhost"),
    port=int(os.getenv("API_DB_PORT", "5433")),
    database=os.getenv("API_DB_NAME", "irrbb"),
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
)


def get_db():
    with engine.connect() as connection:
        yield connection
