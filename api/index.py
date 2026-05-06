from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image

app = FastAPI()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (User's Exact Mathematical Crop Mode)!"}

@app.post("/api")
async def convert_to_zip(
    file: UploadFile = File(...), 
    names: str = Form(...),
    ratios: str = Form(...)  # รับค่าสัดส่วน (Vertical/Horizontal) ที่คำนวณมาจาก Sheet
):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        name_list = [n.strip() for n in names.split(",")]
        ratio_list = [float(r.strip()) for r in ratios.split(",")]
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(len(doc)):
                page = doc.load_page(i)
                mat = fitz.Matrix(3.0, 3.0) 
                pix = page.get_pixmap(matrix=mat)
                
                # แปลงเป็น Image object ของ Pillow เพื่อเตรียมครอป
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                
                # ตรรกะของคุณ: เอา Horizontal (img.width) * สัดส่วน = Vertical ที่แท้จริง
                current_ratio = ratio_list[i] if i < len(ratio_list) else ratio_list[-1]
                target_height = int(img.width * current_ratio)
                
                # ครอปจากตำแหน่งบนสุด Vertex (0,0) ไปจนถึง (Horizontal, Vertical)
                img = img.crop((0, 0, img.width, target_height))
                
                out_bytes = io.BytesIO()
                img.save(out_bytes, format="PNG")
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, out_bytes.getvalue())
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})