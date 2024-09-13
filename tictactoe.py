from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import json
import os
import threading
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Bạn có thể thay đổi khóa bí mật này
app.permanent_session_lifetime = 3600  # Thời gian sống của session

# Mapping giữa giá trị difficulty và tên hiển thị
difficulty_display = {
    'super_hard': 'Siêu khó',
    'hard': 'Khó',
    'normal': 'Bình thường',
    'easy': 'Dễ'
}

# Biến toàn cục để quản lý phòng chờ và trò chơi
waiting_room = []
game = {
    'players': [],
    'ready': {},
    'continue': {},
    'board': [' '] * 9,
    'turn': '',
    'game_over': False,
    'spectators': [],
    'message': ''
}

lock = threading.Lock()  # Để đảm bảo an toàn khi truy cập vào biến toàn cục


def check_winner(board, player):
    win_conditions = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Hàng ngang
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Hàng dọc
        [0, 4, 8], [2, 4, 6]              # Đường chéo
    ]
    for condition in win_conditions:
        if board[condition[0]] == board[condition[1]] == board[condition[2]] == player:
            return True
    return False


def board_full(board):
    return ' ' not in board


def minimax(board, depth, is_maximizing, ai_player, human_player, difficulty):
    if check_winner(board, ai_player):
        if difficulty == 'easy':
            return -10 + depth  # AI cố gắng thua
        else:
            return 10 - depth
    elif check_winner(board, human_player):
        if difficulty == 'easy':
            return 10 - depth  # AI cố gắng thua
        else:
            return depth - 10
    elif board_full(board):
        return 0

    if is_maximizing:
        best_score = -float('inf')
        for i in range(9):
            if board[i] == ' ':
                board[i] = ai_player
                score = minimax(board, depth + 1, False,
                                ai_player, human_player, difficulty)
                board[i] = ' '
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float('inf')
        for i in range(9):
            if board[i] == ' ':
                board[i] = human_player
                score = minimax(board, depth + 1, True,
                                ai_player, human_player, difficulty)
                board[i] = ' '
                best_score = min(score, best_score)
        return best_score


def best_move(board, ai_player, human_player, difficulty):
    if difficulty == 'super_hard':
        # AI không thể đánh bại
        return best_move_minimax(board, ai_player, human_player)
    elif difficulty == 'hard':
        # AI đánh ngẫu nhiên 10% thời gian
        if random.random() < 0.1:
            return random.choice([i for i in range(9) if board[i] == ' '])
        else:
            return best_move_minimax(board, ai_player, human_player)
    elif difficulty == 'normal':
        # AI đánh ngẫu nhiên 30% thời gian
        if random.random() < 0.3:
            return random.choice([i for i in range(9) if board[i] == ' '])
        else:
            return best_move_minimax(board, ai_player, human_player)
    elif difficulty == 'easy':
        # AI cố gắng thua
        return worst_move(board, ai_player, human_player)
    else:
        # Mặc định là siêu khó
        return best_move_minimax(board, ai_player, human_player)


def best_move_minimax(board, ai_player, human_player):
    best_score = -float('inf')
    move = -1
    for i in range(9):
        if board[i] == ' ':
            board[i] = ai_player
            score = minimax(board, 0, False, ai_player,
                            human_player, 'super_hard')
            board[i] = ' '
            if score > best_score:
                best_score = score
                move = i
    return move


def worst_move(board, ai_player, human_player):
    # AI cố gắng thua
    worst_score = float('inf')
    move = -1
    for i in range(9):
        if board[i] == ' ':
            board[i] = ai_player
            score = minimax(board, 0, False, ai_player, human_player, 'easy')
            board[i] = ' '
            if score < worst_score:
                worst_score = score
                move = i
    return move


