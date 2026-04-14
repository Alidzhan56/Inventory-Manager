import hashlib
import hmac

from flask import current_app


def hash_ip(ip: str) -> str:
    ip = (ip or "").strip()

    if not ip:
        return ""

    secret = (current_app.config.get("IP_HASH_SECRET") or "").encode("utf-8")
    value = ip.encode("utf-8")

    return hmac.new(secret, value, hashlib.sha256).hexdigest()


def mask_ip_hash(ip_hash: str, visible: int = 12) -> str:
    ip_hash = (ip_hash or "").strip()

    if not ip_hash:
        return "-"

    if len(ip_hash) <= visible:
        return ip_hash

    return f"{ip_hash[:visible]}..."