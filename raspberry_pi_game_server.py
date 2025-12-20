
import argparse
import json
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

keyboard = Controller()
keyboard_lock = threading.Lock()

pressed_keys = set()
pressed_keyboard_keys = set()
pressed_button_keys = set()
pressed_joystick_keys = set()

stats = {
    "joystick_count": 0,
    "button_count": 0,
    "last_joystick_time": None,
    "last_button_time": None,
    "server_start_time": datetime.now()
}

recent_data = {
    "last_joystick": None,
    "last_button": None
}

last_joystick_state = {
    "x": 0.0,
    "y": 0.0,
    "keys": set(),
    "is_active": False,
    "active_keys": set()
}

last_button_states = {}

DEFAULT_SERVER_PORT = Port

connected_users = {}

_cached_server_ips = None

KEY_MAPPING = {
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "A": Key.space,
    "B": Key.enter,
    "X": '1',
    "Y": '',
}

JOYSTICK_KEY_SET = {KEY_MAPPING["up"], KEY_MAPPING["down"], KEY_MAPPING["left"], KEY_MAPPING["right"]}

JOYSTICK_THRESHOLD = 0.3
JOYSTICK_THRESHOLD_ON = 0.3
JOYSTICK_THRESHOLD_OFF = 0.25

INACTIVITY_RELEASE_TIMEOUT = 0.5

ENABLE_VERBOSE_LOGGING = False

USER_CLEANUP_TIMEOUT = 3600


def resolve_server_port(cli_port=None):
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
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return "127.0.0.1"

def get_all_local_ips(use_cache=True):
    global _cached_server_ips
    
    if use_cache and _cached_server_ips is not None:
        return _cached_server_ips
    
    ips = []
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if ip and ip != '127.0.0.1' and not ip.startswith('::'):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    
    main_ip = get_local_ip()
    if main_ip and main_ip not in ips:
        ips.insert(0, main_ip)
    
    result = ips if ips else ["127.0.0.1"]
    
    if use_cache:
        _cached_server_ips = result
    
    return result

def update_user_activity():
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
    now = datetime.now()
    inactive_ips = []
    
    for ip, info in connected_users.items():
        elapsed = (now - info["last_seen"]).total_seconds()
        if elapsed > USER_CLEANUP_TIMEOUT:
            inactive_ips.append(ip)
    
    for ip in inactive_ips:
        del connected_users[ip]
    
    if inactive_ips:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Cleanup] {len(inactive_ips)}명의 비활성 접속자 제거됨")

@app.route('/', methods=['GET'])
def dashboard():
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
    
    users_list.sort(key=lambda x: x["last_seen"], reverse=True)
    
    return jsonify({
        "status": "ok",
        "total_users": len(users_list),
        "users": users_list
    })

@app.route('/ping', methods=['GET'])
def ping():
    update_user_activity()
    return jsonify({
        "status": "ok",
        "message": "Server is running",
        "server_time": datetime.now().isoformat()
    })

@app.route('/status', methods=['GET'])
def get_status():
    update_user_activity()
    now = datetime.now()
    
    joystick_elapsed = None
    button_elapsed = None
    
    if stats["last_joystick_time"]:
        joystick_elapsed = (now - stats["last_joystick_time"]).total_seconds()
    
    if stats["last_button_time"]:
        button_elapsed = (now - stats["last_button_time"]).total_seconds()
    
    joystick_active = joystick_elapsed is not None and joystick_elapsed < 5.0
    button_active = button_elapsed is not None and button_elapsed < 5.0
    
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
    target_keys = set()
    keys_to_press = []
    is_active = False
    
    previous_active_keys = last_joystick_state.get("active_keys", set())
    
    up_was_active = KEY_MAPPING["up"] in previous_active_keys
    down_was_active = KEY_MAPPING["down"] in previous_active_keys
    
    if up_was_active:
        if y > JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["up"])
            keys_to_press.append("up")
            is_active = True
    else:
        if y > JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["up"])
            keys_to_press.append("up")
            is_active = True
    
    if down_was_active:
        if y < -JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["down"])
            keys_to_press.append("down")
            is_active = True
    else:
        if y < -JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["down"])
            keys_to_press.append("down")
            is_active = True
    
    right_was_active = KEY_MAPPING["right"] in previous_active_keys
    left_was_active = KEY_MAPPING["left"] in previous_active_keys
    
    if right_was_active:
        if x > JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["right"])
            keys_to_press.append("right")
            is_active = True
    else:
        if x > JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["right"])
            keys_to_press.append("right")
            is_active = True
    
    if left_was_active:
        if x < -JOYSTICK_THRESHOLD_OFF:
            target_keys.add(KEY_MAPPING["left"])
            keys_to_press.append("left")
            is_active = True
    else:
        if x < -JOYSTICK_THRESHOLD_ON:
            target_keys.add(KEY_MAPPING["left"])
            keys_to_press.append("left")
            is_active = True
    
    return target_keys, keys_to_press, is_active


