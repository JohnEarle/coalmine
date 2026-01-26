
import sys
import os
sys.path.append(os.getcwd())
from src.models import SessionLocal, CloudEnvironment, ResourceType, init_db
import uuid

# Ensure Tables Exist
init_db()
