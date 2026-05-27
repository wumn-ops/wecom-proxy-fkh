"""企业微信消息加解密（基于官方算法，智能机器人 ReceiveId 为空字符串）。"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import socket
import struct
import time
from typing import Any

from Crypto.Cipher import AES


class WeComCryptoError(Exception):
    pass


class WeComCrypto:
    """智能机器人 Webhook 加解密。"""

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str = "") -> None:
        self.token = token
        self.receive_id = receive_id
        try:
            self.aes_key = base64.b64decode(encoding_aes_key + "=")
        except Exception as exc:  # noqa: BLE001
            raise WeComCryptoError("EncodingAESKey 无效") from exc
        if len(self.aes_key) != 32:
            raise WeComCryptoError("EncodingAESKey 解码后必须为 32 字节")

    def verify_url(
        self,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        echo_str: str,
    ) -> str:
        signature = self._sign(timestamp, nonce, echo_str)
        if signature != msg_signature:
            raise WeComCryptoError("URL 验证签名校验失败")
        return self._decrypt(echo_str)

    def decrypt_callback(
        self,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        post_data: str | bytes,
    ) -> dict[str, Any]:
        encrypt = self._extract_encrypt(post_data)
        signature = self._sign(timestamp, nonce, encrypt)
        if signature != msg_signature:
            raise WeComCryptoError("回调签名校验失败")
        plain = self._decrypt(encrypt)
        return json.loads(plain)

    def encrypt_reply(self, reply: dict[str, Any], nonce: str) -> dict[str, Any]:
        plain = json.dumps(reply, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time()))
        encrypt = self._encrypt(plain)
        signature = self._sign(timestamp, nonce, encrypt)
        return {
            "encrypt": encrypt,
            "msgsignature": signature,
            "timestamp": int(timestamp),
            "nonce": nonce,
        }

    def _extract_encrypt(self, post_data: str | bytes) -> str:
        if isinstance(post_data, bytes):
            post_data = post_data.decode("utf-8")
        post_data = post_data.strip()
        try:
            payload = json.loads(post_data)
            encrypt = payload.get("encrypt")
            if encrypt:
                return encrypt
        except json.JSONDecodeError:
            pass

        # 兼容 XML 包裹格式
        start = post_data.find("<Encrypt><![CDATA[")
        if start == -1:
            raise WeComCryptoError("无法从请求体中解析 encrypt 字段")
        start += len("<Encrypt><![CDATA[")
        end = post_data.find("]]></Encrypt>", start)
        if end == -1:
            raise WeComCryptoError("Encrypt 字段格式错误")
        return post_data[start:end]

    def _sign(self, timestamp: str, nonce: str, encrypt: str) -> str:
        items = sorted([self.token, timestamp, nonce, encrypt])
        return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()

    def _encrypt(self, plain: str) -> str:
        plain_bytes = plain.encode("utf-8")
        receive_id_bytes = self.receive_id.encode("utf-8")
        msg_len = struct.pack("!I", len(plain_bytes))
        rand_bytes = self._random_bytes(16)
        content = rand_bytes + msg_len + plain_bytes + receive_id_bytes
        content = self._pkcs7_pad(content)
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        return base64.b64encode(cipher.encrypt(content)).decode("utf-8")

    def decrypt_media(self, encrypted: bytes) -> bytes:
        """解密智能机器人回调中的图片/文件（AES-256-CBC + PKCS#7）。"""
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        try:
            plain = cipher.decrypt(encrypted)
        except Exception as exc:  # noqa: BLE001
            raise WeComCryptoError("媒体文件解密失败") from exc
        return self._pkcs7_unpad(plain)

    def _decrypt(self, encrypt: str) -> str:
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        try:
            plain = cipher.decrypt(base64.b64decode(encrypt))
        except Exception as exc:  # noqa: BLE001
            raise WeComCryptoError("解密失败") from exc
        plain = self._pkcs7_unpad(plain)
        msg_len = struct.unpack("!I", plain[16:20])[0]
        msg = plain[20 : 20 + msg_len].decode("utf-8")
        receive_id = plain[20 + msg_len :].decode("utf-8")
        if receive_id != self.receive_id:
            raise WeComCryptoError("ReceiveId 校验失败")
        return msg

    @staticmethod
    def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
        pad = block_size - (len(data) % block_size)
        return data + bytes([pad]) * pad

    @staticmethod
    def _pkcs7_unpad(data: bytes) -> bytes:
        pad = data[-1]
        if pad < 1 or pad > 32:
            raise WeComCryptoError("PKCS7 填充无效")
        return data[:-pad]

    @staticmethod
    def _random_bytes(size: int) -> bytes:
        return bytes(random.getrandbits(8) for _ in range(size))


def random_nonce() -> str:
    return str(random.randint(100000000, 999999999999))


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
