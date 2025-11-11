import os, sys, sqlite3, random, datetime, json
from contextlib import closing

from PyQt6.QtCore import Qt, QTimer, QDate, QLocale
from PyQt6.QtGui import QFontDatabase, QFont, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QFrame, QStackedWidget, QGridLayout, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QComboBox,
    QSizePolicy, QFileDialog, QSpacerItem
)

# ---------- PATHS (แก้ให้ตรงเครื่อง) ----------
# ******************************************************************************
# ใช้พาธจากโค้ดหน้าหลัก (main.py) เพื่อให้เชื่อมต่อ DB เดียวกัน
# ⚠️ ตรวจสอบพาธ 4 ตำแหน่งนี้ให้ถูกต้องตามเครื่องของคุณ!
RUBIK_REG   = os.path.join("font", "Rubik-Regular.ttf")
RUBIK_BOLD  = os.path.join("font", "Rubik-Bold.ttf")
FC_MINIMAL  = os.path.join("font", "FC Minimal.ttf")
LOGO_IMG    = os.path.join("picture", "logo.png")

# ใช้พาธฐานข้อมูลที่กำหนดในโค้ดหน้าหลัก
DB_DIR      = DATA_ELEE_PATH = r"dataelee"
DB_USER_PATH = os.path.join(DB_DIR, "passenger_bookings.db")
# DB ของ ADMIN (users.db - ในโค้ดหน้าหลักชี้ไปที่ users.db ในโฟลเดอร์ปัจจุบัน)
# หากต้องการให้ Admin Console ใช้ users.db นี้สำหรับโครงสร้าง bookings, users
DB_ADMIN_PATH = "users.db" 
# ******************************************************************************

# ---------- THEME ----------
BG_MAIN   = "#fbf7f1"
BROWN     = "#8a663f"
CARD_LINE = "#9b7a55"
CARD_BG   = "#fff5ec"
PILL_BG   = "#eaf4f7"
INK       = "#111"
RED_TXT   = "#b35757"
BUTTON_BG = "#eaf4f7" # สีพื้นหลังปุ่มใน Manage Trip

def load_fonts():
    for p in (RUBIK_REG, RUBIK_BOLD, FC_MINIMAL):
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)
def TH(size=26, w=QFont.Weight.Normal): return QFont("FC Minimal", size, w)
def EN(size=18, w=QFont.Weight.DemiBold): return QFont("Rubik", size, w)

# ===================== DB & Helpers (เชื่อมต่อ DB) =====================

def db_connect_user():
    """เชื่อมต่อฐานข้อมูลการจองหลัก (passenger_bookings.db)"""
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB_USER_PATH)

def db_connect_admin():
    """เชื่อมต่อฐานข้อมูลแอดมิน/สรุปการจอง (users.db)"""
    # ตรวจสอบเพื่อรองรับการสร้างตาราง bookings ชั่วคราวใน main.py
    return sqlite3.connect(DB_ADMIN_PATH)

