"""
데이터 처리 모듈
조이스틱 및 버튼 데이터 처리 로직
"""

from datetime import datetime

from . import config
from . import keyboard_handler


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
    up_was_active = config.KEY_MAPPING["up"] in previous_active_keys
    down_was_active = config.KEY_MAPPING["down"] in previous_active_keys
    
    if up_was_active:
        # 위 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if y > config.JOYSTICK_THRESHOLD_OFF:
            target_keys.add(config.KEY_MAPPING["up"])
            keys_to_press.append("up")
            is_active = True
    else:
        # 위 키가 눌려있지 않았으면 높은 임계값으로 시작
        if y > config.JOYSTICK_THRESHOLD_ON:
            target_keys.add(config.KEY_MAPPING["up"])
            keys_to_press.append("up")
            is_active = True
    
    if down_was_active:
        # 아래 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if y < -config.JOYSTICK_THRESHOLD_OFF:
            target_keys.add(config.KEY_MAPPING["down"])
            keys_to_press.append("down")
            is_active = True
    else:
        # 아래 키가 눌려있지 않았으면 높은 임계값으로 시작
        if y < -config.JOYSTICK_THRESHOLD_ON:
            target_keys.add(config.KEY_MAPPING["down"])
            keys_to_press.append("down")
            is_active = True
    
    # 좌/우 방향
    right_was_active = config.KEY_MAPPING["right"] in previous_active_keys
    left_was_active = config.KEY_MAPPING["left"] in previous_active_keys
    
    if right_was_active:
        # 오른쪽 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if x > config.JOYSTICK_THRESHOLD_OFF:
            target_keys.add(config.KEY_MAPPING["right"])
            keys_to_press.append("right")
            is_active = True
    else:
        # 오른쪽 키가 눌려있지 않았으면 높은 임계값으로 시작
        if x > config.JOYSTICK_THRESHOLD_ON:
            target_keys.add(config.KEY_MAPPING["right"])
            keys_to_press.append("right")
            is_active = True
    
    if left_was_active:
        # 왼쪽 키가 이미 눌려있었으면 낮은 임계값으로 유지 (떨림 방지)
        if x < -config.JOYSTICK_THRESHOLD_OFF:
            target_keys.add(config.KEY_MAPPING["left"])
            keys_to_press.append("left")
            is_active = True
    else:
        # 왼쪽 키가 눌려있지 않았으면 높은 임계값으로 시작
        if x < -config.JOYSTICK_THRESHOLD_ON:
            target_keys.add(config.KEY_MAPPING["left"])
            keys_to_press.append("left")
            is_active = True
    
    return target_keys, keys_to_press, is_active


def reset_all_states_internal():
    """
    내부 상태 초기화 함수 (게임 재시작 시 사용)
    """
    # 모든 키 해제
    keyboard_handler.release_all_keys()
    
    # 조이스틱 상태 초기화
    last_joystick_state["x"] = 0.0
    last_joystick_state["y"] = 0.0
    last_joystick_state["keys"] = set()
    last_joystick_state["is_active"] = False
    last_joystick_state["active_keys"] = set()
    
    # 버튼 상태 초기화
    last_button_states.clear()


def process_joystick_data_internal(data, source="HTTP"):
    """
    조이스틱 데이터 처리 공통 함수 (HTTP/MQTT 공통)
    
    Args:
        data: 조이스틱 데이터 딕셔너리 {"x": float, "y": float, "strength": int, "reset": bool}
        source: 데이터 출처 ("HTTP" 또는 "MQTT")
    
    Returns:
        dict: 처리 결과
    """
    try:
        x = data.get('x', 0.0)
        y = data.get('y', 0.0)
        strength = data.get('strength', 0)
        reset_requested = data.get('reset', False)
        
        # 데이터 타입 검증
        try:
            x = float(x)
            y = float(y)
        except (ValueError, TypeError):
            error_msg = f"Invalid data type: x and y must be numbers"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick/{source}] ⚠️ 에러: {error_msg}")
            return {"status": "error", "message": error_msg}
        
        # 게임 재시작 요청이 있으면 상태 초기화
        if reset_requested:
            reset_all_states_internal()
            if config.ENABLE_VERBOSE_LOGGING:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Joystick/{source}] 게임 재시작 - 상태 초기화됨")
        
        # 통계 업데이트
        stats["joystick_count"] += 1
        now = datetime.now()
        stats["last_joystick_time"] = now
        
        # 조이스틱 입력값을 키 매핑으로 변환 (히스테리시스 적용)
        target_keys, keys_to_press, is_active = calculate_joystick_keys(x, y)
        
        # 마지막 조이스틱 상태 저장
        last_joystick_state["x"] = x
        last_joystick_state["y"] = y
        last_joystick_state["keys"] = target_keys.copy()
        last_joystick_state["is_active"] = is_active
        last_joystick_state["active_keys"] = target_keys.copy()
        
        # 조이스틱 키 입력 처리 (press/release)
        keyboard_handler.process_joystick_keys(target_keys)
        
        # 최근 데이터 저장
        recent_data["last_joystick"] = {
            "x": round(x, 2),
            "y": round(y, 2),
            "strength": strength,
            "keys": keys_to_press,
            "time": now.isoformat(),
            "source": source
        }
        
        if config.ENABLE_VERBOSE_LOGGING:
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
        if config.ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return {"status": "error", "message": str(e)}


