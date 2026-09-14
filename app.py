from flask import Flask, jsonify, request
import requests
import os
import re
import urllib.parse

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

    # 💡 [思維轉換] 我們不去 MarineTraffic 了，我們改去 Google 搜尋！
    # 搜尋語法：site:marinetraffic.com mmsi 123456789
    query = f"site:marinetraffic.com mmsi {mmsi}"
    target_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    
    # 只需要最普通的 ScraperAPI 請求，不需要 premium，也不用 render
    payload = {
        'api_key': scraper_api_key,
        'url': target_url
    }

    try:
        print(f"[請求發出] 放棄正面突破，改由 Google 搜尋 MMSI: {mmsi} 的 ShipID...")
        
        # 抓取 Google 搜尋結果，通常只要 3~5 秒
        response = requests.get('http://api.scraperapi.com/', params=payload, timeout=30)
        
        if response.status_code == 200:
            # 💡 [魔法就在這裡] 直接用正則表達式，掃描 HTML 中有沒有出現 shipid:數字
            match = re.search(r'shipid:(\d+)', response.text)
            
            if match:
                ship_id = match.group(1)
                print(f"[成功] 透過 Google 成功攔截 ShipID: {ship_id}")
                return jsonify({"status": "success", "shipid": ship_id})
            else:
                print("[未找到] Google 索引中尚未收錄該 MMSI 的 ShipID")
                return jsonify({"status": "not_found", "shipid": None})
        
        else:
            print(f"[失敗] Google 搜尋失敗，HTTP {response.status_code}")
            return jsonify({
                "status": "error", 
                "message": f"Search failed with status {response.status_code}"
            }), response.status_code
            
    except Exception as e:
        print(f"[錯誤] 連線逾時或發生例外 ({e})")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
