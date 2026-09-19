import base64
import io
import json
import os
from typing import Any, Dict, Optional

import aiohttp
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

import config
from utils.logger import logger

# Matches the backend's XOR "encryptData"/"decryptData" (api/index.ts) used to wrap
# a few legacy JSON responses. Not real encryption - just obfuscation - but the
# response of /api/buy-vip/vietqr-create is only readable through it.
# Kept out of source control: set WOLFMOD_ENC_KEY to the same literal string the
# backend's ENCRYPTION_KEY constant uses.
_ENCRYPTION_KEY = os.getenv("WOLFMOD_ENC_KEY", "")


def _decrypt_enc_field(hex_str: str) -> Any:
    if not _ENCRYPTION_KEY:
        raise RuntimeError("WOLFMOD_ENC_KEY is not configured - cannot decrypt backend response")
    chars = []
    for i in range(0, len(hex_str), 4):
        part = hex_str[i:i + 4]
        code = int(part, 16) ^ ord(_ENCRYPTION_KEY[(i // 4) % len(_ENCRYPTION_KEY)])
        chars.append(chr(code))
    return json.loads("".join(chars))


async def create_vip_invoice(plan: str) -> Optional[Dict[str, Any]]:
    """
    Creates a Plisio USDT payment invoice for a VIP key purchase via the live
    wolfmod.xyz checkout API (the same endpoint the website itself uses).
    Returns the parsed response dict (orderId, invoiceUrl, qrCode, walletAddress,
    amountUsd) on success, or None on failure.
    """
    url = f"{config.WOLFMOD_API_BASE_URL}/api/vip/purchase-usdt"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"plan": plan}, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200 and data.get("success") and data.get("invoiceUrl"):
                    return data
                logger.error("Failed to create VIP invoice (plan=%s): status=%s body=%s", plan, resp.status, data)
                return None
    except Exception as e:
        logger.error("Exception creating VIP invoice (plan=%s): %s", plan, e)
        return None


async def check_vip_order(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Checks payment status of a VIP order via the wolfmod.xyz backend.
    Returns {"status": "pending"} or {"status": "completed", "licenseKey": ...} on
    success, or None if the check itself failed (network/server error).
    """
    url = f"{config.WOLFMOD_API_BASE_URL}/api/buy-vip/plisio-check"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params={"orderId": order_id}, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200 and data.get("success"):
                    return data
                logger.error("Failed to check VIP order %s: status=%s body=%s", order_id, resp.status, data)
                return None
    except Exception as e:
        logger.error("Exception checking VIP order %s: %s", order_id, e)
        return None


async def create_vietqr_invoice(username: str, amount_vnd: int) -> Optional[Dict[str, Any]]:
    """
    Creates a Vietnamese bank-transfer (VietQR / SePay) payment order via the
    wolfmod.xyz backend. amount_vnd must be one of the backend's accepted VND
    tiers (25000 = 2-day, 150000 = 30-day, 700000 = lifetime).
    Returns the decrypted response dict (pendingId, transferCode, memo, amount,
    bankName, accountName, accountNo, qrUrl, qrBase64) on success, or None.
    """
    url = f"{config.WOLFMOD_API_BASE_URL}/api/buy-vip/vietqr-create"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"username": username, "amount": amount_vnd},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                raw = await resp.json(content_type=None)
                if resp.status != 200 or "enc" not in raw:
                    logger.error("Failed to create VietQR invoice (amount=%s): status=%s body=%s", amount_vnd, resp.status, raw)
                    return None
                data = _decrypt_enc_field(raw["enc"])
                if data.get("success") and data.get("qrUrl"):
                    return data
                logger.error("Unexpected VietQR invoice payload (amount=%s): %s", amount_vnd, data)
                return None
    except Exception as e:
        logger.error("Exception creating VietQR invoice (amount=%s): %s", amount_vnd, e)
        return None


async def check_vietqr_order(pending_id: str, transfer_code: str) -> Optional[Dict[str, Any]]:
    """
    Checks payment status of a VietQR/SePay order via the wolfmod.xyz backend
    (guest mode: pendingId + transferCode together act as the bearer secret).
    Returns {"status": "pending"|"confirmed"|"expired", "licenseKey": ...} on
    success, or None if the check itself failed.
    """
    url = f"{config.WOLFMOD_API_BASE_URL}/api/buy-vip/vietqr-check"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params={"pendingId": pending_id, "transferCode": transfer_code},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200 and data.get("success"):
                    return data
                logger.error("Failed to check VietQR order %s: status=%s body=%s", pending_id, resp.status, data)
                return None
    except Exception as e:
        logger.error("Exception checking VietQR order %s: %s", pending_id, e)
        return None


def get_qr_image_bytes(qr_code_field: Optional[str], invoice_url: str) -> io.BytesIO:
    """
    Returns a PNG image (as BytesIO) for the payment QR code. Uses Plisio's own
    rendered QR (base64, only present with a "white-label" Plisio account) when
    available; otherwise generates a QR code locally from the real invoice_url.
    Never fabricates/guesses a payment address - only encodes the literal
    invoice_url returned by the backend.
    """
    if qr_code_field:
        try:
            b64_data = qr_code_field.split(",", 1)[1] if "," in qr_code_field else qr_code_field
            return io.BytesIO(base64.b64decode(b64_data))
        except Exception as e:
            logger.warning("Failed to decode Plisio-provided QR code, generating locally instead: %s", e)

    # Locally-generated fallback (used whenever Plisio doesn't hand back its own
    # rendered QR) — bigger modules + more quiet zone + rounded dots instead of
    # qrcode.make()'s tiny default squares, so it's easy to scan and doesn't
    # look like a placeholder next to the rest of the bot's VIP messaging.
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=14,
        border=3,
    )
    qr.add_data(invoice_url)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        fill_color="black",
        back_color="white",
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
