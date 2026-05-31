import requests
import json
import os

# Đường dẫn Firebase của bạn (Lưu ý vẫn giữ đuôi .json)
FIREBASE_URL = "https://database-set-7a73d-default-rtdb.asia-southeast1.firebasedatabase.app/lightning_data.json"
FILE_CU = "database_set.json"

def chuyen_du_lieu():
    if not os.path.exists(FILE_CU):
        print(f"❌ Không tìm thấy file {FILE_CU} ở thư mục hiện tại.")
        return

    try:
        # 1. Đọc dữ liệu từ file cũ
        print("Đang đọc dữ liệu từ file cũ...")
        with open(FILE_CU, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            
        print(f"Tìm thấy {len(old_data)} bản ghi sét cũ. Bắt đầu tải lên Firebase...")

        # 2. Dùng lệnh PATCH để GỘP dữ liệu cũ vào Firebase (Không bị xóa đè sét mới)
        response = requests.patch(FIREBASE_URL, json=old_data, timeout=60)

        if response.status_code == 200:
            print("✅ XUẤT SẮC! Đã chuyển thành công toàn bộ dữ liệu cũ lên Firebase.")
            print("Bạn có thể xóa file database_set.json trên GitHub cho nhẹ kho được rồi!")
        else:
            print(f"❌ Lỗi đẩy lên Firebase: {response.text}")

    except Exception as e:
        print(f"❌ Có lỗi xảy ra: {e}")

if __name__ == "__main__":
    chuyen_du_lieu()
