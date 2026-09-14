from flask import Flask, jsonify, request
from curl_cffi import requests
import threading
import time
import random
import os

app = Flask(__name__)
thread_local = threading.local()

# 可用的瀏覽器偽裝特徵池 (隨機切換避免單一特徵被鎖定)
IMPERSONATE_LIST = ["chrome110", "chrome116", "chrome120", "safari15_5", "safari17_0"]

def get_session():
    """建立包含完整瀏覽器特徵與初始 Cookie 的 Session"""
    if not hasattr(thread_local, "session"):
        # 1. 隨機選擇一個瀏覽器指紋
        browser_type = random.choice(IMPERSONATE_LIST)
        
        proxies = {}
        proxy_url = os.environ.get("PROXY_URL")
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}
            
        # 💡 [關鍵修正] 加入 verify=False，忽略代理伺服器帶來的 SSL 憑證驗證問題
        session = requests.Session(impersonate=browser_type, proxies=proxies, verify=False)
        
        # 2. 讓 curl_cffi 自動處理 User-Agent 與 sec-ch-ua
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        
        # 3. 預先訪問資料頁面獲取基本 Cookie
        try:
            time.sleep(random.uniform(0.5, 1.5))
            # 這裡也建議加上 verify=False
            session.get("https://www.marinetraffic.com/en/data/?menu=vessels", timeout=15, verify=False)
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
    
    url = f"https://www.marinetraffic.com/en/global_search/search?term={mmsi}"
    max_retries = 2  # 最多內部自動重試 2 次 (共執行 3 次)
    
    for attempt in range(max_retries + 1):
        session = get_session()
        
        try:
            referers = [
                "https://www.marinetraffic.com/",
                "https://www.marinetraffic.com/en/data/?menu=vessels"
            ]
            session.headers["Referer"] = random.choice(referers)

            time.sleep(random.uniform(0.8, 1.8))
            
            response = session.get(url, timeout=20, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results and len(results) > 0:
                    ship_id = results[0].get("id")
                    return jsonify({"status": "success", "shipid": str(ship_id)})
                return jsonify({"status": "not_found", "shipid": None})
            
            else:
                # 💡 [關鍵修改] 把 500, 502, 503 等所有非 200 的錯誤都視為「代理失敗/被阻擋」
                # 並且擷取前 150 個字的錯誤訊息內文，讓我們知道到底是誰在擋
                error_preview = response.text[:150].replace('\n', ' ')
                print(f"[Retry {attempt+1}] 失敗！HTTP {response.status_code}，訊息: {error_preview}")
                
                reset_session() # 銷毀這個爛 IP
                
                # 如果已經是最後一次嘗試，才把真實錯誤訊息回傳給 GAS
                if attempt == max_retries:
                    return jsonify({
                        "status": "error", 
                        "message": f"MT status {response.status_code}. Detail: {error_preview}"
                    }), response.status_code
                
        except Exception as e:
            print(f"[Retry {attempt+1}] 連線逾時或錯誤 ({e})，準備重試...")
            reset_session()
            
            if attempt == max_retries:
                return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    # 開啟 threaded=True 允許處理併發請求
    app.run(host='0.0.0.0', port=port, threaded=True)
