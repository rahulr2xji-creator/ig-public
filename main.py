from flask import Flask, request, jsonify
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from flask_cors import CORS
from datetime import datetime, timedelta
import pytz
from collections import defaultdict
import threading

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# ============================================
# CONFIGURATION
# ============================================

DAILY_LIMIT = 2000  # Daily request limit
RESET_HOUR = 0  # 12:05 AM = 00:05
RESET_MINUTE = 5
TIMEZONE = pytz.timezone('Asia/Kolkata')  # Kolkata timezone
API_KEY = "IG"  # Default API key

# ============================================
# DAILY REQUEST LIMITER
# ============================================

class DailyRequestLimiter:
    def __init__(self, daily_limit: int = DAILY_LIMIT):
        self.daily_limit = daily_limit
        self.request_count = 0
        self.current_date = None
        self.lock = threading.Lock()
        self._update_date()
    
    def _update_date(self):
        """Update current date based on Kolkata time"""
        now = datetime.now(TIMEZONE)
        self.current_date = now.date()
    
    def _should_reset(self) -> bool:
        """Check if counter should be reset at 12:05 AM IST"""
        now = datetime.now(TIMEZONE)
        
        # Check if current time is after reset time (00:05)
        if now.hour > RESET_HOUR or (now.hour == RESET_HOUR and now.minute >= RESET_MINUTE):
            return self.current_date != now.date()
        else:
            # Before reset time, check previous day
            prev_day = (now - timedelta(days=1)).date()
            return self.current_date != prev_day
    
    def can_make_request(self) -> bool:
        """Check if a new request can be made"""
        with self.lock:
            if self._should_reset():
                self.request_count = 0
                self._update_date()
            return self.request_count < self.daily_limit
    
    def increment_request(self) -> int:
        """Increment request counter and return current count"""
        with self.lock:
            if self._should_reset():
                self.request_count = 0
                self._update_date()
            self.request_count += 1
            return self.request_count
    
    def get_remaining_requests(self) -> int:
        """Get remaining requests for today"""
        with self.lock:
            if self._should_reset():
                self.request_count = 0
                self._update_date()
            return max(0, self.daily_limit - self.request_count)
    
    def get_reset_time(self) -> str:
        """Get next reset time in Kolkata timezone"""
        now = datetime.now(TIMEZONE)
        next_reset = now.replace(hour=RESET_HOUR, minute=RESET_MINUTE, second=0, microsecond=0)
        
        if now >= next_reset:
            next_reset += timedelta(days=1)
        
        return next_reset.strftime("%Y-%m-%d %H:%M:%S IST")

# Initialize limiter
key_manager = DailyRequestLimiter(daily_limit=DAILY_LIMIT)

# ============================================
# DEVICE ROTATION SYSTEM
# ============================================

class DeviceRotator:
    def __init__(self):
        self.devices = [
            # Windows Devices
            {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
                "sec_ch_ua_platform": '"Windows"',
                "platform": "Windows 11"
            },
            {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Firefox";v="120"',
                "sec_ch_ua_platform": '"Windows"',
                "platform": "Windows 11"
            },
            {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Chromium";v="118", "Microsoft Edge";v="118"',
                "sec_ch_ua_platform": '"Windows"',
                "platform": "Windows 11"
            },
            # Mac Devices
            {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Brave";v="138"',
                "sec_ch_ua_platform": '"macOS"',
                "platform": "macOS Sonoma"
            },
            {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Safari";v="17.1"',
                "sec_ch_ua_platform": '"macOS"',
                "platform": "macOS Sonoma"
            },
            # Mobile Devices
            {
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Safari";v="17.1"',
                "sec_ch_ua_platform": '"iOS"',
                "platform": "iPhone 15"
            },
            {
                "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Chromium";v="119", "Mobile Safari";v="119"',
                "sec_ch_ua_platform": '"Android"',
                "platform": "Samsung Galaxy S24"
            },
            {
                "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.111 Mobile Safari/537.36",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Chromium";v="118", "Mobile Safari";v="118"',
                "sec_ch_ua_platform": '"Android"',
                "platform": "Google Pixel 7"
            },
            {
                "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36",
                "sec_ch_ua": '"Not)A;Brand";v="8", "Chromium";v="119", "Mobile Safari";v="119"',
                "sec_ch_ua_platform": '"Android"',
                "platform": "Samsung Galaxy A54"
            }
        ]
        self.current_index = 0
        self.lock = threading.Lock()
    
    def get_next_device(self) -> Dict:
        """Get next device in rotation (round-robin)"""
        with self.lock:
            device = self.devices[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.devices)
            return device