def process_joystick_keys(target_keys):
    global pressed_joystick_keys, pressed_keyboard_keys, pressed_button_keys
    
    with keyboard_lock:
        target_joystick_keys = target_keys & JOYSTICK_KEY_SET
        
        keys_to_add_physically = target_joystick_keys - pressed_keyboard_keys - pressed_button_keys
        for key in keys_to_add_physically:
            try:
                keyboard.press(key)
                pressed_keyboard_keys.add(key)
                pressed_joystick_keys.add(key)
            except Exception as e:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"Error pressing key {key}: {e}")
        
        keys_already_pressed = (target_joystick_keys & pressed_keyboard_keys) - pressed_button_keys - pressed_joystick_keys
        for key in keys_already_pressed:
            pressed_joystick_keys.add(key)
            if ENABLE_VERBOSE_LOGGING:
                print(f"[Key] Joystick takes over already pressed key: {key}")
        
        keys_to_maintain = target_joystick_keys & pressed_joystick_keys & pressed_keyboard_keys
        for key in keys_to_maintain:
            try:
                keyboard.release(key)
                time.sleep(0.001)
                keyboard.press(key)
            except Exception as e:
                if ENABLE_VERBOSE_LOGGING:
                    print(f"Error maintaining key {key}: {e}")
        
        keys_to_remove = (pressed_joystick_keys & JOYSTICK_KEY_SET) - target_joystick_keys
        for key in keys_to_remove:
            if key not in pressed_button_keys:
                try:
                    keyboard.release(key)
                    pressed_keyboard_keys.discard(key)
                    pressed_joystick_keys.discard(key)
                except Exception as e:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"Error releasing key {key}: {e}")
            else:
                pressed_joystick_keys.discard(key)
        
        pressed_joystick_keys &= JOYSTICK_KEY_SET
        pressed_joystick_keys |= target_joystick_keys


def process_joystick_data_internal(data, source="HTTP"):
    global pressed_joystick_keys, pressed_keyboard_keys, pressed_button_keys
    
    try:
        x = data.get('x', 0.0)
        y = data.get('y', 0.0)
        strength = data.get('strength', 0)
        reset_requested = data.get('reset', False)
        
        try:
            x = float(x)
            y = float(y)
        except (ValueError, TypeError):
            error_msg = f"Invalid data type: x and y must be numbers"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick/{source}] ⚠️ 에러: {error_msg}")
            return {"status": "error", "message": error_msg}
        
        if reset_requested:
            reset_all_states_internal()
            if ENABLE_VERBOSE_LOGGING:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick/{source}] 게임 재시작 - 상태 초기화됨")
        
        stats["joystick_count"] += 1
        now = datetime.now()
        stats["last_joystick_time"] = now
        
        target_keys, keys_to_press, is_active = calculate_joystick_keys(x, y)
        
        last_joystick_state["x"] = x
        last_joystick_state["y"] = y
        last_joystick_state["keys"] = target_keys.copy()
        last_joystick_state["is_active"] = is_active
        last_joystick_state["active_keys"] = target_keys.copy()
        
        process_joystick_keys(target_keys)
        
        recent_data["last_joystick"] = {
            "x": round(x, 2),
            "y": round(y, 2),
            "strength": strength,
            "keys": keys_to_press,
            "time": now.isoformat(),
            "source": source
        }
        
        if ENABLE_VERBOSE_LOGGING:
            if keys_to_press:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick/{source}] ✓ 데이터 수신 - "
                      f"X: {x:.2f}, Y: {y:.2f} → Keys: {keys_to_press}")
        
        return {
            "status": "ok",
            "received": True,
            "keys_pressed": keys_to_press
        }
        
    except Exception as e:
        error_msg = f"Error processing joystick data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick/{source}] ⚠️ 에러: {error_msg}")
        import traceback
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return {"status": "error", "message": str(e)}


