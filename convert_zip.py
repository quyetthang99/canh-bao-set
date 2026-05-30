import geopandas as gpd
import pandas as pd
import os
import zipfile
import glob

def process_zipped_shapefile():
    zip_filename = "luoi_dien.zip" 
    output_json = "luoidien.json"
    extract_dir = "temp_shp_extracted" # Thư mục tạm để giải nén

    if not os.path.exists(zip_filename):
        print(f"Hệ thống đang chờ bạn upload file {zip_filename} lên...")
        return

    try:
        print(f"Đang giải nén toàn bộ file {zip_filename}...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Quét tìm tất cả các file .shp vừa được giải nén ra
        shp_files = glob.glob(f"{extract_dir}/**/*.shp", recursive=True)
        
        if not shp_files:
            print("Lỗi: Không tìm thấy bất kỳ file .shp nào trong file nén!")
            return
            
        print(f"Đã tìm thấy {len(shp_files)} lớp dữ liệu (Cột, Trạm, Khoảng cột...). Đang gộp...")
        
        # Thông số hệ tọa độ với kinh tuyến trục cực chuẩn xác (104° 45' 03" = 104.750833)
        vn2000_crs = "+proj=tmerc +lat_0=0 +lon_0=104.750833 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
        
        danh_sach_gdfs = []
        for shp in shp_files:
            try:
                gdf = gpd.read_file(shp)
                # Ép hệ tọa độ VN2000
                if gdf.crs is None:
                    gdf.set_crs(vn2000_crs, inplace=True)
                
                # Chuyển đổi sang WGS-84 dùng cho bản đồ Web
                gdf_wgs84 = gdf.to_crs(epsg=4326)
                danh_sach_gdfs.append(gdf_wgs84)
                print(f" - Đã xử lý xong: {os.path.basename(shp)}")
            except Exception as e:
                print(f" - Bỏ qua lớp {os.path.basename(shp)} do lỗi: {e}")
        
        # Gộp tất cả các mảng dữ liệu lại với nhau
        if danh_sach_gdfs:
            combined_gdf = pd.concat(danh_sach_gdfs, ignore_index=True)
            combined_gdf.to_file(output_json, driver="GeoJSON")
            print("✅ Tuyệt vời! Đã nén toàn bộ hạ tầng lưới điện vào luoidien.json vĩnh viễn.")
        else:
            print("❌ Không có dữ liệu hợp lệ để xuất.")
            
    except Exception as e:
        print(f"❌ Quá trình chạy bị lỗi: {e}")

if __name__ == "__main__":
    process_zipped_shapefile()
