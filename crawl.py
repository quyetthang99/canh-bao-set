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
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    db_data = {}
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase...")
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    try:
        print(f"Đang bóc tách mã nguồn...")
        use_proxy = False
        try:
            response = requests.get(source_url, headers=headers, timeout=15)
            if response.status_code != 200:
                use_proxy = True
        except:
            use_proxy = True

        if use_proxy:
            print("Kết nối trực tiếp thất bại, dùng Proxy...")
            response = requests.get(proxy_url, headers=headers, timeout=60)

        if response.status_code == 200:
            raw_text = response.text
            diem_moi = 0
            diem_cap_nhat = 0
            diem_bi_loai = 0
            
            updates = {} 
            
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            for block in valid_blocks:
                try:
                    lat_m = re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    lng_m = re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    
                    if not lat_m or not lng_m: continue
                        
                    lat = float(lat_m.group(1))
                    lng = float(lng_m.group(1))
                    
                    if lat > lng: lat, lng = lng, lat
                    
                    if not (6.5 <= lat <= 23.5 and 102.0 <= lng <= 117.5):
                        diem_bi_loai += 1
                        continue
                    
                    giatri_m = re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    giatri = float(giatri_m.group(1)) if giatri_m else 0.0
                    
                    loaiset_m = re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    loaiset = int(loaiset_m.group(1)) if loaiset_m else 0
                    
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    giay_m = re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    giay = int(giay_m.group(1)) if giay_m else 0
                    
                    # Fix lỗi năm 0026 và khóa múi giờ
                    if nam < 100: nam += 2000
                    vn_tz = timezone(timedelta(hours=7))
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=vn_tz)
                    ts = dt.timestamp()
                    
                    key_string = f"{ts}_{lat}_{lng}"
                    key = hashlib.md5(key_string.encode()).hexdigest()
                    
                    if key not in db_data:
                        # THÊM CỜ DA_CANH_BAO ĐỂ BOT ALERTER NHẬN DIỆN
                        updates[key] = {
                            "lat": lat,
                            "lng": lng,
                            "giatri": giatri,
                            "loaiset": loaiset,
                            "timestamp": ts,
                            "is_new_format": True,
                            "da_canh_bao": False 
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
                            diem_cap_nhat += 1
                            
                except Exception:
                    continue 
            
            seven_days_ago = current_ts - 604800
            diem_xoa = 0
            for k, v in db_data.items():
                if v.get("timestamp", 0) < seven_days_ago:
                    updates[k] = None
                    diem_xoa += 1
            
            if updates:
                print(f"Đang đẩy/xóa dữ liệu bằng PATCH lên Firebase ({len(updates)} tác vụ)...")
                patch_response = requests.patch(FIREBASE_URL, json=updates, timeout=60)
                if patch_response.status_code == 200:
                    print(f"✅ HOÀN TẤT! Đã lưu {diem_moi} điểm mới. BỔ SUNG CƯỜNG ĐỘ cho {diem_cap_nhat} điểm cũ. Đã dọn {diem_xoa} rác.")
                else:
                    print(f"❌ Lỗi Firebase: {patch_response.text}")
                    sys.exit(1)
            else:
                print("✅ Hệ thống quét xong. Không có sét mới, cũng không có dữ liệu cường độ nào được cập nhật thêm.")

        else:
            print(f"❌ Lỗi HTTP: {response.status_code}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Lỗi mạng: {e}")
        sys.exit(1)

if __name__ == "__main__":
    crawl_lightning_data()
