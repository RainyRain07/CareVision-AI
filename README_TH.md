# CareVision AI V1 — คู่มือเริ่มต้น

ต้นแบบใช้งาน **บนเครื่องส่วนตัวเท่านั้น** สร้างต่อจาก Handwriting AI Studio ที่อัปโหลดมา

## เริ่มต้นบน MacBook
1. แตก ZIP และเปิด Terminal ในโฟลเดอร์ `CareVision-AI-V1`
2. `python3 -m venv .venv`
3. `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `cp .env.example .env` และเปิด `.env` เพื่อใส่ Gemini API Key (ห้ามเผยแพร่คีย์)
6. `python -m uvicorn main:app --reload`
7. เปิด http://127.0.0.1:8000 สำหรับ Dashboard และ http://127.0.0.1:8000/scanner สำหรับ AI Scanner

## ทำงานได้แล้ว
- Dashboard แบบ Responsive พร้อมเมนู ภาพรวม สุขภาพ กิจกรรม การเดินทาง ครอบครัว
- สลับมุมมอง User / Family (การสลับหน้าจอ ไม่ใช่ระบบสิทธิ์)
- เพิ่ม/แก้สถานะ/ลบตารางยา นัดหมาย และกิจกรรม; บันทึกใน SQLite บนเครื่อง
- AI Scanner 2 ขั้นตอนจากโค้ดเดิม พร้อม Retry และ Fallback Model
- ดูตำแหน่งปัจจุบันเมื่อผู้ใช้กดยินยอม (ไม่ใช่ GPS Tracking เบื้องหลัง)

## ยังไม่ได้เชื่อมต่อ
LINE Login, LINE OA Push, การแจ้งเตือนตามเวลา, บัญชีผู้ใช้จริง, การเชิญครอบครัว, GPS background, บริการจองรถ, QR สำหรับเว็บไซต์ออนไลน์, AI ประเมินโรค

**ความปลอดภัย:** ยังไม่มี Authentication/Authorization จึงห้ามเปิดพอร์ตนี้สู่สาธารณะ ห้ามนำข้อมูลผู้ป่วยจริงเข้าระบบ และห้ามใช้เป็นคำแนะนำการรักษา ข้อมูลตารางถูกเก็บในไฟล์ `carevision_demo.sqlite3` บนเครื่องที่รันเซิร์ฟเวอร์เท่านั้น การเปิดจากมือถือเครื่องอื่นจะยังไม่ใช่ระบบหลายผู้ใช้ที่ปลอดภัย
