import chess, random
from Piece_data import PIECE_VALUES, shield_bonus, PHASE_WEIGHTS, pst_dict, end_game_pst_dict, KING_PST, QUEEN_PST, ROOK_PST, BISHOP_PST, KNIGHT_PST, PAWN_PST

REDUCED_PENALTY = 5
FULL_PENALTY = 10
EXACT = 0
LOWERBOUND = -1
UPPERBOUND = 1
Flag = 0


TT = {}

def MVV_LVA(board, move):
    piece = board.piece_at(move.from_square)
    if board.is_en_passant(move):
        direction = 1 if piece.color == chess.WHITE else - 1
        ep_square = move.to_square - 8 * direction
        target = board.piece_at(ep_square)
    else:    
        target = board.piece_at(move.to_square)
        
    return abs((PIECE_VALUES[target.piece_type] - PIECE_VALUES[piece.piece_type]) // 10)

def order_moves(board):
    moves = list(board.legal_moves)
    def move_score(move):
        score = 0
        if board.is_castling(move):
            score += 50
        score += MVV_LVA(board, move) if board.is_capture(move) else 0
        if board.gives_check(move):
            score += 25
        return score
    moves.sort(key=move_score, reverse=True)
    return moves

def eval_mobility(board):
    total = 0
    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        sign = 7 if piece and piece.color == chess.WHITE else -7
        total += sign
    return total

def eval_king_safety(board):
    total = 0
    for piece in [chess.KING]:
        for color in [chess.WHITE, chess.BLACK]:
            sign = 1 if color == chess.WHITE else - 1
            king_sq = board.pieces(piece, color)
            king_sq = next(iter(king_sq), None)
            if king_sq is None:
                continue
            piece_obj = board.piece_at(king_sq)
            square_set = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
            total += king_safety_adj_fct(board, sign, square_set, piece_obj)
            
    return total
                    
def king_safety_adj_fct(board, sign, square_set, piece):
    total = 0
    castled_squares = [chess.G1, chess.C1] if piece.color == chess.WHITE else [chess.G8, chess.C8]
    king_sq = board.king(piece.color)
    if king_sq is None:
        return 0
    king_file = chess.square_file(king_sq)
    centrality_penalty = abs(king_file - 3.5) * 2
    if king_sq not in castled_squares:
        total -= centrality_penalty * sign
    
    if king_sq in castled_squares:
        total += 5 * sign
        shield_rank = 6 if piece.color == chess.WHITE else 1
        shield_files = [chess.square_file(king_sq) - 1, chess.square_file(king_sq), chess.square_file(king_sq) + 1]
        shield_count = 0
        for f in shield_files:
            if 0 <= f < 8:
                shield_piece = board.piece_at(chess.square(f, shield_rank))
                if shield_piece and shield_piece.piece_type == chess.PAWN and shield_piece.color == piece.color:
                    shield_count += 1
        total += sign * 15 * (2 * shield_count - 3)

      
    for sq in square_set:
        neighbour = board.piece_at(sq)
        if not neighbour:
            total -= 25 * sign
            continue
        
        if neighbour.piece_type in [chess.ROOK, chess.QUEEN]:
            value = 2
        elif neighbour.piece_type in [chess.KNIGHT, chess.BISHOP]:
            value = 3
        elif neighbour.piece_type == chess.PAWN:
            value = 7
        else:   
            continue

        if neighbour.color == piece.color:
            total += value * sign
        else:
            total -= value * sign
    total += king_safety_long_threat_fct(board, sign, king_sq, piece)
    return total

        

def king_safety_long_threat_fct(board, sign, king_sq, piece):   
    total = 0 
    row, col = divmod(king_sq, 8)
    directions = [(1,-1), (1,1), (-1, -1), (-1, 1), (1,0), (0, -1), (0, 1), (-1, 0)]
    for dr, dc in directions:
        distance = 0
        piece_on_ray = None
        target = (row + dr, col + dc)
        target_r, target_c = target
        square = target_r * 8 + target_c
        while 0<=target_r<8 and 0<=target_c<8:
            square = target_r * 8 + target_c
            if board.piece_at(square):
                piece_on_ray = board.piece_at(square)
                break
            target_r += dr
            target_c += dc
        if piece_on_ray:
            
            distance = max(abs(target_r - row), abs(target_c - col))
            if distance == 1:
                continue
            
            if piece_on_ray.color == piece.color:
                total+= shield_bonus.get(piece_on_ray.piece_type, 0) * sign
                target_r += dr
                target_c += dc
                
                while 0<=target_r<8 and 0<=target_c<8:
                    square = target_r * 8 + target_c
                    shield_ray_piece = board.piece_at(square)
                    if shield_ray_piece:
                        if shield_ray_piece.color != piece.color:
                            if abs(dr) == abs(dc) and shield_ray_piece.piece_type in [chess.BISHOP, chess.QUEEN]:
                                total -= REDUCED_PENALTY * sign
                            elif shield_ray_piece.piece_type in [chess.QUEEN, chess.ROOK]:
                                total -= (REDUCED_PENALTY + 0.5) * sign
                        break
                    target_r += dr
                    target_c += dc
            else:
                if abs(dr) == abs(dc) and piece_on_ray.piece_type in [chess.BISHOP, chess.QUEEN]:
                    total -= FULL_PENALTY * sign
                elif piece_on_ray.piece_type in [chess.ROOK, chess.QUEEN]:
                    total -= (FULL_PENALTY + 0.5) * sign

    return total

def game_phase(board):
    phase = 0
    for piece, weight in PHASE_WEIGHTS.items():
        phase += weight * (len(board.pieces(piece, chess.WHITE))) + (len(board.pieces(piece, chess.BLACK)))
    return phase

def eval_end_game_mobility(board):
    total = 0
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else - 1
        enemy_color = not color
        king_squares = board.pieces(chess.KING, enemy_color)
        enemy_king_sq = next(iter(king_squares), None)
        mobility_count = sum(1 for move in board.legal_moves if move.from_square == enemy_king_sq)
        total -= mobility_count * 40 * sign

    return total
        
def eval_rook_structure(board):
    total = 0
    directions = [(1,0), (0, -1), (0, 1), (-1, 0)]
    for color in [chess.WHITE, chess.BLACK]:
        king_sq = board.pieces(chess.KING, color)
        if not king_sq:
            continue
        sign = 1 if color == chess.WHITE else - 1
        rook_square = board.pieces(chess.ROOK, color)
        if not rook_square:
            continue
        for sq in rook_square:
            row, col = divmod(sq, 8)
            for dr, dc in directions:
                found = False
                target = (row + dr, col + dc)
                target_r, target_c = target
                square = target_r * 8 + target_c
                while 0<=target_r<8 and 0<=target_c<8:
                    square = target_r * 8 + target_c
                    piece = board.piece_at(square)
                    if piece and piece.color != color:
                        found = True
                        total += 30 * sign if piece.piece_type != chess.KING else (60 * sign)
                        break
                    elif piece and piece.piece_type == chess.PAWN and piece.color == color:
                        found = True
                        total -= 30 * sign
                        break
                    target_r += dr
                    target_c += dc
                if not found:
                    total += 15 * sign
    return total

            
def eval_pawn_structure(board):
    total = 0
    white_doubled = [0] * 8
    black_doubled = [0] * 8
    
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else - 1
        square_set = board.pieces(chess.PAWN, color)
        for sq in square_set:
            p_r = p_l = None 
            square = sq if color == chess.WHITE else chess.square_mirror(sq)
            row, col = divmod(square, 8)
            if color == chess.WHITE:
                white_doubled[col] += 1
            else:
                black_doubled[col] += 1
            if 0 <= row < 8: 
                if 0 < col < 7:
                    adj_r = (row + 1) * 8 + (col + 1) if color == chess.WHITE else (row - 1) * 8 + (col + 1)
                    p_r = board.piece_at(adj_r)
                    adj_l = (row + 1) * 8 + (col - 1) if color == chess.WHITE else (row - 1) * 8 + (col - 1)
                    p_l = board.piece_at(adj_l)
                elif col == 0:
                    adj_r = (row + 1) * 8 + (col + 1) if color == chess.WHITE else (row - 1) * 8 + (col + 1)
                    p_r = board.piece_at(adj_r)
                elif col == 7:
                    adj_l = (row + 1) * 8 + (col - 1) if color == chess.WHITE else (row - 1) * 8 + (col - 1)
                    p_l = board.piece_at(adj_l)
                    
            if (p_r and p_r.piece_type == chess.PAWN) or (p_l and p_l.piece_type == chess.PAWN):
                total += 30 * sign 
                
        for file in range(8):
            if sign == 1:
                total -= (white_doubled[file] - 1) * 30 
            else:
                total += (black_doubled[file] - 1) * 30
                
    return total

def eval_material(board):
    total = 0
    for piece in [chess.KNIGHT, chess.ROOK, chess.QUEEN, chess.KING, chess.BISHOP, chess.PAWN]:
        for color in [chess.WHITE, chess.BLACK]:
            sign = 1 if color == chess.WHITE else - 1
            total += len(board.pieces(piece, color)) * PIECE_VALUES[piece] * sign
    return total 
        
    
def eval_pst(board):
    total = 0

    phase = game_phase(board)
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else - 1
        for piece in [chess.PAWN, chess.BISHOP, chess.KNIGHT, chess.ROOK, chess.QUEEN, chess.KING]:
            square_set = board.pieces(piece, color)
            for sq in square_set:
                idx = chess.square_mirror(sq) if color == chess.BLACK else sq
                pst = pst_dict[piece] if phase > 20 else end_game_pst_dict[piece]
                total += pst[idx] * sign

    return total

def eval(board):
    total = 0
    phase = game_phase(board)
    phase_norm = phase / 24.0

    pawn_structure = eval_pawn_structure(board) * (1 + 0.3*(1 - phase_norm))
    material = eval_material(board) * (1 - 0.65 * (1 - phase_norm))
    king_safety = eval_king_safety(board) * (1 - 0.5*(1 - phase_norm))
    rook_structure = eval_rook_structure(board) * (1 + 0.7 * (1 - phase_norm))
    pst = eval_pst(board) * (1.15 + (1 - phase_norm))
    end_game_mobility = eval_end_game_mobility(board)
    mobility = eval_mobility(board) * phase_norm + end_game_mobility * (1-phase_norm)
    total = material * 0.7 + pst * 0.4 + pawn_structure * 0.25 + rook_structure * 0.2 + king_safety * 0.4 + mobility * 0.3 + end_game_mobility * 0.3
    return total


def alphabeta(board, depth, alpha, beta, is_maximizing):
    current_hash = board._transposition_key()
    mate_score = 32000
    original_alpha = alpha
    original_beta = beta
    value = -float('inf') if is_maximizing else float('inf')
    
    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return -mate_score + depth if board.turn == chess.WHITE else mate_score - depth
        return eval(board)
    
    if current_hash in TT:
        entry = TT[current_hash]
        if entry["depth"] >= depth:
            if entry["Flag"] == EXACT:
                return entry["value"]
            elif entry["Flag"] == LOWERBOUND:
                beta = min(beta, entry["value"])
            elif entry["Flag"] == UPPERBOUND:
                alpha = max(alpha, entry["value"])
            if alpha >= beta:
                return entry["value"]
    
    if not board.is_check() and depth >= 3:
        board.push(chess.Move.null())
        current_hash = board._transposition_key()
        score = alphabeta(board, depth - 3, alpha, beta, not is_maximizing)
        board.pop()
        if (is_maximizing and score >= beta) or (not is_maximizing and score <= alpha):
            return score
        
    for move in order_moves(board):
        board.push(move)
        if board.is_repetition() or board.is_stalemate() or board.is_insufficient_material():
            score = 0
        else:
            score = alphabeta(board, depth - 1, alpha, beta, not is_maximizing)
            
        if is_maximizing:
            value = max(value, score)
            alpha = max(alpha, value)
        else:
            value = min(value, score)
            beta = min(beta, value)
            
        board.pop()
        if beta<=alpha:
            break
            
    
    if value >= original_beta:
        Flag = LOWERBOUND
    elif value <= original_alpha:
        Flag = UPPERBOUND
    else:
        Flag = EXACT
        
    if current_hash not in TT or TT[current_hash]["depth"] < depth:
        TT[current_hash] = {
            "depth" : depth,
            "value" : value,
            "Flag" : Flag
        }
    return value

def select_best_move(board, hash, depth):
    is_maximizing = board.turn == chess.WHITE
    best_move = None
    best_value = -float('inf') if is_maximizing else float('inf')
    alpha = -float('inf')
    beta = float('inf')
    
    for move in order_moves(board):
        board.push(move)
        score = alphabeta(board, depth - 1, -float('inf'), float('inf'), not is_maximizing)
        board.pop()
        
        if is_maximizing:
            if score > best_value:
                best_value = score
                best_move = move
                alpha = max(alpha, score)
        else:
            if score < best_value:
                best_value = score
                best_move = move
                beta = min(beta, score)
                
        if beta <= alpha:
            break
        
    return best_move

def ai_move(board, hash, depth = 4):
    return select_best_move(board,  hash, depth)

def ai_play(board,hash):
    if board.is_game_over():
        return None

    return ai_move(board, hash)