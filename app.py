from flask import Flask, jsonify, request
from curl_cffi import requests
import threading
import time
import random
import os

app = Flask(__name__)
thread_local = threading.local()

def get_session():
    """建立包含完整瀏覽器特徵與初始 Cookie 的 Session"""
    if not hasattr(thread_local, "session"):
        session = requests.Session(impersonate="chrome120")
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.marinetraffic.com/en/data/?menu=vessels",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        # 預先訪問一次首頁獲取基本 Cookie，避開 400 錯誤
        try:
            session.get("https://www.marinetraffic.com/", timeout=10)
        except Exception as e:
            print(f"Init cookie error: {e}")
            
        thread_local.session = session
    return thread_local.session

@app.route('/get_shipid', methods=['GET'])
def api_get_shipid():
    mmsi = request.args.get('mmsi')
    if not mmsi:
        return jsonify({"status": "error", "message": "Missing mmsi parameter"}), 400
    
    session = get_session()
    url = f"https://www.marinetraffic.com/en/global_search/search?term={mmsi}"
    
    try:
        # 隨機延遲模擬真人
        time.sleep(random.uniform(1.2, 2.5))
        response = session.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results and len(results) > 0:
                ship_id = results[0].get("id")
                return jsonify({"status": "success", "shipid": str(ship_id)})
            return jsonify({"status": "not_found", "shipid": None})
        else:
            return jsonify({"status": "error", "message": f"MT status {response.status_code}"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
