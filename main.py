from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io

app = FastAPI()

# 1. เพิ่มหน้าแรกสำหรับให้เรากดเข้าเว็บไปเช็คว่า API เปิดติดไหม
@app.get("/")
def read_root():
    return {"status": "✅ API is online and ready to convert PDF to ZIP!"}

# 2. ฟังก์ชันหลักสำหรับรับไฟล์จาก Google Sheet
@app.post("/convert")
async def convert_to_zip(file: UploadFile = File(...), names: str = Form(...)):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        name_list = [n.strip() for n in names.split(",")]
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(len(doc)):
                page = doc.load_page(i)
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                png_bytes = pix.tobytes("png")
                
                # ถ้าชื่อที่ส่งมาไม่พอ ให้ตั้งชื่อสำรองว่า page_x
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        # ถ้ามีอะไรพังตอนประมวลผล ให้พ่น Error ออกมาตรงๆ จะได้รู้สาเหตุ
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})