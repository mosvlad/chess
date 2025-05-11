# handlers.py
import tornado.web
import tornado.websocket
import tornado.escape
import tornado.httputil
import json
import hashlib
import uuid
import asyncio
from datetime import datetime

from models import Database
from chess_engine import ChessGame
from chess_ai import ChessAI

# Global state for active games
active_games = {}
websocket_connections = {}


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_id = self.get_secure_cookie("user")
        if user_id:
            user = Database.get_user_by_id(int(user_id))
            return user
        return None


class MainHandler(BaseHandler):
    def get(self):
        current_user = self.get_current_user()
        if current_user:
            # Get active games
            active_games_list = Database.get_user_active_games(current_user['id'])
            games_available = Database.get_available_games()
            self.render("index.html",
                        user=current_user,
                        active_games=active_games_list,
                        available_games=games_available)
        else:
            self.render("home.html")


class RegisterHandler(BaseHandler):
    def get(self):
        self.render("register.html", error=None)

    def post(self):
        username = self.get_argument("username")
        email = self.get_argument("email")
        password = self.get_argument("password")

        # Check if user already exists
        if Database.get_user_by_username(username):
            self.render("register.html", error="Username already exists")
            return

        # Create user
        user_id = Database.create_user(username, email, password)
        if user_id:
            self.set_secure_cookie("user", str(user_id))
            self.redirect("/")
        else:
            self.render("register.html", error="Registration failed")


class LoginHandler(BaseHandler):
    def get(self):
        self.render("login.html", error=None)

    def post(self):
        username = self.get_argument("username")
        password = self.get_argument("password")

        user = Database.authenticate_user(username, password)
        if user:
            self.set_secure_cookie("user", str(user['id']))
            self.redirect("/")
        else:
            self.render("login.html", error="Invalid username or password")


class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect("/")


class ProfileHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        current_user = self.get_current_user()
        games_history = Database.get_user_game_history(current_user['id'])

        # Calculate stats
        total_games = len(games_history)
        wins = sum(1 for game in games_history if game['winner_id'] == current_user['id'])
        draws = sum(1 for game in games_history if game['winner_id'] is None)
        losses = total_games - wins - draws
        win_rate = round((wins / total_games) * 100, 1) if total_games > 0 else 0

        self.render("profile.html",
                    user=current_user,
                    games_history=games_history,
                    total_games=total_games,
                    wins=wins,
                    draws=draws,
                    losses=losses,
                    win_rate=win_rate)


class GameHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, game_id=None):
        # Handle the case where game_id is "new" (from /game/new)
        if game_id == "new":
            return self.post("new")

        # Handle viewing an existing game
        if not game_id:
            self.redirect("/")
            return

        game = Database.get_game(game_id)
        if not game:
            self.redirect("/")
            return

        current_user = self.get_current_user()

        # Check if user is part of this game
        if current_user['id'] not in [game['white_player_id'], game['black_player_id']]:
            self.redirect("/")
            return

        opponent_id = game['white_player_id'] if current_user['id'] == game['black_player_id'] else game[
            'black_player_id']
        opponent = Database.get_user_by_id(opponent_id) if opponent_id else None

        self.render("game.html",
                    game=game,
                    user=current_user,
                    opponent=opponent,
                    is_white=current_user['id'] == game['white_player_id'])

    @tornado.web.authenticated
    def post(self, game_id=None):
        current_user = self.get_current_user()
        action = self.get_argument("action")

        if action == "create":
            # Create new game
            opponent_type = self.get_argument("opponent_type", "player")

            if opponent_type == "ai":
                # Create game against AI
                new_game_id = Database.create_game(current_user['id'], None, is_ai_game=True)
            else:
                # Create game waiting for opponent
                new_game_id = Database.create_game(current_user['id'], None)

            self.redirect(f"/game/{new_game_id}")

        elif action == "join":
            # Join existing game - this case should have game_id
            if not game_id:
                self.redirect("/")
                return

            game = Database.get_game(game_id)
            if game and not game['black_player_id']:
                Database.join_game(game_id, current_user['id'])

                # Update the active game if it exists
                if game_id in active_games:
                    active_games[game_id].black_player_id = current_user['id']

                self.redirect(f"/game/{game_id}")
            else:
                self.redirect("/")
        else:
            self.redirect("/")


class GameWebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, game_id):
        self.game_id = game_id
        self.user = self.get_secure_cookie("user")
        if not self.user:
            self.close()
            return

        self.user_id = int(self.user)

        # Add to connections
        if game_id not in websocket_connections:
            websocket_connections[game_id] = []
        websocket_connections[game_id].append(self)

        # Get fresh game data from database
        game_data = Database.get_game(game_id)
        if not game_data:
            self.close()
            return

        # Initialize or update game if needed
        if game_id not in active_games:
            active_games[game_id] = ChessGame(
                game_id,
                game_data['white_player_id'],
                game_data['black_player_id'],
                game_data['is_ai_game']
            )
        else:
            # Update existing game with current player data
            game = active_games[game_id]
            if game_data['black_player_id'] and game.black_player_id != game_data['black_player_id']:
                # Update black player if it was just set
                game.black_player_id = game_data['black_player_id']

        # Send current game state
        if game_id in active_games:
            game = active_games[game_id]
            self.write_message({
                "type": "game_state",
                "board": game.get_board_state(),
                "turn": game.get_current_turn(),
                "moves": game.get_legal_moves(),
                "game_status": game.get_game_status(),
                "is_check": game.board.is_check()
            })

    def on_message(self, message):
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "move":
                self.handle_move(data)
            elif message_type == "chat":
                self.handle_chat(data)
            elif message_type == "offer_draw":
                self.handle_draw_offer()
            elif message_type == "resign":
                self.handle_resignation()

        except json.JSONDecodeError:
            self.write_message({"type": "error", "message": "Invalid message format"})

    def handle_move(self, data):
        game = active_games.get(self.game_id)
        if not game:
            self.write_message({"type": "error", "message": "Game not found"})
            return

        from_square = data.get("from")
        to_square = data.get("to")
        promotion = data.get("promotion")

        # Validate and make move
        if game.make_move(self.user_id, from_square, to_square, promotion):
            # Broadcast move to all connected clients
            self.broadcast_to_game({
                "type": "move_made",
                "from": from_square,
                "to": to_square,
                "board": game.get_board_state(),
                "turn": game.get_current_turn(),
                "moves": game.get_legal_moves(),
                "game_status": game.get_game_status(),
                "is_check": game.board.is_check()
            })

            # Check for game end
            status = game.get_game_status()
            if status in ["checkmate", "stalemate", "draw"]:
                winner_id = game.get_winner_id() if status == "checkmate" else None
                Database.end_game(self.game_id, winner_id, status)
                self.broadcast_to_game({
                    "type": "game_ended",
                    "status": status,
                    "winner": winner_id
                })

            # If AI game, make AI move
            elif game.is_ai_game and game.get_current_turn() == "black":
                # Add a small delay for AI move to make it feel more natural
                async def make_ai_move():
                    await asyncio.sleep(1)  # 1 second delay
                    ai_move = ChessAI.get_best_move(game.board)
                    if ai_move:
                        ai_from, ai_to = ai_move
                        if game.make_move(None, ai_from, ai_to):  # AI doesn't have user_id
                            self.broadcast_to_game({
                                "type": "move_made",
                                "from": ai_from,
                                "to": ai_to,
                                "board": game.get_board_state(),
                                "turn": game.get_current_turn(),
                                "moves": game.get_legal_moves(),
                                "game_status": game.get_game_status(),
                                "ai_move": True,
                                "is_check": game.board.is_check()
                            })

                            # Check for game end after AI move
                            ai_status = game.get_game_status()
                            if ai_status in ["checkmate", "stalemate", "draw"]:
                                ai_winner_id = game.get_winner_id() if ai_status == "checkmate" else None
                                Database.end_game(self.game_id, ai_winner_id, ai_status)
                                self.broadcast_to_game({
                                    "type": "game_ended",
                                    "status": ai_status,
                                    "winner": ai_winner_id
                                })

                # Schedule the AI move
                tornado.ioloop.IOLoop.current().add_callback(make_ai_move)
        else:
            # Provide specific error message
            error_message = "Invalid move"
            if game.board.is_check():
                error_message = "Your king is in check! You must make a move to get out of check."
            self.write_message({
                "type": "error",
                "message": error_message,
                "is_check": game.board.is_check(),
                "legal_moves": game.get_legal_moves()
            })

    def handle_chat(self, data):
        message = data.get("message", "")
        user = Database.get_user_by_id(self.user_id)
        if user and message:
            self.broadcast_to_game({
                "type": "chat",
                "user": user['username'],
                "message": message,
                "timestamp": datetime.now().isoformat()
            })

    def handle_draw_offer(self):
        game = active_games.get(self.game_id)
        if game:
            self.broadcast_to_game({
                "type": "draw_offered",
                "by": self.user_id
            }, exclude_self=True)

    def handle_resignation(self):
        game = active_games.get(self.game_id)
        if game:
            # Determine winner
            winner_id = game.black_player_id if self.user_id == game.white_player_id else game.white_player_id
            Database.end_game(self.game_id, winner_id, "resignation")

            self.broadcast_to_game({
                "type": "game_ended",
                "status": "resignation",
                "winner": winner_id
            })

    def broadcast_to_game(self, message, exclude_self=False):
        if self.game_id in websocket_connections:
            for connection in websocket_connections[self.game_id]:
                if exclude_self and connection == self:
                    continue
                try:
                    connection.write_message(message)
                except:
                    pass

    def on_close(self):
        if self.game_id in websocket_connections:
            websocket_connections[self.game_id].remove(self)
            if not websocket_connections[self.game_id]:
                del websocket_connections[self.game_id]

    def get_secure_cookie(self, name):
        # Override to get cookie from WebSocket
        cookie_header = self.request.headers.get("Cookie")
        if cookie_header:
            cookies = tornado.httputil.parse_cookie(cookie_header)
            if name in cookies:
                # Use the application's cookie secret to decode the secure cookie
                value = tornado.web.decode_signed_value(
                    self.application.settings["cookie_secret"],
                    name,
                    cookies[name]
                )
                if value:
                    return value
        return None


class LeaderboardHandler(BaseHandler):
    def get(self):
        top_players = Database.get_top_players(100)

        # Calculate additional statistics
        total_players = len(top_players)
        highest_rating = max([p['elo_rating'] for p in top_players]) if top_players else 0
        average_rating = round(sum([p['elo_rating'] for p in top_players]) / total_players) if total_players > 0 else 0

        # Calculate games played today (simplified - could be enhanced with actual date checking)
        total_games = sum([p['games_played'] for p in top_players] if top_players else [0])

        self.render("leaderboard.html",
                    players=top_players,
                    total_players=total_players,
                    total_games=total_games,
                    highest_rating=highest_rating,
                    average_rating=average_rating,
                    total_pages=1)  # For simplicity, using 1 page