import requests
import json
import os
import time

def crawl_lightning_data():
    # Sử dụng Proxy trung gian để tránh việc máy chủ chính phủ chặn IP máy ảo GitHub (Mỹ)
    original_url = "http://hymetnet.gov.vn/dongset"
    url = f"https://api.allorigins.win/raw?url={original_url}"
    
    # Rút gọn header để Proxy làm việc hiệu quả hơn
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    db_file = "database_set.json"
    
    db_data = {}
    if os.path.exists(db_file):
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except json.JSONDecodeError:
            db_data = {}

    try:
        print("Đang kết nối qua Proxy để cào dữ liệu sét...")
        # Tăng timeout lên 20s vì đi qua Proxy sẽ chậm hơn một chút
        response = requests.get(url, headers=headers, timeout=20)
        print(f"Mã trạng thái HTTP: {response.status_code}")
        
        if response.status_code == 200:
            try:
                new_data = response.json()
                current_time = time.time() 
                diem_moi = 0
                
                # Trộn dữ liệu mới vào Database lịch sử
                for key, value in new_data.items():
                    if key not in db_data:
                        db_data[key] = {
                            "info": value,
                            "timestamp": current_time 
                        }
                        diem_moi += 1
                
                # Lọc bỏ sét cũ quá 7 ngày
                seven_days_ago = current_time - 604800
                filtered_db = {k: v for k, v in db_data.items() if v["timestamp"] >= seven_days_ago}
                
                # Lưu file
                with open(db_file, "w", encoding="utf-8") as f:
                    json.dump(filtered_db, f, ensure_ascii=False, indent=4)
                    
                with open("duongset.json", "w", encoding="utf-8") as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=4)
                
                print(f"✅ Xong! Cào được {len(new_data)} điểm (Thêm {diem_moi} điểm vào lịch sử). Tổng Database: {len(filtered_db)} điểm.")
            
            except json.JSONDecodeError:
                print("❌ Lỗi: Proxy trả về HTML, có thể server Hymetnet đang bảo trì hoặc chặn Proxy.")
        else:
            print(f"❌ Lỗi kết nối. Mã lỗi: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Lỗi mạng hoặc hệ thống: {e}")

if __name__ == "__main__":
    crawl_lightning_data()