# Initialize device rotator
device_rotator = DeviceRotator()

# ============================================
# AUTHENTICATION SYSTEM
# ============================================

def verify_api_key():
    """Verify API key from request - supports key parameter"""
    # Check query parameter first
    api_key = request.args.get('key')
    
    # If not in query, check headers
    if not api_key:
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization')
    
    if not api_key:
        return False
    
    # Remove "Bearer " prefix if present
    if api_key.startswith('Bearer '):
        api_key = api_key[7:]
    
    return api_key == API_KEY

# ============================================
# MAIN DOWNLOADER CLASS
# ============================================

class InstagramDownloader:
    def __init__(self, delay_mode: str = "random", fixed_delay: float = 1.5, delay_min: float = 1.0,
                 delay_max: float = 1.0):
        self.delay_mode = delay_mode
        self.fixed_delay = fixed_delay
        self.delay_min = delay_min
        self.delay_max = delay_max
        
        self.session = requests.Session()
        self._update_session_headers()

    def _update_session_headers(self):
        """Update session headers with next device in rotation"""
        device = device_rotator.get_next_device()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Sec-CH-UA": device["sec_ch_ua"],
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": device["sec_ch_ua_platform"],
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": device["user_agent"]
        })
        return device

    def _delay_request(self):
        """Apply delay based on configuration"""
        if self.delay_mode == "random":
            sec = random.uniform(self.delay_min, self.delay_max)
        else:
            sec = self.fixed_delay
        time.sleep(sec)

    def _validate_instagram_url(self, url: str) -> bool:
        """Validate if URL is a valid Instagram URL"""
        if not url:
            return False
        
        pattern = r'^https?://(www\.)?instagram\.com/.*'
        if not re.match(pattern, url, re.IGNORECASE):
            return False
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        
        valid_patterns = [
            r'^/[-_A-Za-z0-9]+$',
            r'^/p/[-_A-Za-z0-9]+$',
            r'^/reel/[-_A-Za-z0-9]+$',
            r'^/stories/[-_A-Za-z0-9]+/[-_A-Za-z0-9]+$',
            r'^/tv/[-_A-Za-z0-9]+$',
            r'^/guide/[-_A-Za-z0-9]+$',
        ]
        
        for pattern in valid_patterns:
            if re.match(pattern, path):
                return True
        
        return False

    def _extract_js_variable(self, name: str, source: str) -> Optional[str]:
        """Extract JavaScript variable value from source"""
        pattern = re.escape(name) + r'\s*=\s*"([^"]+)"'
        match = re.search(pattern, source)
        return match.group(1) if match else None

    def _parse_media_html(self, html_content: str) -> Dict[str, Any]:
        """Parse the HTML content to extract media information"""
        result = {
            "results_images": 0,
            "results_videos": 0,
            "images": [],
            "videos": []
        }
        
        soup = BeautifulSoup(html_content, 'html.parser')
        download_items = soup.select('ul.download-box li')
        
        for item in download_items:
            thumb_img = item.select_one('div.download-items__thumb img')
            thumb_url = None
            if thumb_img:
                src = thumb_img.get('src', '')
                data_src = thumb_img.get('data-src', '')
                if not src or src == '/imgs/loader.gif':
                    thumb_url = data_src or src
                else:
                    thumb_url = src
            
            icon = item.select_one('div.download-items__thumb i')
            icon_class = icon.get('class', []) if icon else []
            icon_class_str = ' '.join(icon_class) if icon_class else ''
            
            is_image = 'icon-dlimage' in icon_class_str
            is_video = 'icon-dlvideo' in icon_class_str
            
            btn_links = item.select('div.download-items__btn a')
            
            video_href = None
            for link in btn_links:
                if link.has_attr('video'):
                    video_href = link.get('href')
                    is_video = True
                    break
                if 'download video' in link.get_text().lower():
                    video_href = link.get('href')
                    is_video = True
                    break
            
            if is_video and not video_href and btn_links:
                video_href = btn_links[0].get('href')
            
            resolutions = []
            select = item.select_one('div.photo-option select')
            if select:
                for option in select.find_all('option'):
                    label = option.get_text().strip()
                    value = option.get('value', '')
                    if label and value:
                        resolutions.append({label: value})
            
            if is_image:
                result["results_images"] += 1
                result["images"].append({
                    "thumb_url": thumb_url,
                    "resolutions_count": len(resolutions),
                    "resolution": resolutions
                })
            elif is_video:
                result["results_videos"] += 1
                result["videos"].append({
                    "thumb_url": thumb_url,
                    "video_src": video_href,
                    "resolutions_count": len(resolutions),
                    "resolution": resolutions
                })
        
        return result

    def download_instagram_content(self, target_url: str) -> Dict[str, Any]:
        """Main method to download Instagram content"""
        if not target_url:
            return {"error": "Missing 'url' parameter"}
        
        target_url = target_url.strip()
        
        if not self._validate_instagram_url(target_url):
            return {"error": "Invalid Instagram URL. Only profile, post, reel, or story URLs are supported."}
        
        device = self._update_session_headers()
        
        try:
            response = self.session.get("https://saveinsta.to/en/highlights")
            response.raise_for_status()
        except requests.RequestException as e:
            return {"error": f"Failed to fetch initial page: {str(e)}"}
        
        html_content = response.text
        
        script_pattern = r'<script[^>]*>var\s+k_url_search="[^"]+"(.*?)</script>'
        script_match = re.search(script_pattern, html_content, re.DOTALL)
        
        if not script_match:
            return {"error": "JS token block not found"}
        
        script_block = script_match.group(1)
        
        k_prefix_name = self._extract_js_variable("k_prefix_name", script_block)
        k_exp = self._extract_js_variable("k_exp", script_block)
        k_token = self._extract_js_variable("k_token", script_block)
        
        if not all([k_prefix_name, k_exp, k_token]):
            return {"error": "Failed to extract required tokens"}
        
        self._delay_request()
        
        try:
            cf_response = self.session.post(
                "https://saveinsta.to/api/userverify",
                data={"url": target_url},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": "https://saveinsta.to",
                    "Referer": "https://saveinsta.to/en/video",
                    "X-Requested-With": "XMLHttpRequest"
                }
            )
            cf_response.raise_for_status()
            cf_data = cf_response.json()
            
            if not cf_data or "token" not in cf_data:
                return {"error": "CF token not returned"}
            
            cftoken = cf_data["token"]
        except (requests.RequestException, json.JSONDecodeError) as e:
            return {"error": f"Failed to get CF token: {str(e)}"}
        
        self._delay_request()
        
        try:
            final_response = self.session.post(
                "https://saveinsta.to/api/ajaxSearch",
                data={
                    "k_exp": k_exp,
                    "k_token": k_token,
                    "q": target_url,
                    "t": "media",
                    "lang": "en",
                    "v": "v2",
                    "cftoken": cftoken
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": "https://saveinsta.to",
                    "Referer": "https://saveinsta.to/en/highlights",
                    "X-Requested-With": "XMLHttpRequest"
                }
            )
            final_response.raise_for_status()
            final_data = final_response.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            return {"error": f"Failed to fetch media content: {str(e)}"}
        
        if final_data.get("status") == "ok" and "data" in final_data:
            parsed_media = self._parse_media_html(final_data["data"])
            return {
                "success": True,
                "media": parsed_media,
                "device_used": device["platform"]
            }
        else:
            return {
                "error": "Invalid response",
                "raw": final_data
            }


