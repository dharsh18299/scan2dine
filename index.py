# api/index.py
from app import app

# Vercel needs the WSGI application exposed
app = app
