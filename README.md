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

## 코드 구조 설명

### server.py (메인 실행 파일)

- **1-11줄**: 모듈 import 및 패키지 import
  - **이유**: 필요한 라이브러리와 모듈을 가져와서 사용하기 위함
  
- **14-72줄**: `input_watchdog_loop()` 함수 - 입력 타임아웃 감시 루프
  - **이유**: 조이스틱/버튼 입력이 일정 시간 없으면 자동으로 키를 해제하여 키가 계속 눌려있는 문제 방지. 안드로이드에서 데이터가 같으면 전송하지 않는 특성을 고려하여 구현
  
- **75-82줄**: CLI 인자 파싱 (`--port` 옵션 처리)
  - **이유**: 사용자가 명령줄에서 포트를 지정할 수 있도록 하여 유연성 제공
  
- **84-89줄**: 서버 포트 설정 및 IP 주소 가져오기
  - **이유**: 서버가 실행될 IP 주소를 미리 확인하여 접속 정보를 출력하기 위함
  
- **91-142줄**: 서버 시작 정보 출력
  - **이유**: 사용자가 서버에 접속할 수 있는 주소와 사용 가능한 엔드포인트를 쉽게 확인할 수 있도록 하기 위함
  
- **144-145줄**: 입력 감시 스레드 시작
  - **이유**: 백그라운드에서 지속적으로 입력 상태를 모니터링하기 위해 별도 스레드로 실행
  
- **147-152줄**: Flask 서버 실행 및 종료 처리
  - **이유**: 서버를 시작하고 종료 시 모든 키를 해제하여 안전하게 종료하기 위함

### game_server/app.py (Flask 애플리케이션)

- **11-21줄**: 모듈 import 및 Flask 앱 초기화 (템플릿 폴더 경로 설정)
  - **이유**: Flask 앱을 초기화하고 템플릿 폴더 경로를 명시적으로 지정하여 패키지 구조에서도 템플릿을 찾을 수 있도록 함
  
- **30-43줄**: `update_user_activity()` - 접속자 활동 정보 업데이트
  - **이유**: 접속한 사용자의 IP와 활동 시간을 추적하여 대시보드에 표시하기 위함
  
- **46-58줄**: `cleanup_inactive_users()` - 비활성 접속자 정리
  - **이유**: 오래된 접속자 정보를 정리하여 메모리 사용량을 최적화하기 위함
  
- **61-81줄**: `@app.route('/')` - 대시보드 HTML 페이지
  - **이유**: 웹 브라우저로 접속했을 때 서버 상태와 접속 정보를 볼 수 있는 대시보드 제공
  
- **84-110줄**: `@app.route('/users')` - 접속자 목록 JSON 반환
  - **이유**: API를 통해 접속자 정보를 JSON 형식으로 제공하여 다른 애플리케이션에서 활용 가능하도록 함
  
- **113-121줄**: `@app.route('/ping')` - 서버 연결 테스트
  - **이유**: 서버가 정상적으로 실행 중인지 간단히 확인할 수 있는 엔드포인트 제공
  
- **124-175줄**: `@app.route('/status')` - 서버 상태 및 통계 확인
  - **이유**: 서버의 현재 상태, 데이터 수신 통계, 최근 수신 데이터를 확인할 수 있도록 함
  
- **178-229줄**: `@app.route('/joystick')` - 조이스틱 데이터 수신 엔드포인트
  - **이유**: HTTP POST 요청으로 조이스틱 데이터를 받아서 키보드 입력으로 변환하기 위함
  
- **232-276줄**: `@app.route('/button')` - 버튼 데이터 수신 엔드포인트
  - **이유**: HTTP POST 요청으로 버튼 데이터를 받아서 키보드 입력으로 변환하기 위함
  
- **279-283줄**: `@app.route('/stop')` - 모든 키 입력 중지
  - **이유**: 긴급 상황이나 테스트 시 모든 키를 즉시 해제할 수 있도록 함
  
- **286-314줄**: `@app.route('/reset')` - 모든 상태 초기화
  - **이유**: 게임 재시작 시 모든 상태를 초기화하여 깨끗한 상태로 시작할 수 있도록 함

### game_server/config.py (설정 변수)

- **11줄**: `DEFAULT_SERVER_PORT` - 기본 서버 포트 (8443)
  - **이유**: 서버의 기본 포트를 중앙에서 관리하여 변경 시 한 곳만 수정하면 되도록 함
  
