"""
라즈베리파이 Flask 서버 - 게임 키 입력 버전
게임 컨트롤러 입력을 키보드 입력으로 변환하여 게임에 전달

설치 방법:
    pip install flask flask-cors pynput

주의사항:
    - Linux에서 키보드 입력 시뮬레이션은 관리자 권한이 필요할 수 있습니다
    - 게임 창이 포커스되어 있어야 키 입력이 전달됩니다
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from pynput.keyboard import Key, Controller, Listener
from datetime import datetime
import threading
import time
import socket

app = Flask(__name__)
CORS(app)

# 키보드 컨트롤러
keyboard = Controller()

# 현재 눌려있는 키 추적 (중복 입력 방지)
pressed_keys = set()  # 버튼 이름 추적 ("A", "B", "X", "Y")
pressed_keyboard_keys = set()  # 실제 키보드 키 추적 (Key.up, Key.down, 'w', 'a' 등)

# 데이터 수신 통계
stats = {
    "joystick_count": 0,
    "button_count": 0,
    "last_joystick_time": None,
    "last_button_time": None,
    "server_start_time": datetime.now()
}

# 접속자 정보 추적
connected_users = {}  # {ip: {"first_seen": datetime, "last_seen": datetime, "request_count": int}}

# 서버 IP 주소 캐싱 (성능 최적화)
_cached_server_ips = None

# 키 매핑 설정
KEY_MAPPING = {
    # 조이스틱 방향 → 키보드 키
    "up": Key.up,           # 또는 'w'
    "down": Key.down,       # 또는 's'
    "left": Key.left,       # 또는 'a'
    "right": Key.right,     # 또는 'd'
    
    # 버튼 → 키보드 키
    "A": Key.space,         # 점프
    "B": Key.shift,         # 달리기/공격
    "X": 'e',               # 상호작용
    "Y": 'q',               # 특수 액션
}

# 조이스틱 임계값 (이 값 이상일 때만 키 입력)
JOYSTICK_THRESHOLD = 0.3  # 30% 이상

def get_local_ip():
    """로컬 네트워크 IP 주소 가져오기"""
    try:
        # 외부 서버에 연결하지 않고 로컬 IP만 가져오기
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS에 연결 시도 (실제 연결 안됨)
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # 대체 방법: 호스트 이름으로 IP 가져오기
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return "127.0.0.1"

def get_all_local_ips(use_cache=True):
    """모든 로컬 네트워크 IP 주소 가져오기 (캐싱 지원)"""
    global _cached_server_ips
    
    # 캐시된 값이 있으면 반환
    if use_cache and _cached_server_ips is not None:
        return _cached_server_ips
    
    ips = []
    try:
        hostname = socket.gethostname()
        # 모든 IP 주소 가져오기
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if ip and ip != '127.0.0.1' and not ip.startswith('::'):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    
    # 기본 방법으로도 시도
    main_ip = get_local_ip()
    if main_ip and main_ip not in ips:
        ips.insert(0, main_ip)
    
    result = ips if ips else ["127.0.0.1"]
    
    # 캐시에 저장
    if use_cache:
        _cached_server_ips = result
    
    return result

def update_user_activity():
    """접속자 활동 정보 업데이트"""
    ip = request.remote_addr
    now = datetime.now()
    
    if ip not in connected_users:
        connected_users[ip] = {
            "first_seen": now,
            "last_seen": now,
            "request_count": 0
        }
    
    connected_users[ip]["last_seen"] = now
    connected_users[ip]["request_count"] += 1

@app.route('/', methods=['GET'])
def dashboard():
    """메인 대시보드 HTML 페이지"""
    # 서버 IP 주소를 미리 가져와서 템플릿에 삽입 (성능 최적화)
    server_ips = get_all_local_ips()
    ip_links_html = ', '.join(['<a href="http://{}:5000" class="ip-link" target="_blank">http://{}:5000</a>'.format(ip, ip) for ip in server_ips])
    ip_list_text = ', '.join(server_ips)
    
    html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>게임 서버 대시보드</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s;
        }
        .card:hover {
            transform: translateY(-5px);
        }
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.5em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .stat-item:last-child {
            border-bottom: none;
        }
        .stat-label {
            color: #666;
            font-weight: 500;
        }
        .stat-value {
            color: #333;
            font-weight: bold;
            font-size: 1.1em;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }
        .status-active {
            background: #4caf50;
            color: white;
        }
        .status-inactive {
            background: #f44336;
            color: white;
        }
        .users-list {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .users-list h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.5em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .user-item {
            background: #f5f5f5;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .user-info {
            flex: 1;
        }
        .user-ip {
            font-weight: bold;
            color: #333;
            font-size: 1.1em;
            margin-bottom: 5px;
        }
        .user-details {
            color: #666;
            font-size: 0.9em;
        }
        .no-users {
            text-align: center;
            color: #999;
            padding: 40px;
            font-style: italic;
        }
        .last-update {
            text-align: center;
            color: white;
            margin-top: 20px;
            font-size: 0.9em;
            opacity: 0.8;
        }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            margin-top: 10px;
            transition: background 0.3s;
        }
        .refresh-btn:hover {
            background: #5568d3;
        }
        .ip-link {
            color: #667eea;
            text-decoration: none;
            font-weight: bold;
        }
        .ip-link:hover {
            text-decoration: underline;
        }
        .server-info {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            color: white;
        }
        .server-info h3 {
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        .server-info p {
            margin: 5px 0;
            font-size: 0.95em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 게임 서버 대시보드</h1>
        
        <div class="server-info">
            <h3>📡 서버 접속 정보</h3>
            <p><strong>로컬 접속:</strong> <a href="http://localhost:5000" class="ip-link" target="_blank">http://localhost:5000</a></p>
            <p id="network-access"><strong>내부망 접속:</strong> <span id="network-ips">""" + ip_links_html + """</span></p>
            <p style="font-size: 0.85em; opacity: 0.9; margin-top: 10px;">
                💡 같은 Wi-Fi/네트워크에 연결된 다른 기기에서 위의 IP 주소로 접속하세요
            </p>
        </div>
        
        <div class="dashboard">
            <div class="card">
                <h2>📊 서버 상태</h2>
                <div class="stat-item">
                    <span class="stat-label">서버 IP 주소:</span>
                    <span class="stat-value" id="server-ip" style="font-size: 0.9em; word-break: break-all;">""" + ip_list_text + """</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">서버 실행 시간:</span>
                    <span class="stat-value" id="server-uptime">-</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">현재 시간:</span>
                    <span class="stat-value" id="current-time">-</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">데이터 수신 상태:</span>
                    <span class="stat-value" id="data-status">-</span>
                </div>
            </div>
            
            <div class="card">
                <h2>🕹️ 조이스틱 통계</h2>
                <div class="stat-item">
                    <span class="stat-label">총 수신 횟수:</span>
                    <span class="stat-value" id="joystick-count">0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">마지막 수신:</span>
                    <span class="stat-value" id="joystick-last">-</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">상태:</span>
                    <span class="stat-value" id="joystick-status">-</span>
                </div>
            </div>
            
            <div class="card">
                <h2>🔘 버튼 통계</h2>
                <div class="stat-item">
                    <span class="stat-label">총 수신 횟수:</span>
                    <span class="stat-value" id="button-count">0</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">마지막 수신:</span>
                    <span class="stat-value" id="button-last">-</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">상태:</span>
                    <span class="stat-value" id="button-status">-</span>
                </div>
            </div>
        </div>
        
        <div class="users-list">
            <h2>👥 접속자 목록</h2>
            <div id="users-container">
                <div class="no-users">접속자 정보를 불러오는 중...</div>
            </div>
            <button class="refresh-btn" onclick="loadData()">새로고침</button>
        </div>
        
        <div class="last-update">
            마지막 업데이트: <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        function formatTime(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleString('ko-KR');
        }
        
        function formatElapsed(seconds) {
            if (seconds === null || seconds === undefined) return '-';
            if (seconds < 60) return seconds.toFixed(1) + '초 전';
            if (seconds < 3600) return Math.floor(seconds / 60) + '분 전';
            return Math.floor(seconds / 3600) + '시간 전';
        }
        
        function formatUptime(startTime) {
            const start = new Date(startTime);
            const now = new Date();
            const diff = Math.floor((now - start) / 1000);
            const hours = Math.floor(diff / 3600);
            const minutes = Math.floor((diff % 3600) / 60);
            const seconds = diff % 60;
            return `${hours}시간 ${minutes}분 ${seconds}초`;
        }
        
        function loadData() {
            // 병렬로 API 호출 (성능 최적화)
            Promise.all([
                fetch('/status').then(r => r.json()),
                fetch('/users').then(r => r.json())
            ]).then(([statusData, usersData]) => {
                // 서버 상태 업데이트
                document.getElementById('server-uptime').textContent = 
                    formatUptime(statusData.server_start_time);
                document.getElementById('current-time').textContent = 
                    formatTime(statusData.current_time);
                
                const receiving = statusData.summary.receiving_data;
                const statusBadge = receiving 
                    ? '<span class="status-badge status-active">수신 중</span>'
                    : '<span class="status-badge status-inactive">대기 중</span>';
                document.getElementById('data-status').innerHTML = statusBadge;
                
                // 조이스틱 통계
                const js = statusData.statistics.joystick;
                document.getElementById('joystick-count').textContent = js.total_received;
                document.getElementById('joystick-last').textContent = 
                    js.last_received ? formatTime(js.last_received) : '없음';
                const jsStatus = js.is_active 
                    ? '<span class="status-badge status-active">활성</span>'
                    : '<span class="status-badge status-inactive">비활성</span>';
                document.getElementById('joystick-status').innerHTML = jsStatus;
                
                // 버튼 통계
                const btn = statusData.statistics.button;
                document.getElementById('button-count').textContent = btn.total_received;
                document.getElementById('button-last').textContent = 
                    btn.last_received ? formatTime(btn.last_received) : '없음';
                const btnStatus = btn.is_active 
                    ? '<span class="status-badge status-active">활성</span>'
                    : '<span class="status-badge status-inactive">비활성</span>';
                document.getElementById('button-status').innerHTML = btnStatus;
                
                // 접속자 목록 업데이트
                const container = document.getElementById('users-container');
                if (usersData.users && usersData.users.length > 0) {
                    container.innerHTML = usersData.users.map(user => {
                        const firstSeen = formatTime(user.first_seen);
                        const lastSeen = formatTime(user.last_seen);
                        const elapsed = formatElapsed(user.elapsed_seconds);
                        
                        return `
                            <div class="user-item">
                                <div class="user-info">
                                    <div class="user-ip">${user.ip}</div>
                                    <div class="user-details">
                                        첫 접속: ${firstSeen}<br>
                                        마지막 활동: ${lastSeen} (${elapsed})<br>
                                        요청 횟수: ${user.request_count}회
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('');
                } else {
                    container.innerHTML = '<div class="no-users">접속자가 없습니다</div>';
                }
                
                document.getElementById('last-update').textContent = new Date().toLocaleString('ko-KR');
            }).catch(error => {
                console.error('Error:', error);
            });
        }
        
        // 초기 로드 및 자동 새로고침 (5초마다)
        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>
    """
    update_user_activity()
    return render_template_string(html_template)

