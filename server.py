"""
서버 메인 실행 모듈
서버 시작 및 백그라운드 스레드 관리
"""

import argparse
import threading
import time
from datetime import datetime

from game_server import app
from game_server import config
from game_server import data_processor
from game_server import keyboard_handler
from game_server import mqtt_client
from game_server import utils


def input_watchdog_loop():
    """
    조이스틱/버튼 입력이 일정 시간 동안 안 들어오면
    자동으로 모든 키를 떼는 감시 루프.
    안드로이드에서 데이터가 같으면 전송하지 않는 문제를 고려하여 개선됨.
    조이스틱이 활성 상태일 때는 이전 입력을 지속합니다.
    """
    while True:
        try:
            now = datetime.now()
            should_release = False

            # 조이스틱 입력 타임아웃 체크
            if data_processor.stats["last_joystick_time"] is not None:
                elapsed_js = (now - data_processor.stats["last_joystick_time"]).total_seconds()
                
                # 조이스틱이 활성 상태일 때는 이전 입력을 지속
                if data_processor.last_joystick_state.get("is_active", False):
                    # 조이스틱이 활성 상태이면 마지막 상태를 유지하기 위해 주기적으로 다시 적용
                    # INACTIVITY_RELEASE_TIMEOUT 이후부터 주기적으로 상태 유지
                    if elapsed_js > config.INACTIVITY_RELEASE_TIMEOUT:
                        # 마지막 조이스틱 상태를 다시 적용하여 키 유지
                        target_keys = data_processor.last_joystick_state.get("active_keys", set())
                        if target_keys:
                            keyboard_handler.process_joystick_keys(target_keys)
                            if config.ENABLE_VERBOSE_LOGGING:
                                print(f"[Watchdog] 조이스틱 이전 입력 지속: {target_keys}")
                    # 매우 긴 타임아웃(10초)이 지나면 해제 (연결 끊김으로 간주)
                    if elapsed_js > 10.0:
                        should_release = True
                else:
                    # 조이스틱이 중앙 상태였으면 타임아웃 후 해제
                    if elapsed_js > config.INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            # 버튼 입력 타임아웃 체크 (안드로이드 데이터 전송 특성 고려)
            if data_processor.stats["last_button_time"] is not None:
                elapsed_btn = (now - data_processor.stats["last_button_time"]).total_seconds()
                # 버튼이 눌린 상태였으면 더 긴 타임아웃 적용 (안드로이드에서 같은 데이터를 보내지 않아도 유지)
                if data_processor.last_button_states:
                    # 눌린 버튼이 있으면 더 긴 타임아웃 (1.5초)
                    if elapsed_btn > config.INACTIVITY_RELEASE_TIMEOUT * 3:
                        # 버튼 키 해제
                        with keyboard_handler.keyboard_lock:
                            for button_name, btn_state in list(data_processor.last_button_states.items()):
                                if btn_state["pressed"]:
                                    try:
                                        keyboard_handler.keyboard.release(btn_state["key"])
                                        keyboard_handler.pressed_keyboard_keys.discard(btn_state["key"])
                                        keyboard_handler.pressed_keys.discard(button_name)
                                    except Exception as e:
                                        if config.ENABLE_VERBOSE_LOGGING:
                                            print(f"Error releasing button key {button_name}: {e}")
                                    del data_processor.last_button_states[button_name]
                else:
                    # 눌린 버튼이 없으면 일반 타임아웃
                    if elapsed_btn > config.INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            # 일정 시간 동안 입력이 없는데 아직 키가 눌려있으면 해제
            # 단, 조이스틱이 활성 상태였고 타임아웃이 짧으면 유지 (안드로이드 데이터 전송 특성 고려)
            if should_release and keyboard_handler.pressed_keyboard_keys:
                # 조이스틱 방향 키만 선택적으로 해제 (버튼 키는 제외)
                with keyboard_handler.keyboard_lock:
                    # 버튼 키는 제외하고 조이스틱 키만 해제
                    button_keys = {btn_state["key"] for btn_state in data_processor.last_button_states.values() if btn_state["pressed"]}
                    keys_to_release = list((keyboard_handler.pressed_keyboard_keys & config.JOYSTICK_KEY_SET) - button_keys)
                    for key in keys_to_release:
                        try:
                            keyboard_handler.keyboard.release(key)
                            keyboard_handler.pressed_keyboard_keys.discard(key)
                        except Exception as e:
                            if config.ENABLE_VERBOSE_LOGGING:
                                print(f"Error releasing key {key}: {e}")

        except Exception as e:
            if config.ENABLE_VERBOSE_LOGGING:
                print(f"Error in input watchdog loop: {e}")

        # 너무 자주 돌지 않도록 약간 딜레이
        time.sleep(0.05)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="라즈베리파이 게임 컨트롤러 Flask 서버")
    parser.add_argument(
        "--port",
        type=int,
        help=f"서버가 사용할 포트 번호 (기본 {config.DEFAULT_SERVER_PORT}, 환경 변수로도 설정 가능)"
    )
    args = parser.parse_args()

    server_port = utils.resolve_server_port(args.port, config.DEFAULT_SERVER_PORT)
    app.app.config["SERVER_PORT"] = server_port

    # 로컬 IP 주소 가져오기
    cached_server_ips = [None]
    local_ips = utils.get_all_local_ips(use_cache=True, cache_var=cached_server_ips)
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
    print("MQTT 설정:")
    if config.MQTT_ENABLED and config.MQTT_AVAILABLE:
        print(f"  브로커: {config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT}")
        print(f"  토픽 접두사: {config.MQTT_TOPIC_PREFIX}")
        print(f"  발행 토픽: {config.MQTT_TOPIC_PREFIX}/status")
        print(f"  구독 토픽: {config.MQTT_TOPIC_PREFIX}/joystick, {config.MQTT_TOPIC_PREFIX}/button")
    else:
        print("  MQTT: 비활성화됨")
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

    # 입력 감시 쓰레드 시작 (조이스틱/버튼 데이터가 끊기면 자동으로 키 해제)
    watchdog_thread = threading.Thread(target=input_watchdog_loop, daemon=True)
    watchdog_thread.start()
    
    # MQTT 클라이언트 초기화
    if mqtt_client.init_mqtt_client(cached_server_ips):
        # MQTT 상태 발행 루프 시작
        mqtt_status_thread = threading.Thread(target=mqtt_client.mqtt_status_publisher_loop, args=(cached_server_ips,), daemon=True)
        mqtt_status_thread.start()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [MQTT] 상태 발행 루프 시작됨")

    try:
        # 최적화된 서버 설정 (끊김 방지)
        app.app.run(host='0.0.0.0', port=server_port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n서버 종료 중...")
        keyboard_handler.release_all_keys()
        # MQTT 연결 종료
        if mqtt_client.mqtt_client:
            mqtt_client.mqtt_client.loop_stop()
            mqtt_client.mqtt_client.disconnect()
        print("모든 키 입력 해제 완료")