- **14-26줄**: `KEY_MAPPING` - 조이스틱/버튼을 키보드 키로 매핑하는 딕셔너리
  - **이유**: 게임 컨트롤러 입력을 키보드 키로 변환하기 위한 매핑 테이블. 게임에 맞게 쉽게 변경 가능하도록 중앙 관리
  
- **29줄**: `JOYSTICK_KEY_SET` - 조이스틱 방향 키 세트
  - **이유**: 조이스틱 키와 버튼 키를 구분하여 처리하기 위함. 성능 최적화를 위해 반복 생성 방지
  
- **32-37줄**: 조이스틱 임계값 설정 (히스테리시스 적용)
  - **이유**: 조이스틱의 떨림을 방지하기 위해 키를 누르기 시작하는 임계값과 떼는 임계값을 다르게 설정
  
- **42줄**: `INACTIVITY_RELEASE_TIMEOUT` - 입력 정지 타임아웃 (0.5초)
  - **이유**: 입력이 일정 시간 없으면 자동으로 키를 해제하여 키가 계속 눌려있는 문제 방지
  
- **45줄**: `ENABLE_VERBOSE_LOGGING` - 상세 로그 출력 여부
  - **이유**: 디버깅 시 상세한 로그가 필요할 때만 활성화하여 성능에 영향을 주지 않도록 함
  
- **48줄**: `USER_CLEANUP_TIMEOUT` - 비활성 접속자 정리 타임아웃 (3600초)
  - **이유**: 오래된 접속자 정보를 정리하여 메모리 사용량을 최적화하기 위함

### game_server/data_processor.py (데이터 처리)

- **13-19줄**: `stats` - 데이터 수신 통계 딕셔너리
  - **이유**: 조이스틱/버튼 데이터 수신 횟수와 마지막 수신 시간을 추적하여 서버 상태 확인에 사용
  
- **22-25줄**: `recent_data` - 최근 수신된 데이터 저장
  - **이유**: 대시보드에서 최근 수신된 데이터를 표시하기 위함
  
- **28-34줄**: `last_joystick_state` - 마지막 조이스틱 상태 저장
  - **이유**: 안드로이드에서 데이터가 같으면 전송하지 않는 문제를 해결하기 위해 마지막 상태를 저장하고, 히스테리시스 적용을 위해 이전 상태 참조
  
- **37줄**: `last_button_states` - 마지막 버튼 상태 저장
  - **이유**: 버튼 상태 변경을 감지하고 중복 처리 방지를 위함
  
- **40-50줄**: `calculate_joystick_keys()` - 조이스틱 입력값을 키 매핑으로 변환 (히스테리시스 적용)
  - **이유**: 조이스틱의 x, y 좌표를 방향 키로 변환하되, 떨림 방지를 위해 히스테리시스 알고리즘 적용
  
- **이후**: `process_joystick_data_internal()`, `process_button_data_internal()` - 조이스틱/버튼 데이터 처리 함수
  - **이유**: HTTP와 MQTT에서 받은 데이터를 공통으로 처리하기 위한 내부 함수. 데이터 검증, 통계 업데이트, 키 입력 처리 수행

### game_server/keyboard_handler.py (키보드 처리)

- **15줄**: `keyboard` - pynput 키보드 컨트롤러 객체
  - **이유**: 실제 키보드 입력을 시뮬레이션하기 위한 pynput 라이브러리의 Controller 객체
  
- **18줄**: `keyboard_lock` - 키 입력 동기화를 위한 Lock
  - **이유**: 여러 스레드에서 동시에 키 입력을 처리할 때 충돌을 방지하기 위한 동기화 메커니즘
  
- **21-24줄**: 키 상태 추적 변수들 (`pressed_keys`, `pressed_keyboard_keys` 등)
  - **이유**: 현재 눌려있는 키를 추적하여 중복 입력 방지, 조이스틱과 버튼의 키 간섭 방지
  
- **27-39줄**: `press_key()` - 키보드 키 누르기 함수
  - **이유**: 키를 안전하게 누르기 위한 래퍼 함수. 동기화 처리 및 중복 방지 로직 포함
  
- **42-54줄**: `release_key()` - 키보드 키 떼기 함수
  - **이유**: 키를 안전하게 떼기 위한 래퍼 함수. 동기화 처리 및 상태 추적 업데이트 포함
  
- **57-75줄**: `release_all_keys()` - 모든 키보드 키 떼기 함수
  - **이유**: 긴급 상황이나 서버 종료 시 모든 키를 확실하게 해제하기 위함
  
- **이후**: `process_joystick_keys()` - 조이스틱 키 입력 처리 함수
  - **이유**: 조이스틱으로 눌려야 하는 키와 현재 눌려있는 키를 비교하여 필요한 키만 누르고 뗌. 버튼과의 간섭 방지 로직 포함

