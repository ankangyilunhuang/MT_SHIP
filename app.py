from flask import Flask, jsonify, request
import requests
import os
import json
import re

app = Flask(__name__)

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
    
    # 💡 [終極火力全開] 住宅 IP + 隱形瀏覽器 + 指定美國節點
    payload = {
        'api_key': scraper_api_key,
        'url': target_url,
        'premium': 'true',       # 啟用真實住宅 IP
        'render': 'true',        # 💡 強制開啟瀏覽器渲染，破解 Cloudflare JS 驗證
        'country_code': 'us',    # 💡 指定美國 IP (降低被鎖定機率)
        'keep_headers': 'true'
    }
    
    headers = {
        "Referer": "https://www.marinetraffic.com/"
    }

    try:
        print(f"[請求發出] 啟動 Premium + Render 破解 Cloudflare (MMSI: {mmsi})，請等待 30-80 秒...")
        
        # 💡 因為開啟瀏覽器執行 JS 需要比較久的時間，把 timeout 延長到 85 秒
        response = requests.get('http://api.scraperapi.com/', params=payload, headers=headers, timeout=85)
        
        if response.status_code == 200:
            raw_text = response.text
            data = None
            
            # 因為使用了隱形瀏覽器，回傳的 JSON 可能會被包在 <html><body> 標籤裡
            # 這裡我們做智慧解析，把外面包著的 HTML 剝掉
            try:
                data = response.json()
            except:
                clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
                try:
                    data = json.loads(clean_text)
                except:
                    pass
                    
            if data and isinstance(data, dict):
                results = data.get("results", [])
                if results and len(results) > 0:
                    ship_id = results[0].get("id")
                    return jsonify({"status": "success", "shipid": str(ship_id)})
            
            return jsonify({"status": "not_found", "shipid": None})
        
        else:
            error_preview = response.text[:150].replace('\n', ' ')
            print(f"[失敗] HTTP {response.status_code}，訊息: {error_preview}")
            return jsonify({
                "status": "error", 
                "message": f"MT status {response.status_code}. Detail: {error_preview}"
            }), response.status_code
            
    except Exception as e:
        print(f"[錯誤] 連線逾時或發生例外 ({e})")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
