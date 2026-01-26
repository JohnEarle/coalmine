import time
from src.models import init_db
from src.tasks import create_canary

def main():
    print("Initializing Database...")
    init_db()
    print("Database Initialized.")
    
    # In a real app, this might start a web server. 
    # For now, we just keep the container alive so we can exec into it.
    print("App is running. Waiting for commands...")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