### game_server/utils.py (유틸리티)

- **10-26줄**: `resolve_server_port()` - CLI 인자/환경 변수로 포트 결정
  - **이유**: 포트 설정의 우선순위를 명확히 하여 CLI > 환경변수 > 기본값 순으로 결정. 유연한 설정 제공
  
- **29-45줄**: `get_local_ip()` - 로컬 네트워크 IP 주소 가져오기
  - **이유**: 외부 서버에 연결하지 않고 로컬 IP만 가져오기 위해 Google DNS에 연결 시도. 실패 시 호스트 이름으로 대체
  
- **48-77줄**: `get_all_local_ips()` - 모든 로컬 네트워크 IP 주소 가져오기 (캐싱 지원)
  - **이유**: 여러 네트워크 인터페이스가 있을 때 모든 IP를 가져와서 표시. 캐싱을 통해 성능 최적화

### raspberry_pi_game_server.py (단일 파일 버전)

- **14-17줄**: Flask 앱 초기화 및 포트 설정
  - **이유**: 단일 파일로 모든 기능을 포함한 독립 실행 가능한 서버
  
- **19-25줄**: 키보드 컨트롤러 및 키 상태 추적 변수 초기화
  - **이유**: 키 입력 시뮬레이션과 상태 관리를 위한 전역 변수 초기화
  
- **27-38줄**: 통계 및 상태 저장 변수 초기화
  - **이유**: 데이터 수신 통계와 최근 데이터를 저장하기 위한 변수 초기화
  
- **56-65줄**: 키 매핑 설정 (`KEY_MAPPING`)
  - **이유**: 게임 컨트롤러 입력을 키보드 키로 변환하기 위한 매핑 테이블
  
- **69-77줄**: 조이스틱 임계값 및 타임아웃 설정
  - **이유**: 조이스틱 입력의 민감도와 자동 해제 시간 설정
  
- **80-92줄**: `resolve_server_port()` - 포트 해석 함수
  - **이유**: CLI 인자와 환경 변수로부터 포트를 결정하는 함수
  
- **94-100줄**: `get_local_ip()` - 로컬 IP 가져오기
  - **이유**: 서버의 로컬 네트워크 IP 주소를 가져오는 함수
  
- **152-183줄**: `get_all_local_ips()` - 모든 로컬 IP 가져오기
  - **이유**: 모든 네트워크 인터페이스의 IP 주소를 가져오는 함수
  
- **217-237줄**: `@app.route('/')` - 대시보드 라우트
  - **이유**: 웹 브라우저 접속 시 대시보드 HTML 페이지 제공
  
- **269-328줄**: `@app.route('/status')` - 상태 확인 라우트
  - **이유**: 서버 상태와 통계를 JSON으로 반환하는 API 엔드포인트
  
- **330-409줄**: `calculate_joystick_keys()` - 조이스틱 키 계산 함수
  - **이유**: 조이스틱 좌표를 방향 키로 변환하는 함수 (히스테리시스 적용)
  
- **412-482줄**: `process_joystick_keys()` - 조이스틱 키 처리 함수
  - **이유**: 계산된 키를 실제로 누르고 떼는 함수. 버튼과의 간섭 방지
  
- **485-564줄**: `process_joystick_data_internal()` - 조이스틱 데이터 처리 함수
  - **이유**: HTTP/MQTT에서 받은 조이스틱 데이터를 처리하는 공통 함수
  
- **567-726줄**: `process_button_data_internal()` - 버튼 데이터 처리 함수
  - **이유**: HTTP/MQTT에서 받은 버튼 데이터를 처리하는 공통 함수
  
- **729-783줄**: `@app.route('/joystick')` - 조이스틱 엔드포인트
  - **이유**: HTTP POST로 조이스틱 데이터를 받는 엔드포인트
  
- **785-832줄**: `@app.route('/button')` - 버튼 엔드포인트
  - **이유**: HTTP POST로 버튼 데이터를 받는 엔드포인트
  
- **966-1046줄**: `input_watchdog_loop()` - 입력 감시 루프
  - **이유**: 입력이 일정 시간 없으면 자동으로 키를 해제하는 백그라운드 루프
  
- **1049-1128줄**: `if __name__ == '__main__'` - 메인 실행 코드
  - **이유**: 스크립트가 직접 실행될 때 서버를 시작하는 코드

## 라이선스

이 프로젝트는 자유롭게 사용할 수 있습니다.