# Initialize downloader
downloader = InstagramDownloader(
    delay_mode="random",
    delay_min=1.0,
    delay_max=1.0
)

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/download', methods=['GET'])
def download_instagram():
    """
    API endpoint to download Instagram content
    Usage: GET /download?key=API_KEY&url=https://www.instagram.com/reel/DWz5EjgSBeJ/
    """
    
    # Authentication - Check key parameter
    if not verify_api_key():
        return jsonify({
            "error": "Unauthorized",
            "message": "Valid API key required. Use: ?key=YOUR_API_KEY",
            "example": "/download?key=IG-2026-@SecureKey#1234&url=https://www.instagram.com/reel/DWz5EjgSBeJ/"
        }), 401
    
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            "error": "Missing parameter",
            "message": "Please provide 'url' parameter",
            "example": "/download?key=YOUR_API_KEY&url=https://www.instagram.com/p/EXAMPLE/"
        }), 400
    
    if not re.match(r'^https?://(www\.)?instagram\.com/.*', url, re.IGNORECASE):
        return jsonify({
            "error": "Invalid URL",
            "message": "URL must be a valid Instagram link"
        }), 400
    
    # Rate limit check
    if not key_manager.can_make_request():
        reset_time = key_manager.get_reset_time()
        return jsonify({
            "error": "Daily limit reached",
            "message": f"Maximum {DAILY_LIMIT} requests per day",
            "limit": DAILY_LIMIT,
            "used": DAILY_LIMIT,
            "remaining": 0,
            "reset_time": reset_time
        }), 429
    
    # Process request
    result = downloader.download_instagram_content(url)
    
    # Increment counter
    current_count = key_manager.increment_request()
    remaining = key_manager.get_remaining_requests()
    
    # Build response
    response = {
        "success": result.get("success", False),
        "rate_limit": {
            "limit": DAILY_LIMIT,
            "used": current_count,
            "remaining": remaining,
            "reset_time": key_manager.get_reset_time()
        }
    }
    
    if result.get("success"):
        response.update({
            "media": result["media"],
            "device_used": result.get("device_used", "Unknown")
        })
        return jsonify(response), 200
    else:
        response.update({
            "error": result.get("error", "Unknown error")
        })
        return jsonify(response), 400


