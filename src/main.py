import time
from src.models import init_db
from src.tasks import create_canary

def main():
    print("Initializing Database...")
    init_db()
    print("Database Initialized.")
    
    # Keep container alive for CLI access
    print("App is running. Waiting for commands...")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
