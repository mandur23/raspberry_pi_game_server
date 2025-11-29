# 🎮 게임 컨트롤러 Flask 서버 가이드

## 📋 파일 설명

### 1. `raspberry_pi_server.py` (기본 버전)
- 기본적인 데이터 수신 기능
- 조이스틱/버튼 데이터 처리 예시
- 초보자용 간단한 구조

### 2. `raspberry_pi_server_advanced.py` (고급 버전)
- GPIO 제어 예시
- 모터 제어 로직 포함
- 실제 하드웨어 연동 예시

---

## 🚀 설치 및 실행

### 1. 필요한 패키지 설치

```bash
pip install flask flask-cors
```

### 2. 서버 실행

```bash
# 기본 버전
python raspberry_pi_server.py

# 고급 버전
python raspberry_pi_server_advanced.py
```

### 3. 서버 확인

서버가 실행되면 다음 메시지가 표시됩니다:
```
==================================================
게임 컨트롤러 Flask 서버 시작
==================================================
서버 주소: http://0.0.0.0:5000
엔드포인트:
  - GET  /ping      : 연결 테스트
  - POST /joystick   : 조이스틱 데이터 수신
  - POST /button     : 버튼 데이터 수신
  - GET  /status     : 서버 상태 조회
  - POST /reset      : 데이터 초기화
==================================================
```

---

## 📡 데이터 수신 방식

### 조이스틱 데이터

**엔드포인트**: `POST /joystick`

**받는 데이터**:
```json
{
  "type": "joystick",
  "angle": 45,
  "strength": 75,
  "x": 0.53,
  "y": 0.53,
  "timestamp": 1234567890123
}
```

**처리 방법**:
```python
data = request.get_json()  # JSON 자동 파싱
x = data.get('x', 0.0)     # -1.0 ~ 1.0
y = data.get('y', 0.0)     # -1.0 ~ 1.0
strength = data.get('strength', 0)  # 0-100%
```

### 버튼 데이터

**엔드포인트**: `POST /button`

**받는 데이터**:
```json
{
  "type": "button",
  "button": "A",
  "pressed": true,
  "timestamp": 1234567890123
}
```

**처리 방법**:
```python
data = request.get_json()
button = data.get('button', '')      # "A", "B", "X", "Y"
pressed = data.get('pressed', False) # true/false
```

---

## 🔧 실제 사용 예시

### 예시 1: 로봇 모터 제어

```python
@app.route('/joystick', methods=['POST'])
def receive_joystick():
    data = request.get_json()
    x = data.get('x', 0.0)
    y = data.get('y', 0.0)
    
    # 차동 구동 계산
    left_motor = (y + x) * 100
    right_motor = (y - x) * 100
    
    # 모터 제어
    control_motor_left(left_motor)
    control_motor_right(right_motor)
    
    return jsonify({"status": "ok"})
```

### 예시 2: 서보 모터 제어

```python
@app.route('/joystick', methods=['POST'])
def receive_joystick():
    data = request.get_json()
    angle = data.get('angle', 0)  # 0-360도
    
    # 서보 모터 각도 설정
    set_servo_angle(angle)
    
    return jsonify({"status": "ok"})
```

### 예시 3: LED 제어

```python
@app.route('/button', methods=['POST'])
def receive_button():
    data = request.get_json()
    button = data.get('button', '')
    pressed = data.get('pressed', False)
    
    if button == "A" and pressed:
        GPIO.output(18, GPIO.HIGH)  # LED 켜기
    elif button == "A" and not pressed:
        GPIO.output(18, GPIO.LOW)    # LED 끄기
    
    return jsonify({"status": "ok"})
```

---

## 🌐 네트워크 설정

### 라즈베리파이 IP 확인

```bash
hostname -I
# 또는
ifconfig
```

### 방화벽 설정 (필요한 경우)

```bash
sudo ufw allow 5000
```

### 같은 Wi-Fi 네트워크 확인

- Android 기기와 라즈베리파이가 같은 Wi-Fi에 연결되어 있어야 함
- 라즈베리파이 IP 주소를 Android 앱 설정에 입력

---

## 📊 데이터 흐름

```
[Android 앱]
    ↓ HTTP POST
    ↓ JSON 데이터
[라즈베리파이 Flask 서버]
    ↓ 데이터 파싱
    ↓ 로직 처리
[하드웨어 제어]
    (GPIO, 모터, LED 등)
```

---

## ⚠️ 주의사항

1. **보안**: 실제 배포 시에는 인증 및 보안 설정 추가 필요
2. **에러 처리**: 네트워크 오류, 하드웨어 오류 등 예외 처리 필요
3. **성능**: 조이스틱 데이터는 초당 10-30회 전송되므로 효율적인 처리 필요
4. **GPIO**: 라즈베리파이 GPIO 사용 시 적절한 권한 필요

---

## 🔍 디버깅

### 서버 로그 확인

서버 실행 시 콘솔에 실시간으로 데이터가 출력됩니다:
```
[14:30:25] [Joystick] Angle: 45°, Strength: 75%, X: 0.53, Y: 0.53
[14:30:26] [Button] A pressed at 1234567890
```

### 연결 테스트

Android 앱에서 "연결 테스트" 버튼을 누르면 `/ping` 엔드포인트가 호출됩니다.



