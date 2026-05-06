from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image

app = FastAPI()

# ฟังก์ชันไม้ตาย: สแกนพิกเซลจากล่างขึ้นบน (Manual Pixel Scanner)
def trim_bottom_white_space(image_bytes):
    # 1. เทสีขาวอัดทับลงไปเป็นพื้นหลัง แก้ปัญหาพื้นหลังโปร่งใสเพี้ยนเป็นสีดำ
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, (0, 0), img)
    img = bg.convert("RGB")
    
    pixels = img.load()
    width, height = img.size
    
    bottom_crop = height
    
    # 2. สแกนทีละบรรทัด จาก "ล่างสุด" ขึ้น "บนสุด" (ก้าวทีละ 2 พิกเซลเพื่อความไว)
    for y in range(height - 1, -1, -2):
        dark_pixels = 0
        
        # กวาดสายตาแนวนอน (ก้าวทีละ 5 พิกเซล)
        for x in range(0, width, 5):
            r, g, b = pixels[x, y]
            # 3. กรองขยะ: ถ้าสีสว่างเกินไป (ขาว, เทาอ่อน) ให้ข้าม
            # แต่ถ้าเจอสีเข้ม (เส้นขอบตาราง, ตัวหนังสือ) ให้นับ 1
            if r < 240 or g < 240 or b < 240:
                dark_pixels += 1
        
        # 4. ถ้าแนวนอนบรรทัดนั้น มีพิกเซลสีเข้มรวมกัน "มากกว่า 20 จุด"
        # ฟันธง 100% ว่านี่คือ "เส้นขอบตาราง" แน่นอน (ไม่ใช่รอยเปื้อน) ให้สั่งหั่นทันที!
        if dark_pixels > 20:
            bottom_crop = y + 5  # เผื่อความหนาของเส้นตารางไว้ 5 พิกเซล ภาพจะได้ไม่แหว่ง
            break
            
    bottom_crop = min(bottom_crop, height)
    img = img.crop((0, 0, width, bottom_crop))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Manual Pixel Scan Mode)!"}

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
                mat = fitz.Matrix(3.0, 3.0) # คูณความละเอียดภาพ 3 เท่า
                pix = page.get_pixmap(matrix=mat)
                
                # โยนเข้าเครื่องสแกนหั่นขอบล่าง
                cropped_png_bytes = trim_bottom_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})