import requests, json, time, hashlib, re
from datetime import datetime

def crawl_lightning_data():
    # URL hai kho dữ liệu
    WEB_DB_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    ALERT_DB_URL = "https://databandoset-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    source_url = f"http://hymetnet.gov.vn/lightningmaps/?_t={int(time.time())}"
    headers = { "User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache" }
    
    try:
        response = requests.get(source_url, headers=headers, timeout=15)
        if response.status_code != 200: return
        
        raw_text = response.text
        blocks = re.findall(r'\{[^{}]*\}', raw_text)
        updates = {}
        
        for block in blocks:
            try:
                lat = float(re.search(r'lat["\']?\s*:\s*([-\d.]+)', block).group(1))
                lng = float(re.search(r'lng["\']?\s*:\s*([-\d.]+)', block).group(1))
                if lat > lng: lat, lng = lng, lat
                
                # Lọc vùng: Lào Cai - Yên Bái
                if not (21.23 <= lat <= 22.85 and 103.50 <= lng <= 105.00): continue
                
                giatri = float(re.search(r'giatri["\']?\s*:\s*([-\d.]+)', block).group(1) or 0)
                loaiset = int(re.search(r'loaiset["\']?\s*:\s*(\d+)', block).group(1) or 0)
                nam = int(re.search(r'nam["\']?\s*:\s*(\d+)', block).group(1))
                if nam < 100: nam += 2000
                
                ts = datetime(nam, int(re.search(r'thang["\']?\s*:\s*(\d+)', block).group(1)), 
                             int(re.search(r'ngay["\']?\s*:\s*(\d+)', block).group(1)), 
                             int(re.search(r'gio["\']?\s*:\s*(\d+)', block).group(1)), 
                             int(re.search(r'phut["\']?\s*:\s*(\d+)', block).group(1))).timestamp()
                
                key = hashlib.md5(f"{ts}_{lat}_{lng}".encode()).hexdigest()
                updates[key] = {"lat": lat, "lng": lng, "g": giatri, "l": loaiset, "t": ts, "a": False}
            except: continue
        
        if updates:
            # Ghi vào DB1 (Web)
            requests.patch(WEB_DB_URL, json=updates, timeout=60)
            # Ghi vào DB2 (Alert)
            requests.patch(ALERT_DB_URL, json=updates, timeout=60)
            print(f"Đã cập nhật {len(updates)} điểm vào 2 kho dữ liệu.")
            
    except Exception as e: print(f"Lỗi: {e}")

if __name__ == "__main__": crawl_lightning_data()