def process_button_data_internal(data, source="HTTP"):
    global pressed_joystick_keys, pressed_button_keys, pressed_keyboard_keys, pressed_keys
    
    try:
        button = data.get('button', '')
        pressed = data.get('pressed', False)
        
        if not button:
            error_msg = "Button name is required"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button/{source}] ⚠️ 에러: {error_msg}")
            return {"status": "error", "message": error_msg}
        
        stats["button_count"] += 1
        now = datetime.now()
        stats["last_button_time"] = now
        
        if button not in KEY_MAPPING:
            error_msg = f"Unknown button: {button}. Available buttons: {list(KEY_MAPPING.keys())}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button/{source}] ⚠️ 에러: {error_msg}")
            return {"status": "error", "message": error_msg}
        
        key = KEY_MAPPING[button]
        action = "pressed" if pressed else "released"
        
        if not key:
            return {"status": "ok", "message": f"Button {button} has no key mapping"}
        
        previous_state = last_button_states.get(button, {}).get("pressed", False)
        
        if previous_state == pressed:
            return {
                "status": "ok",
                "received": True,
                "button": button,
                "action": action,
                "key": str(key),
                "message": "State unchanged, skipped"
            }
        
        last_button_states[button] = {
            "pressed": pressed,
            "key": key,
            "time": now
        }
        
        if pressed:
            if button not in pressed_keys:
                with keyboard_lock:
                    is_joystick_key = key in JOYSTICK_KEY_SET
                    
                    if is_joystick_key and key in last_joystick_state.get("active_keys", set()):
                        pressed_button_keys.add(key)
                        if ENABLE_VERBOSE_LOGGING:
                            print(f"[Key] Button pressed, joystick key already active: {key}")
                    elif is_joystick_key and key in pressed_joystick_keys:
                        pressed_joystick_keys.discard(key)
                    elif not is_joystick_key and key in pressed_joystick_keys:
                        pressed_joystick_keys.discard(key)
                    
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
                        pressed_button_keys.add(key)
                
                pressed_keys.add(button)
        else:
            if button in pressed_keys:
                with keyboard_lock:
                    pressed_button_keys.discard(key)
                    
                    is_joystick_key = key in JOYSTICK_KEY_SET
                    
                    if is_joystick_key:
                        should_keep_key = key in last_joystick_state.get("active_keys", set())
                        
                        if should_keep_key:
                            pressed_joystick_keys.add(key)
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"[Key] Button released, joystick continues: {key}")
                        else:
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
            
            if button in last_button_states:
                del last_button_states[button]
        
        recent_data["last_button"] = {
            "button": button,
            "pressed": pressed,
            "action": action,
            "key": str(key),
            "time": now.isoformat(),
            "source": source
        }
        
        if ENABLE_VERBOSE_LOGGING:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button/{source}] ✓ 데이터 수신 - "
                  f"{button} {action} → Key: {key}")
        
        return {
            "status": "ok",
            "received": True,
            "button": button,
            "action": action,
            "key": str(key)
        }
        
    except Exception as e:
        error_msg = f"Error processing button data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button/{source}] ⚠️ 에러: {error_msg}")
        import traceback
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return {"status": "error", "message": str(e)}


@app.route('/joystick', methods=['POST', 'OPTIONS'])
def receive_joystick():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    global pressed_joystick_keys, pressed_keyboard_keys, pressed_button_keys
    
    try:
        update_user_activity()
        
        if not request.is_json:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: Content-Type이 application/json이 아닙니다. Content-Type: {request.content_type}")
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        if data is None:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: JSON 데이터가 없습니다")
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        result = process_joystick_data_internal(data, source="HTTP")
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Error receiving joystick data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick] ⚠️ 400 에러: {error_msg}")
        import traceback
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/button', methods=['POST', 'OPTIONS'])
def receive_button():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    
    global pressed_joystick_keys, pressed_button_keys, pressed_keyboard_keys, pressed_keys
    
    try:
        update_user_activity()
        
        if not request.is_json:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: Content-Type이 application/json이 아닙니다. Content-Type: {request.content_type}")
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        
        if data is None:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: JSON 데이터가 없습니다")
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        result = process_button_data_internal(data, source="HTTP")
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Error receiving button data: {e}"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button] ⚠️ 400 에러: {error_msg}")
        import traceback
        if ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/stop', methods=['POST'])
