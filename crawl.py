import requests
import json

def crawl_lightning_data():
    # URL chuẩn xác do bạn phát hiện ra: dongset
    url = "http://hymetnet.gov.vn/dongset" 
    
    # Bộ Header mô phỏng máy tính người dùng tại Việt Nam để chống server chặn
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "http://hymetnet.gov.vn/lightningmaps/",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Mã phản hồi từ server: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Lưu vào file JSON (đặt tên file lưu là duongset.json cho khớp với index.html)
                with open("duongset.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                print(f"Thành công tuyệt đối! Đã cào được {len(data)} điểm sét.")
            except json.JSONDecodeError:
                print("Lỗi: Server Hymetnet chặn IP GitHub, trả về HTML thay vì JSON.")
        else:
            print(f"Lỗi tải dữ liệu. Mã lỗi: {response.status_code}")
            
    except Exception as e:
        print(f"Đã xảy ra lỗi mạng: {e}")

if __name__ == "__main__":
    crawl_lightning_data()
