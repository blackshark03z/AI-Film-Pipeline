import re
import time
import urllib.parse
import urllib.request
import json
from typing import Any, Dict, List, Optional, Set

class TempMailClient:
    """Client giao tiếp với API công khai của tempmail.plus để tự động lấy mã OTP / liên kết xác nhận."""
    BASE_URL = "https://tempmail.plus/api"

    @staticmethod
    def get_inbox(email: str, epin: Optional[str] = None) -> Dict[str, Any]:
        """Lấy danh sách thư trong hộp thư tempmail.plus."""
        email_clean = email.strip()
        params = {"email": email_clean}
        if epin:
            params["epin"] = epin.strip()

        url = f"{TempMailClient.BASE_URL}/mails?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as e:
            return {"result": False, "error": str(e), "mails": []}

    @staticmethod
    def get_mail_detail(email: str, mail_id: str, epin: Optional[str] = None) -> Dict[str, Any]:
        """Lấy nội dung chi tiết của một bức thư theo mail_id."""
        email_clean = email.strip()
        params = {"email": email_clean}
        if epin:
            params["epin"] = epin.strip()

        url = f"{TempMailClient.BASE_URL}/mails/{mail_id}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as e:
            return {"result": False, "error": str(e)}

    @classmethod
    def snapshot_seen_ids(cls, email: str, epin: Optional[str] = None) -> Set[str]:
        """Chụp danh sách mail_id hiện có trước khi kích hoạt gửi OTP."""
        seen: Set[str] = set()
        initial_inbox = cls.get_inbox(email, epin=epin)
        for m in initial_inbox.get("mail_list", initial_inbox.get("mails", [])):
            if isinstance(m, dict):
                mid = m.get("mail_id") or m.get("id")
                if mid is not None:
                    seen.add(str(mid))
        return seen

    @classmethod
    def wait_for_otp_code(
        cls,
        email: str,
        timeout_seconds: int = 60,
        check_interval: float = 3.0,
        epin: Optional[str] = None,
        initial_seen_ids: Optional[Set[str]] = None
    ) -> Optional[str]:
        """Polling hộp thư để chờ mã OTP 6 số (hoặc link xác nhận) gửi về từ Muse."""
        start_time = time.time()
        seen_mail_ids = set(initial_seen_ids) if initial_seen_ids is not None else cls.snapshot_seen_ids(email, epin=epin)

        while time.time() - start_time < timeout_seconds:
            inbox = cls.get_inbox(email, epin=epin)
            mail_items = inbox.get("mail_list", inbox.get("mails", []))

            for m in mail_items:
                if not isinstance(m, dict):
                    continue
                mid = str(m.get("mail_id") or m.get("id"))
                if mid in seen_mail_ids:
                    continue

                seen_mail_ids.add(mid)
                subject = m.get("subject", "")
                
                # Kiểm tra mã trong Subject trước
                subject_match = re.search(r"\b(\d{6})\b", subject)
                if subject_match:
                    return subject_match.group(1)

                # Nếu subject không có, đọc chi tiết body
                detail = cls.get_mail_detail(email, mid, epin=epin)
                content = (detail.get("text") or detail.get("html") or detail.get("body") or "")
                
                body_match = re.search(r"\b(\d{6})\b", content)
                if body_match:
                    return body_match.group(1)

                # Tìm 4 số nếu không có 6 số
                alt_match = re.search(r"\b(\d{4})\b", content)
                if alt_match:
                    return alt_match.group(1)

            time.sleep(check_interval)

        return None
