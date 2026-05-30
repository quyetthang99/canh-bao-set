import requests
import json
import os
import time

def crawl_lightning_data():
    url = "http://hymetnet.gov.vn/dongset" 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "http://hymetnet.gov.vn/lightningmaps/",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    db_file = "database_set.json"
    
    # 1. Đọc dữ liệu lịch sử từ database cũ (nếu đã có file)
    db_data = {}
    if os.path.exists(db_file):
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except json.JSONDecodeError:
            db_data = {}

    try:
        # 2. Lấy dữ liệu sét mới nhất
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            new_data = response.json()
            
            # Lấy mốc thời gian hiện tại (tính bằng giây)
            current_time = time.time() 
            
            # 3. Trộn dữ liệu mới vào Database lịch sử
            # Dùng luôn 'key' (mã sét của hymetnet) để chống lưu trùng lặp
            for key, value in new_data.items():
                if key not in db_data:
                    db_data[key] = {
                        "info": value,
                        "timestamp": current_time # Đóng dấu thời gian lúc cào được
                    }
            
            # 4. BỘ LỌC TỰ ĐỘNG XOÁ DỮ LIỆU CŨ QUÁ 7 NGÀY
            # 7 ngày = 7 * 24 * 60 * 60 = 604800 giây
            seven_days_ago = current_time - 604800
            
            filtered_db = {k: v for k, v in db_data.items() if v["timestamp"] >= seven_days_ago}
            
            # 5. Lưu kết quả ra 2 file
            # File 1: Database tổng chứa sét trong 1 tuần
            with open(db_file, "w", encoding="utf-8") as f:
                json.dump(filtered_db, f, ensure_ascii=False, indent=4)
                
            # File 2: File sét tức thời (để giữ cho bản đồ hiện tại của bạn vẫn chạy bình thường)
            with open("duongset.json", "w", encoding="utf-8") as f:
                json.dump(new_data, f, ensure_ascii=False, indent=4)
            
            print(f"✅ Xong! Vừa lấy {len(new_data)} điểm mới. Database hiện đang giữ {len(filtered_db)} điểm sét trong 7 ngày qua.")
        else:
            print(f"Lỗi tải dữ liệu. Mã lỗi: {response.status_code}")
            
    except Exception as e:
        print(f"Lỗi mạng hoặc hệ thống: {e}")

if __name__ == "__main__":
    crawl_lightning_data()
