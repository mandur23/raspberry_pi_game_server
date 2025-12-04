# 라즈베리파이 게임 서버

게임 컨트롤러 입력을 키보드 입력으로 변환하여 게임에 전달하는 Flask 서버입니다. HTTP와 MQTT 프로토콜을 모두 지원합니다.

## 기능

- 🔌 **HTTP API**: RESTful API를 통해 조이스틱/버튼 데이터 수신
- 📡 **MQTT 지원**: mosquitto 브로커를 통한 실시간 데이터 통신
- 🎮 **키보드 입력 변환**: 조이스틱 및 버튼 입력을 키보드 키로 변환
- 📊 **실시간 대시보드**: 웹 기반 모니터링 대시보드
- 📈 **통계 추적**: 조이스틱/버튼 입력 통계 및 접속자 정보

## 설치

### 1. 필수 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. MQTT 브로커 설치 (선택사항)

**Windows:**
- [mosquitto Windows 설치](https://mosquitto.org/download/)
- 또는 WSL을 사용하여 Linux 버전 설치

**Linux:**
```bash
sudo apt-get update
sudo apt-get install mosquitto mosquitto-clients
```

**macOS:**
```bash
brew install mosquitto
```

### 3. mosquitto 실행

```bash
# Linux/macOS
mosquitto -c /etc/mosquitto/mosquitto.conf

# Windows (설치 경로에 따라 다름)
mosquitto.exe
```

## 사용 방법

### 기본 실행

```bash
python server.py
```

또는 기존 파일 사용:

```bash
python raspberry_pi_game_server.py
```

### 포트 변경

```bash
python server.py --port 8080
```

또는 환경 변수 사용:

```bash
export GAME_SERVER_PORT=8080
python raspberry_pi_game_server.py
```

### MQTT 설정

환경 변수를 통해 MQTT 설정:

```bash
# MQTT 브로커 주소 및 포트
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883

# 토픽 접두사
export MQTT_TOPIC_PREFIX=game_server

# 인증 (선택사항)
export MQTT_USERNAME=your_username
export MQTT_PASSWORD=your_password

# MQTT 활성화/비활성화
export MQTT_ENABLED=true
```

### 서버 실행

서버가 실행되면 다음과 같은 정보가 표시됩니다:

```
============================================================
게임 컨트롤러 Flask 서버 - 키 입력 버전
============================================================
서버 시작됨!
============================================================
📡 접속 주소:
  로컬 접속:
    http://localhost:8443
    http://127.0.0.1:8443

  내부망 접속 (같은 Wi-Fi/네트워크):
    http://192.168.1.100:8443
============================================================
```

## API 엔드포인트

### HTTP API

#### 조이스틱 데이터 전송
```http
POST /joystick
Content-Type: application/json

{
  "x": 0.5,
  "y": 0.5,
  "strength": 75,
  "reset": false
}
```

#### 버튼 데이터 전송
```http
POST /button
Content-Type: application/json

{
  "button": "A",
  "pressed": true
}
```

#### 서버 상태 확인
```http
GET /status
```

#### 대시보드
```http
GET /
```

### MQTT 토픽

#### 발행 (Subscribe)
- `{MQTT_TOPIC_PREFIX}/status`: 서버 상태 정보 (5초마다 자동 발행)

#### 구독 (Publish)
- `{MQTT_TOPIC_PREFIX}/joystick`: 조이스틱 데이터 수신
- `{MQTT_TOPIC_PREFIX}/button`: 버튼 데이터 수신

#### MQTT 메시지 형식

**조이스틱:**
```json
{
  "x": 0.5,
  "y": 0.5,
  "strength": 75,
  "reset": false
}
```

**버튼:**
```json
{
  "button": "A",
  "pressed": true
}
```

## 예제: MQTT를 통한 데이터 전송

### mosquitto_pub를 사용한 조이스틱 데이터 전송

```bash
mosquitto_pub -h localhost -t game_server/joystick -m '{"x": 0.5, "y": 0.5, "strength": 75}'
```

### mosquitto_pub를 사용한 버튼 데이터 전송

```bash
mosquitto_pub -h localhost -t game_server/button -m '{"button": "A", "pressed": true}'
```

### 서버 상태 확인

```bash
mosquitto_sub -h localhost -t game_server/status
```

## 키 매핑

### 조이스틱
- 위 → ↑ (또는 W)
- 아래 → ↓ (또는 S)
- 왼쪽 → ← (또는 A)
- 오른쪽 → → (또는 D)

### 버튼
- A → Space (점프)
- B → Enter (달리기/공격)
- X → 1 (게임 시작)
- Y → (미할당)

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `GAME_SERVER_PORT` | 서버 포트 | 8443 |
| `MQTT_BROKER_HOST` | MQTT 브로커 주소 | localhost |
| `MQTT_BROKER_PORT` | MQTT 브로커 포트 | 1883 |
| `MQTT_TOPIC_PREFIX` | MQTT 토픽 접두사 | game_server |
| `MQTT_CLIENT_ID` | MQTT 클라이언트 ID | game_server_{PID} |
| `MQTT_USERNAME` | MQTT 사용자명 | 없음 |
| `MQTT_PASSWORD` | MQTT 비밀번호 | 없음 |
| `MQTT_ENABLED` | MQTT 활성화 여부 | true |

## 주의사항

1. **관리자 권한**: Linux에서 키보드 입력 시뮬레이션은 관리자 권한이 필요할 수 있습니다.
2. **게임 창 포커스**: 게임 창이 포커스되어 있어야 키 입력이 전달됩니다.
3. **MQTT 브로커**: MQTT 기능을 사용하려면 mosquitto 브로커가 실행 중이어야 합니다.
4. **방화벽**: 다른 기기에서 접속하려면 방화벽에서 포트를 열어야 합니다.

## 프로젝트 구조

코드는 모듈화되어 다음과 같이 구성되어 있습니다:

```
raspberry_pi_game_server/
├── server.py                      # 메인 실행 파일 (서버 시작)
├── game_server/                   # 메인 패키지
│   ├── __init__.py
│   ├── app.py                     # Flask 애플리케이션 및 API 라우트
│   ├── config.py                  # 설정 변수 (키 매핑, MQTT 설정 등)
│   ├── keyboard_handler.py        # 키보드 입력 처리
│   ├── data_processor.py          # 조이스틱/버튼 데이터 처리
│   ├── mqtt_client.py             # MQTT 클라이언트
│   └── utils.py                   # 유틸리티 함수 (IP 주소, 포트 해석)
├── templates/
│   └── dashboard.html             # 웹 대시보드 템플릿
├── requirements.txt               # Python 패키지 의존성
├── README.md                      # 이 파일
└── raspberry_pi_game_server.py    # 기존 단일 파일 (하위 호환성)
```

### 모듈 설명

- **server.py**: 서버 시작, 백그라운드 스레드 관리, 입력 감시 루프
- **app.py**: Flask 웹 서버, HTTP API 엔드포인트, 접속자 관리
- **config.py**: 모든 설정값 중앙 관리 (키 매핑, MQTT 설정, 임계값 등)
- **keyboard_handler.py**: 키보드 입력 시뮬레이션, 키 상태 추적
- **data_processor.py**: 조이스틱/버튼 데이터 처리 로직, 통계 관리
- **mqtt_client.py**: MQTT 브로커 연결, 메시지 구독/발행
- **utils.py**: 네트워크 유틸리티 (IP 주소 가져오기, 포트 해석)

## 라이선스

이 프로젝트는 자유롭게 사용할 수 있습니다.

