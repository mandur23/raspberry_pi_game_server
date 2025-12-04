"""
MQTT 클라이언트 모듈
MQTT 브로커와의 통신 처리
"""

import json
import threading
import time
from datetime import datetime

from . import config
from . import data_processor
from . import utils

# MQTT 클라이언트 (초기화는 나중에)
mqtt_client = None
mqtt_connected = False
mqtt_lock = threading.Lock()


def on_mqtt_connect(client, userdata, flags, rc):
    """MQTT 연결 콜백"""
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ✓ 브로커에 연결되었습니다 ({config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT})")
        
        # 토픽 구독
        joystick_topic = f"{config.MQTT_TOPIC_PREFIX}/joystick"
        button_topic = f"{config.MQTT_TOPIC_PREFIX}/button"
        status_topic = f"{config.MQTT_TOPIC_PREFIX}/status"
        
        client.subscribe(joystick_topic)
        client.subscribe(button_topic)
        client.subscribe(status_topic)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] 토픽 구독: {joystick_topic}, {button_topic}, {status_topic}")
        
        # 연결 성공 메시지 발행
        publish_mqtt_status({"status": "connected", "message": "MQTT 연결 성공"})
    else:
        mqtt_connected = False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 연결 실패: 코드 {rc}")


def on_mqtt_disconnect(client, userdata, rc):
    """MQTT 연결 끊김 콜백"""
    global mqtt_connected
    mqtt_connected = False
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 브로커 연결이 끊어졌습니다")


def on_mqtt_message(client, userdata, msg):
    """MQTT 메시지 수신 콜백"""
    try:
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # JSON 파싱
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 잘못된 JSON 형식: {payload}")
            return
        
        # 토픽에 따라 처리
        if topic.endswith("/joystick"):
            data_processor.process_joystick_data_internal(data, source="MQTT")
        elif topic.endswith("/button"):
            data_processor.process_button_data_internal(data, source="MQTT")
        elif topic.endswith("/status"):
            # 상태 요청에 응답 (MQTT 상태 발행 루프와 동일한 방식으로 처리)
            pass  # 상태는 주기적으로 자동 발행되므로 여기서는 처리하지 않음
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 메시지 처리 에러: {e}")
        import traceback
        if config.ENABLE_VERBOSE_LOGGING:
            traceback.print_exc()


def publish_mqtt_status(status_data):
    """서버 상태를 MQTT로 발행"""
    if not config.MQTT_AVAILABLE or not config.MQTT_ENABLED:
        return
    
    if mqtt_client is None or not mqtt_connected:
        return
    
    try:
        topic = f"{config.MQTT_TOPIC_PREFIX}/status"
        payload = json.dumps(status_data, ensure_ascii=False)
        mqtt_client.publish(topic, payload, qos=1, retain=False)
    except Exception as e:
        if config.ENABLE_VERBOSE_LOGGING:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 상태 발행 에러: {e}")


def init_mqtt_client(cached_server_ips):
    """MQTT 클라이언트 초기화 및 연결"""
    global mqtt_client, mqtt_connected
    
    if not config.MQTT_AVAILABLE:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ paho-mqtt가 설치되지 않아 MQTT 기능을 사용할 수 없습니다")
        return False
    
    if not config.MQTT_ENABLED:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ℹ️ MQTT가 비활성화되어 있습니다 (MQTT_ENABLED=false)")
        return False
    
    try:
        import paho.mqtt.client as mqtt
        
        # MQTT 클라이언트 생성
        mqtt_client = mqtt.Client(client_id=config.MQTT_CLIENT_ID)
        
        # 인증 설정
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            mqtt_client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        
        # 콜백 설정
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect
        mqtt_client.on_message = on_mqtt_message
        
        # 연결 시도
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] 브로커에 연결 중... ({config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT})")
        
        try:
            mqtt_client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, keepalive=60)
            mqtt_client.loop_start()  # 백그라운드 스레드에서 루프 실행
            
            # 연결 확인을 위해 잠시 대기
            time.sleep(1)
            
            if mqtt_connected:
                return True
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 브로커 연결 실패 (mosquitto가 실행 중인지 확인하세요)")
                return False
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 브로커 연결 에러: {e}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] 💡 mosquitto 브로커가 실행 중인지 확인하세요")
            return False
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] ⚠️ 초기화 에러: {e}")
        return False


def mqtt_status_publisher_loop(cached_server_ips):
    """주기적으로 서버 상태를 MQTT로 발행하는 루프"""
    while True:
        try:
            if mqtt_connected:
                # 서버 상태 가져오기 (Flask 컨텍스트 없이 직접 데이터 구성)
                now = datetime.now()
                
                # 마지막 수신으로부터 경과 시간 계산
                joystick_elapsed = None
                button_elapsed = None
                
                if data_processor.stats["last_joystick_time"]:
                    joystick_elapsed = (now - data_processor.stats["last_joystick_time"]).total_seconds()
                
                if data_processor.stats["last_button_time"]:
                    button_elapsed = (now - data_processor.stats["last_button_time"]).total_seconds()
                
                joystick_active = joystick_elapsed is not None and joystick_elapsed < 5.0
                button_active = button_elapsed is not None and button_elapsed < 5.0
                
                server_ips = utils.get_all_local_ips(use_cache=True, cache_var=cached_server_ips)
                
                status_data = {
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
                    },
                    "mqtt_connected": mqtt_connected
                }
                
                publish_mqtt_status(status_data)
        except Exception as e:
            if config.ENABLE_VERBOSE_LOGGING:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] 상태 발행 루프 에러: {e}")
        
        # 5초마다 상태 발행
        time.sleep(5)

