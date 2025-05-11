# models.py
import sqlite3
import hashlib
import uuid
from datetime import datetime
import math
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Database:
    DB_PATH = os.getenv("DATABASE_PATH", "chess.db")

    @classmethod
    def setup_database(cls):
        conn = sqlite3.connect(cls.DB_PATH)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                elo_rating INTEGER DEFAULT 1200,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Games table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                white_player_id INTEGER NOT NULL,
                black_player_id INTEGER,
                is_ai_game BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'active',
                winner_id INTEGER,
                fen_position TEXT,
                moves TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                FOREIGN KEY (white_player_id) REFERENCES users (id),
                FOREIGN KEY (black_player_id) REFERENCES users (id),
                FOREIGN KEY (winner_id) REFERENCES users (id)
            )
        """)

        # Game history table for ELO calculation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                white_player_id INTEGER NOT NULL,
                black_player_id INTEGER,
                winner_id INTEGER,
                white_elo_before INTEGER,
                black_elo_before INTEGER,
                white_elo_after INTEGER,
                black_elo_after INTEGER,
                ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (id),
                FOREIGN KEY (white_player_id) REFERENCES users (id),
                FOREIGN KEY (black_player_id) REFERENCES users (id),
                FOREIGN KEY (winner_id) REFERENCES users (id)
            )
        """)

        conn.commit()
        conn.close()

    @classmethod
    def create_user(cls, username, email, password):
        conn = sqlite3.connect(cls.DB_PATH)
        cursor = conn.cursor()

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            """, (username, email, password_hash))

            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    @classmethod
    def get_user_by_username(cls, username):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    @classmethod
    def get_user_by_id(cls, user_id):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    @classmethod
    def authenticate_user(cls, username, password):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("""
            SELECT * FROM users WHERE username = ? AND password_hash = ?
        """, (username, password_hash))

        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    @classmethod
    def create_game(cls, white_player_id, black_player_id, is_ai_game=False):
        conn = sqlite3.connect(cls.DB_PATH)
        cursor = conn.cursor()

        game_id = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO games (id, white_player_id, black_player_id, is_ai_game, fen_position, moves)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (game_id, white_player_id, black_player_id, is_ai_game,
              "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "[]"))

        conn.commit()
        conn.close()

        return game_id

    @classmethod
    def get_game(cls, game_id):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        game = cursor.fetchone()
        conn.close()

        return dict(game) if game else None

    @classmethod
    def join_game(cls, game_id, black_player_id):
        conn = sqlite3.connect(cls.DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE games SET black_player_id = ? WHERE id = ? AND black_player_id IS NULL
        """, (black_player_id, game_id))

        conn.commit()
        conn.close()

    @classmethod
    def update_game(cls, game_id, fen_position, moves):
        conn = sqlite3.connect(cls.DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE games SET fen_position = ?, moves = ? WHERE id = ?
        """, (fen_position, moves, game_id))

        conn.commit()
        conn.close()

    @classmethod
    def end_game(cls, game_id, winner_id, status):
        conn = sqlite3.connect(cls.DB_PATH)
        cursor = conn.cursor()

        # Get game details
        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        game = cursor.fetchone()

        if not game:
            conn.close()
            return

        # Update game status
        cursor.execute("""
            UPDATE games SET status = ?, winner_id = ?, ended_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (status, winner_id, game_id))

        # Calculate and update ELO ratings if it's a player vs player game
        if not game[3]:  # is_ai_game is False
            white_player_id = game[1]
            black_player_id = game[2]

            if black_player_id:  # Ensure both players exist
                # Get current ELO ratings
                cursor.execute("SELECT elo_rating FROM users WHERE id = ?", (white_player_id,))
                white_elo = cursor.fetchone()[0]

                cursor.execute("SELECT elo_rating FROM users WHERE id = ?", (black_player_id,))
                black_elo = cursor.fetchone()[0]

                # Calculate new ELO ratings
                white_score = 1 if winner_id == white_player_id else (0.5 if winner_id is None else 0)
                black_score = 1 - white_score

                new_white_elo, new_black_elo = cls.calculate_elo(white_elo, black_elo, white_score)

                # Update ELO ratings
                cursor.execute("UPDATE users SET elo_rating = ? WHERE id = ?", (new_white_elo, white_player_id))
                cursor.execute("UPDATE users SET elo_rating = ? WHERE id = ?", (new_black_elo, black_player_id))

                # Record game history
                cursor.execute("""
                    INSERT INTO game_history (game_id, white_player_id, black_player_id, winner_id,
                                            white_elo_before, black_elo_before, white_elo_after, black_elo_after)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (game_id, white_player_id, black_player_id, winner_id,
                      white_elo, black_elo, new_white_elo, new_black_elo))

        conn.commit()
        conn.close()

    @classmethod
    def calculate_elo(cls, rating1, rating2, score1, k_factor=32):
        """Calculate new ELO ratings based on game result"""
        expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
        expected2 = 1 - expected1

        new_rating1 = rating1 + k_factor * (score1 - expected1)
        new_rating2 = rating2 + k_factor * ((1 - score1) - expected2)

        return round(new_rating1), round(new_rating2)

    @classmethod
    def get_user_active_games(cls, user_id):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT g.*, 
                   w.username as white_username,
                   b.username as black_username
            FROM games g
            LEFT JOIN users w ON g.white_player_id = w.id
            LEFT JOIN users b ON g.black_player_id = b.id
            WHERE (g.white_player_id = ? OR g.black_player_id = ?) 
            AND g.status = 'active'
            ORDER BY g.created_at DESC
        """, (user_id, user_id))

        games = cursor.fetchall()
        conn.close()

        return [dict(game) for game in games]

    @classmethod
    def get_available_games(cls):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT g.*, 
                   w.username as white_username,
                   w.elo_rating as white_player_elo
            FROM games g
            LEFT JOIN users w ON g.white_player_id = w.id
            WHERE g.black_player_id IS NULL 
            AND g.status = 'active'
            AND g.is_ai_game = FALSE
            ORDER BY g.created_at DESC
        """)

        games = cursor.fetchall()
        conn.close()

        return [dict(game) for game in games]

    @classmethod
    def get_user_game_history(cls, user_id):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT gh.*, 
                   w.username as white_username,
                   b.username as black_username,
                   g.status as game_status
            FROM game_history gh
            JOIN games g ON gh.game_id = g.id
            LEFT JOIN users w ON gh.white_player_id = w.id
            LEFT JOIN users b ON gh.black_player_id = b.id
            WHERE gh.white_player_id = ? OR gh.black_player_id = ?
            ORDER BY gh.ended_at DESC
            LIMIT 20
        """, (user_id, user_id))

        history = cursor.fetchall()
        conn.close()

        return [dict(record) for record in history]

    @classmethod
    def get_top_players(cls, limit=100):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT u.*, 
                   COUNT(gh.id) as games_played,
                   SUM(CASE WHEN gh.winner_id = u.id THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN gh.winner_id IS NULL THEN 1 ELSE 0 END) as draws
            FROM users u
            LEFT JOIN game_history gh ON u.id = gh.white_player_id OR u.id = gh.black_player_id
            GROUP BY u.id
            ORDER BY u.elo_rating DESC
            LIMIT ?
        """, (limit,))

        players = cursor.fetchall()
        conn.close()

        return [dict(player) for player in players]