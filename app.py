from flask import Flask, jsonify, request
from curl_cffi import requests
import threading
import time
import random
import os
import urllib.parse
import json  # 💡 [新增] 處理 JSON 解析
import re    # 💡 [新增] 用來剝除 HTML 標籤

app = Flask(__name__)
thread_local = threading.local()

IMPERSONATE_LIST = ["chrome110", "chrome116", "chrome120", "safari15_5", "safari17_0"]

def get_session():
    if not hasattr(thread_local, "session"):
        browser_type = random.choice(IMPERSONATE_LIST)
        session = requests.Session(impersonate=browser_type, verify=False)
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "x-requested-with": "XMLHttpRequest",
        })
        thread_local.session = session
        print(f"[Session 建立] 偽裝指紋: {browser_type}")
        
    return thread_local.session

def reset_session():
    if hasattr(thread_local, "session"):
        del thread_local.session

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Render service is awake and ready."}), 200

@app.route('/get_shipid', methods=['GET'])
def api_get_shipid():
    mmsi = request.args.get('mmsi')
    if not mmsi:
        return jsonify({"status": "error", "message": "Missing mmsi parameter"}), 400
    
    scraper_api_key = os.environ.get("SCRAPERAPI_KEY")
    if not scraper_api_key:
        return jsonify({"status": "error", "message": "尚未設定 SCRAPERAPI_KEY 環境變數"}), 500

    target_url = f"https://www.marinetraffic.com/en/global_search/search?term={mmsi}"
    encoded_url = urllib.parse.quote(target_url)
    
    # 💡 [終極武器] 加入 &render=true！命令 ScraperAPI 啟動真實隱形瀏覽器破解 Cloudflare
    api_url = f"http://api.scraperapi.com/?api_key={scraper_api_key}&url={encoded_url}&premium=true&render=true"
    
    session = get_session()
    
    try:
        print(f"[請求發出] 啟動隱形瀏覽器破解 Cloudflare... MMSI: {mmsi}，可能需要 30~60 秒...")
        
        # 因為隱形瀏覽器需要時間執行 JS 腳本，這裡將 timeout 延長到 85 秒
        response = session.get(api_url, timeout=85, verify=False)
        
        if response.status_code == 200:
            raw_text = response.text
            data = None
            
            # 💡 [資料清洗] 瀏覽器有時會把 JSON 包在 HTML 裡面，這裡做智慧解析
            try:
                # 先嘗試直接解析
                data = response.json()
            except:
                # 若失敗，剝除所有 HTML 標籤後再解析一次
                clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
                try:
                    data = json.loads(clean_text)
                except Exception as parse_err:
                    print(f"[解析失敗] 內容已被污染: {clean_text[:100]}")
                    
            # 判斷並擷取 ShipID
            if data and isinstance(data, dict):
                results = data.get("results", [])
                if results and len(results) > 0:
                    ship_id = results[0].get("id")
                    return jsonify({"status": "success", "shipid": str(ship_id)})
            
            return jsonify({"status": "not_found", "shipid": None})
        
        else:
            error_preview = response.text[:150].replace('\n', ' ')
            print(f"[失敗] HTTP {response.status_code}，訊息: {error_preview}")
            reset_session()
            return jsonify({
                "status": "error", 
                "message": f"MT status {response.status_code}. Detail: {error_preview}"
            }), response.status_code
            
    except Exception as e:
        print(f"[錯誤] 連線逾時或發生例外 ({e})")
        reset_session()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
