"""
라즈베리파이 Flask 서버 - 게임 키 입력 버전
게임 컨트롤러 입력을 키보드 입력으로 변환하여 게임에 전달

설치 방법:
    pip install flask flask-cors pynput

주의사항:
    - Linux에서 키보드 입력 시뮬레이션은 관리자 권한이 필요할 수 있습니다
    - 게임 창이 포커스되어 있어야 키 입력이 전달됩니다
"""

import argparse
import os
import socket
import threading
import time
from datetime import datetime

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pynput.keyboard import Key, Controller

Port = 8443
app = Flask(__name__)
CORS(app)
app.config["SERVER_PORT"] = Port

# 키보드 컨트롤러
keyboard = Controller()

# 키 입력 동기화를 위한 Lock (끊김 방지)
keyboard_lock = threading.Lock()

# 현재 눌려있는 키 추적 (중복 입력 방지)
pressed_keys = set()  # 버튼 이름 추적 ("A", "B", "X", "Y")
pressed_keyboard_keys = set()  # 실제 키보드 키 추적 (Key.up, Key.down, 'w', 'a' 등)
pressed_button_keys = set()  # 버튼으로 눌린 키 추적 (조이스틱과 분리)
pressed_joystick_keys = set()  # 조이스틱으로 눌린 키 추적 (버튼과 분리)

# 데이터 수신 통계
stats = {
    "joystick_count": 0,
    "button_count": 0,
    "last_joystick_time": None,
    "last_button_time": None,
    "server_start_time": datetime.now()
}

# 최근 수신된 데이터 (HTML 표시용)
recent_data = {
    "last_joystick": None,  # {"x": 0.5, "y": 0.5, "keys": ["up"], "time": datetime}
    "last_button": None      # {"button": "A", "pressed": True, "key": "space", "time": datetime}
}

# 마지막 조이스틱 상태 저장 (안드로이드에서 데이터가 같으면 전송하지 않는 문제 해결)
last_joystick_state = {
    "x": 0.0,
    "y": 0.0,
    "keys": set(),  # 마지막에 눌려있던 키들
    "is_active": False,  # 조이스틱이 활성 상태인지 (중앙이 아닌지)
    "active_keys": set()  # 현재 활성화된 키들 (히스테리시스 적용)
}

# 마지막 버튼 상태 저장 (안드로이드에서 데이터가 같으면 전송하지 않는 문제 해결)
last_button_states = {}  # {button_name: {"pressed": bool, "key": key, "time": datetime}}

# 기본 포트 (CLI/환경 변수로 덮어쓰기 가능)
DEFAULT_SERVER_PORT = Port

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
    "A": Key.space,         # 공격
    "B": Key.enter,         # 달리기/공격
    "X": '1',               # 게임 시작
    "Y": '',                # 미할당
}

# 조이스틱 방향 키 세트 (성능 최적화: 반복 생성 방지)
JOYSTICK_KEY_SET = {KEY_MAPPING["up"], KEY_MAPPING["down"], KEY_MAPPING["left"], KEY_MAPPING["right"]}

# 조이스틱 임계값 (이 값 이상일 때만 키 입력)
JOYSTICK_THRESHOLD = 0.3  # 30% 이상

# 조이스틱 히스테리시스 (떨림 방지)
# 키를 누르기 시작하는 임계값과 떼는 임계값을 다르게 설정하여 떨림 방지
JOYSTICK_THRESHOLD_ON = 0.3   # 키를 누르기 시작하는 임계값
JOYSTICK_THRESHOLD_OFF = 0.25 # 키를 떼는 임계값 (더 낮게 설정하여 떨림 방지)

# 입력 정지 타임아웃 (초)
# 이 시간 동안 조이스틱/버튼 데이터가 안 들어오면 자동으로 모든 키를 뗀다
# 안드로이드에서 데이터가 같으면 전송하지 않는 문제를 고려하여 시간 증가
INACTIVITY_RELEASE_TIMEOUT = 0.5  # 0.5초로 증가 (안드로이드 데이터 전송 특성 고려)

# 로깅 설정 (성능 최적화)
ENABLE_VERBOSE_LOGGING = False  # True로 설정하면 상세 로그 출력

