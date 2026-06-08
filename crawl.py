import requests
import hashlib
from datetime import datetime, timezone

def chay_bu_6_tieng():
    # LINK 6 TIẾNG CHUẨN XÁC BÁC VỪA LẤY ĐƯỢC
    api_url = "https://evntools.com/api/lightning/geojson?start_time=2026-06-08T10%3A36%3A43.623Z&end_time=2026-06-08T16%3A36%3A43.623Z&limit=50000&min_lat=21.344385808373335&max_lat=22.378015781668726&min_lon=104.19433593750001&max_lon=105.70220947265626"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    FIREBASE_URL = "https://datasetweb-default-rtdb.asia-southeast1.firebasedatabase.app/.json"
    
    # 1. Tải dữ liệu cũ để không ghi đè
    db_data = {}
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase Web...")
        fb_res = requests.get(FIREBASE_URL, timeout=30)
        if fb_res.status_code == 200 and fb_res.json():
            db_data = fb_res.json()
    except Exception as e:
        print(f"Lỗi: {e}")

    # 2. Hút dữ liệu từ link gốc 6 tiếng
    print("Đang kết nối để vét sạch dữ liệu 6 tiếng vừa qua...")
    try:
        response = requests.get(api_url, headers=headers, timeout=60)
        if response.status_code == 200:
            features = response.json().get("features", [])
            print(f"🔍 THÀNH CÔNG: Đã kéo về tổng cộng {len(features)} tia sét từ máy chủ!")
            
            updates = {}
            diem_moi = 0
            
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
                
                # Chuyển thời gian ra số
                try:
                    dt = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    ts = dt.timestamp()
                except:
                    try:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        ts = dt.timestamp()
                    except: continue

                key = hashlib.md5(f"{ts}_{lat}_{lng}".encode()).hexdigest()
                
                if key not in db_data:
                    updates[key] = {
                        "lat": lat, "lng": lng, "giatri": giatri, 
                        "loaiset": loaiset, "timestamp": ts, 
                        "src": nguon, "is_new_format": True
                    }
                    diem_moi += 1
            
            # 3. Đẩy bù lên Firebase
            if updates:
                print(f"Đang nhồi {diem_moi} điểm sét bù vào hệ thống...")
                patch_res = requests.patch(FIREBASE_URL, json=updates, timeout=60)
                if patch_res.status_code == 200:
                    print("✅ TUYỆT VỜI! Đã khôi phục và bù đắp xong dữ liệu 6 tiếng trên Web.")
                else:
                    print("❌ Lỗi nhồi Firebase.")
            else:
                print("✅ Máy chủ trả dữ liệu, nhưng toàn bộ số sét này đã có sẵn trong Firebase của bác rồi.")
        else:
            print(f"❌ Lỗi HTTP: {response.status_code}")
    except Exception as e:
        print(f"❌ Lỗi mạng: {e}")

if __name__ == "__main__":
    chay_bu_6_tieng()
