
import argparse
import threading
import time
from datetime import datetime

from game_server import app
from game_server import config
from game_server import data_processor
from game_server import keyboard_handler
from game_server import utils


def input_watchdog_loop():
    """입력 타임아웃 감시 루프"""
    while True:
        try:
            now = datetime.now()
            should_release = False

            if data_processor.stats["last_joystick_time"] is not None:
                elapsed_js = (now - data_processor.stats["last_joystick_time"]).total_seconds()
                
                if data_processor.last_joystick_state.get("is_active", False):
                    if elapsed_js > config.INACTIVITY_RELEASE_TIMEOUT:
                        target_keys = data_processor.last_joystick_state.get("active_keys", set())
                        if target_keys:
                            keyboard_handler.process_joystick_keys(target_keys)
                            if config.ENABLE_VERBOSE_LOGGING:
                                print(f"[Watchdog] 조이스틱 이전 입력 지속: {target_keys}")
                    if elapsed_js > 10.0:
                        should_release = True
                else:
                    if elapsed_js > config.INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            if data_processor.stats["last_button_time"] is not None:
                elapsed_btn = (now - data_processor.stats["last_button_time"]).total_seconds()
                if data_processor.last_button_states:
                    if elapsed_btn > config.INACTIVITY_RELEASE_TIMEOUT * 3:
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
                    if elapsed_btn > config.INACTIVITY_RELEASE_TIMEOUT:
                        should_release = True

            if should_release and keyboard_handler.pressed_keyboard_keys:
                with keyboard_handler.keyboard_lock:
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
        app.app.run(host='0.0.0.0', port=server_port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n서버 종료 중...")
        keyboard_handler.release_all_keys()
        print("모든 키 입력 해제 완료")

