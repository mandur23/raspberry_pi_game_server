"""
유틸리티 함수 모듈
네트워크, 포트 해석 등 유틸리티 함수들
"""

import os
import socket


def resolve_server_port(cli_port=None, default_port=8443):
    """
    CLI 인자나 환경 변수를 기반으로 사용할 포트를 결정한다.
    우선순위: CLI > GAME_SERVER_PORT > PORT > 기본값.
    """
    if cli_port is not None:
        return cli_port

    for env_var in ("GAME_SERVER_PORT", "PORT"):
        env_value = os.environ.get(env_var)
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                print(f"⚠️  환경 변수 {env_var}='{env_value}' 값이 올바른 정수가 아니어서 무시합니다.")

    return default_port


def get_local_ip():
    """로컬 네트워크 IP 주소 가져오기"""
    try:
        # 외부 서버에 연결하지 않고 로컬 IP만 가져오기
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS에 연결 시도 (실제 연결 안됨)
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # 대체 방법: 호스트 이름으로 IP 가져오기
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return "127.0.0.1"


def get_all_local_ips(use_cache=True, cache_var=None):
    """모든 로컬 네트워크 IP 주소 가져오기 (캐싱 지원)"""
    # 캐시된 값이 있으면 반환
    if use_cache and cache_var is not None and cache_var[0] is not None:
        return cache_var[0]
    
    ips = []
    try:
        hostname = socket.gethostname()
        # 모든 IP 주소 가져오기
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if ip and ip != '127.0.0.1' and not ip.startswith('::'):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    
    # 기본 방법으로도 시도
    main_ip = get_local_ip()
    if main_ip and main_ip not in ips:
        ips.insert(0, main_ip)
    
    result = ips if ips else ["127.0.0.1"]
    
    # 캐시에 저장
    if use_cache and cache_var is not None:
        cache_var[0] = result
    
    return result

