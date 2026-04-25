import os
import time

import psycopg
from dotenv import load_dotenv

load_dotenv()


def wait_for_db(max_attempts: int = 30, delay_seconds: int = 2) -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@db:5432/device_manager",
    )

    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(database_url):
                print("Database is ready")
                return
        except Exception as exc:
            print(
                f"Waiting for database ({attempt}/{max_attempts}): {exc}",
                flush=True,
            )
            time.sleep(delay_seconds)

    raise RuntimeError("Database did not become ready in time")


if __name__ == "__main__":
    wait_for_db()