"""Direct API client for LanguageNut.com - handles all HTTP communication"""

import asyncio
import json
import random
import time
import logging

logger = logging.getLogger(__name__)

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not installed. Install with: pip install aiohttp")

class LNApiClient:
    """API client for LanguageNut.com"""

    def __init__(self, base_url: str = None):
        # FIXED: Correct API base URL
        self.base_url = base_url or "https://api.languagenut.com"
        self.token = None
        self.username = None
        self.logged_in = False
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
        ]

    def _get_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def _get_headers(self, content_type: str = None) -> dict:
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-GB,en;q=0.9",
            "Referer": "https://www.languagenut.com/",
            "Origin": "https://www.languagenut.com",
            "DNT": "1",
            "Connection": "keep-alive",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Sync GET request"""
        import requests
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()
        try:
            from curl_cffi import requests as curl_requests
            resp = curl_requests.get(url, params=params, headers=headers, impersonate="chrome125", timeout=15)
        except ImportError:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        raise Exception(f"GET {endpoint} returned {resp.status_code}: {resp.text[:200]}")

    def _post(self, endpoint: str, data: dict = None) -> dict:
        """Sync POST request"""
        import requests
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers("application/x-www-form-urlencoded; charset=UTF-8")
        try:
            from curl_cffi import requests as curl_requests
            resp = curl_requests.post(url, data=data, headers=headers, impersonate="chrome125", timeout=15)
        except ImportError:
            resp = requests.post(url, data=data, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        raise Exception(f"POST {endpoint} returned {resp.status_code}: {resp.text[:200]}")

    async def _get_async(self, endpoint: str, params: dict = None) -> dict:
        """Async GET request.
        FIXED: Uses text + json.loads instead of resp.json()
        because LN returns Content-Type: application/javascript not application/json
        """
        if not HAS_AIOHTTP:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._get, endpoint, params)
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers()
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                if resp.status == 200:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        raise Exception(f"GET {endpoint} invalid JSON: {text[:200]}")
                raise Exception(f"GET {endpoint} returned {resp.status}: {text[:200]}")

    async def _post_async(self, endpoint: str, data: dict = None) -> dict:
        """Async POST request.
        FIXED: Uses text + json.loads instead of resp.json()
        """
        if not HAS_AIOHTTP:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._post, endpoint, data)
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_headers("application/x-www-form-urlencoded; charset=UTF-8")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                if resp.status == 200:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        raise Exception(f"POST {endpoint} invalid JSON: {text[:200]}")
                raise Exception(f"POST {endpoint} returned {resp.status}: {text[:200]}")

    # =================================================================
    # Auth methods
    # =================================================================

    async def login(self, username: str, password: str) -> dict:
        """Login. FIXED: GET with query params, checks newToken."""
        result = await self._get_async("loginController/attemptLogin", {
            "username": username,
            "pass": password,
        })
        if result and "newToken" in result:
            self.token = result["newToken"]
            self.username = username
            self.logged_in = True
            logger.info(f"Logged in as {username}")
        else:
            error = result.get("error", result.get("msg", "UNKNOWN")) if result else "NO_RESPONSE"
            raise Exception(f"Login failed: {error}")
        return result

    def login_sync(self, username: str, password: str) -> dict:
        """Sync login."""
        result = self._get("loginController/attemptLogin", {
            "username": username,
            "pass": password,
        })
        if result and "newToken" in result:
            self.token = result["newToken"]
            self.username = username
            self.logged_in = True
        return result

    async def call_lnut(self, endpoint: str, params: dict = None) -> dict:
        """Generic GET helper — token as query param."""
        if params is None:
            params = {}
        if self.token and "token" not in params:
            params["token"] = self.token
        return await self._get_async(endpoint, params=params)

    # =================================================================
    # Game data methods
    # =================================================================

    async def get_game_vocab(self, curriculum_uid: int, product: str = "secondary") -> dict:
        if not self.token:
            raise Exception("Not logged in.")
        params = {"curriculumUid": curriculum_uid, "product": product,
                  "_": int(time.time() * 1000), "token": self.token}
        return await self._get_async("gameDataController/getGameVocab", params=params)

    async def add_game_score(self, correct_uids: list, incorrect_uids: list,
                             product: str = "secondary") -> dict:
        if not self.token:
            raise Exception("Not logged in.")
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        data = {
            "correctVocabUids": json.dumps(correct_uids),
            "incorrectVocabUids": json.dumps(incorrect_uids),
            "timeStamp": timestamp, "dontStoreStats": "false",
            "product": product, "token": self.token,
        }
        return await self._post_async("gameDataController/addGameScore", data=data)

    async def get_assignments(self) -> dict:
        if not self.token: raise Exception("Not logged in.")
        return await self.call_lnut("assignmentController/getViewableAll", params={"token": self.token})

    async def get_stats(self) -> dict:
        if not self.token: raise Exception("Not logged in.")
        return await self.call_lnut("stats/get", params={"token": self.token})

    async def get_profile(self) -> dict:
        if not self.token: raise Exception("Not logged in.")
        return await self.call_lnut("profile/get", params={"token": self.token})