@app.route('/status', methods=['GET'])
def status_check():
    """Check status and rate limit info"""
    remaining = key_manager.get_remaining_requests()
    reset_time = key_manager.get_reset_time()
    
    return jsonify({
        "service": "Instagram Downloader API",
        "status": "active",
        "rate_limit": {
            "daily_limit": DAILY_LIMIT,
            "used": key_manager.request_count,
            "remaining": remaining,
            "reset_time": reset_time
        },
        "devices": {
            "total": len(device_rotator.devices),
            "current_index": device_rotator.current_index + 1
        },
        "timezone": "Asia/Kolkata (IST)",
        "current_time": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S IST")
    })


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with instructions"""
    remaining = key_manager.get_remaining_requests()
    reset_time = key_manager.get_reset_time()
    
    return jsonify({
        "service": "Instagram Downloader API",
        "version": "2.0",
        "features": {
            "authentication": "API key required (key parameter)",
            "rate_limit": f"{DAILY_LIMIT} requests per day (resets at 12:05 AM IST)",
            "device_rotation": f"Rotates between {len(device_rotator.devices)} different devices",
            "supported_types": ["profile", "post", "reel", "story", "igtv", "guide"]
        },
        "endpoints": {
            "/download": {
                "method": "GET",
                "params": {
                    "key": "Your API key (required)",
                    "url": "Instagram URL (required)"
                },
                "example": "/download?key={key}&url=https://www.instagram.com/reel/DWz5EjgSBeJ/"
            }
        },
        "rate_limit_status": {
            "used": key_manager.request_count,
            "remaining": remaining,
            "reset_time": reset_time
        }
    })


# ============================================
# MAIN - RUN SERVER
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("📸 Instagram Downloader API")
    print("=" * 60)
    print(f"📊 Daily Limit: {DAILY_LIMIT} requests/day")
    print(f"⏰ Reset Time: 12:05 AM IST")
    print(f"🌍 Timezone: Asia/Kolkata (IST)")
    print(f"📱 Devices Available: {len(device_rotator.devices)}")
    print("=" * 60)
    print("📍 Local: http://localhost:5000")
    print("📥 Example: http://localhost:5000/download?key={key}&url=https://www.instagram.com/reel/DWz5EjgSBeJ/")
    print("=" * 60)
    print(f"🕐 Current IST Time: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 Next Reset: {key_manager.get_reset_time()}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)