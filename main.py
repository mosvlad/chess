# main.py
import os
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import tornado.escape
import json
import sqlite3
import hashlib
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our modules
from handlers import (
    MainHandler,
    RegisterHandler,
    LoginHandler,
    LogoutHandler,
    ProfileHandler,
    GameHandler,
    GameWebSocketHandler,
    LeaderboardHandler
)
from models import Database
from chess_engine import ChessGame
from chess_ai import ChessAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Application settings
settings = {
    "cookie_secret": os.getenv("COOKIE_SECRET", "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__"),
    "login_url": "/login",
    "template_path": os.path.join(os.path.dirname(__file__), "templates"),
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    "xsrf_cookies": True,
    "debug": os.getenv("DEBUG", "True").lower() == "true",
}

# Global state for active games
active_games = {}
websocket_connections = {}


def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/register", RegisterHandler),
        (r"/login", LoginHandler),
        (r"/logout", LogoutHandler),
        (r"/profile", ProfileHandler),
        (r"/game/new", GameHandler),  # Add this route for creating new games
        (r"/game/([^/]+)", GameHandler),  # Keep this for viewing games
        (r"/websocket/([^/]+)", GameWebSocketHandler),
        (r"/leaderboard", LeaderboardHandler),
    ], **settings)


def main():
    # Check if cookie secret is set
    if settings["cookie_secret"] == "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__":
        logger.warning("WARNING: Using default cookie secret. Please set COOKIE_SECRET in .env file!")
        logger.warning("Generate a secure secret with: python -c \"import secrets; print(secrets.token_hex(32))\"")

    # Initialize database
    Database.setup_database()

    # Create application
    app = make_app()

    # Get port and host from environment
    port = int(os.getenv("PORT", 8888))
    host = os.getenv("HOST", "0.0.0.0")  # Listen on all interfaces by default

    # Create HTTP server
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(port, address=host)

    if host == "0.0.0.0":
        logger.info(f"Chess application started on http://0.0.0.0:{port}")
        logger.info("Server is accessible from all network interfaces")
        logger.info(f"Local access: http://localhost:{port}")

        # Try to determine and display local IP address
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            logger.info(f"Network access: http://{local_ip}:{port}")
        except:
            logger.info("Network access: http://[your-local-ip]:" + str(port))
    else:
        logger.info(f"Chess application started on http://{host}:{port}")

    logger.info(f"Debug mode: {settings['debug']}")
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()