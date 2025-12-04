"""
Flask 애플리케이션 모듈
웹 서버 및 API 라우트 정의
"""

from datetime import datetime

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from . import config
from . import data_processor
from . import keyboard_handler
from . import utils

# Flask 앱 초기화
app = Flask(__name__)
CORS(app)

# 서버 IP 주소 캐싱 (성능 최적화)
_cached_server_ips = [None]  # 리스트로 래핑하여 참조 전달

# 접속자 정보 추적
connected_users = {}  # {ip: {"first_seen": datetime, "last_seen": datetime, "request_count": int}}


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
        if elapsed > config.USER_CLEANUP_TIMEOUT:
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
    server_ips = utils.get_all_local_ips(use_cache=True, cache_var=_cached_server_ips)
    server_port = app.config.get("SERVER_PORT", config.DEFAULT_SERVER_PORT)
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
    
    if data_processor.stats["last_joystick_time"]:
        joystick_elapsed = (now - data_processor.stats["last_joystick_time"]).total_seconds()
    
    if data_processor.stats["last_button_time"]:
        button_elapsed = (now - data_processor.stats["last_button_time"]).total_seconds()
    
    # 데이터 수신 여부 판단 (5초 이내면 활성)
    joystick_active = joystick_elapsed is not None and joystick_elapsed < 5.0
    button_active = button_elapsed is not None and button_elapsed < 5.0
    
    # 서버 IP 주소 가져오기 (캐시 사용)
    server_ips = utils.get_all_local_ips(use_cache=True, cache_var=_cached_server_ips)
    
    return jsonify({
        "status": "ok",
        "server_running": True,
        "server_start_time": data_processor.stats["server_start_time"].isoformat(),
        "current_time": now.isoformat(),
        "server_ips": server_ips,
        "statistics": {
            "joystick": {
                "total_received": data_processor.stats["joystick_count"],
                "last_received": data_processor.stats["last_joystick_time"].isoformat() if data_processor.stats["last_joystick_time"] else None,
                "elapsed_seconds": round(joystick_elapsed, 2) if joystick_elapsed is not None else None,
                "is_active": joystick_active
            },
            "button": {
                "total_received": data_processor.stats["button_count"],
                "last_received": data_processor.stats["last_button_time"].isoformat() if data_processor.stats["last_button_time"] else None,
                "elapsed_seconds": round(button_elapsed, 2) if button_elapsed is not None else None,
                "is_active": button_active
            }
        },
        "recent_data": {
            "joystick": data_processor.recent_data["last_joystick"],
            "button": data_processor.recent_data["last_button"]
        },
        "summary": {
            "receiving_data": joystick_active or button_active,
            "message": "데이터 수신 중" if (joystick_active or button_active) else "데이터 수신 대기 중"
        }
    })


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
        
        # 공통 처리 함수 호출
        result = data_processor.process_joystick_data_internal(data, source="HTTP")
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Error receiving joystick data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: {error_msg}")
        import traceback
        if config.ENABLE_VERBOSE_LOGGING:
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
        
        # 공통 처리 함수 호출
        result = data_processor.process_button_data_internal(data, source="HTTP")
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Error receiving button data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: {error_msg}")
        import traceback
        if config.ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/stop', methods=['POST'])
def stop_all():
    """모든 키 입력 중지"""
    keyboard_handler.release_all_keys()
    return jsonify({"status": "ok", "message": "All keys released"})


@app.route('/reset', methods=['POST'])
def reset_all_states():
    """
    모든 상태 초기화 (게임 재시작 시 사용)
    키 상태, 조이스틱 상태, 버튼 상태 모두 초기화
    """
    try:
        # 모든 키 해제
        keyboard_handler.release_all_keys()
        
        # 조이스틱 상태 초기화
        data_processor.last_joystick_state["x"] = 0.0
        data_processor.last_joystick_state["y"] = 0.0
        data_processor.last_joystick_state["keys"] = set()
        data_processor.last_joystick_state["is_active"] = False
        data_processor.last_joystick_state["active_keys"] = set()
        
        # 버튼 상태 초기화
        data_processor.last_button_states.clear()
        
        if config.ENABLE_VERBOSE_LOGGING:
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