def stop_all():
    release_all_keys()
    return jsonify({"status": "ok", "message": "All keys released"})

@app.route('/reset', methods=['POST'])
def reset_all_states():
    try:
        release_all_keys()
        
        last_joystick_state["x"] = 0.0
        last_joystick_state["y"] = 0.0
        last_joystick_state["keys"] = set()
        last_joystick_state["is_active"] = False
        last_joystick_state["active_keys"] = set()
        
        last_button_states.clear()
        
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
    try:
        data = request.get_json()
        return jsonify({
            "status": "ok",
            "message": "Key mapping updated"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def press_key(key):
    global pressed_keyboard_keys
    try:
        with keyboard_lock:
            if key not in pressed_keyboard_keys:
                keyboard.press(key)
                pressed_keyboard_keys.add(key)
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[Key] Pressed: {key}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"Error pressing key {key}: {e}")

def release_key(key):
    global pressed_keyboard_keys
    try:
        with keyboard_lock:
            if key in pressed_keyboard_keys:
                keyboard.release(key)
                pressed_keyboard_keys.discard(key)
                if ENABLE_VERBOSE_LOGGING:
                    print(f"[Key] Released: {key}")
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"Error releasing key {key}: {e}")

def release_all_keys():
    global pressed_joystick_keys, pressed_button_keys, pressed_keyboard_keys, pressed_keys
    try:
        with keyboard_lock:
            keys_to_release = list(pressed_keyboard_keys)
            for key in keys_to_release:
                try:
                    keyboard.release(key)
                except Exception as e:
                    if ENABLE_VERBOSE_LOGGING:
                        print(f"Error releasing key {key}: {e}")
            pressed_keyboard_keys.clear()
            
            pressed_keys.clear()
            pressed_button_keys.clear()
            pressed_joystick_keys.clear()
    except Exception as e:
        if ENABLE_VERBOSE_LOGGING:
            print(f"Error releasing all keys: {e}")

def reset_all_states_internal():
    global pressed_joystick_keys, pressed_button_keys
    release_all_keys()
    
    last_joystick_state["x"] = 0.0
    last_joystick_state["y"] = 0.0
    last_joystick_state["keys"] = set()
    last_joystick_state["is_active"] = False
    last_joystick_state["active_keys"] = set()
    
    last_button_states.clear()
    
    with keyboard_lock:
        pressed_button_keys.clear()
        pressed_joystick_keys.clear()


def input_watchdog_loop():
    while True:
        try:
            now = datetime.now()
            should_release = False

            if stats["last_joystick_time"] is not None:
                elapsed_js = (now - stats["last_joystick_time"]).total_seconds()
                
                if last_joystick_state.get("is_active", False):
                    if elapsed_js > INACTIVITY_RELEASE_TIMEOUT:
                        target_keys = last_joystick_state.get("active_keys", set())
                        if target_keys:
                            process_joystick_keys(target_keys)
                            if ENABLE_VERBOSE_LOGGING:
                                print(f"[Watchdog] 조이스틱 이전 입력 지속: {target_keys}")
                    if elapsed_js > 10.0:
                        should_release = True
                else:
                    if elapsed_js > INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            if stats["last_button_time"] is not None:
                elapsed_btn = (now - stats["last_button_time"]).total_seconds()
                if last_button_states:
                    if elapsed_btn > INACTIVITY_RELEASE_TIMEOUT * 3:
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
                    if elapsed_btn > INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            if should_release and pressed_keyboard_keys:
                with keyboard_lock:
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

    watchdog_thread = threading.Thread(target=input_watchdog_loop, daemon=True)
    watchdog_thread.start()

    try:
        app.run(host='0.0.0.0', port=server_port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n서버 종료 중...")
        release_all_keys()
        print("모든 키 입력 해제 완료")
