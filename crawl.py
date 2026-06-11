import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG QUÉT KÉP V13 (ĐỒNG BỘ 2 FIREBASE SONG SONG)...")
    
    # 1. TẠO KHUNG THỜI GIAN LÙI 90 PHÚT
    now_utc = datetime.now(timezone.utc)
    past_utc = now_utc - timedelta(minutes=90)
    
    end_time = now_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    current_ts = int(now_utc.timestamp())

    # --- CẤU HÌNH API NGUỒN ---
    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"
    headers_hymetnet = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}

    api_url_vaisala = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )
    headers_vaisala = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    # --- CẤU HÌNH ĐƯỜNG DẪN 2 KHO FIREBASE ---
    FIREBASE_MAIN_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    FIREBASE_BACKUP_URL = "https://datasetweb-duphong-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 2. TẢI DỮ LIỆU LỊCH SỬ (CƠ CHẾ DỰ PHÒNG KHI ĐỌC)
    db_data = {}
    read_success = False
    
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase CHÍNH...")
        fb_response = requests.get(FIREBASE_MAIN_URL, timeout=25)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
            read_success = True
            print("✅ Tải bộ nhớ từ Firebase CHÍNH thành công.")
    except Exception as e:
        print(f"⚠️ Firebase CHÍNH lỗi hoặc hết hạn mức băng thông: {e}")

    # Nếu Firebase chính tèo, lập tức cứu viện bằng Firebase dự phòng
    if not read_success:
        try:
            print("🔄 Đang chuyển hướng sang đọc dữ liệu từ Firebase DỰ PHÒNG...")
            fb_response = requests.get(FIREBASE_BACKUP_URL, timeout=25)
            if fb_response.status_code == 200 and fb_response.json() is not None:
                db_data = fb_response.json()
                print("✅ Tải bộ nhớ từ Firebase DỰ PHÒNG thành công.")
        except Exception as e:
            print(f"❌ Thất bại: Cả 2 kho Firebase đều không thể truy cập: {e}")

    # =====================================================================
    # BỘ NÃO AI: XÂY DỰNG BẢN ĐỒ TÌM KIẾM KHÔNG GIAN - THỜI GIAN
    # =====================================================================
    recent_index = {}
    for k, v in db_data.items():
        if v is None: continue
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
                print(f"   [THAY THẾ] Phát hiện điểm Bóng ma. Đang lên lịch xóa để đè điểm Xịn từ {nguon}...")
                
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
                print(f"   [THÊM MỚI] Ghi nhận 1 tia sét mới từ {nguon}.")

    # =====================================================================
    # LUỒNG 1: HYMETNET
    # =====================================================================
    print("\n[LUỒNG 1] Đang quét dữ liệu Hymetnet...")
    diem_quet_h = 0
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
                    if current_ts - ts <= 5400: # Lọc khung 90 phút (5400 giây)
                        diem_quet_h += 1
                        process_strike(lat, lng, giatri, loaiset, ts, "Hymetnet")
                except: continue
            print(f"✅ Xong luồng Hymetnet: Quét được {diem_quet_h} điểm sét.")
    except Exception as e: print(f"❌ Lỗi Hymetnet: {e}")

    # =====================================================================
    # LUỒNG 2: EVNTOOLS (VAISALA)
    # =====================================================================
    print("\n[LUỒNG 2] Đang quét EVNTools (Vaisala)...")
    diem_quet_v = 0
    for attempt in range(2):
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
                    loaiset = p.get("type", 0)
                    nguon = p.get("source", "Vaisala").title()
                    
                    try:
                        dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        ts = dt.timestamp()
                    except:
                        try: ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                        except: continue
                        
                    diem_quet_v += 1
                    process_strike(lat, lng, giatri, loaiset, ts, nguon)
                print(f"✅ Xong luồng EVNTools: Quét được {diem_quet_v} điểm sét.")
                break
            elif res_v.status_code == 429:
                print("⚠️ Máy chủ Vaisala báo lỗi 429 (Bị chặn IP). Bỏ qua luồng 2.")
                break
            else:
                print(f"❌ Luồng EVNTools lỗi HTTP {res_v.status_code}")
                break
        except Exception as e: 
            print(f"⚠️ Lỗi kết nối EVNTools: {e}")
            time.sleep(3)

    # =====================================================================
    # DỌN DẸP RÁC 14 NGÀY
    # =====================================================================
    seven_days_ago = current_ts - 1209600
    diem_xoa = 0
    for k, v in db_data.items():
        if v is None: continue
        ts_val = v.get("timestamp", 0)
        if isinstance(ts_val, str):
            try: ts_val = datetime.fromisoformat(ts_val.replace("Z", "+00:00")).timestamp()
            except: ts_val = 0 
        if float(ts_val) < seven_days_ago:
            updates[k] = None 
            diem_xoa += 1

    # =====================================================================
    # ĐẨY DỮ LIỆU ĐỒNG THỜI LÊN CẢ 2 FIREBASE
    # =====================================================================
    print("\n---------------------------------------------------")
    print("📊 TỔNG KẾT VÀ TIẾN HÀNH ĐỒNG BỘ SONG SONG:")
    if updates:
        # Lệnh bắn lên kho CHÍNH
        try:
            print(f"🔄 Đang đẩy {len(updates)} tác vụ lên Firebase CHÍNH...")
            requests.patch(FIREBASE_MAIN_URL, json=updates, timeout=40)
            print("✅ Ghi Firebase CHÍNH hoàn tất.")
        except Exception as e:
            print(f"❌ Firebase CHÍNH lỗi hoặc chặn ghi (Có thể hết quota): {e}")

        # Lệnh bắn lên kho DỰ PHÒNG
        try:
            print(f"🔄 Đang đẩy {len(updates)} tác vụ lên Firebase DỰ PHÒNG...")
            requests.patch(FIREBASE_BACKUP_URL, json=updates, timeout=40)
            print("✅ Ghi Firebase DỰ PHÒNG hoàn tất.")
        except Exception as e:
            print(f"❌ Không thể đồng bộ sang Firebase DỰ PHÒNG: {e}")
            
        print(f"\n📊 KẾT QUẢ SÀNG LỌC: Thêm mới {diem_moi} điểm. Thay thế {diem_thay_the} điểm Bóng ma. Dọn {diem_xoa} rác cũ.")
    else:
        print(f"✅ Hệ thống đã quét xong. Toàn bộ dữ liệu sạch đã tồn tại trên các kho, không cần cập nhật thêm.")
    print("---------------------------------------------------")

if __name__ == "__main__":
    crawl_lightning_data()
