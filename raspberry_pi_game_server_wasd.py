"""
라즈베리파이 Flask 서버 - WASD 키 입력 버전
게임 컨트롤러를 WASD 키로 매핑 (FPS 게임 스타일)

설치:
    pip install flask flask-cors pynput
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pynput.keyboard import Key, Controller
from datetime import datetime

app = Flask(__name__)
CORS(app)

keyboard = Controller()
pressed_keys = set()

# WASD 키 매핑
KEY_MAPPING = {
    "up": 'w',
    "down": 's',
    "left": 'a',
    "right": 'd',
    "A": Key.space,      # 점프
    "B": Key.shift,      # 달리기
    "X": 'e',           # 상호작용
    "Y": 'q',           # 특수 액션
}

JOYSTICK_THRESHOLD = 0.3

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/joystick', methods=['POST'])
def receive_joystick():
    """조이스틱 → WASD 키 변환"""
    try:
        data = request.get_json()
        x = data.get('x', 0.0)
        y = data.get('y', 0.0)
        
        # 이전 키 모두 떼기
        release_all_direction_keys()
        
        if abs(x) < JOYSTICK_THRESHOLD and abs(y) < JOYSTICK_THRESHOLD:
            return jsonify({"status": "ok", "keys": "none"})
        
        keys_pressed = []
        
        # WASD 입력
        if y > JOYSTICK_THRESHOLD:
            keyboard.press(KEY_MAPPING["up"])
            keys_pressed.append("W")
        if y < -JOYSTICK_THRESHOLD:
            keyboard.press(KEY_MAPPING["down"])
            keys_pressed.append("S")
        if x > JOYSTICK_THRESHOLD:
            keyboard.press(KEY_MAPPING["right"])
            keys_pressed.append("D")
        if x < -JOYSTICK_THRESHOLD:
            keyboard.press(KEY_MAPPING["left"])
            keys_pressed.append("A")
        
        print(f"[Joystick] X: {x:.2f}, Y: {y:.2f} → {keys_pressed}")
        
        return jsonify({"status": "ok", "keys": keys_pressed})
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/button', methods=['POST'])
def receive_button():
    """버튼 → 키 입력"""
    try:
        data = request.get_json()
        button = data.get('button', '')
        pressed = data.get('pressed', False)
        
        if button not in KEY_MAPPING:
            return jsonify({"status": "error"}), 400
        
        key = KEY_MAPPING[button]
        
        if pressed:
            keyboard.press(key)
            pressed_keys.add(button)
        else:
            keyboard.release(key)
            pressed_keys.discard(button)
        
        action = "pressed" if pressed else "released"
        print(f"[Button] {button} {action} → {key}")
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def release_all_direction_keys():
    """방향 키만 모두 떼기"""
    for direction in ["up", "down", "left", "right"]:
        if direction in KEY_MAPPING:
            try:
                keyboard.release(KEY_MAPPING[direction])
            except:
                pass

@app.route('/stop', methods=['POST'])
def stop_all():
    """모든 키 해제"""
    release_all_direction_keys()
    for button in list(pressed_keys):
        if button in KEY_MAPPING:
            try:
                keyboard.release(KEY_MAPPING[button])
            except:
                pass
    pressed_keys.clear()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("=" * 60)
    print("게임 컨트롤러 서버 - WASD 키 입력")
    print("=" * 60)
    print("조이스틱 → WASD")
    print("버튼 A → Space, B → Shift, X → E, Y → Q")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)