# 접속자 정보 정리 설정
USER_CLEANUP_TIMEOUT = 3600  # 1시간 (초 단위) - 이 시간 이상 비활성 접속자 제거


def resolve_server_port(cli_port=None):
    """
    CLI 인자나 환경 변수를 기반으로 사용할 포트를 결정한다.
    우선순위: CLI > GAME_SERVER_PORT > PORT > 기본값.
    """
    if cli_port is not None:
        return cli_port

    for env_var in ("GAME_SERVER_PORT", "PORT"):
        env_value = os.environ.get(env_var)
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                print(f"⚠️  환경 변수 {env_var}='{env_value}' 값이 올바른 정수가 아니어서 무시합니다.")

    return DEFAULT_SERVER_PORT

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

def cleanup_inactive_users():
    """오래된 접속자 정보 정리 (메모리 최적화)"""
    now = datetime.now()
    inactive_ips = []
    
    for ip, info in connected_users.items():
        elapsed = (now - info["last_seen"]).total_seconds()
        if elapsed > USER_CLEANUP_TIMEOUT:
            inactive_ips.append(ip)
    
    # 비활성 접속자 제거
    for ip in inactive_ips:
        del connected_users[ip]
    
    if inactive_ips:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Cleanup] {len(inactive_ips)}명의 비활성 접속자 제거됨")

@app.route('/', methods=['GET'])
def dashboard():
    """메인 대시보드 HTML 페이지"""
    # 서버 IP 주소를 미리 가져와서 템플릿에 삽입 (성능 최적화)
    server_ips = get_all_local_ips()
    server_port = app.config.get("SERVER_PORT", DEFAULT_SERVER_PORT)
    ip_links_html = ', '.join([
        f'<a href="http://{ip}:{server_port}" class="ip-link" target="_blank">http://{ip}:{server_port}</a>'
        for ip in server_ips
    ])
    ip_list_text = ', '.join(server_ips)
    local_link_html = (
        f'<a href="http://localhost:{server_port}" class="ip-link" target="_blank">'
        f'http://localhost:{server_port}</a>'
    )
    
    update_user_activity()
    return render_template('dashboard.html', 
                         local_link_html=local_link_html,
                         ip_links_html=ip_links_html,
                         ip_list_text=ip_list_text)

@app.route('/users', methods=['GET'])
def get_users():
    """접속자 목록 반환"""
    # 비활성 접속자 정리 (최적화)
    cleanup_inactive_users()
    
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
        "recent_data": {
            "joystick": recent_data["last_joystick"],
            "button": recent_data["last_button"]
        },
        "summary": {
            "receiving_data": joystick_active or button_active,
            "message": "데이터 수신 중" if (joystick_active or button_active) else "데이터 수신 대기 중"
        }
    })

def calculate_joystick_keys(x, y):
    """
    조이스틱 입력값(x, y)을 키 매핑으로 변환 (히스테리시스 적용)
    
    Args:
        x: 조이스틱 X 좌표 (-1.0 ~ 1.0)
        y: 조이스틱 Y 좌표 (-1.0 ~ 1.0)
    
    Returns:
        tuple: (target_keys: set, keys_to_press: list, is_active: bool)
    """
    target_keys = set()  # 눌려야 할 키 집합
    keys_to_press = []  # 눌려야 할 키 이름 리스트
    is_active = False  # 조이스틱이 활성 상태인지
    
    # 이전에 활성화된 키들 가져오기
    previous_active_keys = last_joystick_state.get("active_keys", set())
    
    # 히스테리시스 적용: 키를 누르기 시작할 때는 높은 임계값, 떼기 시작할 때는 낮은 임계값 사용
    # 위/아래 방향
    up_was_active = KEY_MAPPING["up"] in previous_active_keys
    down_was_active = KEY_MAPPING["down"] in previous_active_keys
    
    if up_was_active:
        # 위 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if y > JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["up"])
            keys_to_press.append("up")
            is_active = True
    else:
        # 위 키가 눌려있지 않았으면 높은 임계값으로 시작
        if y > JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["up"])
            keys_to_press.append("up")
            is_active = True
    
    if down_was_active:
        # 아래 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if y < -JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["down"])
            keys_to_press.append("down")
            is_active = True
    else:
        # 아래 키가 눌려있지 않았으면 높은 임계값으로 시작
        if y < -JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["down"])
            keys_to_press.append("down")
            is_active = True
    
    # 좌/우 방향
    right_was_active = KEY_MAPPING["right"] in previous_active_keys
    left_was_active = KEY_MAPPING["left"] in previous_active_keys
    
    if right_was_active:
        # 오른쪽 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if x > JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["right"])
            keys_to_press.append("right")
            is_active = True
    else:
        # 오른쪽 키가 눌려있지 않았으면 높은 임계값으로 시작
        if x > JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["right"])
            keys_to_press.append("right")
            is_active = True
    
    if left_was_active:
        # 왼쪽 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if x < -JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["left"])
            keys_to_press.append("left")
            is_active = True
    else:
        # 왼쪽 키가 눌려있지 않았으면 높은 임계값으로 시작
        if x < -JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["left"])
            keys_to_press.append("left")
            is_active = True
    
    return target_keys, keys_to_press, is_active


