import os
import json
import re
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parent / ".env")
ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Handwriting AI Studio")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
ALLOWED = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 8 * 1024 * 1024


def parse_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(502, "AI ส่งผลลัพธ์ไม่เป็น JSON กรุณาลองอีกครั้ง") from exc



async def ask_ai(client, image, mime, instruction):
    import base64

    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า Gemini API Key")

    primary = os.getenv(
        "GEMINI_MODEL", "gemini-2.5-flash"
    ).strip().removeprefix("models/")

    fallback = os.getenv(
        "GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite"
    ).strip().removeprefix("models/")

    models = list(dict.fromkeys([primary, fallback]))

    payload = {
        "contents": [{
            "parts": [
                {"text": instruction},
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(image).decode("ascii")
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json"
        }
    }

    errors = []

    for model in models:
        url = (
            "https://generativelanguage.googleapis.com"
            f"/v1beta/models/{model}:generateContent"
        )

        for attempt in range(3):
            try:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": key},
                    json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    parts = result["candidates"][0]["content"]["parts"]
                    output = "".join(
                        part.get("text", "") for part in parts
                    )
                    return parse_json(output)

                try:
                    detail = response.json().get("error", {}).get(
                        "message", response.text[:300]
                    )
                except ValueError:
                    detail = response.text[:300]

                error = f"{model}: HTTP {response.status_code}: {detail}"
                print("Gemini error:", error, flush=True)

                if response.status_code not in (
                    429, 500, 502, 503, 504
                ):
                    errors.append(error)
                    break

                if attempt == 2:
                    errors.append(error)

            except httpx.RequestError as exc:
                error = f"{model}: {type(exc).__name__}"
                print("Gemini network error:", error, flush=True)

                if attempt == 2:
                    errors.append(error)

            except (ValueError, KeyError, IndexError) as exc:
                error = f"{model}: invalid response ({type(exc).__name__})"
                print("Gemini response error:", error, flush=True)
                errors.append(error)
                break

            if attempt < 2:
                await asyncio.sleep(2 ** (attempt + 1))

    raise HTTPException(
        502,
        "AI ไม่สำเร็จ กรุณาตรวจสอบ Render Logs"
    )


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "dashboard.html")


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED:
        raise HTTPException(400, "รองรับเฉพาะ JPG, PNG และ WEBP")
    data = await file.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "ไฟล์ต้องไม่เกิน 8 MB")
    if not data:
        raise HTTPException(400, "ไฟล์ว่างเปล่า")

    first_prompt = '''คุณคือ AI ตัวที่ 1 สำหรับถอดข้อความลายมือภาษาไทยและอังกฤษจากภาพ
อ่านเฉพาะสิ่งที่เห็นจริง ไม่เติมข้อมูล ไม่ตีความเป็นข้อเท็จจริงใหม่
รักษาการขึ้นบรรทัดและคำสะกดต้นฉบับ ถ้าอ่านไม่ออกให้ใช้ [อ่านไม่ชัด]
ตอบ JSON object เท่านั้น รูปแบบ {"transcription":"ข้อความที่อ่านได้"}'''
    async with httpx.AsyncClient(timeout=90) as client:
        first = await ask_ai(client, data, file.content_type, first_prompt)
        draft = first.get("transcription", "")
        if not isinstance(draft, str):
            raise HTTPException(502, "AI ตัวแรกส่งผลลัพธ์ผิดรูปแบบ")
        second_prompt = f'''คุณคือ AI ตัวที่ 2 ตรวจสอบการถอดข้อความกับภาพต้นฉบับอย่างเป็นอิสระ
ข้อความจาก AI ตัวแรก: {json.dumps(draft, ensure_ascii=False)}
ตรวจสอบทุกบรรทัดเทียบกับภาพ แก้เฉพาะเมื่อมองเห็นชัด ไม่เดาชื่อคน ชื่อยา ปริมาณยา หรือเลข
จุดไม่แน่ใจให้ใช้ [อ่านไม่ชัด] และแจ้งใน uncertainties
ดึงข้อมูลเฉพาะที่ปรากฏชัดเจนจากเอกสารลง fields เป็น key-value ไม่ต้องเดา
ตอบ JSON object เท่านั้น รูปแบบ:
{{"verified_text":"...", "uncertainties":["..."], "fields":{{"วันที่":"..."}}}}
หากไม่มี fields ให้ส่ง {{}} และ uncertainties ให้ส่ง []'''
        second = await ask_ai(client, data, file.content_type, second_prompt)
    return {
        "draft": draft,
        "verified_text": str(second.get("verified_text", draft)),
        "uncertainties": second.get("uncertainties", []) if isinstance(second.get("uncertainties", []), list) else [],
        "fields": second.get("fields", {}) if isinstance(second.get("fields", {}), dict) else {},
        "notice": "AI อาจอ่านผิด โปรดตรวจสอบกับภาพต้นฉบับก่อนนำไปใช้"
    }


# LOCAL DEMO ONLY: No authentication. Never expose this server publicly or use real patient data.
DB_PATH = ROOT / "carevision_demo.sqlite3"

def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, kind TEXT NOT NULL, scheduled TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created TEXT NOT NULL)")
    db.commit()
    return db

@app.get("/scanner")
def scanner():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"status":"online", "api_key_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()), "mode":"local_demo"}

@app.get("/api/tasks")
def list_tasks():
    with connect_db() as db:
        return [dict(row) for row in db.execute("SELECT * FROM tasks ORDER BY scheduled, id")]

from pydantic import BaseModel, Field
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    kind: str = Field(pattern="^(medication|appointment|activity)$")
    scheduled: str = Field(min_length=10, max_length=40)

@app.post("/api/tasks", status_code=201)
def add_task(item: TaskIn):
    try:
        datetime.fromisoformat(item.scheduled)
    except ValueError:
        raise HTTPException(400, "รูปแบบวันเวลาไม่ถูกต้อง")
    with connect_db() as db:
        cur = db.execute("INSERT INTO tasks (title,kind,scheduled,status,created) VALUES (?,?,?,?,?)", (item.title.strip(),item.kind,item.scheduled,"pending",datetime.now().isoformat()))
        db.commit()
        return {"id":cur.lastrowid,"ok":True}

@app.patch("/api/tasks/{task_id}")
def update_task(task_id:int, status:str):
    if status not in ("pending","done"):
        raise HTTPException(400,"สถานะไม่ถูกต้อง")
    with connect_db() as db:
        cur=db.execute("UPDATE tasks SET status=? WHERE id=?",(status,task_id))
        db.commit()
        if not cur.rowcount: raise HTTPException(404,"ไม่พบรายการ")
    return {"ok":True}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id:int):
    with connect_db() as db:
        cur=db.execute("DELETE FROM tasks WHERE id=?",(task_id,))
        db.commit()
        if not cur.rowcount: raise HTTPException(404,"ไม่พบรายการ")
    return {"ok":True}
