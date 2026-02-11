# inventory/utils/geoip_api.py
import requests

def country_for_ip(ip: str) -> str | None:
    if not ip or ip in ("127.0.0.1", "::1"):
        return "Localhost"

    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=2)
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("country_code")  # e.g. "BG"
    except Exception:
        return None