def process_joystick_keys(target_keys):
    """
    조이스틱 키 입력 처리 (press/release)
    버튼과 조이스틱 키를 분리하여 추적하여 간섭 방지
    
    Args:
        target_keys: 눌려야 할 키 집합
    """
    global pressed_joystick_keys, pressed_keyboard_keys, pressed_button_keys
    
    with keyboard_lock:
        # 조이스틱으로 눌려야 하는 키 (조이스틱 방향 키만)
        target_joystick_keys = target_keys & JOYSTICK_KEY_SET
        
        # 조이스틱으로 눌려야 하는데 안 눌려있는 키 → 누르기
        # 버튼이 이미 눌려있는 키는 물리적으로 누르지 않지만, 조이스틱 추적에는 포함
        keys_to_add_physically = target_joystick_keys - pressed_keyboard_keys - pressed_button_keys
        for key in keys_to_add_physically:
            try:
                keyboard.press(key)
                pressed_keyboard_keys.add(key)
                pressed_joystick_keys.add(key)
            except Exception as e:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"Error pressing key {key}: {e}")
        
        # 이미 눌려있지만 조이스틱 추적에 없는 키 추가 (버튼을 떼고 난 후 조이스틱이 계속 같은 방향일 때)
        # 버튼이 눌려있지 않고, 키가 이미 눌려있고, 조이스틱이 이 키를 눌러야 하면 추적에 추가
        keys_already_pressed = (target_joystick_keys & pressed_keyboard_keys) - pressed_button_keys - pressed_joystick_keys
        for key in keys_already_pressed:
            # 조이스틱 추적에 추가 (물리적으로는 이미 눌려있음)
            pressed_joystick_keys.add(key)
            if ENABLE_VERBOSE_LOGGING:
                print(f"[Key] Joystick takes over already pressed key: {key}")
        
        # 이미 눌려있고 조이스틱 추적에도 있는 키는 유지 (키가 지속적으로 눌려있도록 보장)
        # 키가 이미 눌려있고 조이스틱이 이 키를 눌러야 하면, 주기적으로 다시 눌러서 지속성 보장
        keys_to_maintain = target_joystick_keys & pressed_joystick_keys & pressed_keyboard_keys
        for key in keys_to_maintain:
            # 키가 이미 눌려있지만, 지속성을 위해 주기적으로 다시 누르기
            # 일부 시스템에서는 키가 자동으로 해제될 수 있으므로 주기적으로 다시 눌러야 함
            try:
                # 키를 release 후 press하여 지속성 보장 (더 확실한 방법)
                keyboard.release(key)
                time.sleep(0.001)  # 매우 짧은 딜레이
                keyboard.press(key)
            except Exception as e:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"Error maintaining key {key}: {e}")
        
        # 조이스틱으로 눌려있는데 뗴야 하는 키 → 떼기
        # 버튼이 눌려있는 키는 건드리지 않음
        keys_to_remove = (pressed_joystick_keys & JOYSTICK_KEY_SET) - target_joystick_keys
        for key in keys_to_remove:
            # 버튼이 이 키를 사용 중이면 건드리지 않음
            if key not in pressed_button_keys:
                try:
                    keyboard.release(key)
                    pressed_keyboard_keys.discard(key)
                    pressed_joystick_keys.discard(key)
                except Exception as e:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"Error releasing key {key}: {e}")
            else:
                # 버튼이 사용 중이면 조이스틱 추적에서만 제거 (물리적 키는 유지)
                pressed_joystick_keys.discard(key)
        
        # 조이스틱 키 추적 업데이트 (버튼과 분리)
        # 조이스틱 키만 유지하고 새로운 키 추가
        pressed_joystick_keys &= JOYSTICK_KEY_SET  # 조이스틱 키만 유지
        pressed_joystick_keys |= target_joystick_keys  # 새로운 조이스틱 키 추가 (버튼이 눌러도 추적)


