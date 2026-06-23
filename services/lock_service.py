"""本机应用锁：使用 PBKDF2 保存不可逆密码摘要。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path


PBKDF2_ITERATIONS = 310_000


class LockService:
    def __init__(self, config_path: str | Path) -> None:
        self.path = Path(config_path).expanduser().resolve()

    def is_enabled(self) -> bool:
        return self.path.is_file()

    @staticmethod
    def _derive(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )

    def set_password(self, password: str) -> None:
        if len(password) < 6:
            raise ValueError("密码至少需要 6 个字符。")
        salt = os.urandom(16)
        digest = self._derive(password, salt)
        payload = {
            "version": 1,
            "iterations": PBKDF2_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
            "digest": base64.b64encode(digest).decode("ascii"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(self.path)

    def verify(self, password: str) -> bool:
        if not self.is_enabled():
            return True
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            salt = base64.b64decode(payload["salt"])
            expected = base64.b64decode(payload["digest"])
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return hmac.compare_digest(self._derive(password, salt), expected)

    def disable(self, password: str) -> None:
        if not self.verify(password):
            raise ValueError("当前密码不正确。")
        self.path.unlink(missing_ok=True)

    def change_password(self, current_password: str, new_password: str) -> None:
        if not self.verify(current_password):
            raise ValueError("当前密码不正确。")
        self.set_password(new_password)
