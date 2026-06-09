import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG QUÉT KÉP (CHỐNG GHI ĐÈ | NGUỒN CHÍNH: HYMETNET)...")
    
    # 1. TẠO KHUNG THỜI GIAN LÙI 45 PHÚT 
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=45)
    
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    current_ts = int(time.time())

    # --- CẤU HÌNH API NGUỒN CHÍNH (HYMETNET) ---
    url_hymetnet = f"http://hymetnet.gov.vn/lightningmaps/?_t={current_ts}"
    proxy_hymetnet = f"https://api.allorigins.win/raw?url={url_hymetnet}&disableCache=true"
    headers_hymetnet = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache"
    }

    # --- CẤU HÌNH API NGUỒN PHỤ (VAISALA/EVNTOOLS) ---
    api_url_vaisala = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )
    headers_vaisala = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

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

    updates = {}
    diem_moi_hymetnet = 0
    diem_moi_vaisala = 0
    diem_bi_trung = 0 # Biến đếm số điểm bị loại bỏ do trùng lặp

    # =====================================================================
    # LUỒNG 1 (CHÍNH): CÀO DỮ LIỆU TỪ HYMETNET
    # =====================================================================
    print("\n[LUỒNG 1 - CHÍNH] Đang kết nối máy chủ Tổng cục KTTV (Hymetnet)...")
    hymetnet_success = False
    try:
        res_h = requests.get(url_hymetnet, headers=headers_hymetnet, timeout=15)
        if res_h.status_code != 200:
            res_h = requests.get(proxy_hymetnet, headers=headers_hymetnet, timeout=30)
            
        if res_h.status_code == 200:
            raw_text = res_h.text
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            for block in valid_blocks:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    
                    if not (21.40 <= lat <= 22.60 and 103.70 <= lng <= 105.30):
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
                    
                    dt = datetime(nam, thang, ngay, gio, phut, giay, tzinfo=timezone.utc)
                    ts = dt.timestamp()
                    
                    if current_ts - ts > 2700: 
                        continue

                    # THUẬT TOÁN CHỐNG TRÙNG LẶP: Làm tròn tọa độ 4 số thập phân (sai số ~11m)
                    lat_round = round(lat, 4)
                    lng_round = round(lng, 4)
                    ts_int = int(ts)
                    key = hashlib.md5(f"{ts_int}_{lat_round}_{lng_round}".encode()).hexdigest()
                    
                    if key not in db_data:
                        updates[key] = {
                            "lat": lat, "lng": lng, "giatri": giatri,
                            "loaiset": loaiset, "timestamp": ts,
                            "src": "Hymetnet", "is_new_format": True
                        }
                        db_data[key] = updates[key]
                        diem_moi_hymetnet += 1
                except Exception:
                    continue
            hymetnet_success = True
            print(f"✅ Luồng CHÍNH (Hymetnet) hoạt động tốt. Lấy thành công {diem_moi_hymetnet} điểm.")
        else:
            print(f"❌ Luồng CHÍNH (Hymetnet) báo lỗi HTTP {res_h.status_code}")
    except Exception as e:
        print(f"❌ Lỗi mạng Hymetnet: {e}")


    # =====================================================================
    # LUỒNG 2 (PHỤ): CÀO DỮ LIỆU TỪ VAISALA (CHỈ BỔ SUNG NẾU CHƯA CÓ)
    # =====================================================================
    print("\n[LUỒNG 2 - PHỤ] Đang quét bổ sung từ máy chủ EVNTools (Vaisala)...")
    vaisala_success = False
    for attempt in range(2):
        try:
            res_v = requests.get(api_url_vaisala, headers=headers_vaisala, timeout=20)
            if res_v.status_code == 200:
                features = res_v.json().get("features", [])
                
                for feature in features:
                    props = feature.get("properties", {})
                    geom = feature.get("geometry", {})
                    if not geom or not props: continue
                    
                    coords = geom.get("coordinates", [])
                    if len(coords) < 2: continue
                    lng, lat = coords[0], coords[1]
                    
                    loaiset = props.get("type", 0) 
                    giatri = abs(float(props.get("amplitude", 0)))
                    nguon = props.get("source", "Vaisala").title()
                    time_str = props.get("timestamp", props.get("time"))
                    
                    try:
                        dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        ts = dt.timestamp()
                    except:
                        try:
                            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                            ts = dt.timestamp()
                        except: continue

                    # Dùng chung thuật toán làm tròn để khớp với Luồng 1
                    lat_round = round(lat, 4)
                    lng_round = round(lng, 4)
                    ts_int = int(ts)
                    key = hashlib.md5(f"{ts_int}_{lat_round}_{lng_round}".encode()).hexdigest()
                    
                    # CƠ CHẾ CHỐNG GHI ĐÈ: Nếu đã có khóa này rồi thì bỏ qua hoàn toàn
                    if key in db_data or key in updates:
                        diem_bi_trung += 1
                        continue
                    else:
                        # NẾU HYMETNET BỎ SÓT -> VAISALA MỚI ĐƯỢC PHÉP BỔ SUNG VÀO
                        updates[key] = {
                            "lat": lat, "lng": lng, "giatri": giatri,
                            "loaiset": loaiset, "timestamp": ts,
                            "src": nguon, "is_new_format": True
                        }
                        db_data[key] = updates[key] 
                        diem_moi_vaisala += 1
                        
                vaisala_success = True
                print(f"✅ Luồng PHỤ (Vaisala) quét xong. Bổ sung {diem_moi_vaisala} điểm sót. (Đã chặn ghi đè {diem_bi_trung} điểm trùng lặp).")
                break
            elif res_v.status_code == 429:
                print("⚠️ Máy chủ Vaisala báo lỗi 429 (Bị chặn IP). Bỏ qua luồng phụ.")
                break
            else:
                print(f"❌ Luồng PHỤ (Vaisala) lỗi HTTP {res_v.status_code}")
                break
        except Exception as e:
            print(f"Lỗi kết nối Vaisala: {e}")
            time.sleep(3)

    if not hymetnet_success and not vaisala_success:
        print("\n🚨 THẤT BẠI TRẦM TRỌNG: Cả 2 máy chủ nguồn đều sập hoặc từ chối kết nối!")
        sys.exit(1)

    # =====================================================================
    # 3. DỌN SẠCH DỮ LIỆU CŨ QUÁ 7 NGÀY
    # =====================================================================
    seven_days_ago = current_ts - 604800
    diem_xoa = 0
    for k, v in db_data.items():
        ts_val = v.get("timestamp", 0)
        if isinstance(ts_val, str):
            try:
                dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                ts_val = dt.timestamp()
            except:
                ts_val = 0 
        
        if float(ts_val) < seven_days_ago:
            updates[k] = None 
            diem_xoa += 1

    # =====================================================================
    # 4. ĐẨY DỮ LIỆU LÊN FIREBASE (PATCH)
    # =====================================================================
    if updates:
        print(f"\nĐang đồng bộ gói dữ liệu PATCH lên Firebase Web ({len(updates)} tác vụ)...")
        patch_response = requests.patch(FIREBASE_URL, json=updates, timeout=60)
        if patch_response.status_code == 200:
            tong_moi = diem_moi_hymetnet + diem_moi_vaisala
            print(f"✅ HOÀN TẤT VẬN HÀNH! Đã lưu tổng cộng {tong_moi} điểm sét mới. Đã dọn {diem_xoa} rác.")
        else:
            print(f"❌ Lỗi Firebase: {patch_response.text}")
            sys.exit(1)
    else:
        print("\n✅ Hệ thống quét xong. Không có xung sét mới trong 45 phút qua.")

if __name__ == "__main__":
    crawl_lightning_data()
