from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image

app = FastAPI()

# ฟังก์ชันหั่นขอบล่างขั้นเด็ดขาด (ใช้ Threshold กรองเงาขยะทิ้ง)
def trim_bottom_white_space(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # 1. แปลงภาพเป็นโหมดขาวดำ (Grayscale) เพื่อให้อ่านค่าง่าย
    gray = img.convert("L")
    
    # 2. กรองสี: ถ้าจุดไหนสีอ่อนเกินไป (เช่น พื้นหลังขาว หรือขอบเทาจางๆ) ให้ตั้งค่าเป็น 0
    # ส่วนสีที่เข้มกว่า 250 (เส้นขอบตาราง สีพื้นหลังเซลล์ ข้อความ) ให้ตั้งค่าเป็น 255
    mask = gray.point(lambda p: 255 if p < 250 else 0)
    
    # 3. ให้หาระยะที่มีจุดสี 255 อยู่
    bbox = mask.getbbox()
    
    if bbox:
        # bbox[3] จะจับพิกัดของ "เส้นตารางเส้นล่างสุด" ได้อย่างแม่นยำ โดยไม่สนขยะอื่นๆ
        img = img.crop((0, 0, img.width, bbox[3]))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Ultra Zero Edge Mode)!"}

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
                
                # ส่งเข้าฟังก์ชันหั่นแบบใหม่
                cropped_png_bytes = trim_bottom_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})