import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(__file__))

# FastAPI is ASGI — wrap it for Passenger (WSGI) using a2wsgi
from a2wsgi import ASGIMiddleware
from main import app

application = ASGIMiddleware(app)