@app.route('/users', methods=['GET'])
def get_users():
    """접속자 목록 반환"""
    now = datetime.now()
    users_list = []
    
    for ip, info in connected_users.items():
        elapsed = (now - info["last_seen"]).total_seconds()
        users_list.append({
            "ip": ip,
            "first_seen": info["first_seen"].isoformat(),
            "last_seen": info["last_seen"].isoformat(),
            "request_count": info["request_count"],
            "elapsed_seconds": round(elapsed, 2)
        })
    
    # 마지막 활동 시간 순으로 정렬
    users_list.sort(key=lambda x: x["last_seen"], reverse=True)
    
    return jsonify({
        "status": "ok",
        "total_users": len(users_list),
        "users": users_list
    })

@app.route('/ping', methods=['GET'])
def ping():
    """서버 연결 테스트"""
    update_user_activity()
    return jsonify({
        "status": "ok",
        "message": "Server is running",
        "server_time": datetime.now().isoformat()
    })

@app.route('/status', methods=['GET'])
def get_status():
    """서버 상태 및 데이터 수신 통계 확인"""
    update_user_activity()
    now = datetime.now()
    
    # 마지막 수신으로부터 경과 시간 계산
    joystick_elapsed = None
    button_elapsed = None
    
    if stats["last_joystick_time"]:
        joystick_elapsed = (now - stats["last_joystick_time"]).total_seconds()
    
    if stats["last_button_time"]:
        button_elapsed = (now - stats["last_button_time"]).total_seconds()
    
    # 데이터 수신 여부 판단 (5초 이내면 활성)
    joystick_active = joystick_elapsed is not None and joystick_elapsed < 5.0
    button_active = button_elapsed is not None and button_elapsed < 5.0
    
    # 서버 IP 주소 가져오기 (캐시 사용)
    server_ips = get_all_local_ips(use_cache=True)
    
    return jsonify({
        "status": "ok",
        "server_running": True,
        "server_start_time": stats["server_start_time"].isoformat(),
        "current_time": now.isoformat(),
        "server_ips": server_ips,
        "statistics": {
            "joystick": {
                "total_received": stats["joystick_count"],
                "last_received": stats["last_joystick_time"].isoformat() if stats["last_joystick_time"] else None,
                "elapsed_seconds": round(joystick_elapsed, 2) if joystick_elapsed is not None else None,
                "is_active": joystick_active
            },
            "button": {
                "total_received": stats["button_count"],
                "last_received": stats["last_button_time"].isoformat() if stats["last_button_time"] else None,
                "elapsed_seconds": round(button_elapsed, 2) if button_elapsed is not None else None,
                "is_active": button_active
            }
        },
        "summary": {
            "receiving_data": joystick_active or button_active,
            "message": "데이터 수신 중" if (joystick_active or button_active) else "데이터 수신 대기 중"
        }
    })