def save_history(username, result, opponent=None, difficulty=None, mode='ai'):
    history = {}
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try:
                history = json.load(f)
            except json.decoder.JSONDecodeError:
                history = {}

    user_history = history.get(username, {})
    mode_history = user_history.get('mode', {})
    if mode == 'ai':
        ai_history = mode_history.get('ai', {})
        if difficulty not in ai_history:
            ai_history[difficulty] = {'games': [],
                                      'wins': 0, 'losses': 0, 'draws': 0}
        ai_history[difficulty]['games'].append(result)
        if result == 'Thắng':
            ai_history[difficulty]['wins'] += 1
        elif result == 'Thua':
            ai_history[difficulty]['losses'] += 1
        elif result == 'Hòa':
            ai_history[difficulty]['draws'] += 1
        mode_history['ai'] = ai_history
    elif mode == 'pvp':
        pvp_history = mode_history.get(
            'pvp', {'games': [], 'wins': 0, 'losses': 0, 'draws': 0})
        game_record = {
            'opponent': opponent,
            'result': result,
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        pvp_history['games'].append(game_record)
        if result == 'Thắng':
            pvp_history['wins'] += 1
        elif result == 'Thua':
            pvp_history['losses'] += 1
        elif result == 'Hòa':
            pvp_history['draws'] += 1
        mode_history['pvp'] = pvp_history

    user_history['mode'] = mode_history
    history[username] = user_history

    with open('history.json', 'w') as f:
        json.dump(history, f)


def get_score(username, difficulty):
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try:
                history = json.load(f)
            except json.decoder.JSONDecodeError:
                history = {}
        user_history = history.get(username, {})

        difficulty_history = user_history.get(
            difficulty, {'wins': 0, 'losses': 0, 'draws': 0})
        wins = difficulty_history.get('wins', 0)
        losses = difficulty_history.get('losses', 0)
        draws = difficulty_history.get('draws', 0)
        return wins, losses, draws
    else:
        return 0, 0, 0


def get_full_history(username):
    if os.path.exists('history.json'):
        with open('history.json', 'r') as f:
            try:
                history = json.load(f)
            except json.decoder.JSONDecodeError:
                history = {}

        user_history = history.get(username, {}).get('mode', {})

        return user_history
    else:
        return {}


def initialize_history_file():
    if not os.path.exists('history.json') or os.stat('history.json').st_size == 0:
        with open('history.json', 'w') as f:
            json.dump({}, f)


@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('mode') == 'ai':
        # Chế độ chơi với AI
        return ai_game()
    else:
        # Chế độ chơi với người
        return player_game()


def ai_game():
    # Khởi tạo bàn cờ và các biến trong session nếu chưa có
    if 'board' not in session or 'player_symbol' not in session or 'turn' not in session:
        session['board'] = [' '] * 9
        # Ngẫu nhiên chọn ký hiệu
        symbols = ['X', 'O']
        session['player_symbol'] = random.choice(symbols)
        session['ai_symbol'] = 'O' if session['player_symbol'] == 'X' else 'X'
        # Ngẫu nhiên quyết định ai đi trước
        session['turn'] = random.choice(
            [session['player_symbol'], session['ai_symbol']])
        # Thông báo ai đi trước
        if session['turn'] == session['player_symbol']:
            message = 'Bạn đi trước.'
        else:
            message = 'Máy đi trước.'
        session['message'] = message
        session['game_over'] = False  # Khởi tạo game_over là False

    board = session['board']
    message = session.get('message', '')
    # Giữ lại thông báo trong session
    message_from_session = session.get('message', None)
    game_over = session.get('game_over', False)
    difficulty = session.get('difficulty', 'super_hard')

    # Nếu là lượt của máy và trò chơi chưa kết thúc, máy sẽ đánh
    if session['turn'] == session['ai_symbol'] and not game_over:
        ai_player = session['ai_symbol']
        human_player = session['player_symbol']
        move = best_move(board, ai_player, human_player, difficulty)
        if move != -1:
            board[move] = ai_player
            print(f"AI moved to position {move}.")
        # Kiểm tra máy thắng
        if check_winner(board, ai_player):
            session['message'] = 'Bạn đã thua!'
            session['game_over'] = True
            print(f"Người chơi {session['username']}: Thua")
            save_history(session['username'], difficulty, 'Thua')
        # Kiểm tra hòa
        elif board_full(board):
            session['message'] = 'Hòa!'
            session['game_over'] = True
            print(f"Người chơi {session['username']}: Hòa")
            save_history(session['username'], difficulty, 'Hòa')
        else:
            session['turn'] = session['player_symbol']
        session['board'] = board

        # In tỉ số hiện tại sau khi AI đánh
        wins, losses, draws = get_score(session['username'], difficulty)
        print(f"Tỉ số hiện tại ({difficulty_display.get(difficulty, difficulty)}): {
              session['username']} {wins} - Máy {losses} - Hòa {draws}")

    # Cập nhật biến game_over
    game_over = session.get('game_over', False)

    # Kiểm tra xem có phải lượt của người chơi không
    is_player_turn = session['turn'] == session['player_symbol'] and not game_over

    # Lấy tỉ số của người chơi cho độ khó hiện tại
    wins, losses, draws = get_score(session['username'], difficulty)
    score_message = f"Tỉ số hiện tại ({difficulty_display.get(difficulty, difficulty)}): {
        session['username']} {wins} - Máy {losses} - Hòa {draws}"

    return render_template('game.html', board=board, message=message, message_from_session=message_from_session, game_over=game_over, score_message=score_message, is_player_turn=is_player_turn)