def db_init():
    """เตรียมฐานข้อมูล users.db ให้มีตาราง bookings, users, payments และ routes"""
    # ใช้ db_connect_admin() สำหรับสร้างโครงสร้างตาราง admin (users.db)
    with closing(db_connect_admin()) as conn, conn, closing(conn.cursor()) as cur:
        cur.execute("PRAGMA foreign_keys = ON;")

        # สร้างตาราง Users
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            phone TEXT,
            email TEXT,
            created_at TEXT DEFAULT (DATE('now'))
        )
        """)
        
        # สร้างตาราง Bookings (ตารางสรุปการจองที่ main.py บันทึก)
        # ตารางนี้ต้องตรงกับที่ _db_connect_admin() ใน main.py สร้างไว้
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_no TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            route_from TEXT NOT NULL,
            route_to TEXT NOT NULL,
            date TEXT NOT NULL,          -- YYYY-MM-DD
            status TEXT NOT NULL,        -- รอดำเนินการ/ยืนยัน/เรียบร้อย/ยกเลิก
            phone TEXT,
            email TEXT,
            seat TEXT,
            price REAL,
            vat REAL,
            slip_path TEXT,
            dep_time TEXT,
            arr_time TEXT,
            created_at TEXT DEFAULT (DATETIME('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)

        # สร้างตาราง Payments
        cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            method TEXT,
            paid_at TEXT DEFAULT (DATETIME('now')),
            note TEXT,
            FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
        )
        """)

        # 🌟 ส่วนที่เพิ่ม: สร้างตาราง ROUTES 🌟
        cur.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_from TEXT NOT NULL,
            route_to TEXT NOT NULL,
            departure_time TEXT NOT NULL, -- เช่น '07:00'
            duration TEXT,                -- เช่น '4:00 ชม.'
            capacity INTEGER NOT NULL DEFAULT 40,
            UNIQUE(route_from, route_to, departure_time) -- ไม่ให้มีเที่ยวซ้ำกัน
        )
        """)
        # 🌟 สิ้นสุดส่วนที่เพิ่ม 🌟

        # เพิ่ม Admin user หากไม่มี
        cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO users(username, password_hash, role, email) VALUES(?,?,?,?)",
                ("admin", "Admin1234 (replace with hash)", "admin", "admin@example.com")
            )
            
        conn.commit()
    
    # ⚠️ ตรวจสอบว่าตาราง passenger_bookings ใน DB_USER_PATH มีอยู่หรือไม่
    try:
        with closing(db_connect_user()) as conn, conn, closing(conn.cursor()) as cur:
            cur.execute("SELECT 1 FROM passenger_bookings LIMIT 1")
    except sqlite3.OperationalError:
        print("WARNING: 'passenger_bookings.db' does not contain 'passenger_bookings' table. Please run main app first.")


# 🌟 ส่วนที่เพิ่ม: ฟังก์ชันสำหรับบันทึกเส้นทางใหม่ 🌟
def db_add_route(frm: str, to: str, dep_time: str, duration: str, capacity: int):
    """บันทึกเส้นทางใหม่เข้าตาราง routes ของ users.db"""
    sql = """
    INSERT INTO routes (route_from, route_to, departure_time, duration, capacity)
    VALUES (?, ?, ?, ?, ?)
    """
    try:
        with closing(db_connect_admin()) as conn, conn, closing(conn.cursor()) as cur:
            cur.execute(sql, (frm, to, dep_time, duration, capacity))
            return True, "บันทึกสำเร็จ"
    except sqlite3.IntegrityError:
        return False, "เที่ยวรถนี้มีอยู่ในระบบแล้ว (เส้นทางและเวลาออกซ้ำกัน)"
    except Exception as e:
        return False, f"ข้อผิดพลาดในการบันทึก: {e}"
# 🌟 สิ้นสุดส่วนที่เพิ่ม 🌟

def db_search_bookings(keyword: str):
    """ค้นหารายการจองในตาราง bookings ของ users.db"""
    kw = f"%{keyword.strip()}%" if keyword.strip() else "%"
    sql = """
    SELECT id, ticket_no, customer_name, route_from, route_to, date, status, price, vat
    FROM bookings
    WHERE ticket_no LIKE ? OR customer_name LIKE ? OR (route_from || ' - ' || route_to) LIKE ?
          OR date LIKE ? OR status LIKE ?
    ORDER BY date DESC, id DESC
    """
    with closing(db_connect_admin()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql, (kw,kw,kw,kw,kw))
        return cur.fetchall()

def db_get_all_routes():
    """ดึงรายการเส้นทางที่ไม่ซ้ำกัน (route_from, route_to) จากตาราง bookings ใน users.db"""
    # NOTE: ฟังก์ชันนี้ยังคงดึงข้อมูลจากตาราง bookings (เก่า) เพื่อให้เข้ากันได้กับ DeleteTripPage
    sql = """
    SELECT route_from, route_to, COUNT(*) as c
    FROM bookings
    GROUP BY route_from, route_to
    ORDER BY route_from ASC, route_to ASC
    """
    with closing(db_connect_admin()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql)
        return cur.fetchall()

def db_delete_route_demo(route_from: str, route_to: str):
    """ลบรายการจองทั้งหมดของเส้นทางนั้นในตาราง bookings (users.db) และที่นั่งใน passenger_bookings (passenger_bookings.db)"""
    deleted_admin_rows = 0
    deleted_user_rows = 0
    
    try:
        with closing(db_connect_admin()) as conn_admin, conn_admin, closing(conn_admin.cursor()) as cur_admin:
            # 1. ลบรายการสรุปการจองใน users.db
            cur_admin.execute("DELETE FROM bookings WHERE route_from=? AND route_to=?", (route_from, route_to))
            deleted_admin_rows = cur_admin.rowcount
    except Exception as e:
        print(f"Error deleting admin bookings: {e}")

    try:
        with closing(db_connect_user()) as conn_user, conn_user, closing(conn_user.cursor()) as cur_user:
            # 2. ลบรายการจองที่นั่งใน passenger_bookings.db
            cur_user.execute("""
                DELETE FROM passenger_bookings
                WHERE trip_info_json LIKE ? AND trip_info_json LIKE ?
            """, (f'%origin": "{route_from}"%', f'%dest": "{route_to}"%'))
            deleted_user_rows = cur_user.rowcount

    except sqlite3.OperationalError:
        # อาจเกิดถ้าตาราง passenger_bookings ไม่มี
        pass
    except Exception as e:
        print(f"Error deleting user bookings: {e}")

    return deleted_admin_rows, deleted_user_rows # ส่งคืนจำนวนรายการที่ถูกลบ


def db_get_booking(row_id:int):
    """ดึงข้อมูลการจองจากตาราง bookings ของ users.db"""
    with closing(db_connect_admin()) as conn, closing(conn.cursor()) as cur:
        cur.execute("""SELECT id,ticket_no,customer_name,route_from,route_to,date,status,
                             phone,email,seat,price,vat,slip_path,dep_time,arr_time
                         FROM bookings WHERE id=?""", (row_id,))
        return cur.fetchone()

def _count_seats(seat_text:str)->int:
    if not seat_text: return 0
    return len([s.strip() for s in seat_text.split(",") if s.strip()])

# 🚨 ฟังก์ชันนี้ได้รับการแก้ไขเพื่อรวมการเชื่อมต่อ DB ทั้งหมดไว้ใน with block เดียว 🚨
def db_stats_for_date(ymd:str):
    """ดึงสถิติจากตาราง bookings และ routes ของ users.db"""
    with closing(db_connect_admin()) as conn, conn, closing(conn.cursor()) as cur:
        cur.execute("""
            SELECT route_from, route_to, dep_time, seat, price, COALESCE(vat, price*0.07) as vat_e
            FROM bookings
            WHERE date=? AND status <> 'ยกเลิก'
        """, (ymd,))
        rows = cur.fetchall()

        total_orders = len(rows)
        total_revenue = 0.0
        by_trip = {}
        for (frm,to,dep,seat,price,vat) in rows:
            total_revenue += float(price or 0) + float(vat or 0)
            key = (frm or "", to or "", dep or "")
            by_trip.setdefault(key, 0)
            by_trip[key] += _count_seats(seat or "")

        # คำนวณที่นั่งว่างจริง: ดึงเส้นทางทั้งหมดที่เป็นไปได้จากตาราง routes
        all_routes_trips = {}
        
        # 🌟 แก้ไข: การเรียกใช้ SQL ถูกรวมอยู่ใน with block นี้ 🌟
        cur.execute("SELECT route_from, route_to, departure_time, capacity FROM routes")
        available_routes = cur.fetchall()
        # 🌟 สิ้นสุดการแก้ไข 🌟
        
        for (frm, to, dep_time, capacity) in available_routes:
            key = (frm, to, dep_time)
            all_routes_trips[key] = by_trip.get(key, 0) # จำนวนที่นั่งที่จองแล้ว

        total_seats_in_service = sum(capacity for (_,_,_,capacity) in available_routes)

        total_booked_seats = sum(all_routes_trips.values())
        
        total_remaining = total_seats_in_service - total_booked_seats
        total_remaining = max(0, total_remaining) # ไม่ให้ติดลบ

        avg_per_order = (total_revenue/total_orders) if total_orders else 0.0

        top_map = {}
        for (frm,to,dep,seat,price,vat) in rows:
            key = f"{frm} → {to}"
            top_map[key] = top_map.get(key, 0) + 1
        top_routes = sorted(top_map.items(), key=lambda x: (-x[1], x[0]))[:3]
        least = min(top_map.items(), key=lambda x: (x[1], x[0])) if top_map else None

        return {
            "orders": total_orders,
            "revenue": total_revenue,
            "avg": avg_per_order,
            "seats_remaining": total_remaining,
            "top_routes": top_routes,
            "least_route": least
        }

def db_get_all_users():
    """ดึงข้อมูลผู้ใช้งานจากตาราง users ของ users.db"""
    sql = "SELECT id, username, role, phone, email, created_at FROM users ORDER BY role DESC, username ASC"
    with closing(db_connect_admin()) as conn, closing(conn.cursor()) as cur:
        cur.execute(sql)
        return cur.fetchall()
        
# ===================== Small UI Widgets (ไม่มีการเปลี่ยนแปลง) =====================
class StatBox(QFrame):
    def __init__(self, title:str, subtitle: str):
        super().__init__()
        self.setStyleSheet(f"QFrame{{background:{CARD_BG};border:2px solid {CARD_LINE};border-radius:12px;}} QLabel{{border:none}}")
        v = QVBoxLayout(self); v.setContentsMargins(18,16,18,14); v.setSpacing(4)
        
        self.t = QLabel(title); self.t.setFont(TH(30, QFont.Weight.Bold))
        self.s = QLabel(subtitle); self.s.setFont(TH(24)); self.s.setStyleSheet("color:#b25050;")
        self.red = QLabel("—"); self.red.setFont(TH(30, QFont.Weight.Black)); self.red.setStyleSheet("color:#b25050;")
        
        v.addWidget(self.t); v.addWidget(self.s); v.addStretch(1); v.addWidget(self.red)
        
    def set_value(self, text:str): self.red.setText(text)

class SoftPill(QFrame):
    def __init__(self, label:str):
        super().__init__()
        self.setStyleSheet("QFrame{background:#eaf4f7;border:none;border-radius:12px;} QLabel{border:none}")
        v = QVBoxLayout(self); v.setContentsMargins(16,10,16,10); v.setSpacing(2)
        self.lb = QLabel(label); self.lb.setFont(TH(22))
        self.val = QLabel("0.00 บาท"); self.val.setFont(TH(22,QFont.Weight.Bold))
        v.addWidget(self.lb); v.addWidget(self.val)
    def set_value(self, text:str): self.val.setText(text)

class ListCard(QFrame):
    def __init__(self, title:str, subtitle:str=""):
        super().__init__()
        self.setStyleSheet(f"QFrame{{background:{CARD_BG};border:2px solid {CARD_LINE};border-radius:12px;}} QLabel{{border:none}}")
        v = QVBoxLayout(self); v.setContentsMargins(18,16,18,16); v.setSpacing(10)
        h = QLabel(title); h.setFont(TH(30, QFont.Weight.Bold))
        v.addWidget(h)
        if subtitle:
            s = QLabel(subtitle); s.setFont(TH(24)); v.addWidget(s)
        
        def pill():
            p = QLabel(" "); p.setMinimumHeight(48); p.setFont(TH(24))
            p.setStyleSheet("background:#eaf4f7;border:none;border-radius:10px;padding:8px 14px;")
            return p
        self.r1, self.r2, self.r3 = pill(), pill(), pill()
        v.addWidget(self.r1); v.addWidget(self.r2); v.addWidget(self.r3); v.addStretch(1)
        
    def set_rows(self, rows):
        a = rows + ["",""]
        self.r1.setText(a[0] if len(a)>0 else "")
        self.r2.setText(a[1] if len(a)>1 else "")
        self.r3.setText(a[2] if len(a)>2 else "")

# ===================== Manage Trip — Hub =====================
# (ไม่มีการเปลี่ยนแปลง)
class ManageTripHubPage(QWidget):
    def __init__(self, go_add_cb, go_delete_cb):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)

        panel = QFrame()
        panel.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}}")
        pv = QVBoxLayout(panel); pv.setContentsMargins(24,24,24,24); pv.setSpacing(28)

        pv.addStretch(1)

        def big_btn(text, callback):
            b = QPushButton(text)
            b.setMinimumHeight(84)
            b.setMinimumWidth(640)
            b.setStyleSheet("QPushButton{background:#eaf4f7;border:2px solid #9b7a55;border-radius:20px;font-family:'Rubik';font-size:28px;font-weight:800;color:#000;}")
            b.clicked.connect(callback)
            return b

        self.btn_add = big_btn("ADD TRIP", go_add_cb)
        self.btn_del = big_btn("DELETE TRIP", go_delete_cb)

        row = QVBoxLayout(); row.setSpacing(22)
        c1 = QHBoxLayout(); c1.addStretch(1); c1.addWidget(self.btn_add); c1.addStretch(1)
        c2 = QHBoxLayout(); c2.addStretch(1); c2.addWidget(self.btn_del); c2.addStretch(1)
        row.addLayout(c1); row.addLayout(c2)

        pv.addLayout(row)
        pv.addStretch(2)

        root.addWidget(panel)

# ===================== Add Trip Page (บันทึกจริง) =====================
class AddTripPage(QWidget):
    def __init__(self, save_callback):
        super().__init__()
        self.save_callback = save_callback
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        
        wrap = QFrame()
        wrap.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        wl = QVBoxLayout(wrap); wl.setContentsMargins(30,30,30,30); wl.setSpacing(25)

        grid = QGridLayout(); grid.setHorizontalSpacing(30); grid.setVerticalSpacing(20)
        
        def title(t): lb=QLabel(t); lb.setFont(TH(30, QFont.Weight.Bold)); return lb
        def field(): 
            z=QLineEdit(); z.setFont(TH(24)); z.setMinimumHeight(70)
            z.setStyleSheet(f"QLineEdit{{border:2px solid {CARD_LINE};border-radius:10px;padding:10px 12px;}}")
            return z
        
        # --- ช่องกรอกข้อมูล ---
        grid.addWidget(title("จังหวัดต้นทาง"), 0, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(title("จังหวัดปลายทาง"), 0, 1, Qt.AlignmentFlag.AlignTop)
        self.in_from = field()
        self.in_to = field()
        # กำหนดค่าเริ่มต้นให้เป็น ขอนแก่น
        self.in_from.setText("ขอนแก่น")
        self.in_from.setReadOnly(True) 
        grid.addWidget(self.in_from, 1, 0)
        grid.addWidget(self.in_to, 1, 1)

        grid.addWidget(title("ความจุที่นั่ง"), 2, 0)
        grid.addWidget(title("ระยะเวลาในการเดินทาง (เช่น 4:00 ชม.)"), 2, 1)
        self.in_capacity = field()
        self.in_duration = field()
        self.in_capacity.setText("40") # กำหนดค่าเริ่มต้น
        grid.addWidget(self.in_capacity, 3, 0)
        grid.addWidget(self.in_duration, 3, 1)

        time_layout = QVBoxLayout()
        time_layout.addWidget(title("เวลาออก (เลือกได้หลายเวลา)"))
        time_btn_row = QHBoxLayout()
        self.time_buttons = {}
        for t in ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00"]: # เพิ่มตัวเลือกเวลามากขึ้น
            b = QPushButton(t); b.setCheckable(True); b.setFixedSize(130, 70); b.setFont(TH(26))
            b.setStyleSheet(f"""
                QPushButton{{background:{BUTTON_BG};border:2px solid {CARD_LINE};border-radius:12px;}} 
                QPushButton:checked{{background:#a9c5cf;color:white;border-color:#a9c5cf;}}
            """)
            self.time_buttons[t] = b
            time_btn_row.addWidget(b)
        time_btn_row.addStretch(1)
        time_layout.addLayout(time_btn_row)
        grid.addLayout(time_layout, 4, 0, 1, 2) # ขยายให้เต็ม 2 คอลัมน์

        btn_save = QPushButton("บันทึกเที่ยว")
        btn_save.setFixedSize(220, 70); btn_save.setFont(TH(30, QFont.Weight.Bold))
        btn_save.setStyleSheet("QPushButton{background:#a9c5cf;border:none;border-radius:16px;color:white;}")
        btn_save.clicked.connect(self._save_trip)
        grid.addWidget(btn_save, 5, 1, 1, 1, Qt.AlignmentFlag.AlignRight) # ย้ายไปอยู่คอลัมน์ 1

        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        wl.addLayout(grid); wl.addStretch(1)
        root.addWidget(wrap)

    def _save_trip(self):
        # 🚀 ส่วนที่แก้ไขโค้ด: นำข้อมูลไปบันทึกจริงลงในตาราง routes 🚀
        try:
            frm = self.in_from.text().strip()
            to = self.in_to.text().strip()
            # ตรวจสอบว่า capacity และ duration ถูกกรอกหรือไม่
            capacity_text = self.in_capacity.text().strip()
            duration = self.in_duration.text().strip()
            
            if not to:
                QMessageBox.warning(self, "ข้อมูลไม่ครบถ้วน", "กรุณากรอกจังหวัดปลายทาง"); return
            if not capacity_text or not capacity_text.isdigit() or int(capacity_text) <= 0:
                QMessageBox.warning(self, "ข้อมูลไม่ครบถ้วน", "กรุณากรอกความจุที่นั่งที่ถูกต้อง (ตัวเลขเท่านั้น)"); return
            if not duration:
                QMessageBox.warning(self, "ข้อมูลไม่ครบถ้วน", "กรุณากรอกระยะเวลาในการเดินทาง"); return
            
            capacity = int(capacity_text)
            selected_times = [t for t, b in self.time_buttons.items() if b.isChecked()]
            
            if not selected_times:
                QMessageBox.warning(self, "ข้อมูลไม่ครบถ้วน", "กรุณาเลือกเวลาออกอย่างน้อย 1 เวลา"); return
            
            success_count = 0
            duplicate_count = 0
            error_messages = []
            
            for dep_time in selected_times:
                is_success, msg = db_add_route(frm, to, dep_time, duration, capacity)
                if is_success:
                    success_count += 1
                elif "ซ้ำกัน" in msg:
                    duplicate_count += 1
                else:
                    error_messages.append(f"เวลา {dep_time}: {msg}")
            
            final_msg = f"สรุปการบันทึกเที่ยวรถไป **{to}**:\n"
            final_msg += f"- **บันทึกสำเร็จ:** {success_count} เที่ยว\n"
            if duplicate_count > 0:
                final_msg += f"- **มีอยู่แล้ว (ไม่บันทึกซ้ำ):** {duplicate_count} เที่ยว\n"
            if error_messages:
                final_msg += f"\n**ข้อผิดพลาดที่เกิดขึ้น:**\n" + "\n".join(error_messages)
            
            QMessageBox.information(self, "บันทึกเที่ยวรถ", final_msg)
            self.save_callback()

        except Exception as e:
            QMessageBox.critical(self, "ข้อผิดพลาดร้ายแรง", f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")
# 🚀 สิ้นสุดส่วนที่แก้ไข 🚀


# ===================== DELETE TRIP PAGE =====================
# (ไม่มีการเปลี่ยนแปลง)
class DeleteTripPage(QWidget):
    def __init__(self, back_cb):
        super().__init__()
        self.back_cb = back_cb
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)

        self.panel = QFrame(); self.panel.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        self.pv = QVBoxLayout(self.panel); self.pv.setContentsMargins(18,18,18,18); self.pv.setSpacing(18)
        
        self.routes_grid = QGridLayout()
        self.routes_grid.setHorizontalSpacing(15)
        self.routes_grid.setVerticalSpacing(15)
        self.pv.addLayout(self.routes_grid)
        self.pv.addStretch(1)

        row = QHBoxLayout(); row.addStretch(1)
        self.btn_back = QPushButton("ออก"); self.btn_back.setFixedSize(220,64)
        self.btn_back.setStyleSheet("QPushButton{background:#eaf0f3;color:#000;border:none;border-radius:16px;font-family:'Rubik';font-weight:800;font-size:22px;}")
        self.btn_back.clicked.connect(self.back_cb)
        row.addWidget(self.btn_back); row.addStretch(1)
        self.pv.addLayout(row)

        root.addWidget(self.panel)
        self.refresh_routes()

    def _delete_route_demo(self, frm: str, to: str):
        reply = QMessageBox.question(self, 'ยืนยันการลบ',
            f"คุณต้องการลบเส้นทาง {frm} → {to} จริงหรือไม่?\n(นี่คือการลบรายการจองทั้งหมดที่เกี่ยวข้องในทั้ง 2 ฐานข้อมูล)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            deleted_admin_rows, deleted_user_rows = db_delete_route_demo(frm, to)
            QMessageBox.information(self, "ลบสำเร็จ", 
                f"ลบเส้นทาง {frm} → {to} เรียบร้อยแล้ว\n"
                f"- ลบรายการสรุปการจอง (users.db): {deleted_admin_rows} รายการ\n"
                f"- ลบการจองที่นั่ง (passenger_bookings.db): {deleted_user_rows} รายการ"
            )
            self.refresh_routes()

    def refresh_routes(self):
        for i in reversed(range(self.routes_grid.count())): 
            widget = self.routes_grid.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        routes = db_get_all_routes()
        col_count = 3 
        
        card_style = f"QFrame{{background:{BUTTON_BG}; border:1px solid {CARD_LINE}; border-radius:12px;}}"
        btn_style = "QPushButton{background:transparent; border:none; font-size:32px;}"
        
        display_routes = []
        for frm, to, count in routes:
            if frm == 'ขอนแก่น':
                display_routes.append((frm, to, count))

        if not display_routes:
            self.routes_grid.addWidget(QLabel("ไม่พบเส้นทางในระบบ"), 0, 0, 1, col_count)
            return

        for index, (frm, to, count) in enumerate(display_routes):
            row = index // col_count
            col = index % col_count
            
            route_name = f"{frm} – {to}"
            
            container = QFrame()
            container.setStyleSheet(card_style)
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(15, 10, 10, 10) 
            h_layout.setSpacing(10)
            
            label = QLabel(route_name)
            label.setFont(TH(28))
            h_layout.addWidget(label, 1)

            delete_button = QPushButton("🗑️")
            delete_button.setFixedSize(50, 50)
            delete_button.setFont(QFont("Arial", 18))
            delete_button.setStyleSheet(btn_style)
            
            delete_button.clicked.connect(lambda checked, f=frm, t=to: self._delete_route_demo(f, t))
            
            h_layout.addWidget(delete_button)
            
            self.routes_grid.addWidget(container, row, col)
            self.routes_grid.setColumnStretch(col, 1)

# ===================== SimpleStubPage (ไม่มีการเปลี่ยนแปลง) =====================
class SimpleStubPage(QWidget):
    def __init__(self, title:str, back_cb):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        panel = QFrame(); panel.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        pv = QVBoxLayout(panel); pv.setContentsMargins(18,18,18,18); pv.setSpacing(18)
        h = QLabel(title); h.setFont(TH(32, QFont.Weight.Bold))
        pv.addWidget(h)
        pv.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1)
        back = QPushButton("ออก"); back.setFixedSize(220,64)
        back.setStyleSheet("QPushButton{background:#eaf0f3;color:#000;border:none;border-radius:16px;font-family:'Rubik';font-weight:800;font-size:22px;}")
        back.clicked.connect(back_cb)
        row.addWidget(back); row.addStretch(1)
        pv.addLayout(row)
        root.addWidget(panel)

# ===================== BOOKING & PAYMENT PAGE (NEW COMBINED) =====================
# (ไม่มีการเปลี่ยนแปลงการทำงาน)
class BookingAndPaymentPage(QWidget):
    def __init__(self, go_detail_cb):
        super().__init__()
        self.go_detail_cb = go_detail_cb
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)

        wrap = QFrame()
        wrap.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLineEdit{{background:transparent;border:2px solid {CARD_LINE};border-radius:10px;padding:12px 14px;font-family:'FC Minimal';font-size:26px;}} QTableWidget{{background:transparent;border:2px solid {CARD_LINE};border-radius:10px;gridline-color: transparent;}} QHeaderView::section{{background:transparent;border:none;font-family:'FC Minimal';font-size:24px;font-weight:700;padding:6px;}}")
        wl = QVBoxLayout(wrap); wl.setContentsMargins(16,16,16,16); wl.setSpacing(12)
        
        # Header ค้นหา
        search_wrap = QFrame(); search_wrap.setStyleSheet(f"QFrame{{border:2px solid {CARD_LINE}; border-radius:10px;}}")
        shl = QHBoxLayout(search_wrap); shl.setContentsMargins(10,5,10,5)
        self.search = QLineEdit(); self.search.setPlaceholderText("ค้นหาการจอง")
        self.search.setStyleSheet("QLineEdit{border:none;}")
        shl.addWidget(self.search)
        wl.addWidget(search_wrap)
        
        # ตาราง
        # คอลัมน์: เลขที่ตั๋ว, ลูกค้า, เที่ยวรถ, วันที่, สถานะ, จำนวนเงิน
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["เลขที่ตั๋ว","ลูกค้า","เที่ยวรถ","วันที่","สถานะ","จำนวนเงิน"])
        hh = self.table.horizontalHeader()
        
        # การกำหนดขนาดคอลัมน์เพื่อให้คล้ายภาพ:
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # เลขที่ตั๋ว
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)         # ลูกค้า
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)         # เที่ยวรถ
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # วันที่
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # สถานะ
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # จำนวนเงิน
        
        self.table.verticalHeader().setVisible(False)
        self.table.setFont(TH(22))
        wl.addWidget(self.table)
        
        root.addWidget(wrap)
        self.search.textChanged.connect(self.refresh)
        self.table.cellDoubleClicked.connect(self._open_detail)
        self.refresh()
        
    def _badge(self, status:str)->QWidget:
        display_status = status
        if status == "ยืนยัน":
            display_status = "เรียบร้อย"
            
        c = {"รอดำเนินการ":"#c7e7ff","ยืนยัน":"#bfe6c8","เรียบร้อย":"#bfe6c8","ยกเลิก":"#f3c2c2"}.get(status,"#c7e7ff")
        w = QLabel(display_status); w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setStyleSheet(f"QLabel{{background:{c};border:2px solid {CARD_LINE};border-radius:8px;padding:4px 8px;font-family:'FC Minimal';font-size:20px;}}")
        return w
        
    def refresh(self): 
        rows = db_search_bookings(self.search.text())
        self.table.setRowCount(0)
        
        for (rid, tno, cust, frm, to, date, status, price, vat) in rows:
            r = self.table.rowCount(); self.table.insertRow(r)
            def item(s): x=QTableWidgetItem(s); x.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable); return x
            
            it = item(tno); it.setData(Qt.ItemDataRole.UserRole, rid)
            
            # คำนวณจำนวนเงิน
            amount = float(price or 0) + float(vat if vat is not None else 0)
            amount_str = f"{amount:,.2f}"
            
            self.table.setItem(r,0,it)
            self.table.setItem(r,1,item(cust))
            self.table.setItem(r,2,item(f"{frm} - {to}"))
            self.table.setItem(r,3,item(self._pretty(date)))
            self.table.setCellWidget(r,4,self._badge(status)) # สถานะใช้ Widget
            self.table.setItem(r,5,item(amount_str)) # จำนวนเงิน
            
    def _open_detail(self, row, col):
        it = self.table.item(row,0)
        if not it: return
        self.go_detail_cb(it.data(Qt.ItemDataRole.UserRole), mode="booking")
        
    @staticmethod
    def _pretty(d):
        try: y,m,dd = d.split("-"); return f"{int(dd)}/{int(m)}/{y}"
        except: return d


class BookingDetailPage(QWidget):
    # (ไม่มีการเปลี่ยนแปลงการทำงาน)
    def __init__(self, go_back_cb):
        super().__init__()
        self.row_id=None
        self.go_back_cb = go_back_cb
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        main = QHBoxLayout(); main.setSpacing(12)
        left = QFrame(); left.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        lv = QVBoxLayout(left); lv.setContentsMargins(16,16,16,16); lv.setSpacing(10)
        title = QLabel("รายการการจอง"); title.setFont(TH(30, QFont.Weight.Bold))
        lv.addWidget(title)
        self.summary = QFrame(); self.summary.setStyleSheet("QFrame{background:#eaf4f7;border:none;border-radius:8px;} QLabel{border:none}")
        sv = QVBoxLayout(self.summary); sv.setContentsMargins(14,12,14,12); sv.setSpacing(6)
        self.lb_route = QLabel(); self.lb_route.setFont(TH(28, QFont.Weight.Bold))
        self.lb_date = QLabel(); self.lb_dep = QLabel(); self.lb_arr = QLabel()
        self.lb_cust = QLabel(); self.lb_seat = QLabel(); self.lb_price = QLabel(); self.lb_vat = QLabel()
        for w in (self.lb_date,self.lb_dep,self.lb_arr,self.lb_cust,self.lb_seat,self.lb_price,self.lb_vat): w.setFont(TH(24))
        for w in (self.lb_route,self.lb_date,self.lb_dep,self.lb_arr,self.lb_cust,self.lb_seat,self.lb_price,self.lb_vat): sv.addWidget(w)
        self.total = QFrame(); self.total.setStyleSheet("QFrame{background:#e8e1d8;border-radius:8px;} QLabel{border:none}")
        tb = QHBoxLayout(self.total); tb.setContentsMargins(12,8,12,8)
        t = QLabel("ทั้งหมด"); t.setFont(TH(26, QFont.Weight.Bold)); self.lb_total = QLabel("— บาท"); self.lb_total.setFont(TH(26, QFont.Weight.Bold))
        tb.addWidget(t); tb.addStretch(1); tb.addWidget(self.lb_total)
        lv.addWidget(self.summary); lv.addWidget(self.total)
        main.addWidget(left,2)
        right_col = QVBoxLayout(); right_col.setSpacing(10)
        info = QFrame(); info.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        iv = QVBoxLayout(info); iv.setContentsMargins(16,16,16,16); iv.setSpacing(8)
        h = QLabel("ข้อมูลผู้จองตั๋วโดยสาร"); h.setFont(TH(30, QFont.Weight.Bold)); iv.addWidget(h)
        self.cus_name = QLabel(); self.cus_phone = QLabel(); self.cus_email = QLabel()
        for w in (self.cus_name,self.cus_phone,self.cus_email): w.setFont(TH(24)); iv.addWidget(w)
        right_col.addWidget(info)
        action = QFrame(); action.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        ac = QGridLayout(action); ac.setContentsMargins(16,16,16,16); ac.setHorizontalSpacing(12); ac.setVerticalSpacing(8)
        self.slip_box = QFrame(); self.slip_box.setStyleSheet("QFrame{background:#eaf4f7;border:none;border-radius:8px;} QLabel{border:none}")
        sb = QVBoxLayout(self.slip_box); sb.setContentsMargins(8,8,8,8)
        self.slip_img = QLabel("รูปสลิปที่ผู้ใช้อัปโหลด"); self.slip_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slip_img.setMinimumSize(360,210); self.slip_img.setFont(TH(22))
        sb.addWidget(self.slip_img)
        
        # เพิ่มปุ่มยืนยัน/ยกเลิก (Admin Actions)
        self.btn_confirm = QPushButton("✅ ยืนยันการชำระเงิน")
        self.btn_cancel = QPushButton("❌ ยกเลิกการจอง")
        btn_style = "QPushButton{background:#60a080;color:white;border:none;border-radius:12px;padding:8px;font-family:'FC Minimal';font-size:24px;}"
        self.btn_confirm.setStyleSheet(btn_style)
        self.btn_cancel.setStyleSheet(btn_style.replace("#60a080", "#c76060"))
        
        self.btn_confirm.clicked.connect(self._confirm_booking)
        self.btn_cancel.clicked.connect(self._cancel_booking)
        
        action_row = QHBoxLayout()
        action_row.addWidget(self.btn_confirm)
        action_row.addWidget(self.btn_cancel)
        
        iv.addLayout(action_row) # เพิ่มปุ่มใน Info Box 
        
        ac.addWidget(self.slip_box, 0,0,1,1)
        right_col.addWidget(info)
        main.addLayout(right_col,1)
        root.addLayout(main)
        self.bottom_wrap = QWidget()
        row = QHBoxLayout(self.bottom_wrap); row.setContentsMargins(0,0,0,0); row.setSpacing(12)
        row.addStretch(1)
        self.btn_back = QPushButton("ออก")
        self.btn_back.setFixedSize(220,64)
        self.btn_back.setStyleSheet("QPushButton{background:#eaf0f3;color:#000;border:none;border-radius:16px;font-family:'Rubik';font-weight:800;font-size:22px;}")
        self.btn_back.clicked.connect(self.go_back_cb) 
        row.addWidget(self.btn_back)
        row.addStretch(1)
        root.addWidget(self.bottom_wrap)

    def _confirm_booking(self):
        self._update_status("ยืนยัน", "ยืนยันการชำระเงิน", "การจองถูกยืนยันเรียบร้อยแล้ว")
        
    def _cancel_booking(self):
        self._update_status("ยกเลิก", "ยกเลิกการจอง", "การจองถูกยกเลิกเรียบร้อยแล้ว")

    def _update_status(self, new_status:str, title:str, message:str):
        if self.row_id is None:
            QMessageBox.warning(self, title, "ไม่พบรายการจองที่จะอัปเดต"); return

        try:
            with closing(db_connect_admin()) as conn_admin, conn_admin, closing(conn_admin.cursor()) as cur_admin:
                # อัปเดตตาราง bookings ใน users.db
                cur_admin.execute("UPDATE bookings SET status=? WHERE id=?", (new_status, self.row_id))
                
                # ถ้า 'ยืนยัน' ให้ค้นหา ticket_no และอัปเดต is_booked ใน passenger_bookings.db
                if new_status == 'ยืนยัน':
                    # ดึง ticket_no
                    cur_admin.execute("SELECT ticket_no FROM bookings WHERE id=?", (self.row_id,))
                    ticket_no = cur_admin.fetchone()[0]
                    
                    if ticket_no:
                        with closing(db_connect_user()) as conn_user, conn_user, closing(conn_user.cursor()) as cur_user:
                            # อัปเดตสถานะใน passenger_bookings (ตั้งเป็น is_booked = 1 อยู่แล้ว แต่ยืนยันอีกครั้งเพื่อความชัวร์)
                            cur_user.execute("UPDATE passenger_bookings SET is_booked=1 WHERE ticket_no=?", (ticket_no,))
                            
                elif new_status == 'ยกเลิก':
                    # ดึง ticket_no
                    cur_admin.execute("SELECT ticket_no FROM bookings WHERE id=?", (self.row_id,))
                    ticket_no = cur_admin.fetchone()[0]

                    if ticket_no:
                        with closing(db_connect_user()) as conn_user, conn_user, closing(conn_user.cursor()) as cur_user:
                            # ลบรายการจองที่นั่งใน passenger_bookings (เพื่อให้ที่นั่งว่าง)
                            cur_user.execute("DELETE FROM passenger_bookings WHERE ticket_no=?", (ticket_no,))
                            
            QMessageBox.information(self, title, message)
            self.load_row(self.row_id) # โหลดข้อมูลใหม่เพื่ออัปเดตหน้าจอ
            
        except Exception as e:
            QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถอัปเดตสถานะได้: {e}")

    def load_row(self, rid:int, mode:str="manage"):
        self.row_id = rid
        data = db_get_booking(rid)
        if not data:
            QMessageBox.warning(self,"ไม่พบข้อมูล","รายการนี้ถูกลบไปแล้ว"); return
        (_id,ticket,name,frm,to,date,status,phone,email,seat,price,vat,slip,dep,arr)=data
        self.lb_route.setText(f"{frm} - {to} (TICKET: {ticket})")
        
        # ตรวจสอบสถานะเพื่อเปิด/ปิดปุ่ม
        is_pending = (status == 'รอดำเนินการ')
        self.btn_confirm.setEnabled(is_pending)
        self.btn_cancel.setEnabled(status != 'ยกเลิก')
        
        # อัปเดต UI 
        self.lb_date.setText(f"วันที่ {self._pretty(date)}")
        self.lb_dep.setText(f"{(dep or '-').replace(':','.') }    {frm} บขส.3")
        self.lb_arr.setText(f"{(arr or '-').replace(':','.') }    {to}")
        self.lb_cust.setText(f"คุณ {name} (สถานะ: {status})") # แสดงสถานะ
        self.lb_seat.setText(f"ที่นั่ง    {seat or '-'}")
        p = float(price or 0); v = float(vat or round(p*0.07,2)); total = round(p+v,2)
        self.lb_price.setText(f"ราคา    {p:,.0f} บาท")
        self.lb_vat.setText(f"TAX VAT7%    {v:,.2f} บาท")
        self.lb_total.setText(f"{total:,.2f} บาท")
        self.cus_name.setText(f"คุณ {name}")
        self.cus_phone.setText(f"เบอร์โทร {phone or '-'}")
        self.cus_email.setText(f"Email {email or '-'}")
        if slip and os.path.exists(slip):
            pix = QPixmap(slip).scaled(360,210, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.slip_img.setPixmap(pix)
        else:
            self.slip_img.setPixmap(QPixmap())

    @staticmethod
    def _pretty(d):
        try: y,m,dd = d.split("-"); return f"{int(dd)}/{int(m)}/{y}"
        except: return d

class DashboardPage(QWidget):
    # (ฟังก์ชัน _refresh_stats ถูกแก้ไขเพื่อรวมการเชื่อมต่อ DB)
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        panel = QFrame(); panel.setStyleSheet(f"QFrame{{border:3px solid {CARD_LINE};border-radius:10px;}} QLabel{{border:none}}")
        p = QVBoxLayout(panel); p.setContentsMargins(18,18,18,18); p.setSpacing(18)
        rowTop = QHBoxLayout(); rowTop.setSpacing(18)
        self.box_orders    = StatBox("จำนวนการจองวันนี้", "ตัวเลขที่นี่คือคนจองมาจริง")
        self.box_income    = StatBox("รายได้", "รายได้จริง")
        self.box_seats     = StatBox("รายการเที่ยวทั้งหมด", "ที่นั่งที่เหลือจริง")
        rowTop.addWidget(self.box_orders,1)
        rowTop.addWidget(self.box_income,1)
        rowTop.addWidget(self.box_seats,1)
        p.addLayout(rowTop)
        group = QFrame(); group.setStyleSheet(f"QFrame{{border:2px solid {CARD_LINE};border-radius:12px;}} QLabel{{border:none}}")
        g = QGridLayout(group); g.setContentsMargins(14,14,14,14); g.setHorizontalSpacing(18); g.setVerticalSpacing(10)
        g.addWidget(self._title("สรุปยอดจองตามช่วงเวลา"), 0,0,1,1)
        selWrap = QHBoxLayout(); selWrap.setSpacing(10)
        self.dayBox = QComboBox(); self.monthBox = QComboBox(); self.yearBox = QComboBox()
        for cb in (self.dayBox,self.monthBox,self.yearBox):
            cb.setStyleSheet("QComboBox{font-family:'FC Minimal';font-size:26px;padding:6px 10px;border:2px solid #9b7a55;border-radius:10px;}")
            cb.setMinimumHeight(48)
        self.dayBox.addItems([f"{d:02d}" for d in range(1,32)])
        self.monthBox.addItems([f"{m:02d}" for m in range(1,13)])
        this_year = datetime.date.today().year
        self.yearBox.addItems([str(y) for y in range(this_year-2, this_year+3)])
        today = datetime.date.today()
        self.dayBox.setCurrentText(f"{today.day:02d}")
        self.monthBox.setCurrentText(f"{today.month:02d}")
        self.yearBox.setCurrentText(str(today.year))
        selWrap.addWidget(self._title("เลือกวันที่"));      selWrap.addWidget(self.dayBox)
        selWrap.addWidget(self._title("เลือกเดือน")); selWrap.addWidget(self.monthBox)
        selWrap.addWidget(self._title("เลือกปี"));      selWrap.addWidget(self.yearBox)
        selWrap.addStretch(1)
        g.addLayout(selWrap, 0,1,1,2)
        self.pill_income = SoftPill(f"รายได้วันที่ {today.strftime('%d/%m/%Y')} (บาท)")
        self.pill_orders = SoftPill("จำนวนการจอง")
        self.pill_avg      = SoftPill("ยอดเฉลี่ยต่อออเดอร์ (บาท)")
        g.addWidget(self.pill_income, 1,0,1,1)
        g.addWidget(self.pill_orders, 1,1,1,1)
        g.addWidget(self.pill_avg,    1,2,1,1)
        p.addWidget(group)
        rowBottom = QHBoxLayout(); rowBottom.setSpacing(18)
        self.topRoutes = ListCard("Top Routes")
        self.emptyTrip = ListCard("เที่ยวรถเปล่า", subtitle="เที่ยวรถที่ผู้ใช้ไม่ค่อยกดจอง")
        rowBottom.addWidget(self.topRoutes,2)
        rowBottom.addWidget(self.emptyTrip,1)
        p.addLayout(rowBottom)
        root.addWidget(panel)
        self.dayBox.currentIndexChanged.connect(self._refresh_stats)
        self.monthBox.currentIndexChanged.connect(self._refresh_stats)
        self.yearBox.currentIndexChanged.connect(self._refresh_stats)
        self._refresh_stats()
        self.timer=QTimer(self); self.timer.timeout.connect(self._refresh_stats)
        self.timer.start(4000)
    def _title(self, t): lb = QLabel(t); lb.setFont(TH(28, QFont.Weight.Bold)); return lb
    def _selected_date_str(self)->str:
        d = self.dayBox.currentText()
        m = self.monthBox.currentText()
        y = self.yearBox.currentText()
        return f"{y}-{m}-{d}"
    def _refresh_stats(self, *args):
        ymd = self._selected_date_str()
        stats = db_stats_for_date(ymd)
        d_obj = QDate(int(self.yearBox.currentText()), int(self.monthBox.currentText()), int(self.dayBox.currentText()))
        self.pill_income.layout().itemAt(0).widget().setText(f"รายได้วันที่ {d_obj.toString('dd/MM/yyyy')} (บาท)")
        self.box_orders.set_value(f"{stats['orders']:,} ครั้ง")
        self.box_income.set_value(f"{stats['revenue']:,.2f} บาท")
        self.box_seats.set_value(f"ที่นั่งที่เหลือจริง {stats['seats_remaining']:,} ที่นั่ง")
        self.pill_income.set_value(f"{stats['revenue']:,.2f} บาท")
        self.pill_orders.set_value(f"{stats['orders']:,} ครั้ง")
        self.pill_avg.set_value(f"{stats['avg']:,.2f} บาท")
        top_rows = [f"{r} (จอง {c} ครั้ง)" for (r,c) in stats["top_routes"]]
        self.topRoutes.set_rows(top_rows)
        if stats["least_route"]:
            r,c = stats["least_route"]
            self.emptyTrip.set_rows([f"{r} (ใช้งานน้อยสุด {c} ครั้ง)"])
        else:
            self.emptyTrip.set_rows(["—"])

class UserManagementPage(QWidget):
    # (ไม่มีการเปลี่ยนแปลง)
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        t = QLabel("USER MANAGEMENT"); t.setFont(TH(32, QFont.Weight.Bold)); t.setStyleSheet("border:none")
        root.addWidget(t)
        info = QLabel("ข้อมูลผู้ใช้งานทั้งหมดที่ดึงมาจาก users.db"); info.setFont(TH(24))
        root.addWidget(info)
        self.user_list = QTextEdit(); self.user_list.setReadOnly(True); self.user_list.setFont(TH(22))
        self.user_list.setStyleSheet(f"QTextEdit{{border:2px solid {CARD_LINE};border-radius:10px;padding:10px;}}")
        root.addWidget(self.user_list)
        refresh_btn = QPushButton("Refresh User List")
        refresh_btn.setFixedSize(200, 50)
        refresh_btn.setStyleSheet("QPushButton{background:#a9c5cf;border:none;border-radius:12px;color:white;font-family:Rubik;font-weight:700;font-size:18px;}")
        refresh_btn.clicked.connect(self.load_users)
        h_row = QHBoxLayout(); h_row.addStretch(1); h_row.addWidget(refresh_btn); h_row.addStretch(1)
        root.addLayout(h_row)
        root.addStretch(1)
        self.load_users()
    def load_users(self):
        users = db_get_all_users() # ใช้ฟังก์ชันใหม่ที่เชื่อมต่อ users.db
        if not users:
            self.user_list.setText("ไม่พบผู้ใช้งานในระบบ")
            return
        text = "ID | USERNAME | ROLE | PHONE | EMAIL | CREATED_AT\n"
        text += "---" * 15 + "\n"
        for user_id, username, role, phone, email, created_at in users:
            text += f"{user_id:<3} | {username:<10} | {role:<5} | {phone or '-':<10} | {email or '-':<20} | {created_at}\n"
        self.user_list.setText(text)

# ===================== MAIN SHELL (ไม่มีการเปลี่ยนแปลง) =====================
class AdminApp(QWidget):
    def __init__(self, current_user="admin"):
        super().__init__()
        load_fonts(); db_init()

        self.setWindowTitle(f"Go with CREPE — Admin — {current_user}")
        self.resize(1366, 768)
        self.setStyleSheet(f"background:{BG_MAIN}; color:{INK};")

        root = QVBoxLayout(self); root.setContentsMargins(28,14,28,14); root.setSpacing(14)

        # Header
        header = QHBoxLayout(); header.setSpacing(18)
        logo = QLabel()
        if os.path.exists(LOGO_IMG):
            pix = QPixmap(LOGO_IMG).scaled(210,210, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo.setPixmap(pix)
        logo.setFixedSize(230,130)
        header.addWidget(logo, alignment=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)

        # Nav
        self.nav = QFrame(objectName="nav")
        self.nav.setStyleSheet(f"""
            QFrame#nav {{background:{BROWN};border-radius:28px;padding:6px;}}
            QPushButton[role="nav"] {{
                border:none;border-radius:18px;padding:6px 18px;min-height:34px;color:white;
                font-family:Rubik;font-size:15px;font-weight:700;background:transparent;
            }}
            QPushButton[role="nav"][active="true"] {{ background:#eaf4f7; color:#000; }}
            QPushButton[role="nav"]:hover {{ background:#9b7447; }}
        """)
        navrow = QHBoxLayout(self.nav); navrow.setContentsMargins(10,4,10,4); navrow.setSpacing(6)
        
        self.b_dash=QPushButton("DASHBOARD")
        self.b_trip=QPushButton("MANAGE TRIP")       
        # เมนูใหม่ BOOKING&PAYMENT
        self.b_booking_pay=QPushButton("BOOKING&PAYMENT")
        self.b_user=QPushButton("USER MANAGEMENT")
        
        for b in (self.b_dash,self.b_trip,self.b_booking_pay,self.b_user):
            b.setProperty("role","nav"); b.clicked.connect(self._nav_clicked); navrow.addWidget(b)
        header.addStretch(1); header.addWidget(self.nav, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        # Pages
        self.stack = QStackedWidget(); root.addWidget(self.stack)
        self.p_dash      = DashboardPage()
        self.p_tripHub   = ManageTripHubPage(self._go_add_trip, self._go_delete_trip) 
        self.p_addTrip   = AddTripPage(self._back_to_trip_hub)
        self.p_delTrip   = DeleteTripPage(self._back_to_trip_hub) 
        self.p_booking_pay = BookingAndPaymentPage(self._go_detail) 
        self.p_detail    = BookingDetailPage(self._back_to_booking_pay)
        self.p_user      = UserManagementPage()

        for p in (self.p_dash, self.p_tripHub, self.p_addTrip, self.p_delTrip, 
                  self.p_booking_pay, self.p_detail, self.p_user):
            self.stack.addWidget(p)

        # หน้าแรก = DASHBOARD
        self.stack.setCurrentWidget(self.p_dash)
        self._set_active(self.b_dash)

    def _set_active(self,btn):
        for b in (self.b_dash,self.b_trip,self.b_booking_pay,self.b_user):
            b.setProperty("active","true" if b is btn else "false")
            b.style().unpolish(b); b.style().polish(b); b.update()

    def _nav_clicked(self):
        s = self.sender()
        mapping = {
            self.b_dash:self.p_dash,
            self.b_trip:self.p_tripHub,
            self.b_booking_pay:self.p_booking_pay,
            self.b_user:self.p_user
        }
        self.stack.setCurrentWidget(mapping.get(s,self.p_dash))
        self._set_active(s)
        if s == self.b_user:
            self.p_user.load_users()
        elif s == self.b_booking_pay:
            self.p_booking_pay.refresh()

    # ----- MANAGE TRIP flows -----
    def _go_add_trip(self):
        self.stack.setCurrentWidget(self.p_addTrip)
        self._set_active(self.b_trip)
    def _go_delete_trip(self):
        self.p_delTrip.refresh_routes()
        self.stack.setCurrentWidget(self.p_delTrip)
        self._set_active(self.b_trip)
    def _back_to_trip_hub(self):
        self.stack.setCurrentWidget(self.p_tripHub)
        self._set_active(self.b_trip)

    # ----- Booking Detail flows -----
    def _go_detail(self, row_id:int, mode:str="booking"):
        self.p_detail.load_row(row_id, mode=mode)
        self.stack.setCurrentWidget(self.p_detail)
        self._set_active(self.b_booking_pay)

    def _back_to_booking_pay(self):
        self.p_booking_pay.refresh()
        self.stack.setCurrentWidget(self.p_booking_pay)
        self._set_active(self.b_booking_pay)

# -------- RUN --------
if __name__ == "__main__":
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    w = AdminApp()
    w.show()
    sys.exit(app.exec())