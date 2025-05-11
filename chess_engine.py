# chess_engine.py
import chess
import chess.engine
import json
from models import Database


class ChessGame:
    def __init__(self, game_id, white_player_id, black_player_id, is_ai_game=False):
        self.game_id = game_id
        self.white_player_id = white_player_id
        self.black_player_id = black_player_id
        self.is_ai_game = is_ai_game

        # Load existing game state or create new
        game_data = Database.get_game(game_id)
        if game_data and game_data['fen_position'] and game_data[
            'fen_position'] != "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
            self.board = chess.Board(game_data['fen_position'])
            try:
                self.move_history = json.loads(game_data['moves']) if game_data['moves'] else []
            except:
                self.move_history = []
        else:
            self.board = chess.Board()
            self.move_history = []

    def get_board_state(self):
        """Return current board state as a dictionary for the frontend"""
        board_state = {}

        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                board_state[chess.square_name(square)] = {
                    'piece': piece.symbol(),
                    'color': 'white' if piece.color else 'black'
                }

        return board_state

    def get_current_turn(self):
        """Return whose turn it is"""
        return 'white' if self.board.turn else 'black'

    def get_legal_moves(self):
        """Return all legal moves in UCI format"""
        legal_moves = []
        for move in self.board.legal_moves:
            legal_moves.append({
                'from': chess.square_name(move.from_square),
                'to': chess.square_name(move.to_square),
                'promotion': move.promotion if move.promotion else None
            })
        return legal_moves

    def make_move(self, user_id, from_square, to_square, promotion=None):
        """Make a move on the board"""
        # Debug logging
        print(f"DEBUG: make_move called - user_id: {user_id}, turn: {self.board.turn}")
        print(f"DEBUG: white_player_id: {self.white_player_id}, black_player_id: {self.black_player_id}")
        print(f"DEBUG: Is in check: {self.board.is_check()}")

        # Validate it's the player's turn
        if not self.is_ai_game and user_id:
            if self.board.turn and user_id != self.white_player_id:
                print(f"Invalid turn: White's turn but user {user_id} is not white player {self.white_player_id}")
                return False
            if not self.board.turn and user_id != self.black_player_id:
                print(f"Invalid turn: Black's turn but user {user_id} is not black player {self.black_player_id}")
                return False

        # Create the move
        try:
            from_sq = chess.parse_square(from_square)
            to_sq = chess.parse_square(to_square)

            # Check if promotion is needed
            piece = self.board.piece_at(from_sq)
            if piece and piece.piece_type == chess.PAWN:
                if (piece.color and chess.square_rank(to_sq) == 7) or \
                        (not piece.color and chess.square_rank(to_sq) == 0):
                    if not promotion:
                        promotion = chess.QUEEN  # Default to queen
                    if isinstance(promotion, str):
                        promotion = chess.Piece.from_symbol(promotion.upper()).piece_type

            move = chess.Move(from_sq, to_sq, promotion=promotion)

            # Validate the move is legal
            if move not in self.board.legal_moves:
                if self.board.is_check():
                    print(f"Move {move} invalid: You must get out of check!")
                    print(f"Legal moves in check: {[str(m) for m in self.board.legal_moves]}")
                else:
                    print(f"Illegal move: {move} not in legal moves")
                return False

            # Make the move
            san_notation = self.board.san(move)  # Get SAN before making the move
            self.board.push(move)

            # Store move in history
            move_data = {
                'from': from_square,
                'to': to_square,
                'promotion': promotion,
                'san': san_notation,
                'fen': self.board.fen()
            }
            self.move_history.append(move_data)

            # Update database
            Database.update_game(self.game_id, self.board.fen(), json.dumps(self.move_history))

            return True

        except Exception as e:
            print(f"Error making move: {e}")
            print(f"Current board state: {self.board.fen()}")
            print(f"Attempted move: {from_square} to {to_square}")
            return False

    def get_game_status(self):
        """Check if the game has ended"""
        if self.board.is_checkmate():
            return "checkmate"
        elif self.board.is_stalemate():
            return "stalemate"
        elif self.board.is_insufficient_material():
            return "draw"
        elif self.board.is_seventyfive_moves():
            return "draw"
        elif self.board.is_fivefold_repetition():
            return "draw"
        elif self.board.is_check():
            return "check"
        else:
            return "active"

    def get_winner_id(self):
        """Return the winner's user ID if the game has ended"""
        if self.board.is_checkmate():
            # The player who just moved wins
            if self.board.turn:  # It's white's turn but black just checkmated
                return self.black_player_id
            else:  # It's black's turn but white just checkmated
                return self.white_player_id
        return None

    def get_fen(self):
        """Return the current FEN position"""
        return self.board.fen()

    def get_move_history(self):
        """Return the move history"""
        return self.move_history

    def get_piece_at(self, square):
        """Get piece at a specific square"""
        piece = self.board.piece_at(chess.parse_square(square))
        if piece:
            return {
                'piece': piece.symbol(),
                'color': 'white' if piece.color else 'black'
            }
        return None

    def is_square_attacked(self, square, by_color):
        """Check if a square is attacked by a specific color"""
        return self.board.is_attacked_by(by_color, chess.parse_square(square))

    def get_attacking_pieces(self, square):
        """Get all pieces attacking a specific square"""
        attackers = []
        sq = chess.parse_square(square)

        for attacker_square in chess.SQUARES:
            piece = self.board.piece_at(attacker_square)
            if piece and self.board.is_attacked_by(piece.color, sq):
                attackers.append({
                    'square': chess.square_name(attacker_square),
                    'piece': piece.symbol(),
                    'color': 'white' if piece.color else 'black'
                })

        return attackers