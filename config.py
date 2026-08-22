HOST="localhost"
USER="root"
PASSWORD="12345678"
DATABASE="scan2dine"
import os

HOST = os.environ.get("HOST")
PORT = int(os.environ.get("PORT", 3306))
USER = os.environ.get("USER")
PASSWORD = os.environ.get("PASSWORD")
DATABASE = os.environ.get("DATABASE")