def process_button_data_internal(data, source="HTTP"):
    """
    버튼 데이터 처리 공통 함수 (HTTP/MQTT 공통)
    
    Args:
        data: 버튼 데이터 딕셔너리 {"button": str, "pressed": bool}
        source: 데이터 출처 ("HTTP" 또는 "MQTT")
    
    Returns:
        dict: 처리 결과
    """
    try:
        button = data.get('button', '')
        pressed = data.get('pressed', False)
        
        # 버튼 이름 검증
        if not button:
            error_msg = "Button name is required"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button/{source}] ⚠️ 에러: {error_msg}")
            return {"status": "error", "message": error_msg}
        
        # 통계 업데이트
        stats["button_count"] += 1
        now = datetime.now()
        stats["last_button_time"] = now
        
        if button not in config.KEY_MAPPING:
            error_msg = f"Unknown button: {button}. Available buttons: {list(config.KEY_MAPPING.keys())}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Button/{source}] ⚠️ 에러: {error_msg}")
            return {"status": "error", "message": error_msg}
        
        key = config.KEY_MAPPING[button]
        action = "pressed" if pressed else "released"
        
        # 빈 키 매핑 체크
        if not key:
            return {"status": "ok", "message": f"Button {button} has no key mapping"}
        
        # 이전 버튼 상태 확인 (중복 처리 방지)
        previous_state = last_button_states.get(button, {}).get("pressed", False)
        
        # 상태가 변경되지 않았으면 처리하지 않음
        if previous_state == pressed:
            return {
                "status": "ok",
                "received": True,
                "button": button,
                "action": action,
                "key": str(key),
                "message": "State unchanged, skipped"
            }
        
        # 마지막 버튼 상태 저장
        last_button_states[button] = {
            "pressed": pressed,
            "key": key,
            "time": now
        }
        
        # 상태가 변경되었을 때만 키 입력 처리
        if pressed:
            if button not in keyboard_handler.pressed_keys:
                with keyboard_handler.keyboard_lock:
                    is_joystick_key = key in config.JOYSTICK_KEY_SET
                    
                    if is_joystick_key and key in last_joystick_state.get("active_keys", set()):
                        keyboard_handler.pressed_button_keys.add(key)
                        if config.ENABLE_VERBOSE_LOGGING:
                            print(f"[Key] Button pressed, joystick key already active: {key}")
                    elif is_joystick_key and key in keyboard_handler.pressed_joystick_keys:
                        keyboard_handler.pressed_joystick_keys.discard(key)
                    elif not is_joystick_key and key in keyboard_handler.pressed_joystick_keys:
                        keyboard_handler.pressed_joystick_keys.discard(key)
                    
                    if key not in keyboard_handler.pressed_keyboard_keys:
                        try:
                            keyboard_handler.keyboard.press(key)
                            keyboard_handler.pressed_keyboard_keys.add(key)
                            keyboard_handler.pressed_button_keys.add(key)
                            if config.ENABLE_VERBOSE_LOGGING:
                                print(f"[Key] Pressed (Button): {key}")
                        except Exception as e:
                            if config.ENABLE_VERBOSE_LOGGING:
                                print(f"Error pressing key {key}: {e}")
                    else:
                        keyboard_handler.pressed_button_keys.add(key)
                
                keyboard_handler.pressed_keys.add(button)
        else:
            if button in keyboard_handler.pressed_keys:
                with keyboard_handler.keyboard_lock:
                    keyboard_handler.pressed_button_keys.discard(key)
                    
                    is_joystick_key = key in config.JOYSTICK_KEY_SET
                    
                    if is_joystick_key:
                        should_keep_key = key in last_joystick_state.get("active_keys", set())
                        
                        if should_keep_key:
                            keyboard_handler.pressed_joystick_keys.add(key)
                            if config.ENABLE_VERBOSE_LOGGING:
                                print(f"[Key] Button released, joystick continues: {key}")
                        else:
                            if key in keyboard_handler.pressed_keyboard_keys:
                                try:
                                    keyboard_handler.keyboard.release(key)
                                    keyboard_handler.pressed_keyboard_keys.discard(key)
                                    keyboard_handler.pressed_joystick_keys.discard(key)
                                    if config.ENABLE_VERBOSE_LOGGING:
                                        print(f"[Key] Released (Button): {key}")
                                except Exception as e:
                                    if config.ENABLE_VERBOSE_LOGGING:
                                        print(f"Error releasing key {key}: {e}")
                    else:
                        if key in keyboard_handler.pressed_keyboard_keys:
                            try:
                                keyboard_handler.keyboard.release(key)
                                keyboard_handler.pressed_keyboard_keys.discard(key)
                                if config.ENABLE_VERBOSE_LOGGING:
                                    print(f"[Key] Released (Button): {key}")
                            except Exception as e:
                                if config.ENABLE_VERBOSE_LOGGING:
                                    print(f"Error releasing key {key}: {e}")
                
                keyboard_handler.pressed_keys.discard(button)
            
            if button in last_button_states:
                del last_button_states[button]
        
        # 최근 데이터 저장
        recent_data["last_button"] = {
            "button": button,
            "pressed": pressed,
            "action": action,
            "key": str(key),
            "time": now.isoformat(),
            "source": source
        }
        
        if config.ENABLE_VERBOSE_LOGGING:
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
        if config.ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()
        return {"status": "error", "message": str(e)}