@app.route('/joystick', methods=['POST'])
def receive_joystick():
    """
    조이스틱 데이터를 키보드 입력으로 변환
    
    받는 데이터:
    {
        "x": 0.53,    # -1.0 ~ 1.0 (좌우)
        "y": 0.53,   # -1.0 ~ 1.0 (앞뒤)
        "strength": 75
    }
    
    변환:
    - y > 0.3  → 위쪽 키 (W 또는 ↑)
    - y < -0.3 → 아래쪽 키 (S 또는 ↓)
    - x > 0.3  → 오른쪽 키 (D 또는 →)
    - x < -0.3 → 왼쪽 키 (A 또는 ←)
    """
    try:
        update_user_activity()
        data = request.get_json()
        x = data.get('x', 0.0)  # -1.0 ~ 1.0
        y = data.get('y', 0.0)  # -1.0 ~ 1.0
        strength = data.get('strength', 0)
        
        # 통계 업데이트
        stats["joystick_count"] += 1
        stats["last_joystick_time"] = datetime.now()
        
        # 이전에 눌려있던 키 모두 떼기
        release_all_keys()
        
        # 임계값 이상일 때만 키 입력
        if abs(x) < JOYSTICK_THRESHOLD and abs(y) < JOYSTICK_THRESHOLD:
            # 조이스틱이 중앙에 있으면 모든 키 떼기
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ✓ 데이터 수신됨 (중앙 위치) - 총 {stats['joystick_count']}회")
            return jsonify({"status": "ok", "keys": "none"})
        
        keys_to_press = []
        
        # 위/아래 방향
        if y > JOYSTICK_THRESHOLD:
            # 위쪽 (앞으로)
            press_key(KEY_MAPPING["up"])
            keys_to_press.append("up")
        elif y < -JOYSTICK_THRESHOLD:
            # 아래쪽 (뒤로)
            press_key(KEY_MAPPING["down"])
            keys_to_press.append("down")
        
        # 좌/우 방향
        if x > JOYSTICK_THRESHOLD:
            # 오른쪽
            press_key(KEY_MAPPING["right"])
            keys_to_press.append("right")
        elif x < -JOYSTICK_THRESHOLD:
            # 왼쪽
            press_key(KEY_MAPPING["left"])
            keys_to_press.append("left")
        
        # 대각선 이동 (동시에 여러 키 누르기)
        # 이미 위에서 처리됨
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ✓ 데이터 수신됨 - "
              f"X: {x:.2f}, Y: {y:.2f} → Keys: {keys_to_press} (총 {stats['joystick_count']}회)")
        
        return jsonify({
            "status": "ok",
            "received": True,
            "keys_pressed": keys_to_press
        })
        
    except Exception as e:
        print(f"Error receiving joystick data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/button', methods=['POST'])
def receive_button():
    """
    버튼 데이터를 키보드 입력으로 변환
    
    받는 데이터:
    {
        "button": "A",      # "A", "B", "X", "Y"
        "pressed": true     # true = 눌림, false = 떼어짐
    }
    """
    try:
        update_user_activity()
        data = request.get_json()
        button = data.get('button', '')
        pressed = data.get('pressed', False)
        
        # 통계 업데이트
        stats["button_count"] += 1
        stats["last_button_time"] = datetime.now()
        
        if button not in KEY_MAPPING:
            return jsonify({"status": "error", "message": f"Unknown button: {button}"}), 400
        
        key = KEY_MAPPING[button]
        action = "pressed" if pressed else "released"
        
        if pressed:
            press_key(key)
            pressed_keys.add(button)
        else:
            release_key(key)
            pressed_keys.discard(button)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ✓ 데이터 수신됨 - "
              f"{button} {action} → Key: {key} (총 {stats['button_count']}회)")
        
        return jsonify({
            "status": "ok",
            "received": True,
            "button": button,
            "action": action,
            "key": str(key)
        })
        
    except Exception as e:
        print(f"Error receiving button data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/stop', methods=['POST'])
def stop_all():
    """모든 키 입력 중지"""
    release_all_keys()
    return jsonify({"status": "ok", "message": "All keys released"})

@app.route('/config', methods=['POST'])
def update_key_mapping():
    """키 매핑 설정 변경"""
    try:
        data = request.get_json()
        
        # 예시: {"A": "space", "B": "shift"}
        # 실제 구현 시 키 문자열을 Key 객체로 변환 필요
        return jsonify({
            "status": "ok",
            "message": "Key mapping updated"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def press_key(key):
    """키보드 키 누르기"""
    try:
        # 키가 이미 눌려있지 않으면 누르기
        if key not in pressed_keyboard_keys:
            keyboard.press(key)
            pressed_keyboard_keys.add(key)
    except Exception as e:
        print(f"Error pressing key {key}: {e}")

def release_key(key):
    """키보드 키 떼기"""
    try:
        # 키가 눌려있으면 떼기
        if key in pressed_keyboard_keys:
            keyboard.release(key)
            pressed_keyboard_keys.discard(key)
    except Exception as e:
        print(f"Error releasing key {key}: {e}")

def release_all_keys():
    """모든 키보드 키 떼기"""
    try:
        # 현재 눌려있는 모든 키보드 키를 떼기
        keys_to_release = list(pressed_keyboard_keys)
        for key in keys_to_release:
            try:
                keyboard.release(key)
            except Exception as e:
                print(f"Error releasing key {key}: {e}")
        pressed_keyboard_keys.clear()
        
        # 버튼 추적도 초기화
        pressed_keys.clear()
    except Exception as e:
        print(f"Error releasing all keys: {e}")

if __name__ == '__main__':
    # 로컬 IP 주소 가져오기
    local_ips = get_all_local_ips()
    main_ip = local_ips[0] if local_ips else "127.0.0.1"
    
    print("=" * 60)
    print("게임 컨트롤러 Flask 서버 - 키 입력 버전")
    print("=" * 60)
    print("서버 시작됨!")
    print("=" * 60)
    print("📡 접속 주소:")
    print("  로컬 접속:")
    print("    http://localhost:5000")
    print("    http://127.0.0.1:5000")
    print("")
    print("  내부망 접속 (같은 Wi-Fi/네트워크):")
    for ip in local_ips:
        print(f"    http://{ip}:5000")
    print("=" * 60)
    print("엔드포인트:")
    print("  GET  /           - 대시보드 (접속자 정보) ⭐")
    print("  GET  /ping       - 서버 연결 테스트")
    print("  GET  /status     - 데이터 수신 상태 확인")
    print("  GET  /users      - 접속자 목록 (JSON)")
    print("  POST /joystick   - 조이스틱 데이터 수신")
    print("  POST /button     - 버튼 데이터 수신")
    print("  POST /stop       - 모든 키 입력 중지")
    print("=" * 60)
    print("키 매핑:")
    print("  조이스틱:")
    print("    위    → ↑ (또는 W)")
    print("    아래  → ↓ (또는 S)")
    print("    왼쪽  → ← (또는 A)")
    print("    오른쪽 → → (또는 D)")
    print("  버튼:")
    print("    A → Space (점프)")
    print("    B → Shift (달리기/공격)")
    print("    X → E (상호작용)")
    print("    Y → Q (특수 액션)")
    print("=" * 60)
    print("💡 내부망 접속 방법:")
    print("  1. 같은 Wi-Fi/네트워크에 연결되어 있어야 합니다")
    print("  2. 다른 기기(스마트폰, 태블릿 등)에서 위의 IP 주소로 접속")
    print("  3. 방화벽이 포트 5000을 차단하지 않는지 확인")
    print("")
    print("🔧 Windows 방화벽 설정 (필요한 경우):")
    print("  방법 1: PowerShell 관리자 권한으로 실행")
    print("    New-NetFirewallRule -DisplayName 'Flask Server' -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow")
    print("")
    print("  방법 2: Windows 방화벽 설정")
    print("    1. Windows 보안 > 방화벽 및 네트워크 보호")
    print("    2. 고급 설정 > 인바운드 규칙 > 새 규칙")
    print("    3. 포트 선택 > TCP > 특정 로컬 포트: 5000")
    print("    4. 연결 허용 > 모든 프로필 > 이름: Flask Server")
    print("=" * 60)
    print("⚠️  주의: 게임 창이 포커스되어 있어야 키 입력이 전달됩니다")
    print("=" * 60)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n서버 종료 중...")
        release_all_keys()
        print("모든 키 입력 해제 완료")