def player_game():
    global waiting_room, game, lock
    with lock:
        username = session['username']
        message = ''
        if username not in game['players'] and username not in game['spectators']:
            if len(game['players']) < 2:
                game['players'].append(username)
                game['ready'][username] = False
                game['continue'][username] = False
                message = 'Bạn đã tham gia trò chơi. Hãy nhấn "Sẵn sàng" khi bạn đã sẵn sàng.'
            else:
                game['spectators'].append(username)
                message = 'Bạn đang xem trò chơi.'
        else:
            if username in game['players']:
                if game['game_over']:
                    message = game['message'] + \
                        ' Trò chơi đã kết thúc. Hãy nhấn "Tiếp tục" để chơi ván mới.'
                elif not game['ready'].get(username):
                    message = 'Hãy nhấn "Sẵn sàng" khi bạn đã sẵn sàng.'
                elif not all(game['ready'].get(p, False) for p in game['players']):
                    message = 'Chờ người chơi khác sẵn sàng.'
                else:
                    message = game['message']
            else:
                message = 'Bạn đang xem trò chơi.'

        # Tính toán trạng thái sẵn sàng của tất cả người chơi
        all_players_ready = len(game['players']) == 2 and all(
            game['ready'].get(p, False) for p in game['players'])
        all_players_continue = len(game['players']) == 2 and all(
            game['continue'].get(p, False) for p in game['players'])

        # Bắt đầu trò chơi khi cả hai người chơi đã sẵn sàng
        if all_players_ready and not game['game_over'] and not game['turn']:
            # Khởi tạo trò chơi
            game['board'] = [' '] * 9
            game['turn'] = random.choice(game['players'])
            game['message'] = f"Người chơi {game['turn']} đi trước."
            message += ' ' + game['message']

        # Đặt lại trò chơi khi cả hai người chơi đã nhấn 'Tiếp tục'
        if game['game_over'] and all_players_continue:
            # Đặt lại trò chơi
            game['board'] = [' '] * 9
            game['game_over'] = False
            game['message'] = ''
            game['turn'] = ''
            # Đặt lại trạng thái 'ready' và 'continue'
            for p in game['players']:
                game['ready'][p] = False
                game['continue'][p] = False
            message = 'Trò chơi đã được đặt lại. Hãy nhấn "Sẵn sàng" khi bạn đã sẵn sàng.'

        board = game['board']
        game_over = game['game_over']
        message_from_session = session.get('message', None)
        is_player_turn = (username == game['turn'] and not game_over)

    return render_template(
        'game_pvp.html',
        board=board,
        message=message,
        message_from_session=message_from_session,
        game_over=game_over,
        is_player_turn=is_player_turn,
        game=game,
        all_players_ready=all_players_ready,
        all_players_continue=all_players_continue
    )


@app.route('/move', methods=['POST'])
def move():
    if session.get('mode') == 'ai':
        return ai_move()
    else:
        return player_move()


def ai_move():
    data = request.get_json()
    position = data['position']
    board = session.get('board', [' '] * 9)
    player_symbol = session['player_symbol']
    ai_symbol = session['ai_symbol']
    difficulty = session.get('difficulty', 'super_hard')

    # Kiểm tra nếu là lượt của người chơi
    if session['turn'] != player_symbol:
        return jsonify({'status': 'error', 'message': 'Không phải lượt của bạn.'})

    # Kiểm tra nước đi hợp lệ
    if board[position] != ' ':
        return jsonify({'status': 'error', 'message': 'Vị trí đã được đánh.'})
    board[position] = player_symbol
    print(f"Người chơi {session['username']} đã đánh vào vị trí {position}.")

    # Kiểm tra người chơi thắng
    if check_winner(board, player_symbol):
        session['message'] = 'Bạn đã thắng!'
        session['game_over'] = True
        print(f"Người chơi {session['username']}: Thắng")
        save_history(session['username'], difficulty, 'Thắng')
    # Kiểm tra hòa
    elif board_full(board):
        session['message'] = 'Hòa!'
        session['game_over'] = True
        print(f"Người chơi {session['username']}: Hòa")
        save_history(session['username'], difficulty, 'Hòa')
    else:
        # Lượt của máy sẽ được xử lý trong index()
        session['turn'] = ai_symbol

    session['board'] = board

    # In tỉ số hiện tại sau khi người chơi đánh
    wins, losses, draws = get_score(session['username'], difficulty)
    print(f"Tỉ số hiện tại ({difficulty_display.get(difficulty, difficulty)}): {
          session['username']} {wins} - Máy {losses} - Hòa {draws}")

    return jsonify({'status': 'ok'})


