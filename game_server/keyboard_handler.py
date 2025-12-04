"""
키보드 입력 처리 모듈
키보드 입력 시뮬레이션 및 키 상태 관리
"""

import threading
import time
from datetime import datetime
from pynput.keyboard import Controller

from . import config


# 키보드 컨트롤러
keyboard = Controller()

# 키 입력 동기화를 위한 Lock (끊김 방지)
keyboard_lock = threading.Lock()

# 현재 눌려있는 키 추적 (중복 입력 방지)
pressed_keys = set()  # 버튼 이름 추적 ("A", "B", "X", "Y")
pressed_keyboard_keys = set()  # 실제 키보드 키 추적 (Key.up, Key.down, 'w', 'a' 등)
pressed_button_keys = set()  # 버튼으로 눌린 키 추적 (조이스틱과 분리)
pressed_joystick_keys = set()  # 조이스틱으로 눌린 키 추적 (버튼과 분리)


def press_key(key):
    """키보드 키 누르기 (동기화 처리로 끊김 방지, 중복 방지)"""
    try:
        with keyboard_lock:
            # 키가 이미 눌려있지 않으면 누르기 (중복 방지)
            if key not in pressed_keyboard_keys:
                keyboard.press(key)
                pressed_keyboard_keys.add(key)
                if config.ENABLE_VERBOSE_LOGGING:
                    print(f"[Key] Pressed: {key}")
    except Exception as e:
        if config.ENABLE_VERBOSE_LOGGING:
            print(f"Error pressing key {key}: {e}")


def release_key(key):
    """키보드 키 떼기 (동기화 처리로 끊김 방지, 확실한 해제 보장)"""
    try:
        with keyboard_lock:
            # 키가 눌려있으면 떼기 (확실한 해제 보장)
            if key in pressed_keyboard_keys:
                keyboard.release(key)
                pressed_keyboard_keys.discard(key)
                if config.ENABLE_VERBOSE_LOGGING:
                    print(f"[Key] Released: {key}")
    except Exception as e:
        if config.ENABLE_VERBOSE_LOGGING:
            print(f"Error releasing key {key}: {e}")


def release_all_keys():
    """모든 키보드 키 떼기 (동기화 처리로 끊김 방지)"""
    try:
        with keyboard_lock:
            # 현재 눌려있는 모든 키보드 키를 떼기
            keys_to_release = list(pressed_keyboard_keys)
            for key in keys_to_release:
                try:
                    keyboard.release(key)
                except Exception as e:
                    if config.ENABLE_VERBOSE_LOGGING:
                        print(f"Error releasing key {key}: {e}")
            pressed_keyboard_keys.clear()
            
            # 버튼 및 조이스틱 추적도 초기화
            pressed_keys.clear()
            pressed_button_keys.clear()
            pressed_joystick_keys.clear()
    except Exception as e:
        if config.ENABLE_VERBOSE_LOGGING:
            print(f"Error releasing all keys: {e}")


def process_joystick_keys(target_keys):
    """
    조이스틱 키 입력 처리 (press/release)
    버튼과 조이스틱 키를 분리하여 추적하여 간섭 방지
    
    Args:
        target_keys: 눌려야 할 키 집합
    """
    with keyboard_lock:
        # 조이스틱으로 눌려야 하는 키 (조이스틱 방향 키만)
        target_joystick_keys = target_keys & config.JOYSTICK_KEY_SET
        
        # 조이스틱으로 눌려야 하는데 안 눌려있는 키 → 누르기
        # 버튼이 이미 눌려있는 키는 물리적으로 누르지 않지만, 조이스틱 추적에는 포함
        keys_to_add_physically = target_joystick_keys - pressed_keyboard_keys - pressed_button_keys
        for key in keys_to_add_physically:
            try:
                keyboard.press(key)
                pressed_keyboard_keys.add(key)
                pressed_joystick_keys.add(key)
            except Exception as e:
                if config.ENABLE_VERBOSE_LOGGING:
                    print(f"Error pressing key {key}: {e}")
        
        # 이미 눌려있지만 조이스틱 추적에 없는 키 추가 (버튼을 떼고 난 후 조이스틱이 계속 같은 방향일 때)
        # 버튼이 눌려있지 않고, 키가 이미 눌려있고, 조이스틱이 이 키를 눌러야 하면 추적에 추가
        keys_already_pressed = (target_joystick_keys & pressed_keyboard_keys) - pressed_button_keys - pressed_joystick_keys
        for key in keys_already_pressed:
            # 조이스틱 추적에 추가 (물리적으로는 이미 눌려있음)
            pressed_joystick_keys.add(key)
            if config.ENABLE_VERBOSE_LOGGING:
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
                if config.ENABLE_VERBOSE_LOGGING:
                    print(f"Error maintaining key {key}: {e}")
        
        # 조이스틱으로 눌려있는데 뗴야 하는 키 → 떼기
        # 버튼이 눌려있는 키는 건드리지 않음
        keys_to_remove = (pressed_joystick_keys & config.JOYSTICK_KEY_SET) - target_joystick_keys
        for key in keys_to_remove:
            # 버튼이 이 키를 사용 중이면 건드리지 않음
            if key not in pressed_button_keys:
                try:
                    keyboard.release(key)
                    pressed_keyboard_keys.discard(key)
                    pressed_joystick_keys.discard(key)
                except Exception as e:
                    if config.ENABLE_VERBOSE_LOGGING:
                        print(f"Error releasing key {key}: {e}")
            else:
                # 버튼이 사용 중이면 조이스틱 추적에서만 제거 (물리적 키는 유지)
                pressed_joystick_keys.discard(key)
        
        # 조이스틱 키 추적 업데이트 (버튼과 분리)
        # 조이스틱 키만 유지하고 새로운 키 추가
        pressed_joystick_keys &= config.JOYSTICK_KEY_SET  # 조이스틱 키만 유지
        pressed_joystick_keys |= target_joystick_keys  # 새로운 조이스틱 키 추가 (버튼이 눌러도 추적)

