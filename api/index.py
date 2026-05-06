from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image

app = FastAPI()

def trim_bottom_white_space(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pixels = img.load()
    width, height = img.size
    
    bottom_crop = height
    
    # 1. กระโดดข้ามขอบกระดาษ! เริ่มสแกนโดยถอยขึ้นมาจากขอบล่าง 20 พิกเซล 
    for y in range(height - 20, -1, -2):
        dark_pixels = 0
        
        # 2. กระโดดข้ามขอบซ้ายขวา! ตัดพื้นที่ริมขอบทิ้งฝั่งละ 50 พิกเซล สแกนแค่ตรงกลาง
        for x in range(50, width - 50, 5):
            r, g, b = pixels[x, y]
            
            # ถ้าเป็นสีเข้ม (เส้นตาราง, สีพื้นหลังตารางแถวล่างสุด)
            if r < 235 or g < 235 or b < 235:
                dark_pixels += 1
        
        # 3. ถ้าเจอพิกเซลเข้มๆ รวมกันเกิน 30 จุด ฟันธงว่าเป็นตารางแน่นอน!
        if dark_pixels > 30:
            bottom_crop = y + 5 # เผื่อที่ให้เส้นขอบ 5 พิกเซล ภาพจะได้ไม่แหว่ง
            break
            
    bottom_crop = min(bottom_crop, height)
    img = img.crop((0, 0, width, bottom_crop))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Safe Zone Pixel Scanner Mode)!"}

@app.post("/api")
async def convert_to_zip(file: UploadFile = File(...), names: str = Form(...)):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        name_list = [n.strip() for n in names.split(",")]
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(len(doc)):
                page = doc.load_page(i)
                mat = fitz.Matrix(3.0, 3.0) 
                pix = page.get_pixmap(matrix=mat)
                
                # เข้าเครื่องสแกนเจาะไข่แดง
                cropped_png_bytes = trim_bottom_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})