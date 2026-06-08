import requests
import json
import time
import sys
import hashlib
from datetime import datetime, timezone, timedelta

def crawl_lightning_data():
    # 1. TỰ ĐỘNG TẠO KHUNG THỜI GIAN (Quét dữ liệu trong 10 phút gần nhất)
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=10)
    
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_time = past.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # 2. ĐƯỜNG DẪN API VAISALA (Sử dụng chính xác dải tọa độ dọn sẵn khu vực của bác)
    api_url = (
        f"https://evntools.com/api/lightning/geojson?start_time={start_time}&end_time={end_time}"
        f"&limit=50000&min_lat=21.4543&max_lat=22.5379&min_lon=103.7878&max_lon=105.2957"
    )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    # Giữ nguyên đường dẫn kho lưu trữ Firebase Web của bác
    FIREBASE_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 3. TẢI DỮ LIỆU LỊCH SỬ TỪ FIREBASE WEB
    db_data = {}
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase Web...")
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi đọc Firebase: {e}")

    # 4. KẾT NỐI API EVNTOOLS VỚI CƠ CHẾ TỰ ĐỘNG THỬ LẠI NẾU GẶP LỖI 502
    max_retries = 3
    features = []
    response = None
    
    for attempt in range(max_retries):
        try:
            print(f"Đang kết nối API lấy dữ liệu sét 10 phút gần nhất (Lần thử {attempt+1})...")
            response = requests.get(api_url, headers=headers, timeout=25)
            if response.status_code == 200:
                features = response.json().get("features", [])
                break
            elif response.status_code == 502:
                print("⚠️ Hệ thống đối tác báo lỗi 502 (Bad Gateway). Đang chờ để kết nối lại...")
                time.sleep(5)
            else:
                print(f"❌ Máy chủ trả về mã lỗi HTTP {response.status_code}")
                break
        except Exception as e:
            print(f"Lỗi kết nối đường truyền: {e}")
            time.sleep(5)

    if response is None or response.status_code != 200:
        print("❌ Không thể đồng bộ dữ liệu do máy chủ đối tác phản hồi lỗi kéo dài.")
        sys.exit(1)

    # 5. XỬ LÝ DỮ LIỆU ĐỒNG BỘ
    diem_moi = 0
    diem_cap_nhat = 0
    updates = {} 

    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        if not geom or not props: continue
        
        coords = geom.get("coordinates", [])
        if len(coords) < 2: continue
        lng, lat = coords[0], coords[1]
        
        # GIỮ NGUYÊN TOÀN BỘ SÉT ĐÁM MÂY VÀ SÉT MẶT ĐẤT (Không lọc bỏ trường type)
        loaiset = props.get("type", 0) 
        giatri = abs(float(props.get("amplitude", 0)))
        nguon = props.get("source", "Vaisala").title()
        time_str = props.get("timestamp", props.get("time"))
        
        # Đổi chuỗi ISO thời gian sang định dạng timestamp chuẩn để phục vụ dọn rác 7 ngày
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            ts = dt.timestamp()
        except:
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                ts = dt.timestamp()
            except:
                continue

        # Thiết lập khóa định danh không trùng lặp
        key_string = f"{ts}_{lat}_{lng}"
        key = hashlib.md5(key_string.encode()).hexdigest()
        
        if key in db_data:
            # KIỂM TRA VÀ CẬP NHẬT CƯỜNG ĐỘ (Nếu mốc cũ đang khuyết dữ liệu)
            old_giatri = db_data[key].get("giatri", 0)
            if (old_giatri == 0 or old_giatri == 0.0) and giatri > 0:
                updated_record = db_data[key].copy()
                updated_record["giatri"] = giatri
                updated_record["loaiset"] = loaiset
                updates[key] = updated_record
                db_data[key] = updated_record
                diem_cap_nhat += 1
        else:
            # GHI NHẬN TIA SÉT MỚI HOÀN TOÀN (Bảo toàn cấu trúc Object để Frontend đọc mượt mà)
            updates[key] = {
                "lat": lat,
                "lng": lng,
                "giatri": giatri,
                "loaiset": loaiset,
                "timestamp": ts,
                "src": nguon,
                "is_new_format": True
            }
            db_data[key] = updates[key] 
            diem_moi += 1

    # 6. BỘ LỌC TỰ ĐỘNG DỌN SẠCH DỮ LIỆU CŨ QUÁ 7 NGÀY
    current_ts = int(time.time())
    seven_days_ago = current_ts - 604800
    diem_xoa = 0
    for k, v in db_data.items():
        if v.get("timestamp", 0) < seven_days_ago:
            updates[k] = None  # Gửi lệnh dọn sạch mốc cũ trên Firebase
            diem_xoa += 1

    # 7. ĐẨY DỮ LIỆU LÊN KHO LƯU TRỮ
    if updates:
        print(f"Đang đồng bộ gói dữ liệu PATCH lên Firebase Web ({len(updates)} tác vụ)...")
        patch_response = requests.patch(FIREBASE_URL, json=updates, timeout=60)
        if patch_response.status_code == 200:
            print(f"✅ HOÀN TẤT VẬN HÀNH! Đã bổ sung {diem_moi} điểm sét mới (Mây + Đất). Cập nhật dữ liệu cường độ cho {diem_cap_nhat} điểm cũ. Đã quét dọn sạch {diem_xoa} rác dữ liệu quá 7 ngày.")
        else:
            print(f"❌ Lỗi Firebase: {patch_response.text}")
            sys.exit(1)
    else:
        print("✅ Hệ thống quét xong. Không có xung sét mới hoặc mốc dữ liệu cần thay đổi.")

if __name__ == "__main__":
    crawl_lightning_data()
