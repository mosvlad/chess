# chess_ai.py
import chess
import random
from typing import Optional, Tuple


class ChessAI:
    """Simple chess AI that uses basic evaluation and minimax with limited depth"""

    # Piece values for material evaluation
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000
    }

    # Position bonus tables for different pieces
    PAWN_TABLE = [
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0
    ]

    KNIGHT_TABLE = [
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50,
    ]

    BISHOP_TABLE = [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20,
    ]

    ROOK_TABLE = [
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, 10, 10, 10, 10, 5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        0, 0, 0, 5, 5, 0, 0, 0
    ]

    QUEEN_TABLE = [
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20
    ]

    KING_MIDDLE_GAME_TABLE = [
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20,
        20, 30, 10, 0, 0, 10, 30, 20
    ]

    @classmethod
    def get_best_move(cls, board: chess.Board, depth: int = 3) -> Optional[Tuple[str, str]]:
        """Get the best move for the current position"""
        best_move = None
        best_value = float('-inf')

        # Get all legal moves
        legal_moves = list(board.legal_moves)

        if not legal_moves:
            return None

        # Add some randomness to the opening
        if len(board.move_stack) < 4:
            random.shuffle(legal_moves)

        # Evaluate each move
        for move in legal_moves:
            board.push(move)
            value = cls.minimax(board, depth - 1, float('-inf'), float('inf'), False)
            board.pop()

            if value > best_value:
                best_value = value
                best_move = move

        if best_move:
            return (chess.square_name(best_move.from_square), chess.square_name(best_move.to_square))

        # Fallback to random move
        move = random.choice(legal_moves)
        return (chess.square_name(move.from_square), chess.square_name(move.to_square))

    @classmethod
    def minimax(cls, board: chess.Board, depth: int, alpha: float, beta: float, maximizing_player: bool) -> float:
        """Minimax algorithm with alpha-beta pruning"""
        if depth == 0 or board.is_game_over():
            return cls.evaluate_position(board)

        if maximizing_player:
            max_eval = float('-inf')
            for move in board.legal_moves:
                board.push(move)
                eval_score = cls.minimax(board, depth - 1, alpha, beta, False)
                board.pop()
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in board.legal_moves:
                board.push(move)
                eval_score = cls.minimax(board, depth - 1, alpha, beta, True)
                board.pop()
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    @classmethod
    def evaluate_position(cls, board: chess.Board) -> float:
        """Evaluate the current position"""
        if board.is_checkmate():
            return -20000 if board.turn else 20000

        if board.is_stalemate() or board.is_insufficient_material():
            return 0

        evaluation = 0

        # Material evaluation
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                value = cls.PIECE_VALUES.get(piece.piece_type, 0)
                if piece.color == chess.WHITE:
                    evaluation += value
                else:
                    evaluation -= value

                # Positional evaluation
                evaluation += cls.get_position_value(piece, square)

        # Mobility evaluation (number of legal moves)
        evaluation += len(list(board.legal_moves)) * 10
        board.push(chess.Move.null())
        evaluation -= len(list(board.legal_moves)) * 10
        board.pop()

        # King safety evaluation
        evaluation += cls.evaluate_king_safety(board, chess.WHITE)
        evaluation -= cls.evaluate_king_safety(board, chess.BLACK)

        # Pawn structure evaluation
        evaluation += cls.evaluate_pawn_structure(board, chess.WHITE)
        evaluation -= cls.evaluate_pawn_structure(board, chess.BLACK)

        return evaluation

    @classmethod
    def get_position_value(cls, piece: chess.Piece, square: int) -> float:
        """Get positional value for a piece"""
        piece_type = piece.piece_type
        color = piece.color

        # Flip square for black pieces
        if color == chess.BLACK:
            square = 63 - square

        if piece_type == chess.PAWN:
            value = cls.PAWN_TABLE[square]
        elif piece_type == chess.KNIGHT:
            value = cls.KNIGHT_TABLE[square]
        elif piece_type == chess.BISHOP:
            value = cls.BISHOP_TABLE[square]
        elif piece_type == chess.ROOK:
            value = cls.ROOK_TABLE[square]
        elif piece_type == chess.QUEEN:
            value = cls.QUEEN_TABLE[square]
        elif piece_type == chess.KING:
            value = cls.KING_MIDDLE_GAME_TABLE[square]
        else:
            value = 0

        return value if color == chess.WHITE else -value

    @classmethod
    def evaluate_king_safety(cls, board: chess.Board, color: bool) -> float:
        """Evaluate king safety"""
        king_square = board.king(color)
        if king_square is None:
            return 0

        safety_score = 0

        # Check if king is castled
        if color == chess.WHITE:
            if king_square in [chess.G1, chess.C1]:
                safety_score += 30
        else:
            if king_square in [chess.G8, chess.C8]:
                safety_score += 30

        # Penalty for exposed king
        attackers = 0
        for attacker_square in chess.SQUARES:
            piece = board.piece_at(attacker_square)
            if piece and piece.color != color:
                if board.is_attacked_by(piece.color, king_square):
                    attackers += 1

        safety_score -= attackers * 20

        return safety_score

    @classmethod
    def evaluate_pawn_structure(cls, board: chess.Board, color: bool) -> float:
        """Evaluate pawn structure"""
        score = 0
        pawns = board.pieces(chess.PAWN, color)

        # Doubled pawns penalty
        files = {}
        for pawn in pawns:
            file = chess.square_file(pawn)
            files[file] = files.get(file, 0) + 1

        for count in files.values():
            if count > 1:
                score -= (count - 1) * 20

        # Isolated pawns penalty
        for pawn in pawns:
            file = chess.square_file(pawn)
            is_isolated = True

            # Check adjacent files
            for adj_file in [file - 1, file + 1]:
                if 0 <= adj_file <= 7:
                    for adj_pawn in pawns:
                        if chess.square_file(adj_pawn) == adj_file:
                            is_isolated = False
                            break

            if is_isolated:
                score -= 25

        # Passed pawns bonus
        for pawn in pawns:
            if cls.is_passed_pawn(board, pawn, color):
                score += 50

        return score

    @classmethod
    def is_passed_pawn(cls, board: chess.Board, pawn_square: int, color: bool) -> bool:
        """Check if a pawn is a passed pawn"""
        file = chess.square_file(pawn_square)
        rank = chess.square_rank(pawn_square)

        # Check files in front of the pawn
        start_rank = rank + 1 if color else rank - 1
        end_rank = 8 if color else -1
        step = 1 if color else -1

        for check_rank in range(start_rank, end_rank, step):
            for check_file in [file - 1, file, file + 1]:
                if 0 <= check_file <= 7:
                    square = chess.square(check_file, check_rank)
                    piece = board.piece_at(square)
                    if piece and piece.piece_type == chess.PAWN and piece.color != color:
                        return False

        return True