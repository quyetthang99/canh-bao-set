import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    # 1. CHIÊU TRÒ CHỐNG CACHE
    current_ts = int(time.time())
    source_url = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}" 
    proxy_url = f"https://api.codetabs.com/v1/proxy?quest={source_url}"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    # Đọc DB cũ từ Firebase
    db_data = {}
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase...")
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    try:
        print(f"Đang bóc tách mã nguồn (Chống Cache)...")
        response = requests.get(proxy_url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            raw_text = response.text
            diem_moi = 0
            diem_bi_loai = 0 # Biến đếm số điểm sét ngoài lãnh thổ bị loại bỏ
            
            # LƯỚI VÉT SIÊU RỘNG
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            vn_tz = timezone(timedelta(hours=7))
            
            for block in valid_blocks:
                try:
                    lat_m = re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    lng_m = re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    
                    if not lat_m or not lng_m:
                        continue
                        
                    lat = float(lat_m.group(1))
                    lng = float(lng_m.group(1))
                    
                    # --- BỘ LỌC LÃNH THỔ & CHỦ QUYỀN VIỆT NAM ---
                    # Vĩ độ: 6.5 (Nam) đến 23.5 (Bắc)
                    # Kinh độ: 102.0 (Tây) đến 117.5 (Đông - Bao gồm Hoàng Sa & Trường Sa)
                    if not (6.5 <= lat <= 23.5 and 102.0 <= lng <= 117.5):
                        diem_bi_loai += 1
                        continue # Nếu nằm ngoài khung này thì bỏ qua luôn, không lưu
                    
                    # Lấy cường độ và loại
                    giatri_m = re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    giatri = float(giatri_m.group(1)) if giatri_m else 0.0
                    
                    loaiset_m = re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    loaiset = int(loaiset_m.group(1)) if loaiset_m else 0
                    
                    # Lấy thời gian
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    
                    giay_m = re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    giay = int(giay_m.group(1)) if giay_m else 0
                    
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=vn_tz)
                    ts = dt.timestamp()
                    
                    key_string = f"{ts}_{lat}_{lng}"
                    key = hashlib.md5(key_string.encode()).hexdigest()
                    
                    if key not in db_data:
                        db_data[key] = {
                            "lat": lat,
                            "lng": lng,
                            "giatri": giatri,
                            "loaiset": loaiset,
                            "timestamp": ts,
                            "is_new_format": True
                        }
                        diem_moi += 1
                except Exception:
                    continue 
            
            # 3. Dọn rác
            seven_days_ago = current_ts - 604800
            filtered_db = {k: v for k, v in db_data.items() if v["timestamp"] >= seven_days_ago}
            
            # 4. Đẩy Firebase
            print(f"Đang đẩy dữ liệu lên Firebase...")
            put_response = requests.put(FIREBASE_URL, json=filtered_db, timeout=30)
            if put_response.status_code == 200:
                print(f"✅ HOÀN TẤT! Đã lưu {diem_moi} điểm sét. Đã XÓA {diem_bi_loai} điểm ngoài lãnh thổ. Tổng kho: {len(filtered_db)} điểm.")
            else:
                print(f"❌ Lỗi Firebase: {put_response.text}")
                sys.exit(1)
        else:
            print(f"❌ Lỗi HTTP: {response.status_code}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Lỗi mạng: {e}")
        sys.exit(1)

if __name__ == "__main__":
    crawl_lightning_data()
