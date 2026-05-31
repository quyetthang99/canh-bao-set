import requests
import json
import time
import sys

def crawl_lightning_data():
    original_url = "http://hymetnet.gov.vn/dongset" 
    proxy_url = f"https://api.codetabs.com/v1/proxy?quest={original_url}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # --- ĐỊA CHỈ FIREBASE CỦA BẠN ---
    FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
    
    # 1. Lấy dữ liệu cũ từ Firebase về để đối chiếu
    db_data = {}
    try:
        print("Đang tải dữ liệu lịch sử từ Firebase...")
        fb_response = requests.get(FIREBASE_URL, timeout=30)
        if fb_response.status_code == 200 and fb_response.json() is not None:
            db_data = fb_response.json()
    except Exception as e:
        print(f"Lỗi khi đọc Firebase (có thể DB đang trống): {e}")

    # 2. Cào dữ liệu sét mới nhất
    try:
        print(f"Đang lấy dữ liệu sét mới từ trạm trinh sát...")
        response = requests.get(proxy_url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            new_data = response.json()
            current_time = time.time() 
            diem_moi = 0
            
            # 3. Lọc trùng lặp & Gộp data
            for key, value in new_data.items():
                if key not in db_data:
                    db_data[key] = {"info": value, "timestamp": current_time}
                    diem_moi += 1
            
            # 4. Dọn rác (Giữ lại sét trong 7 ngày)
            seven_days_ago = current_time - 604800
            filtered_db = {k: v for k, v in db_data.items() if v["timestamp"] >= seven_days_ago}
            
            # 5. Đẩy toàn bộ dữ liệu sạch sẽ lên lại Firebase
            print(f"Đang đẩy {len(filtered_db)} bản ghi lên Firebase...")
            put_response = requests.put(FIREBASE_URL, json=filtered_db, timeout=30)
            
            if put_response.status_code == 200:
                print(f"✅ THÀNH CÔNG! Đã thêm {diem_moi} điểm sét mới. Kích thước Database: {len(filtered_db)}.")
            else:
                print(f"❌ Lỗi đẩy lên Firebase: {put_response.text}")
                sys.exit(1)
        else:
            print(f"❌ Lỗi HTTP: {response.status_code}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Lỗi mạng: {e}")
        sys.exit(1)

if __name__ == "__main__":
    crawl_lightning_data()
