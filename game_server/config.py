"""
설정 변수 모듈
모든 설정값을 중앙에서 관리
"""

import os
from datetime import datetime
from pynput.keyboard import Key

# 서버 기본 설정
DEFAULT_SERVER_PORT = 8443

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

# MQTT 설정
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "game_server")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", f"game_server_{os.getpid()}")
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", None)
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", None)
MQTT_ENABLED = os.environ.get("MQTT_ENABLED", "true").lower() == "true"

# MQTT 가용성 확인
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("⚠️  paho-mqtt가 설치되지 않았습니다. MQTT 기능을 사용하려면 'pip install paho-mqtt'를 실행하세요.")

