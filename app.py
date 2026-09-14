from flask import Flask, jsonify, request
from curl_cffi import requests
import threading
import time
import random
import os

app = Flask(__name__)
thread_local = threading.local()

# 可用的瀏覽器偽裝特徵池 (隨機切換避免單一特徵被鎖定)
IMPERSONATE_LIST = ["chrome116", "chrome120", "edge116", "safari17_0"]

def get_session():
    """建立包含完整瀏覽器特徵與初始 Cookie 的 Session"""
    if not hasattr(thread_local, "session"):
        # 1. 隨機選擇一個瀏覽器指紋
        browser_type = random.choice(IMPERSONATE_LIST)
        
        # 💡 [進階防護] 若未來仍被擋，可在 Render 環境變數設定 PROXY_URL 
        # 例如：http://user:pass@proxy_ip:port
        proxies = {}
        proxy_url = os.environ.get("PROXY_URL")
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}
            
        session = requests.Session(impersonate=browser_type, proxies=proxies)
        
        # 2. ⚠️ 關鍵修正：讓 curl_cffi 自動處理 User-Agent 與 sec-ch-ua
        # 我們只補充需要的「業務邏輯 Headers」，絕對不要手動寫死 User-Agent
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        
        # 3. 預先訪問資料頁面獲取基本 Cookie (Cloudflare 初步檢查)
        try:
            # 模擬人類訪問首頁的思考時間
            time.sleep(random.uniform(0.5, 1.5))
            session.get("https://www.marinetraffic.com/en/data/?menu=vessels", timeout=15)
        except Exception as e:
            print(f"Init cookie error: {e}")
            
        thread_local.session = session
        print(f"[Session 建立] 偽裝指紋: {browser_type}")
        
    return thread_local.session

def reset_session():
    """當遇到 403 阻擋時，銷毀當前 Session (丟棄被污染的 Cookie)"""
    if hasattr(thread_local, "session"):
        del thread_local.session
        print("[Session 重置] 遭遇 403 或連線阻擋，已清除當前 Session，下次將重新生成。")

@app.route('/', methods=['GET'])
def health_check():
    """供 GAS 喚醒確認用"""
    return jsonify({"status": "ok", "message": "Render service is awake and ready."}), 200

@app.route('/get_shipid', methods=['GET'])
def api_get_shipid():
    mmsi = request.args.get('mmsi')
    if not mmsi:
        return jsonify({"status": "error", "message": "Missing mmsi parameter"}), 400
    
    session = get_session()
    url = f"https://www.marinetraffic.com/en/global_search/search?term={mmsi}"
    
    try:
        # 動態修改 Referer，模擬用戶在網站內不同的頁面發出搜尋
        referers = [
            "https://www.marinetraffic.com/",
            "https://www.marinetraffic.com/en/data/?menu=vessels"
        ]
        session.headers["Referer"] = random.choice(referers)

        # 隨機延遲 (配合 GAS 的 3.5s 已經夠長，這裡微調即可)
        time.sleep(random.uniform(0.8, 1.8))
        
        response = session.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results and len(results) > 0:
                ship_id = results[0].get("id")
                return jsonify({"status": "success", "shipid": str(ship_id)})
            return jsonify({"status": "not_found", "shipid": None})
        
        elif response.status_code in [403, 401, 429]:
            # ⚠️ 關鍵修正：若被擋，立刻銷毀 Session，避免下次請求繼續失敗
            reset_session()
            return jsonify({"status": "error", "message": f"MT Blocked request (Status {response.status_code}). Session reset."}), response.status_code
            
        else:
            return jsonify({"status": "error", "message": f"MT status {response.status_code}"}), response.status_code
            
    except Exception as e:
        # 發生 Timeout 或其他網路層阻擋時，也視為 Session 失效並重置
        reset_session()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    # 開啟 threaded=True 允許處理併發請求
    app.run(host='0.0.0.0', port=port, threaded=True)
