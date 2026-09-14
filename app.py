from flask import Flask, jsonify, request
import requests  # 💡 [關鍵改變] 換回 Python 官方最標準的網路套件
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
    
    # 💡 [終極修正] 把參數交給 requests 自動進行最標準的編碼，ScraperAPI 絕對不會漏接！
    payload = {
        'api_key': scraper_api_key,
        'url': target_url,
        'premium': 'true',       # 強制開啟住宅 IP
        'keep_headers': 'true'   # 保留我們給的 Referer
    }
    
    # 偽裝成從首頁點擊進去的正常行為
    headers = {
        "Referer": "https://www.marinetraffic.com/"
    }

    try:
        print(f"[請求發出] 透過標準 API 呼叫 ScraperAPI (MMSI: {mmsi})，請等待...")
        
        # 發送標準請求，不搞任何特殊偽裝
        response = requests.get('http://api.scraperapi.com/', params=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            raw_text = response.text
            data = None
            
            # 嘗試解析 JSON
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