def player_move():
    global game, lock
    data = request.get_json()
    position = data['position']
    username = session['username']

    with lock:
        # Kiểm tra nếu là lượt của người chơi
        if game['turn'] != username:
            return jsonify({'status': 'error', 'message': 'Không phải lượt của bạn.'})

        board = game['board']

        # Kiểm tra nước đi hợp lệ
        if board[position] != ' ':
            return jsonify({'status': 'error', 'message': 'Vị trí đã được đánh.'})
        symbol = 'X' if game['players'].index(username) == 0 else 'O'
        board[position] = symbol
        print(f"Người chơi {username} đã đánh vào vị trí {position}.")

        # Kiểm tra người chơi thắng
        if check_winner(board, symbol):
            game['message'] = f'Người chơi {username} đã thắng!'
            game['game_over'] = True
            opponent = game['players'][1 - game['players'].index(username)]
            print(f"Người chơi {username}: Thắng")
            # Lưu lịch sử cho cả hai người chơi
            save_history(username, 'Thắng', opponent=opponent, mode='pvp')
            save_history(opponent, 'Thua', opponent=username, mode='pvp')
        # Kiểm tra hòa
        elif board_full(board):
            game['message'] = 'Hòa!'
            game['game_over'] = True
            opponent = game['players'][1 - game['players'].index(username)]
            print("Trò chơi hòa!")
            # Lưu lịch sử hòa cho cả hai người chơi
            save_history(username, 'Hòa', opponent=opponent, mode='pvp')
            save_history(opponent, 'Hòa', opponent=username, mode='pvp')
        else:
            # Chuyển lượt cho người chơi khác
            index = game['players'].index(username)
            game['turn'] = game['players'][1 - index]
            game['message'] = f"Lượt của {game['turn']}."
        game['board'] = board

    return jsonify({'status': 'ok'})


@app.route('/reset')
def reset():
    session.pop('board', None)
    session.pop('player_symbol', None)
    session.pop('ai_symbol', None)
    session.pop('turn', None)
    session.pop('message', None)
    session.pop('game_over', None)
    return redirect(url_for('index'))


@app.route('/ready', methods=['POST'])
def player_ready():
    global game, lock
    username = session['username']
    with lock:
        if username in game['players']:
            game['ready'][username] = True
            game['message'] = f"Người chơi {username} đã sẵn sàng."
    return redirect(url_for('index'))


@app.route('/continue', methods=['POST'])
def player_continue():
    global game, lock
    username = session['username']
    with lock:
        if username in game['players']:
            game['continue'][username] = True
            game['message'] = f"Người chơi {username} đã sẵn sàng tiếp tục."
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    global game, lock
    username = session.get('username')
    if username:
        with lock:
            if username in game['players']:
                game['players'].remove(username)
                game['ready'].pop(username, None)
                game['continue'].pop(username, None)
                # Kết thúc trò chơi nếu có người rời đi
                game['game_over'] = True
                game['message'] = f"Người chơi {username} đã rời trò chơi."
                game['turn'] = ''
            if username in game['spectators']:
                game['spectators'].remove(username)
    session.clear()
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        session['mode'] = request.form['mode']
        if session['mode'] == 'ai':
            session['difficulty'] = request.form['difficulty']
        session.permanent = True
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/change_difficulty', methods=['GET', 'POST'])
def change_difficulty():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        session['difficulty'] = request.form['difficulty']
        # Bạn có thể chọn đặt lại trò chơi sau khi thay đổi độ khó
        # return redirect(url_for('reset'))
        return redirect(url_for('index'))
    return render_template('change_difficulty.html')


@app.route('/change_mode', methods=['GET', 'POST'])
def change_mode():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        session['mode'] = request.form['mode']
        if session['mode'] == 'ai':
            session['difficulty'] = request.form['difficulty']
        # Đặt lại các biến trò chơi
        session.pop('board', None)
        session.pop('player_symbol', None)
        session.pop('ai_symbol', None)
        session.pop('turn', None)
        session.pop('message', None)
        session.pop('game_over', None)
        return redirect(url_for('index'))
    return render_template('change_mode.html')


@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    user_history = get_full_history(username)
    return render_template('history.html', username=username, history=user_history, difficulty_display=difficulty_display)


if __name__ == '__main__':
    initialize_history_file()
    app.run(debug=False)
