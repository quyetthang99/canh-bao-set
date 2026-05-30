import requests
import json
import os
import time
import sys

def crawl_lightning_data():
    # URL gốc của bạn
    original_url = "http://hymetnet.gov.vn/dongset" 
    
    # Bơm thêm tham số thời gian để đánh lừa Proxy, bắt nó luôn lấy dữ liệu mới nhất (chống Cache)
    proxy_url = f"https://api.allorigins.win/raw?url={original_url}&t={time.time()}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    db_file = "database_set.json"
    
    # Đọc Database cũ
    db_data = {}
    if os.path.exists(db_file):
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except json.JSONDecodeError:
            db_data = {}

    try:
        print(f"Đang kết nối để lấy dữ liệu từ: {original_url}")
        response = requests.get(proxy_url, headers=headers, timeout=20)
        
        # In thẳng 200 ký tự đầu tiên ra log để "bắt tận tay" xem nó là tọa độ hay trang HTML
        preview = response.text[:200].replace('\n', ' ')
        print(f"👉 Dữ liệu máy chủ trả về: {preview}...")
        
        if response.status_code == 200:
            try:
                new_data = response.json()
            except json.JSONDecodeError:
                print("❌ LỖI NGHIÊM TRỌNG: Dữ liệu tải về là trang web HTML, không phải tọa độ JSON!")
                print("Nguyên nhân: Đường link 'dongset' có thể là link giao diện web, không phải link API.")
                sys.exit(1) # Đánh sập tiến trình để báo dấu X ĐỎ trên GitHub
                
            current_time = time.time() 
            diem_moi = 0
            
            for key, value in new_data.items():
                if key not in db_data:
                    db_data[key] = {"info": value, "timestamp": current_time}
                    diem_moi += 1
            
            seven_days_ago = current_time - 604800
            filtered_db = {k: v for k, v in db_data.items() if v["timestamp"] >= seven_days_ago}
            
            with open(db_file, "w", encoding="utf-8") as f:
                json.dump(filtered_db, f, ensure_ascii=False, indent=4)
                
            with open("duongset.json", "w", encoding="utf-8") as f:
                json.dump(new_data, f, ensure_ascii=False, indent=4)
            
            print(f"✅ THÀNH CÔNG! Đã cào được {len(new_data)} điểm (Thêm {diem_moi} điểm vào lịch sử).")
        else:
            print(f"❌ Lỗi HTTP: {response.status_code}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Lỗi mạng: {e}")
        sys.exit(1)

if __name__ == "__main__":
    crawl_lightning_data()
