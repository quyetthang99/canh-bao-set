import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG QUÉT KÉP V10 (NGUỒN 1: HYMETNET | NGUỒN 2: EVN NLDC A0)...")
    
    # 1. TẠO KHUNG THỜI GIAN
    now_utc = datetime.now(timezone.utc)
    past_utc = now_utc - timedelta(minutes=45)
    current_ts = int(now_utc.timestamp())

    # --- CẤU HÌNH API NGUỒN 1 (HYMETNET) ---
    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"
    headers_hymetnet = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}

    # --- CẤU HÌNH API NGUỒN 2 (EVN NLDC A0) ---
    # Chuyển đổi sang giờ Việt Nam để gọi API NLDC
    now_vn = now_utc + timedelta(hours=7)
    past_vn = past_utc + timedelta(hours=7)
    
    st_nldc = past_vn.strftime("%m/%d/%Y %H:%M:%S").replace(" ", "%20")
    et_nldc = now_vn.strftime("%m/%d/%Y %H:%M:%S").replace(" ", "%20")
    
    # Polygon khoanh vùng khu vực Tây Bắc theo đúng API bác bắt được
    poly_nldc = "POLYGON((102.15968874336798%2019.872389109859633,106.99367311837037%2019.872389109859633,106.99367311837037%2022.950557561116803,102.15968874336798%2022.950557561116803,102.15968874336798%2019.872389109859633))"
    
    api_url_nldc = (
        f"https://weather.nldc.evn.vn/a0services/rest/gsv_data/dulieuset?"
        f"starttime={st_nldc}&endtime={et_nldc}&fields=thoigian,x,y,cuongdo,distance"
        f"&polygon={poly_nldc}&_dc={int(time.time()*1000)}&start=0&limit=5000&page=1"
    )
    headers_nldc = {"User-Agent": "Mozilla/5.0"}

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
            
        if current_ts - float(ts_val) <= 7200:
            lat_r = round(float(v.get("lat", 0)), 4)
            lng_r = round(float(v.get("lng", 0)), 4)
            loc_key = f"{lat_r}_{lng_r}"
            
            if loc_key not in recent_index:
                recent_index[loc_key] = []
            recent_index[loc_key].append({'key': k, 'ts': float(ts_val), 'g': float(v.get("giatri", 0))})

    updates = {}
    diem_moi = 0
    diem_thay_the = 0

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
                if abs(ts_int - old_pt['ts']) <= 2100: 
                    old_g = old_pt['g']
                    old_ts_is_rounded = (old_pt['ts'] % 60 == 0) 
                    new_ts_is_exact = (ts_int % 60 != 0) 
                    
                    if (old_g == 0 or old_g == 0.0) and giatri != 0:
                        keys_to_delete.append(old_pt['key'])
                        continue 
                    elif old_ts_is_rounded and new_ts_is_exact:
                        keys_to_delete.append(old_pt['key'])
                        continue 
                    else:
                        is_duplicate = True
                        break 

        if not is_duplicate or keys_to_delete:
            for k_del in keys_to_delete:
                updates[k_del] = None 
                diem_thay_the += 1
                
            updates[new_key] = {
                "lat": lat, "lng": lng, "giatri": giatri,
                "loaiset": loaiset, "timestamp": ts_int,
                "src": nguon, "is_new_format": True
            }
            
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
            print("✅ Xong luồng Hymetnet.")
    except Exception as e: print(f"Lỗi Hymetnet: {e}")

    # =====================================================================
    # LUỒNG 2: EVN NLDC (A0)
    # =====================================================================
    print("\n[LUỒNG 2] Quét EVN NLDC (A0)...")
    for _ in range(2):
        try:
            res_n = requests.get(api_url_nldc, headers=headers_nldc, timeout=20)
            if res_n.status_code == 200:
                features = res_n.json().get("searchResult", [])
                for item in features:
                    try:
                        lat = float(item.get("y", 0))
                        lng = float(item.get("x", 0))
                        if not (21.40 <= lat <= 22.60 and 103.70 <= lng <= 105.30): continue
                        
                        giatri = float(item.get("cuongdo", 0))
                        time_str = item.get("thoigian", "") # VD: "6/9/2026 8:11:27 PM"
                        
                        # Chuyển đổi định dạng giờ của NLDC (Giờ VN) sang Giờ Quốc Tế (UTC)
                        try:
                            dt_vn = datetime.strptime(time_str, "%m/%d/%Y %I:%M:%S %p")
                        except ValueError:
                            # Dự phòng nếu API trả về 24h format
                            dt_vn = datetime.strptime(time_str, "%m/%d/%Y %H:%M:%S")
                            
                        dt_utc = dt_vn.replace(tzinfo=timezone(timedelta(hours=7))).astimezone(timezone.utc)
                        ts = dt_utc.timestamp()
                        
                        # Dữ liệu của A0 chủ yếu là sét đánh đất (0)
                        loaiset = 0 
                        
                        process_strike(lat, lng, giatri, loaiset, ts, "EVN NLDC")
                    except: continue
                print(f"✅ Xong luồng EVN NLDC.")
                break
        except Exception as e: 
            print(f"Lỗi kết nối NLDC: {e}")
            time.sleep(3)

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
            print(f"✅ HOÀN TẤT! Nạp {diem_moi} điểm mới. XÓA & THAY THẾ {diem_thay_the} điểm 'Bóng ma'. Dọn {diem_xoa} rác 7 ngày.")
        else:
            print("❌ Lỗi Firebase")
            sys.exit(1)
    else:
        print("\n✅ Không có biến động dữ liệu.")

if __name__ == "__main__":
    crawl_lightning_data()
