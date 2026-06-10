import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG QUÉT KÉP V9 (THAY THẾ SÉT LÀM TRÒN BẰNG SÉT CHUẨN)...")
    
    # 1. TẠO KHUNG THỜI GIAN LÙI 45 PHÚT ĐỂ VÉT SẠCH CẢ DỮ LIỆU ĐÃ LÀM NÉT
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=45)
    
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    current_ts = int(time.time())

    # --- CẤU HÌNH API ---
    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"
    headers_hymetnet = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}

    api_url_vaisala = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )
    headers_vaisala = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    FIREBASE_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 2. TẢI DỮ LIỆU CŨ TỪ FIREBASE
    db_data = {}
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase Web...")
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    # =====================================================================
    # BỘ NÃO AI: XÂY DỰNG BẢN ĐỒ TÌM KIẾM KHÔNG GIAN - THỜI GIAN
    # =====================================================================
    recent_index = {}
    for k, v in db_data.items():
        ts_val = v.get("timestamp", 0)
        if isinstance(ts_val, str):
            try: ts_val = datetime.fromisoformat(ts_val.replace("Z", "+00:00")).timestamp()
            except: ts_val = 0
            
        # Chỉ quét các mốc trong 2 tiếng gần nhất để đối chiếu
        if current_ts - float(ts_val) <= 7200:
            lat_r = round(float(v.get("lat", 0)), 4)
            lng_r = round(float(v.get("lng", 0)), 4)
            loc_key = f"{lat_r}_{lng_r}"
            
            if loc_key not in recent_index:
                recent_index[loc_key] = []
            recent_index[loc_key].append({'key': k, 'ts': float(ts_val), 'g': float(v.get("giatri", 0))})

    updates = {}
    diem_moi = 0
    diem_thay_the = 0 # Điểm dỏm bị xóa và thay bằng điểm xịn

    # HÀM XỬ LÝ LÕI: QUYẾT ĐỊNH XÓA, THÊM HAY BỎ QUA
    def process_strike(lat, lng, giatri, loaiset, ts, nguon):
        nonlocal diem_moi, diem_thay_the
        
        lat_round = round(lat, 4)
        lng_round = round(lng, 4)
        ts_int = int(ts)
        new_key = hashlib.md5(f"{ts_int}_{lat_round}_{lng_round}".encode()).hexdigest()
        
        loc_key = f"{lat_round}_{lng_round}"
        is_duplicate = False
        keys_to_delete = []

        if loc_key in recent_index:
            for old_pt in recent_index[loc_key]:
                # Nếu cùng vị trí và cách nhau dưới 35 phút -> Chắc chắn là cùng 1 tia sét
                if abs(ts_int - old_pt['ts']) <= 2100: 
                    old_g = old_pt['g']
                    old_ts_is_rounded = (old_pt['ts'] % 60 == 0) # Kiểm tra xem giờ cũ có bị làm tròn chẵn phút không
                    new_ts_is_exact = (ts_int % 60 != 0) # Giờ mới có giây lẻ không
                    
                    # QUY LUẬT 1: Cũ không có cường độ (0) mà mới CÓ cường độ -> THAY THẾ!
                    if (old_g == 0 or old_g == 0.0) and giatri > 0:
                        keys_to_delete.append(old_pt['key'])
                        continue # Đánh dấu xóa cũ, tiếp tục để thêm mới
                        
                    # QUY LUẬT 2: Cũ bị làm tròn thời gian, mới có giây chính xác -> THAY THẾ!
                    elif old_ts_is_rounded and new_ts_is_exact:
                        keys_to_delete.append(old_pt['key'])
                        continue 
                        
                    # QUY LUẬT 3: Nếu điểm cũ đã xịn rồi (Có cường độ, có thời gian lẻ) -> BỎ QUA MỚI!
                    else:
                        is_duplicate = True
                        break 

        if not is_duplicate or keys_to_delete:
            # Gửi lệnh xóa các điểm "Bóng ma" lên Firebase
            for k_del in keys_to_delete:
                updates[k_del] = None 
                diem_thay_the += 1
                
            # Ghi nhận điểm Xịn
            updates[new_key] = {
                "lat": lat, "lng": lng, "giatri": giatri,
                "loaiset": loaiset, "timestamp": ts_int,
                "src": nguon, "is_new_format": True
            }
            
            # Cập nhật lại vào bộ nhớ tạm để các tia sét tiếp theo không dẫm lên
            if loc_key not in recent_index:
                recent_index[loc_key] = []
            recent_index[loc_key].append({'key': new_key, 'ts': ts_int, 'g': giatri})
            
            if not keys_to_delete:
                diem_moi += 1

    # =====================================================================
    # LUỒNG 1: HYMETNET
    # =====================================================================
    print("\n[LUỒNG 1] Quét Hymetnet...")
    try:
        res_h = requests.get(url_hymetnet, headers=headers_hymetnet, timeout=15)
        if res_h.status_code != 200: res_h = requests.get(proxy_hymetnet, headers=headers_hymetnet, timeout=30)
        if res_h.status_code == 200:
            blocks = re.findall(r'\{[^{}]*\}', res_h.text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            for block in valid_blocks:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    if not (21.40 <= lat <= 22.60 and 103.70 <= lng <= 105.30): continue
                        
                    g_m = re.search(r'["\']?giatri["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE)
                    giatri = float(g_m.group(1)) if g_m else 0.0
                    l_m = re.search(r'["\']?loaiset["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    loaiset = int(l_m.group(1)) if l_m else 0
                    
                    nam = int(re.search(r'["\']?nam["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    thang = int(re.search(r'["\']?thang["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    ngay = int(re.search(r'["\']?ngay["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    gio = int(re.search(r'["\']?gio["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    phut = int(re.search(r'["\']?phut["\']?\s*:\s*(\d+)', block, re.IGNORECASE).group(1))
                    giay_m = re.search(r'["\']?giay["\']?\s*:\s*(\d+)', block, re.IGNORECASE)
                    giay = int(giay_m.group(1)) if giay_m else 0
                    
                    ts = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=timezone.utc).timestamp()
                    if current_ts - ts <= 2700: 
                        process_strike(lat, lng, giatri, loaiset, ts, "Hymetnet")
                except: continue
    except Exception as e: print(f"Lỗi Hymetnet: {e}")

    # =====================================================================
    # LUỒNG 2: VAISALA
    # =====================================================================
    print("[LUỒNG 2] Quét Vaisala...")
    for _ in range(2):
        try:
            res_v = requests.get(api_url_vaisala, headers=headers_vaisala, timeout=20)
            if res_v.status_code == 200:
                features = res_v.json().get("features", [])
                for f in features:
                    p = f.get("properties", {})
                    g = f.get("geometry", {})
                    if not g or not p: continue
                    coords = g.get("coordinates", [])
                    if len(coords) < 2: continue
                    lng, lat = coords[0], coords[1]
                    giatri = abs(float(p.get("amplitude", 0)))
                    ts_str = p.get("timestamp", p.get("time"))
                    try:
                        dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        ts = dt.timestamp()
                    except:
                        try: ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                        except: continue
                    process_strike(lat, lng, giatri, p.get("type", 0), ts, p.get("source", "Vaisala").title())
                break
        except: time.sleep(3)

    # =====================================================================
    # DỌN DẸP RÁC 7 NGÀY
    # =====================================================================
    seven_days_ago = current_ts - 604800
    diem_xoa = 0
    for k, v in db_data.items():
        ts_val = v.get("timestamp", 0)
        if isinstance(ts_val, str):
            try: ts_val = datetime.fromisoformat(ts_val.replace("Z", "+00:00")).timestamp()
            except: ts_val = 0 
        if float(ts_val) < seven_days_ago:
            updates[k] = None 
            diem_xoa += 1

    # ĐẨY DỮ LIỆU
    if updates:
        print(f"\nĐang đồng bộ ({len(updates)} tác vụ PATCH)...")
        patch_response = requests.patch(FIREBASE_URL, json=updates, timeout=60)
        if patch_response.status_code == 200:
            print(f"✅ HOÀN TẤT! Nạp {diem_moi} điểm mới. XÓA {diem_thay_the} điểm 'Bóng ma' để đè điểm Xịn lên. Dọn {diem_xoa} rác 7 ngày.")
        else:
            print("❌ Lỗi Firebase")
            sys.exit(1)
    else:
        print("\n✅ Không có biến động dữ liệu.")

if __name__ == "__main__":
    crawl_lightning_data()
