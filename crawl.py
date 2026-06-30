import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data_realtime():
    print("🚀 KHỞI ĐỘNG BOT TỨC THỜI: QUÉT SÉT (10 PHÚT QUA - KHÔNG LỌC CƯỜNG ĐỘ)...")
    
    # 1. TẠO KHUNG THỜI GIAN LÙI 10 PHÚT 
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=10)
    
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    current_ts = int(time.time())

    # Phạm vi quét (Lào Cai & Vùng lân cận)
    MIN_LAT, MAX_LAT = 21.10, 23.00
    MIN_LNG, MAX_LNG = 103.30, 105.20

    # --- CẤU HÌNH API NGUỒN ---
    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"
    headers_hymetnet = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache"
    }

    api_url_vaisala = (
        f"https://evntools.com/api/lightning/map-data?start_time={start_time}&end_time={end_time}"
        f"&limit=5000&min_lat={MIN_LAT}&max_lat={MAX_LAT}&min_lon={MIN_LNG}&max_lon={MAX_LNG}"
    )
    headers_vaisala = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    # FIREBASE ĐÍCH MỚI
    FIREBASE_URL = "https://data-set-tuc-thoi-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 2. TẢI BỘ NHỚ TỪ FIREBASE ĐỂ TRÁNH TRÙNG LẶP
    db_data = {}
    try:
        print("Đang kết nối Firebase...")
        fb_response = requests.get(FIREBASE_URL, timeout=15)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    updates = {}
    diem_moi = 0

    # LUỒNG 1: CÀO HYMETNET (CHỈ TỪ CHỐI THỜI GIAN QUÁ HẠN, LẤY MỌI CƯỜNG ĐỘ)
    print("\n[LUỒNG 1] Đang quét Hymetnet...")
    hymetnet_success = False
    try:
        res_h = requests.get(url_hymetnet, headers=headers_hymetnet, timeout=10)
        if res_h.status_code != 200:
            res_h = requests.get(proxy_hymetnet, headers=headers_hymetnet, timeout=20)
            
        if res_h.status_code == 200:
            raw_text = res_h.text
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            for block in valid_blocks:
                try:
                    # BỎ QUA BỘ LỌC CƯỜNG ĐỘ, CHỈ LẤY GIÁ TRỊ NẾU CÓ, KHÔNG CÓ THÌ GÁN 0
                    loaiset_m = re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    loaiset = int(loaiset_m.group(1)) if loaiset_m else 0
                    
                    giatri_m = re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    giatri = float(giatri_m.group(1)) if giatri_m else 0.0
                        
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    
                    if not (MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG):
                        continue
                        
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    giay_m = re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    giay = int(giay_m.group(1)) if giay_m else 0
                    
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=timezone.utc)
                    ts = dt.timestamp()
                    
                    # CHỈ LẤY SÉT TRONG 10 PHÚT (600 GIÂY) QUA
                    if current_ts - ts > 600: 
                        continue

                    lat_round = round(lat, 4)
                    lng_round = round(lng, 4)
                    ts_int = int(ts)
                    key = hashlib.md5(f"{ts_int}_{lat_round}_{lng_round}".encode()).hexdigest()
                    
                    if key not in db_data and key not in updates:
                        updates[key] = {"lat": lat, "lng": lng, "g": giatri, "t": ts_int, "l": loaiset}
                        db_data[key] = updates[key]
                        diem_moi += 1
                except Exception:
                    continue
            hymetnet_success = True
            print(f"✅ Hymetnet: Đã ghi nhận {diem_moi} điểm.")
        else:
            print(f"❌ Hymetnet lỗi HTTP {res_h.status_code}")
    except Exception as e:
        print(f"❌ Lỗi mạng Hymetnet: {e}")

    # LUỒNG 2: CÀO VAISALA (NẾU CẦN BỔ SUNG, BỎ QUA KIỂM TRA GIÁ TRỊ CƯỜNG ĐỘ)
    print("\n[LUỒNG 2] Đang quét Vaisala...")
    vaisala_success = False
    try:
        res_v = requests.get(api_url_vaisala, headers=headers_vaisala, timeout=15)
        if res_v.status_code == 200:
            raw_data = res_v.json()
            items = []
            
            if isinstance(raw_data, dict) and "features" in raw_data: items = raw_data["features"]
            elif isinstance(raw_data, dict) and "data" in raw_data: items = raw_data["data"]
            elif isinstance(raw_data, list): items = raw_data

            diem_v = 0
            for item in items:
                lat = lng = giatri = time_str = None
                loaiset = 0

                if "geometry" in item and "properties" in item:
                    geom = item.get("geometry", {})
                    props = item.get("properties", {})
                    coords = geom.get("coordinates", [])
                    if len(coords) >= 2: lng, lat = coords[0], coords[1]
                    giatri = abs(float(props.get("amplitude", 0)))
                    loaiset = props.get("type", 0)
                    time_str = props.get("timestamp", props.get("time"))
                else:
                    lat = item.get("lat") or item.get("latitude")
                    lng = item.get("lon") or item.get("longitude") or item.get("lng")
                    g_raw = item.get("amplitude") or item.get("peak_current") or item.get("current") or 0
                    giatri = abs(float(g_raw))
                    loaiset = item.get("type", 0)
                    time_str = item.get("timestamp") or item.get("time") or item.get("datetime")

                # Không lọc cường độ (g = 0 vẫn lấy), chỉ cần có tọa độ và thời gian
                if lat is None or lng is None or not time_str:
                    continue

                try:
                    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    ts = dt.timestamp()
                except:
                    try:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        ts = dt.timestamp()
                    except: continue

                # Chỉ lấy 10 phút (600 giây) qua
                if current_ts - ts > 600:
                    continue

                lat_round = round(float(lat), 4)
                lng_round = round(float(lng), 4)
                ts_int = int(ts)
                key = hashlib.md5(f"{ts_int}_{lat_round}_{lng_round}".encode()).hexdigest()
                
                if key not in db_data and key not in updates:
                    updates[key] = {"lat": float(lat), "lng": float(lng), "g": giatri, "t": ts_int, "l": int(loaiset)}
                    db_data[key] = updates[key] 
                    diem_v += 1
                    diem_moi += 1
                    
            vaisala_success = True
            print(f"✅ Vaisala: Bổ sung {diem_v} điểm.")
        elif res_v.status_code == 429:
            print("⚠️ Vaisala báo lỗi 429 (Chặn IP).")
    except Exception as e:
        print(f"❌ Lỗi Vaisala: {e}")

    # 3. DỌN SẠCH DỮ LIỆU CŨ QUÁ 2 GIỜ (7200 GIÂY)
    two_hours_ago = current_ts - 7200
    diem_xoa = 0
    for k, v in db_data.items():
        if v is None: continue
        t_val = v.get("t", 0)
        if float(t_val) < two_hours_ago:
            updates[k] = None 
            diem_xoa += 1

    # 4. ĐẨY DỮ LIỆU LÊN FIREBASE
    if updates:
        print(f"\n🔄 Đang đồng bộ {len(updates)} tác vụ lên Firebase Tức Thời...")
        try:
            res = requests.patch(FIREBASE_URL, json=updates, timeout=15)
            if res.status_code == 200: 
                print(f"✅ HOÀN TẤT! Ghi nhận {diem_moi} điểm mới. Xóa {diem_xoa} điểm cũ (>2h).")
            else:
                print(f"❌ Lỗi ghi Firebase: HTTP {res.status_code}")
        except Exception as e: 
            print(f"❌ Mất kết nối ghi Firebase: {e}")
    else:
        print("\n✅ Không có điểm sét mới nào trong 10 phút qua, và không có rác cần dọn.")

if __name__ == "__main__":
    crawl_lightning_data_realtime()
