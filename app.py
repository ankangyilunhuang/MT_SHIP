from flask import Flask, jsonify, request
from curl_cffi import requests
import threading
import time
import random
import os
import urllib.parse  # 💡 [新增] 用來安全地編碼網址

app = Flask(__name__)
thread_local = threading.local()

IMPERSONATE_LIST = ["chrome110", "chrome116", "chrome120", "safari15_5", "safari17_0"]

def get_session():
    if not hasattr(thread_local, "session"):
        browser_type = random.choice(IMPERSONATE_LIST)
        
        # 💡 [修改] 因為改用 REST API，這裡不需要再設定 proxies 了，變得更乾淨！
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
    
    # 從環境變數取得你的 API KEY
    scraper_api_key = os.environ.get("SCRAPERAPI_KEY")
    if not scraper_api_key:
        return jsonify({"status": "error", "message": "尚未設定 SCRAPERAPI_KEY 環境變數"}), 500

    # 1. 這是我們真正要抓的 MarineTraffic 網址
    target_url = f"https://www.marinetraffic.com/en/global_search/search?term={mmsi}"
    # 將目標網址進行編碼，確保特殊字元不會跑掉
    encoded_url = urllib.parse.quote(target_url)
    
    # 2. 💡 [關鍵修正] 組裝 ScraperAPI 的 REST API 網址
    # 這裡明確地寫上 premium=true 以及 keep_headers=true，保證 ScraperAPI 絕對收得到！
    api_url = f"http://api.scraperapi.com/?api_key={scraper_api_key}&url={encoded_url}&premium=true&keep_headers=true"
    
    session = get_session()
    
    try:
        referers = [
            "https://www.marinetraffic.com/",
            "https://www.marinetraffic.com/en/data/?menu=vessels"
        ]
        session.headers["Referer"] = random.choice(referers)
        
        print(f"[請求發出] 透過 REST API 查詢 MMSI: {mmsi}，請耐心等待 60 秒...")
        # 呼叫我們組好的 api_url
        response = session.get(api_url, timeout=60, verify=False)
        
        if response.status_code == 200:
            data = response.json()
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
