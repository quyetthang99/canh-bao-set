import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

# =========================================================================
# HÀM KIỂM TRA TRÙNG LẶP THÔNG MINH (LỌC SAI SỐ GIỮA CÁC NGUỒN SÉT)
# =========================================================================
def kiem_tra_trung_lap(new_lat, new_lng, new_ts, db_data, updates):
    """
    So sánh điểm sét mới với kho dữ liệu.
    Bỏ qua những điểm đã bị đánh dấu xóa (updates[k] = None)
    """
    for k, v in db_data.items():
        if v is None or updates.get(k) is None: 
            continue
        old_lat = v.get("lat", 0)
        old_lng = v.get("lng", 0)
        old_ts = v.get("t", 0)
        
        if abs(new_ts - old_ts) <= 5 and abs(new_lat - old_lat) <= 0.002 and abs(new_lng - old_lng) <= 0.002:
            return True # Đã tồn tại điểm sét này rồi, báo Trùng!
    return False


def crawl_lightning_data_realtime():
    print("🚀 KHỞI ĐỘNG BOT TỨC THỜI: QUÉT SÉT (10 PHÚT QUA)")
    
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
    
    # 2. TẢI BỘ NHỚ TỪ FIREBASE 
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

    # =========================================================================
    # BƯỚC 2.5: DỌN DẸP CÁC ĐIỂM TRÙNG LẶP ĐÃ TỒN TẠI TRÊN FIREBASE
    # =========================================================================
    print("\n[LỌC RÁC] Đang quét các điểm bị trùng có sẵn trên Firebase...")
    diem_trung_cu = 0
    keys_to_keep = []
    
    for k1, v1 in db_data.items():
        if v1 is None: continue
        is_duplicate = False
        
        # So sánh với các điểm đã quyết định giữ lại
        for k2 in keys_to_keep:
            v2 = db_data[k2]
            # Nếu lệch thời gian < 5s và tọa độ < 200m thì coi là Trùng
            if abs(v1["t"] - v2["t"]) <= 5 and abs(v1["lat"] - v2["lat"]) <= 0.002 and abs(v1["lng"] - v2["lng"]) <= 0.002:
                is_duplicate = True
                break
                
        if is_duplicate:
            updates[k1] = None  # Đánh dấu để XÓA trên Firebase
            diem_trung_cu += 1
        else:
            keys_to_keep.append(k1)
            
    if diem_trung_cu > 0:
        print(f"🧹 Đã phát hiện và sẽ xóa {diem_trung_cu} điểm sét trùng lặp lưu từ trước.")
    else:
        print("✨ Cơ sở dữ liệu Firebase hiện tại đang sạch sẽ, không có điểm trùng.")

    # LUỒNG 1: CÀO HYMETNET
    print("\n[LUỒNG 1] Đang quét Hymetnet...")
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
                    
                    if current_ts - ts > 600: 
                        continue

                    lat_round = round(lat, 4)
                    lng_round = round(lng, 4)
                    ts_int = int(ts)
                    key = hashlib.md5(f"{ts_int}_{lat_round}_{lng_round}".encode()).hexdigest()
                    
                    # Kiểm tra không bị trùng với Firebase VÀ không bị trùng với updates
                    if key not in db_data and updates.get(key) is not None:
                        if not kiem_tra_trung_lap(lat, lng, ts_int, db_data, updates):
                            updates[key] = {"lat": lat, "lng": lng, "g": giatri, "t": ts_int, "l": loaiset, "src": "Hymetnet"}
                            db_data[key] = updates[key] 
                            diem_moi += 1
                except Exception:
                    continue
            print(f"✅ Hymetnet: Đã ghi nhận {diem_moi} điểm mới (Đã lọc trùng).")
        else:
            print(f"❌ Hymetnet lỗi HTTP {res_h.status_code}")
    except Exception as e:
        print(f"❌ Lỗi mạng Hymetnet: {e}")

    # LUỒNG 2: CÀO VAISALA
    print("\n[LUỒNG 2] Đang quét Vaisala...")
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

                if current_ts - ts > 600:
                    continue

                lat_float = float(lat)
                lng_float = float(lng)
                ts_int = int(ts)
                key = hashlib.md5(f"{ts_int}_{round(lat_float, 4)}_{round(lng_float, 4)}".encode()).hexdigest()
                
                if key not in db_data and updates.get(key) is not None:
                    if not kiem_tra_trung_lap(lat_float, lng_float, ts_int, db_data, updates):
                        updates[key] = {"lat": lat_float, "lng": lng_float, "g": giatri, "t": ts_int, "l": int(loaiset), "src": "Vaisala"}
                        db_data[key] = updates[key]
                        diem_v += 1
                        diem_moi += 1
                    
            print(f"✅ Vaisala: Bổ sung {diem_v} điểm mới (Đã lọc trùng).")
        elif res_v.status_code == 429:
            print("⚠️ Vaisala báo lỗi 429 (Chặn IP).")
    except Exception as e:
        print(f"❌ Lỗi Vaisala: {e}")

    # 3. DỌN SẠCH DỮ LIỆU CŨ QUÁ 2 GIỜ (7200 GIÂY)
    two_hours_ago = current_ts - 7200
    diem_xoa_cu = 0
    for k, v in db_data.items():
        if v is None or k in updates: continue
        t_val = v.get("t", 0)
        if float(t_val) < two_hours_ago:
            updates[k] = None 
            diem_xoa_cu += 1

    # 4. ĐẨY DỮ LIỆU LÊN FIREBASE
    if updates:
        print(f"\n🔄 Đang đồng bộ {len(updates)} tác vụ lên Firebase Tức Thời...")
        try:
            res = requests.patch(FIREBASE_URL, json=updates, timeout=15)
            if res.status_code == 200: 
                print(f"✅ HOÀN TẤT! Ghi nhận {diem_moi} điểm mới. Đã dọn dẹp {diem_xoa_cu} điểm cũ và {diem_trung_cu} điểm trùng lặp.")
            else:
                print(f"❌ Lỗi ghi Firebase: HTTP {res.status_code}")
        except Exception as e: 
            print(f"❌ Mất kết nối ghi Firebase: {e}")
    else:
        print("\n✅ Không có điểm sét mới nào trong 10 phút qua, và không có rác cần dọn.")

if __name__ == "__main__":
    crawl_lightning_data_realtime()
