import requests
import json
import time
import sys
import re
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    print("🚀 KHỞI ĐỘNG HỆ THỐNG QUÉT KÉP (NGUỒN CHÍNH: HYMETNET | NGUỒN PHỤ: VAISALA)...")
    
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

    # CẤU HÌNH FIREBASE WEB
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
    diem_moi = 0
    diem_cap_nhat = 0

    # =====================================================================
    # LUỒNG 1 (CHÍNH): CÀO DỮ LIỆU TỪ HYMETNET
    # =====================================================================
    print("\n[LUỒNG 1 - CHÍNH] Đang kết nối máy chủ Tổng cục KTTV (Hymetnet)...")
    hymetnet_success = False
    try:
        res_h = requests.get(url_hymetnet, headers=headers_hymetnet, timeout=15)
        if res_h.status_code != 200:
            print("Kết nối trực tiếp thất bại, dùng Proxy để lách luật...")
            res_h = requests.get(proxy_hymetnet, headers=headers_hymetnet, timeout=30)
            
        if res_h.status_code == 200:
            raw_text = res_h.text
            blocks = re.findall(r'\{[^{}]*\}', raw_text)
            valid_blocks = [b for b in blocks if 'lat' in b.lower() and 'lng' in b.lower() and 'nam' in b.lower()]
            
            diem_hymetnet = 0
            for block in valid_blocks:
                try:
                    lat = float(re.search(r'["\']?lat["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    lng = float(re.search(r'["\']?lng["\']?\s*:\s*([-\d.]+)', block, re.IGNORECASE).group(1))
                    if lat > lng: lat, lng = lng, lat
                    
                    # Cắt khung địa lý Lào Cai - Yên Bái
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
                    
                    # Chỉ lấy dữ liệu trong 45 phút gần đây (45 phút = 2700 giây)
                    if current_ts - ts > 2700: 
                        continue

                    key = hashlib.md5(f"{ts}_{lat}_{lng}".encode()).hexdigest()
                    
                    if key not in db_data:
                        updates[key] = {
                            "lat": lat, "lng": lng, "giatri": giatri,
                            "loaiset": loaiset, "timestamp": ts,
                            "src": "Hymetnet", "is_new_format": True
                        }
                        db_data[key] = updates[key]
                        diem_moi += 1
                        diem_hymetnet += 1
                except Exception:
                    continue
            hymetnet_success = True
            print(f"✅ Luồng CHÍNH (Hymetnet) hoạt động tốt. Tìm thấy {diem_hymetnet} điểm sét.")
        else:
            print(f"❌ Luồng CHÍNH (Hymetnet) báo lỗi HTTP {res_h.status_code}")
    except Exception as e:
        print(f"❌ Lỗi mạng Hymetnet: {e}")


    # =====================================================================
    # LUỒNG 2 (PHỤ): CÀO DỮ LIỆU TỪ VAISALA (BỔ SUNG/DỰ PHÒNG)
    # =====================================================================
    print("\n[LUỒNG 2 - PHỤ] Đang quét bổ sung từ máy chủ EVNTools (Vaisala)...")
    vaisala_success = False
    for attempt in range(2):
        try:
            res_v = requests.get(api_url_vaisala, headers=headers_vaisala, timeout=20)
            if res_v.status_code == 200:
                features = res_v.json().get("features", [])
                diem_vaisala = 0
                
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

                    key = hashlib.md5(f"{ts}_{lat}_{lng}".encode()).hexdigest()
                    
                    # NẾU CÓ SẴN (Do Hymetnet lấy trước đó) -> KIỂM TRA CẬP NHẬT CƯỜNG ĐỘ
                    if key in db_data:
                        old_giatri = db_data[key].get("giatri", 0)
                        if (old_giatri == 0 or old_giatri == 0.0) and giatri > 0:
                            rec = db_data[key].copy()
                            rec["giatri"] = giatri
                            # Gắn đè nhãn nguồn sang Vaisala nếu nó cập nhật được độ nét
                            rec["src"] = "Hymetnet + Vaisala" 
                            updates[key] = rec
                            db_data[key] = rec
                            diem_cap_nhat += 1
                    else:
                        # NẾU HYMETNET BỎ SÓT -> VAISALA BỔ SUNG VÀO
                        updates[key] = {
                            "lat": lat, "lng": lng, "giatri": giatri,
                            "loaiset": loaiset, "timestamp": ts,
                            "src": nguon, "is_new_format": True
                        }
                        db_data[key] = updates[key] 
                        diem_moi += 1
                        diem_vaisala += 1
                        
                vaisala_success = True
                print(f"✅ Luồng PHỤ (Vaisala) quét xong. Bổ sung thêm {diem_vaisala} điểm bị sót.")
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

    # Đánh giá tổng quan 2 luồng
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
            print(f"✅ HOÀN TẤT VẬN HÀNH! Đã gắp mới {diem_moi} điểm sét. Cập nhật cường độ cho {diem_cap_nhat} điểm. Đã dọn {diem_xoa} rác.")
        else:
            print(f"❌ Lỗi Firebase: {patch_response.text}")
            sys.exit(1)
    else:
        print("\n✅ Hệ thống quét xong. Không có xung sét mới trong 45 phút qua.")

if __name__ == "__main__":
    crawl_lightning_data()