@app.route('/joystick', methods=['POST', 'OPTIONS'])
def receive_joystick():
    """
    조이스틱 데이터를 키보드 입력으로 변환 (최적화: 차등 처리)
    
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
    # OPTIONS 요청 처리 (CORS preflight)
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    # 전역 변수 사용 선언 (함수 시작 부분에 위치)
    global pressed_joystick_keys, pressed_keyboard_keys, pressed_button_keys
    
    try:
        update_user_activity()
        
        # Content-Type 확인
        if not request.is_json:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: Content-Type이 application/json이 아닙니다. Content-Type: {request.content_type}")
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        # 데이터 유효성 검사
        if data is None:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: JSON 데이터가 없습니다")
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        x = data.get('x', 0.0)  # -1.0 ~ 1.0
        y = data.get('y', 0.0)  # -1.0 ~ 1.0
        strength = data.get('strength', 0)
        reset_requested = data.get('reset', False)  # 게임 재시작 플래그
        
        # 데이터 타입 검증
        try:
            x = float(x)
            y = float(y)
        except (ValueError, TypeError):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: 잘못된 데이터 타입 - x: {x}, y: {y}")
            return jsonify({"status": "error", "message": f"Invalid data type: x and y must be numbers"}), 400
        
        # 게임 재시작 요청이 있으면 상태 초기화
        if reset_requested:
            reset_all_states_internal()
            if ENABLE_VERBOSE_LOGGING:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] 게임 재시작 - 상태 초기화됨")
        
        # 통계 업데이트
        stats["joystick_count"] += 1
        now = datetime.now()
        stats["last_joystick_time"] = now
        
        # 조이스틱 입력값을 키 매핑으로 변환 (히스테리시스 적용)
        target_keys, keys_to_press, is_active = calculate_joystick_keys(x, y)
        
        # 마지막 조이스틱 상태 저장 (안드로이드 데이터 전송 문제 해결)
        last_joystick_state["x"] = x
        last_joystick_state["y"] = y
        last_joystick_state["keys"] = target_keys.copy()
        last_joystick_state["is_active"] = is_active
        last_joystick_state["active_keys"] = target_keys.copy()  # 히스테리시스를 위한 활성 키 저장
        
        # 조이스틱 키 입력 처리 (press/release)
        process_joystick_keys(target_keys)
        
        # 최근 데이터 저장
        recent_data["last_joystick"] = {
            "x": round(x, 2),
            "y": round(y, 2),
            "strength": strength,
            "keys": keys_to_press,
            "time": now.isoformat()
        }
        
        # 로깅 최소화 (성능 최적화)
        if ENABLE_VERBOSE_LOGGING:
            if keys_to_press:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ✓ 데이터 수신됨 - "
                      f"X: {x:.2f}, Y: {y:.2f} → Keys: {keys_to_press} (총 {stats['joystick_count']}회)")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ✓ 데이터 수신됨 (중앙 위치) - 총 {stats['joystick_count']}회")
        
        return jsonify({
            "status": "ok",
            "received": True,
            "keys_pressed": keys_to_press
        })
        
    except Exception as e:
        error_msg = f"Error receiving joystick data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: {error_msg}")
        import traceback
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/button', methods=['POST', 'OPTIONS'])
def receive_button():
    """
    버튼 데이터를 키보드 입력으로 변환
    
    받는 데이터:
    {
        "button": "A",      # "A", "B", "X", "Y"
        "pressed": true     # true = 눌림, false = 떼어짐
    }
    """
    # OPTIONS 요청 처리 (CORS preflight)
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    # 전역 변수 사용 선언 (함수 시작 부분에 위치)
    global pressed_joystick_keys, pressed_button_keys, pressed_keyboard_keys, pressed_keys
    
    try:
        update_user_activity()
        
        # Content-Type 확인
        if not request.is_json:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: Content-Type이 application/json이 아닙니다. Content-Type: {request.content_type}")
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        # 데이터 유효성 검사
        if data is None:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: JSON 데이터가 없습니다")
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        button = data.get('button', '')
        pressed = data.get('pressed', False)
        
        # 버튼 이름 검증
        if not button:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: 버튼 이름이 없습니다")
            return jsonify({"status": "error", "message": "Button name is required"}), 400
        
        # 통계 업데이트
        stats["button_count"] += 1
        now = datetime.now()
        stats["last_button_time"] = now
        
        if button not in KEY_MAPPING:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: 알 수 없는 버튼 - {button}")
            return jsonify({"status": "error", "message": f"Unknown button: {button}. Available buttons: {list(KEY_MAPPING.keys())}"}), 400
        
        key = KEY_MAPPING[button]
        action = "pressed" if pressed else "released"
        
        # 빈 키 매핑 체크 (Y 버튼 등)
        if not key:
            return jsonify({"status": "ok", "message": f"Button {button} has no key mapping"})
        
        # 이전 버튼 상태 확인 (중복 처리 방지)
        previous_state = last_button_states.get(button, {}).get("pressed", False)
        
        # 상태가 변경되지 않았으면 처리하지 않음 (계속 눌리는 문제 해결)
        if previous_state == pressed:
            # 이미 같은 상태이므로 추가 처리 없이 반환
            return jsonify({
                "status": "ok",
                "received": True,
                "button": button,
                "action": action,
                "key": str(key),
                "message": "State unchanged, skipped"
            })
        
        # 마지막 버튼 상태 저장 (안드로이드 데이터 전송 문제 해결)
        last_button_states[button] = {
            "pressed": pressed,
            "key": key,
            "time": now
        }
        
        # 상태가 변경되었을 때만 키 입력 처리 (조이스틱과 분리)
        if pressed:
            # 버튼이 눌렸을 때만 press (이미 눌려있지 않은 경우만)
            if button not in pressed_keys:
                with keyboard_lock:
                    is_joystick_key = key in JOYSTICK_KEY_SET
                    
                    # 조이스틱 방향 키인 경우: 조이스틱이 이 키를 계속 누르고 있어야 하는지 확인
                    if is_joystick_key and key in last_joystick_state.get("active_keys", set()):
                        # 조이스틱이 계속 이 키를 누르고 있어야 하므로 조이스틱 추적은 유지
                        # 버튼도 이 키를 사용하므로 버튼 추적에 추가
                        pressed_button_keys.add(key)
                        if ENABLE_VERBOSE_LOGGING:
                            print(f"[Key] Button pressed, joystick key already active: {key}")
                    elif is_joystick_key and key in pressed_joystick_keys:
                        # 조이스틱이 이 키를 사용하지 않으면 조이스틱 추적에서 제거
                        pressed_joystick_keys.discard(key)
                    elif not is_joystick_key and key in pressed_joystick_keys:
                        # 조이스틱 방향 키가 아닌 경우: 조이스틱이 이 키를 사용 중이면 제거
                        pressed_joystick_keys.discard(key)
                    
                    # 키가 이미 눌려있지 않으면 누르기
                    if key not in pressed_keyboard_keys:
                        try:
                            keyboard.press(key)
                            pressed_keyboard_keys.add(key)
                            pressed_button_keys.add(key)
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"[Key] Pressed (Button): {key}")
                        except Exception as e:
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"Error pressing key {key}: {e}")
                    else:
                        # 이미 눌려있으면 버튼 키로만 추적
                        pressed_button_keys.add(key)
                
                pressed_keys.add(button)
        else:
            # 버튼이 떼어졌을 때만 release (눌려있는 경우만)
            if button in pressed_keys:
                with keyboard_lock:
                    # 버튼 키 추적에서 제거
                    pressed_button_keys.discard(key)
                    
                    # 조이스틱이 이 키를 사용 중인지 확인
                    is_joystick_key = key in JOYSTICK_KEY_SET
                    
                    if is_joystick_key:
                        # 조이스틱 방향 키인 경우: 조이스틱이 현재 이 키를 계속 눌러야 하는지 확인
                        should_keep_key = key in last_joystick_state.get("active_keys", set())
                        
                        if should_keep_key:
                            # 조이스틱이 이 키를 계속 눌러야 함
                            pressed_joystick_keys.add(key)
                            # 키가 이미 눌려있으므로 해제하지 않음 (조이스틱이 계속 사용)
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"[Key] Button released, joystick continues: {key}")
                        else:
                            # 조이스틱이 이 키를 사용하지 않으므로 해제
                            if key in pressed_keyboard_keys:
                                try:
                                    keyboard.release(key)
                                    pressed_keyboard_keys.discard(key)
                                    pressed_joystick_keys.discard(key)
                                    if ENABLE_VERBOSE_LOGGING:
                                        print(f"[Key] Released (Button): {key}")
                                except Exception as e:
                                    if ENABLE_VERBOSE_LOGGING:
                                        print(f"Error releasing key {key}: {e}")
                    else:
                        # 조이스틱 방향 키가 아닌 경우 (일반 버튼 키) - 바로 해제
                        if key in pressed_keyboard_keys:
                            try:
                                keyboard.release(key)
                                pressed_keyboard_keys.discard(key)
                                if ENABLE_VERBOSE_LOGGING:
                                    print(f"[Key] Released (Button): {key}")
                            except Exception as e:
                                if ENABLE_VERBOSE_LOGGING:
                                    print(f"Error releasing key {key}: {e}")
                
                pressed_keys.discard(button)
            # 버튼이 떼어졌으면 마지막 상태에서 제거
            if button in last_button_states:
                del last_button_states[button]
        
        # 최근 데이터 저장
        recent_data["last_button"] = {
            "button": button,
            "pressed": pressed,
            "action": action,
            "key": str(key),
            "time": now.isoformat()
        }
        
        # 로깅 최소화 (성능 최적화)
        if ENABLE_VERBOSE_LOGGING:
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
        error_msg = f"Error receiving button data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: {error_msg}")
        import traceback
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/stop', methods=['POST'])
def stop_all():
    """모든 키 입력 중지"""
    release_all_keys()
    return jsonify({"status": "ok", "message": "All keys released"})

@app.route('/reset', methods=['POST'])
def reset_all_states():
    """
    모든 상태 초기화 (게임 재시작 시 사용)
    키 상태, 조이스틱 상태, 버튼 상태 모두 초기화
    """
    try:
        # 모든 키 해제
        release_all_keys()
        
        # 조이스틱 상태 초기화
        last_joystick_state["x"] = 0.0
        last_joystick_state["y"] = 0.0
        last_joystick_state["keys"] = set()
        last_joystick_state["is_active"] = False
        last_joystick_state["active_keys"] = set()
        
        # 버튼 상태 초기화
        last_button_states.clear()
        
        # 통계는 유지 (선택사항)
        # stats["joystick_count"] = 0
        # stats["button_count"] = 0
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Reset] 모든 상태 초기화됨")
        
        return jsonify({
            "status": "ok",
            "message": "All states reset successfully"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

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
    """키보드 키 누르기 (동기화 처리로 끊김 방지, 중복 방지)"""
    global pressed_keyboard_keys  # 전역 변수 사용 선언
    try:
        with keyboard_lock:
            # 키가 이미 눌려있지 않으면 누르기 (중복 방지)
            if key not in pressed_keyboard_keys:
                keyboard.press(key)
                pressed_keyboard_keys.add(key)
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[Key] Pressed: {key}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"Error pressing key {key}: {e}")

def release_key(key):
    """키보드 키 떼기 (동기화 처리로 끊김 방지, 확실한 해제 보장)"""
    global pressed_keyboard_keys  # 전역 변수 사용 선언
    try:
        with keyboard_lock:
            # 키가 눌려있으면 떼기 (확실한 해제 보장)
            if key in pressed_keyboard_keys:
                keyboard.release(key)
                pressed_keyboard_keys.discard(key)
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[Key] Released: {key}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"Error releasing key {key}: {e}")

def release_all_keys():
    """모든 키보드 키 떼기 (동기화 처리로 끊김 방지)"""
    global pressed_joystick_keys, pressed_button_keys, pressed_keyboard_keys, pressed_keys  # 전역 변수 사용 선언
    try:
        with keyboard_lock:
            # 현재 눌려있는 모든 키보드 키를 떼기
            keys_to_release = list(pressed_keyboard_keys)
            for key in keys_to_release:
                try:
                    keyboard.release(key)
                except Exception as e:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"Error releasing key {key}: {e}")
            pressed_keyboard_keys.clear()
            
            # 버튼 및 조이스틱 추적도 초기화
            pressed_keys.clear()
            pressed_button_keys.clear()
            pressed_joystick_keys.clear()
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"Error releasing all keys: {e}")

def reset_all_states_internal():
    """
    내부 상태 초기화 함수 (게임 재시작 시 사용)
    """
    global pressed_joystick_keys, pressed_button_keys  # 전역 변수 사용 선언
    # 모든 키 해제
    release_all_keys()
    
    # 조이스틱 상태 초기화
    last_joystick_state["x"] = 0.0
    last_joystick_state["y"] = 0.0
    last_joystick_state["keys"] = set()
    last_joystick_state["is_active"] = False
    last_joystick_state["active_keys"] = set()
    
    # 버튼 상태 초기화
    last_button_states.clear()
    
    # 키 추적 초기화
    with keyboard_lock:
        pressed_button_keys.clear()
        pressed_joystick_keys.clear()


def input_watchdog_loop():
    """
    조이스틱/버튼 입력이 일정 시간 동안 안 들어오면
    자동으로 모든 키를 떼는 감시 루프.
    안드로이드에서 데이터가 같으면 전송하지 않는 문제를 고려하여 개선됨.
    조이스틱이 활성 상태일 때는 이전 입력을 지속합니다.
    """
    while True:
        try:
            now = datetime.now()
            should_release = False

            # 조이스틱 입력 타임아웃 체크
            if stats["last_joystick_time"] is not None:
                elapsed_js = (now - stats["last_joystick_time"]).total_seconds()
                
                # 조이스틱이 활성 상태일 때는 이전 입력을 지속
                if last_joystick_state.get("is_active", False):
                    # 조이스틱이 활성 상태이면 마지막 상태를 유지하기 위해 주기적으로 다시 적용
                    # INACTIVITY_RELEASE_TIMEOUT 이후부터 주기적으로 상태 유지
                    if elapsed_js > INACTIVITY_RELEASE_TIMEOUT:
                        # 마지막 조이스틱 상태를 다시 적용하여 키 유지
                        target_keys = last_joystick_state.get("active_keys", set())
                        if target_keys:
                            process_joystick_keys(target_keys)
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"[Watchdog] 조이스틱 이전 입력 지속: {target_keys}")
                    # 매우 긴 타임아웃(10초)이 지나면 해제 (연결 끊김으로 간주)
                    if elapsed_js > 10.0:
                        should_release = True
                else:
                    # 조이스틱이 중앙 상태였으면 타임아웃 후 해제
                    if elapsed_js > INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            # 버튼 입력 타임아웃 체크 (안드로이드 데이터 전송 특성 고려)
            if stats["last_button_time"] is not None:
                elapsed_btn = (now - stats["last_button_time"]).total_seconds()
                # 버튼이 눌린 상태였으면 더 긴 타임아웃 적용 (안드로이드에서 같은 데이터를 보내지 않아도 유지)
                if last_button_states:
                    # 눌린 버튼이 있으면 더 긴 타임아웃 (1.5초)
                    if elapsed_btn > INACTIVITY_RELEASE_TIMEOUT * 3:
                        # 버튼 키 해제
                        with keyboard_lock:
                            for button_name, btn_state in list(last_button_states.items()):
                                if btn_state["pressed"]:
                                    try:
                                        keyboard.release(btn_state["key"])
                                        pressed_keyboard_keys.discard(btn_state["key"])
                                        pressed_keys.discard(button_name)
                                    except Exception as e:
                                        if ENABLE_VERBOSE_LOGGING:
                                            print(f"Error releasing button key {button_name}: {e}")
                                    del last_button_states[button_name]
                else:
                    # 눌린 버튼이 없으면 일반 타임아웃
                    if elapsed_btn > INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            # 일정 시간 동안 입력이 없는데 아직 키가 눌려있으면 해제
            # 단, 조이스틱이 활성 상태였고 타임아웃이 짧으면 유지 (안드로이드 데이터 전송 특성 고려)
            if should_release and pressed_keyboard_keys:
                # 조이스틱 방향 키만 선택적으로 해제 (버튼 키는 제외)
                with keyboard_lock:
                    # 버튼 키는 제외하고 조이스틱 키만 해제
                    button_keys = {btn_state["key"] for btn_state in last_button_states.values() if btn_state["pressed"]}
                    keys_to_release = list((pressed_keyboard_keys & JOYSTICK_KEY_SET) - button_keys)
                    for key in keys_to_release:
                        try:
                            keyboard.release(key)
                            pressed_keyboard_keys.discard(key)
                        except Exception as e:
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"Error releasing key {key}: {e}")

        except Exception as e:
            if ENABLE_VERBOSE_LOGGING:
                print(f"Error in input watchdog loop: {e}")

        # 너무 자주 돌지 않도록 약간 딜레이
        time.sleep(0.05)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="라즈베리파이 게임 컨트롤러 Flask 서버")
    parser.add_argument(
        "--port",
        type=int,
        help=f"서버가 사용할 포트 번호 (기본 {DEFAULT_SERVER_PORT}, 환경 변수로도 설정 가능)"
    )
    args = parser.parse_args()

    server_port = resolve_server_port(args.port)
    app.config["SERVER_PORT"] = server_port

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
    print(f"    http://localhost:{server_port}")
    print(f"    http://127.0.0.1:{server_port}")
    print("")
    print("  내부망 접속 (같은 Wi-Fi/네트워크):")
    for ip in local_ips:
        print(f"    http://{ip}:{server_port}")
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
    print("    X → 1 (게임 시작)")
    print("    Y → Q (특수 액션)")
    print("=" * 60)
    print("💡 내부망 접속 방법:")
    print("  1. 같은 Wi-Fi/네트워크에 연결되어 있어야 합니다")
    print("  2. 다른 기기(스마트폰, 태블릿 등)에서 위의 IP 주소로 접속")
    print(f"  3. 방화벽이 포트 {server_port}을 차단하지 않는지 확인")
    print("")
    print("🔧 Windows 방화벽 설정 (필요한 경우):")
    print("  방법 1: PowerShell 관리자 권한으로 실행")
    print(f"    New-NetFirewallRule -DisplayName 'Flask Server' -Direction Inbound -LocalPort {server_port} -Protocol TCP -Action Allow")
    print("")
    print("  방법 2: Windows 방화벽 설정")
    print("    1. Windows 보안 > 방화벽 및 네트워크 보호")
    print("    2. 고급 설정 > 인바운드 규칙 > 새 규칙")
    print(f"    3. 포트 선택 > TCP > 특정 로컬 포트: {server_port}")
    print("    4. 연결 허용 > 모든 프로필 > 이름: Flask Server")
    print("=" * 60)
    print("⚠️  주의: 게임 창이 포커스되어 있어야 키 입력이 전달됩니다")
    print("=" * 60)

    # 입력 감시 쓰레드 시작 (조이스틱/버튼 데이터가 끊기면 자동으로 키 해제)
    watchdog_thread = threading.Thread(target=input_watchdog_loop, daemon=True)
    watchdog_thread.start()

    try:
        # 최적화된 서버 설정 (끊김 방지)
        app.run(host='0.0.0.0', port=server_port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n서버 종료 중...")
        release_all_keys()
        print("모든 키 입력 해제 완료")
