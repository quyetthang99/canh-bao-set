import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    # URL mà bạn đã tìm thấy trong tab Sources/Network
    # Nếu nó là 1 file đuôi .js hay .json cụ thể, hãy thay link vào đây. Nếu là trang chủ, cứ để nguyên.
    source_url = "http://hymetnet.gov.vn/lightningmaps/" 
    proxy_url = f"https://api.codetabs.com/v1/proxy?quest={source_url}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    # 1. Đọc DB cũ từ Firebase
    db_data = {}
    try:
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    # 2. Cào dữ liệu sét mới
    try:
        print(f"Đang phân tích mã nguồn từ: {source_url}")
        response = requests.get(proxy_url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            raw_text = response.text
            diem_moi = 0
            current_time = time.time()
            
            # Thuật toán Regex quét tìm TẤT CẢ các đoạn code có chứa lat, lng, giatri, loaiset
            # Bất chấp việc nó nằm trong file JSON hay bị kẹp giữa code JS lộn xộn
            blocks = re.findall(r'\{[^{}]*lat[^{}]*giatri[^{}]*loaiset[^{}]*\}', raw_text, re.IGNORECASE)
            
            vn_tz = timezone(timedelta(hours=7)) # Set chuẩn múi giờ Việt Nam
            
            for block in blocks:
                try:
                    # Bóc tách từng giá trị bất chấp có dấu ngoặc kép hay không
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block).group(1))
                    giatri = float(re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block).group(1))
                    loaiset = int(re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block).group(1))
                    
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block).group(1))
                    giay = int(re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block).group(1))
                    
                    # Convert giờ VN thành Timestamp quốc tế để dùng cho hàm lọc của Web
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=vn_tz)
                    ts = dt.timestamp()
                    
                    # Tạo mã định danh độc nhất (MD5 Hash) để chống trùng lặp
                    key_string = f"{ts}_{lat}_{lng}"
                    key = hashlib.md5(key_string.encode()).hexdigest()
                    
                    if key not in db_data:
                        db_data[key] = {
                            "lat": lat,
                            "lng": lng,
                            "giatri": giatri,
                            "loaiset": loaiset,
                            "timestamp": ts,
                            "is_new_format": True # Đánh dấu dữ liệu xịn
                        }
                        diem_moi += 1
                except Exception:
                    continue # Bỏ qua nếu block code bị lỗi hoặc thiếu biến
            
            print(f"Đã bóc tách thành công {len(blocks)} điểm sét từ mã nguồn.")
            
            # 3. Dọn rác 7 ngày
            seven_days_ago = current_time - 604800
            filtered_db = {k: v for k, v in db_data.items() if v["timestamp"] >= seven_days_ago}
            
            # 4. Đẩy lên Firebase
            put_response = requests.put(FIREBASE_URL, json=filtered_db, timeout=30)
            if put_response.status_code == 200:
                print(f"✅ HOÀN TẤT! Đã đẩy {diem_moi} điểm sét CHI TIẾT mới. Tổng DB: {len(filtered_db)}.")
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
