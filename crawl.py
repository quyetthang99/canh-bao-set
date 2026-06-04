import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    current_ts = int(time.time())
    source_url = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}" 
    proxy_url = f"https://api.allorigins.win/raw?url={source_url}&disableCache=true"
    headers = { "User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache" }
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    db_data = {}
    try:
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json():
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")
        sys.exit(1)

    try:
        use_proxy = False
        try:
            response = requests.get(source_url, headers=headers, timeout=15)
            if response.status_code != 200: use_proxy = True
        except: use_proxy = True

        if use_proxy: response = requests.get(proxy_url, headers=headers, timeout=60)

        if response.status_code == 200:
            raw_text = response.text
            updates = {} 
            diem_moi = 0
            
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            for block in valid_blocks:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    
                    if not (6.5 <= lat <= 23.5 and 102.0 <= lng <= 117.5): continue
                    
                    giatri = float(re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1)) if re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE) else 0.0
                    loaiset = int(re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1)) if re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE) else 0
                    
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    giay = int(re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1)) if re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE) else 0
                    
                    if nam < 100: nam += 2000
                    vn_tz = timezone(timedelta(hours=7))
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=vn_tz)
                    ts = dt.timestamp()
                    key = hashlib.md5(f"{ts}_{lat}_{lng}".encode()).hexdigest()
                    
                    if key not in db_data:
                        # Thêm cờ da_canh_bao = False để Bot 2 (alert.py) biết đây là điểm sét mới
                        updates[key] = {
                            "lat": lat, "lng": lng, "giatri": giatri, "loaiset": loaiset, 
                            "timestamp": ts, "is_new_format": True, "da_canh_bao": False
                        }
                        db_data[key] = updates[key] 
                        diem_moi += 1
                    else:
                        old_giatri = db_data[key].get("giatri", 0)
                        if (old_giatri == 0 or old_giatri == 0.0) and giatri > 0:
                            updated_record = db_data[key].copy()
                            updated_record["giatri"] = giatri
                            updated_record["loaiset"] = loaiset
                            updates[key] = updated_record
                            db_data[key] = updated_record
                            
                except Exception: continue 
            
            # Dọn rác 7 ngày
            seven_days_ago = current_ts - 604800
            for k, v in db_data.items():
                if v.get("timestamp", 0) < seven_days_ago: updates[k] = None 
            
            if updates:
                requests.patch(FIREBASE_URL, json=updates, timeout=60)
                print(f"Đã cập nhật {len(updates)} tác vụ lên Firebase (Mới: {diem_moi}).")
            else:
                print("Chưa có sét mới.")
        else: sys.exit(1)
    except Exception as e: sys.exit(1)

if __name__ == "__main__":
    crawl_lightning_data()
