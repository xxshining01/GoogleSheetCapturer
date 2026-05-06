from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
import fitz  # PyMuPDF
import zipfile
import io
from PIL import Image, ImageOps

app = FastAPI()

# ฟังก์ชันสแกน Pixel จากล่างขึ้นบนตามตรรกะที่คุณแนะนำ
def trim_bottom_white_space(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # 1. แปลงภาพเป็นขาวดำ เพื่อให้เช็คความสว่างของสีกราฟิกได้ง่าย
    gray = img.convert("L")
    
    # 2. กลับสีภาพ (Invert) พื้นขาวจะกลายเป็นดำ(0) และเส้นตารางจะกลายเป็นขาวสว่าง
    inverted = ImageOps.invert(gray)
    
    # 3. ตั้งเกณฑ์ความเข้ม (Threshold): สีเทาอ่อน ขยะ PDF หรือเงากระดาษ จะถูกปัดเป็นดำให้หมด (ไม่นับ)
    # ส่วนสีไหนที่เข้มระดับเส้นตารางหรือตัวหนังสือ จะถูกปัดเป็นสว่างสุดเพื่อเป็นจุดมาร์ค
    mask = inverted.point(lambda p: 255 if p > 15 else 0)
    
    # 4. ฟังก์ชัน getbbox() จะทำหน้าที่ "สแกนจากขอบเข้าหาตรงกลาง" จนกว่าจะเจอพิกเซลสว่างจุดแรก
    bbox = mask.getbbox()
    
    if bbox:
        # bbox[3] คือพิกัด Y (แนวตั้ง) ของเส้นตารางล่างสุดที่ระบบสแกนเจอ
        # หั่นจากจุดเริ่มต้น ไปบรรจบชิดเส้นขอบตารางล่างสุดพอดีเป๊ะๆ!
        img = img.crop((0, 0, img.width, bbox[3]))
    
    out_bytes = io.BytesIO()
    img.save(out_bytes, format="PNG")
    return out_bytes.getvalue()

@app.get("/api")
def read_root():
    return {"status": "✅ API Online (Bottom-Up Pixel Scan Mode)!"}

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
                
                # ส่งเข้าฟังก์ชันสแกนพิกเซล
                cropped_png_bytes = trim_bottom_white_space(pix.tobytes("png"))
                
                file_name = f"{name_list[i]}.png" if i < len(name_list) else f"page_{i+1}.png"
                zip_file.writestr(file_name, cropped_png_bytes)
                
        zip_buffer.seek(0)
        return Response(content=zip_buffer.getvalue(), media_type="application/zip")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Python Error: {str(e)}"})