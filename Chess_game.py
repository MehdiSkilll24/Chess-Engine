import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, QGridLayout, QVBoxLayout, QStyle, QLabel
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5 import QtCore
from PyQt5.QtGui import QIcon
import chess
import random
from ai_logic import ai_play

color_list = ["#f0d9b5", "#b58863"]


class ChessBoard(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setMinimumSize(1800, 1000)
        self.setMaximumSize(1920, 1080)
        self.grid = QGridLayout()
        self.grid.setSpacing(0)
        board_widget = QWidget()
        board_widget.setLayout(self.grid)
        
        self.tiles = {}
        self.board = chess.Board()
        self.zobrist = 0
        self.current_hash = self.board._transposition_key()

        self.selected_square = None
        self.human_color = chess.WHITE
        
        self.undo_button = QPushButton()
        self.undo_button.setIcon(QIcon('undo arrow.webp'))
        self.undo_button.setIconSize(QtCore.QSize(40, 40))
        self.undo_button.clicked.connect(self.undo_move)
          
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(board_widget, 1)
        self.status_label = QLabel("Your turn")
        self.status_label.setStyleSheet("""
        QLabel {
            font-size: 18px;
            font-weight: bold;
            color: white;
            background-color: rgba(0,0,0,0.5);
            padding: 5px;
        }
        """)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # Add to layout with proper positioning
        layout = QVBoxLayout()
        layout.addWidget(self.status_label, alignment=Qt.AlignLeft | Qt.AlignTop)  # Top-left
        layout.addWidget(board_widget, 1)  # Main board
        layout.addWidget(self.undo_button, 0, Qt.AlignCenter)  # Button
        self.setLayout(layout)
    
        for row in range(8):
            for col in range(8):
                btn = QPushButton()
                color_index = (row + col) % 2
                btn.setStyleSheet(f"background-color: {color_list[color_index]}; border: none;")
                btn.clicked.connect(lambda _, r=row, c=col: self.handle_square_click(r, c))
                self.grid.addWidget(btn, row, col)
                self.tiles[(row, col)] = btn
                
        self.fill_board()

    def resizeEvent(self, event):
        board_size = min(self.width(), self.height())
        tile_size = board_size // 8
        font_size = max(12, tile_size//2)

        for row in range(8):
            for col in range(8):
                btn = self.tiles[(row, col)]
                btn.setFixedSize(tile_size, tile_size)
                font = btn.font()
                font.setPixelSize(font_size)
                btn.setFont(font)
                square = (7-row)*8 + col
                piece = self.board.piece_at(square)
                text_color = "#000000" if(piece and piece.color == chess.BLACK) else "#FFFFFF" if piece else "transparent"
                self.tiles[(row, col)].setStyleSheet(f"""
                    background-color: {color_list[(row + col) % 2]};
                    border: none;
                    font-size: {font_size}px;
                    font-weight: bold;
                    color:{text_color};
                """)
        margin_right = (self.width() - board_size) // 2
        margin_left = (self.height() - board_size) // 2
        self.grid.setContentsMargins(margin_right, margin_left, margin_right , margin_left)

        super().resizeEvent(event)

    def undo_move(self):
        for i in range(2):
            if not self.board.move_stack:
                break
            
            self.board.pop()

        if not self.board.move_stack:
            self.undo_button.setDisabled(True)

        self.fill_board()
        self.resizeEvent(None)

    def fill_board(self):
        
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            row = 7 - square // 8
            col = square % 8
            btn = self.tiles[(row, col)]
            color_index = (row + col) % 2
            btn.setStyleSheet(f"""
                background-color: {color_list[color_index]};
                border: none;
                font-weight: bold;
            """)
            if piece:
                btn.setText(piece.unicode_symbol())
                color = "#000000" if piece.color == chess.BLACK else "#FFFFFF"
                current_style = btn.styleSheet()
                btn.setStyleSheet(current_style + f"color: {color};")
            else:
                btn.setText("")
                
    
    def handle_square_click(self, row, col):
 
        
        square = (7 - row) * 8 + col
        
        if self.selected_square == None:
            piece = self.board.piece_at(square) 
            if piece and piece.color == self.board.turn:
                self.selected_square = square   
                self.highlight_square(row, col, "#8bb381")
            

        else:
            if square == self.selected_square:
                return
            move = chess.Move(self.selected_square, square)
            
            piece = self.board.piece_at(self.selected_square)
            
            if piece and piece.piece_type == chess.PAWN:
                to_rank = chess.square_rank(square)
                if(piece.color == chess.BLACK and to_rank == 0) or (piece.color == chess.WHITE and to_rank == 7):
                    move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)
            
            if move in self.board.legal_moves:
                self.current_hash = self.board._transposition_key()
                self.board.push(move)
                self.undo_button.setEnabled(True)
                self.fill_board()
                self.reset_highlight()
                square = move.to_square
                row, col = divmod(chess.square_mirror(square), 8)
                self.highlight_square(row, col, "#aeb381")
                print(move)
                self.selected_square = None
                if self.board.is_checkmate():
                    print("AI in Checkmate !")
                elif self.board.is_check():
                    print("AI in Check !")
                if self.board.turn != self.human_color:  
                    self.ai_turn()
            else:
                self.reset_highlight()
                self.selected_square = None
                return

    def ai_turn(self):
        self.status_label.setText("Ai is thinking...")
        QApplication.processEvents()
        
        move = ai_play(self.board, self.current_hash)
        if move:
            self.current_hash = self.board._transposition_key()
            self.board.push(move)
            self.fill_board()
            print(move)
            square_start = move.from_square
            square_end = move.to_square
            ai_squarestart = chess.square_mirror(square_start)
            row, col = divmod(ai_squarestart, 8)
            self.highlight_square(row,col, "#349699")
            ai_square_end = chess.square_mirror(square_end)
            row,col = divmod(ai_square_end, 8)
            self.highlight_square(row,col, "#265285")
            if self.board.is_checkmate():
                print("Player in Checkmate !")
            elif self.board.is_check():
                print("Player in Check !")
        self.status_label.setText("Your turn")
    
    
    def highlight_square(self, row, col, color):
        piece = self.board.piece_at((7-row) * 8 + col)
        if piece is None:
            text_color = "#000000"
        else:    
            text_color = "#000000" if piece.color == chess.BLACK else "#FFFFFF"
        self.tiles[(row, col)].setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #333;
            font-size: {self.tiles[(row, col)].font().pixelSize()}px;
            font-weight: bold;
            color: {text_color};
        """)
    
    def reset_highlight(self):
        for row in range(8):
            for col in range(8):
                color = color_list[(row+col) % 2]
                self.tiles[(row, col)].setStyleSheet(f"""
                    background-color: {color};
                    border: none;
                    font-size: {self.tiles[(row, col)].font().pixelSize()}px;
                    font-weight: bold;
                """)
                square = (7-row) * 8 + col
                piece = self.board.piece_at(square)
                if piece:
                    current_style = self.tiles[(row, col)].styleSheet()
                    new_color = "#000000" if piece.color == chess.BLACK else "#FFFFFF"
                    self.tiles[(row, col)].setStyleSheet(current_style + f"color: {new_color};")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess")
        self.board = ChessBoard()
        self.setCentralWidget(self.board)
        self.setStyleSheet("background-color: #1f5754;")
        self.showMaximized()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
