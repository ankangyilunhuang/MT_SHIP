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
    # 💡 [新增] 接收從 GAS 傳來的船名
    name = request.args.get('name', '') 
    
    if not mmsi:
        return jsonify({"status": "error", "message": "Missing mmsi parameter"}), 400
    
    scraper_api_key = os.environ.get("SCRAPERAPI_KEY")
    if not scraper_api_key:
        return jsonify({"status": "error", "message": "尚未設定 SCRAPERAPI_KEY 環境變數"}), 500

    # 💡 [關鍵進化] 將 MMSI 與 船名 組合進行搜尋。
    # 例如：site:marinetraffic.com 412445575 MIN YUN YU 0082
    # 這樣 Google 就只會回傳符合該船名的精準 ShipID 網頁！
    query_str = f"site:marinetraffic.com {mmsi} {name}".strip()
    target_url = f"https://www.google.com/search?q={urllib.parse.quote(query_str)}"
    
    payload = {
        'api_key': scraper_api_key,
        'url': target_url
    }

    try:
        print(f"[請求發出] Google 精準搜尋 MMSI: {mmsi}, 船名: {name} ...")
        
        response = requests.get('http://api.scraperapi.com/', params=payload, timeout=30)
        
        if response.status_code == 200:
            match = re.search(r'shipid:(\d+)', response.text)
            
            if match:
                ship_id = match.group(1)
                print(f"[成功] 成功攔截對應 ShipID: {ship_id}")
                return jsonify({"status": "success", "shipid": ship_id})
            else:
                print("[未找到] Google 索引中未發現完全吻合的 ShipID")
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
