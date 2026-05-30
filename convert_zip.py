import geopandas as gpd
import os

def process_zipped_shapefile():
    # Tên file zip bạn sẽ upload lên (bạn có thể nén tất cả .shp, .shx, .dbf, .prj vào file này)
    zip_filename = "luoi_dien.zip" 
    output_json = "luoidien.json"
    
    # Logic thông minh: Nếu đã có file JSON rồi thì không làm gì cả để tiết kiệm tài nguyên
    if os.path.exists(output_json):
        print(f"File {output_json} đã tồn tại. Đã lưu vĩnh viễn, bỏ qua chuyển đổi!")
        return

    if not os.path.exists(zip_filename):
        print(f"Hệ thống đang chờ bạn upload file {zip_filename} lên...")
        return

    try:
        print(f"Đang đọc trực tiếp Shapefile từ file nén {zip_filename}...")
        # Geopandas hỗ trợ cú pháp zip:// để đọc thẳng vào ruột file nén
        gdf = gpd.read_file(f"zip://{zip_filename}")
        
        # Khai báo hệ tọa độ VN-2000 (Kinh tuyến trục Lào Cai: 104.75)
        vn2000_crs = "+proj=tmerc +lat_0=0 +lon_0=104.75 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
        
        if gdf.crs is None:
            gdf.set_crs(vn2000_crs, inplace=True)
        
        print("Đang chuyển đổi tọa độ VN-2000 sang WGS-84...")
        gdf_wgs84 = gdf.to_crs(epsg=4326)
        
        print("Đang xuất ra file và lưu vĩnh viễn...")
        gdf_wgs84.to_file(output_json, driver="GeoJSON")
        print("✅ Thành công! Dữ liệu đã được khóa trong file luoidien.json.")
        
    except Exception as e:
        print(f"❌ Lỗi xử lý: {e}")

if __name__ == "__main__":
    process_zipped_shapefile()