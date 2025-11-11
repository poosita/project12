import os, sys, re, random, sqlite3
import json
from contextlib import closing
from PyQt6.QtCore import Qt, QDate, QLocale, QMarginsF, QRectF, QLineF, QUrl, QSize
from PyQt6.QtGui import (
    QFontDatabase, QFont, QPixmap, QPainter, QColor,
    QPageSize, QPageLayout, QPdfWriter, QPen, QPainterPath, QIcon, QDesktopServices
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QComboBox, QDateEdit,
    QHBoxLayout, QVBoxLayout, QGridLayout, QFrame, QMessageBox, QSizePolicy,
    QStackedWidget, QLineEdit, QSpacerItem, QFileDialog
)

# ---------- CLI context ----------
def _get_arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default

CURRENT_USER = _get_arg("--user", "guest")

# ---------- Paths (แก้ตามเครื่องคุณ) ----------
# ******************************************************************************
# ⚠️ ตรวจสอบพาธ 4 ตำแหน่งนี้ให้ถูกต้องตามเครื่องของคุณ!
LOGO_IMG    = r"picture\logo.png"
QR_IMG      = r"picture\QR.png"
RUBIK_REG   = r"font\Rubik-Regular.ttf"
RUBIK_BOLD  = r"font\Rubik-Bold.ttf"
FC_MINIMAL  = r"font\FC Minimal.ttf"
# ******************************************************************************

PROFILE_DIR  = os.path.join(os.path.expanduser("passenger_bookings"))
PROFILE_PATH = os.path.join(PROFILE_DIR, "profile_avatar.png")

# ---------- DB ( passenger_bookings.db - ระบบ DB ใหม่ ) ----------
DB_DIR      = r"C:\Users\LOQ\OneDrive - Khon Kaen University\Desktop\project python\dataelee"  
DB_USER_PATH = os.path.join(DB_DIR, "passenger_bookings.db") 

# DB ของ ADMIN (ต้องชี้ไปที่เดียวกันกับที่ Admin.py ใช้)
DB_ADMIN_PATH = "users.db"

def db_connect_user():
    """เชื่อมต่อฐานข้อมูลผู้ใช้งาน (passenger_bookings.db)"""
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB_USER_PATH)

def _db_connect_admin():
    # สร้างไฟล์ Admin DB ชั่วคราวหากไม่มี (เพื่อไม่ให้โค้ดส่วนนี้ Error)
    if not os.path.exists(DB_ADMIN_PATH):
          con = sqlite3.connect(DB_ADMIN_PATH)
          con.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_no TEXT, customer_name TEXT, route_from TEXT, route_to TEXT, date TEXT, status TEXT,
                phone TEXT, email TEXT, seat TEXT, price REAL, vat REAL, slip_path TEXT, dep_time TEXT, arr_time TEXT
            );
          """)
          con.commit()
          return con
    return sqlite3.connect(DB_ADMIN_PATH)

def _check_and_add_column(con, table_name, column_name, column_type):
    """ฟังก์ชันช่วยเหลือ: ตรวจสอบว่าคอลัมน์มีอยู่แล้วหรือไม่ หากไม่มีให้เพิ่มเข้าไป (Migration)"""
    try:
        cur = con.cursor()
        # ตรวจสอบว่าคอลัมน์มีอยู่ในตารางหรือไม่
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in cur.fetchall()]
        
        if column_name not in columns:
            # เพิ่มคอลัมน์หากยังไม่มี
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            print(f"INFO: Added column {column_name} to table {table_name}")
            con.commit()
            return True
        return False
    except sqlite3.OperationalError as e:
        # อาจเกิดข้อผิดพลาดหากตารางไม่มีอยู่
        print(f"WARNING: Could not check/add column {column_name}. Error: {e}")
        return False

def init_db():
    """สร้างตารางรวมสำหรับเก็บข้อมูลการจองและที่นั่ง (และอัปเดตโครงสร้างเดิม)"""
    try:
        with db_connect_user() as con:
            cur = con.cursor()
            # 1. สร้างตาราง passenger_bookings หากยังไม่มี
            cur.execute("""
            CREATE TABLE IF NOT EXISTS passenger_bookings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                
                first_name      TEXT NOT NULL,
                last_name       TEXT NOT NULL,
                phone           TEXT NOT NULL,
                citizen_id      TEXT NOT NULL,
                email           TEXT,
                
                travel_date     TEXT NOT NULL,
                trip_info_json  TEXT NOT NULL,
                seat_code       TEXT NOT NULL,
                is_booked       INTEGER DEFAULT 1,
                ticket_no       TEXT,              
                
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(travel_date, trip_info_json, seat_code)
            );
            """)
            con.commit()

            # 2. Migration: เพิ่มคอลัมน์ที่จำเป็นหากมาจาก DB เวอร์ชันเก่า
            _check_and_add_column(con, "passenger_bookings", "ticket_no", "TEXT")

            # 3. สร้างตาราง route_info (หากยังไม่ได้รันสคริปต์ import_routes.py มาก่อน)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS route_info (
                    province_th TEXT PRIMARY KEY,
                    price INTEGER NOT NULL,
                    arrivals_json TEXT NOT NULL
                );
            """)
            con.commit()

    except sqlite3.OperationalError as e:
        print(f"Error during DB initialization: {e}")

# ---------- Route DB Function (NEW) ----------

def get_routes_from_admin_db() -> dict:
    """🌟 ดึงข้อมูลเส้นทางจากตาราง ROUTES ใน USERS.DB (ที่ Admin Console บันทึก) 🌟"""
    route_map = {}
    try:
        with closing(_db_connect_admin()) as conn, closing(conn.cursor()) as cur:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='routes';")
            if not cur.fetchone(): return {} # ตาราง routes ไม่มี

            cur.execute("SELECT route_from, route_to, departure_time, duration, capacity FROM routes")
            routes = cur.fetchall()
            
            for frm, to, dep_time, duration, capacity in routes:
                if frm == "ขอนแก่น":
                    # ใช้ปลายทางเป็น Key หลัก
                    route_map.setdefault(to, {}).setdefault('arrivals', []).append(dep_time)
                    # กำหนดคุณสมบัติอื่น ๆ (ใช้ค่าแรกที่พบ)
                    if 'price' not in route_map[to]:
                        # NOTE: ตาราง routes ไม่มีคอลัมน์ราคาโดยตรง, ต้องกำหนดค่าเริ่มต้น
                        route_map[to]['price'] = 100 
                    route_map[to]['duration'] = duration
                    route_map[to]['capacity'] = capacity
            
            # เรียงลำดับเวลาออกรถ
            for dest in route_map:
                if 'arrivals' in route_map[dest]:
                    route_map[dest]['arrivals'].sort()
        
    except Exception as e:
        print(f"ERROR: Could not fetch route data from users.db/routes: {e}")
        return {} 

    return route_map

def get_all_routes_from_db() -> dict:
    """ดึงข้อมูลเส้นทางทั้งหมดจากตาราง route_info ใน passenger_bookings.db (FALLBACK เก่า)"""
    routes = {}
    try:
        with db_connect_user() as con: 
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='route_info';")
            if not cur.fetchone(): return {}

            cur.execute("SELECT province_th, price, arrivals_json FROM route_info")
            
            for province_th, price, arrivals_json in cur.fetchall():
                # โค้ดเดิมใช้ arrivals_json แต่ขาด duration/capacity
                arrivals_list = json.loads(arrivals_json) 
                
                routes[province_th] = {
                    "price": price,
                    "arrivals": arrivals_list,
                    "duration": "N/A", # Hardcoded เพื่อให้โค้ดอื่นไม่ Error
                    "capacity": 40
                }
    except Exception as e:
        print(f"ERROR: Could not fetch route data from passenger_bookings.db/route_info: {e}")
        return {} 
    
    return routes

# 🚨 ฟังก์ชันนี้ถูกประกาศใน Global Scope 🚨
def _admin_db_save_booking_summary(data: dict, seat_list: list[str], ticket_no: str):
    """
    บันทึกสรุปการจองลงในฐานข้อมูล 'bookings' ของ Admin (users.db) 
    """
    try:
        with _db_connect_admin() as con:
            cur = con.cursor()
            
            price_each = float(data['price_each'])
            qty = len(seat_list)
            subtotal = price_each * qty
            vat = round(subtotal * 0.07, 2)
            
            customer_name = f"{data['first_name']} {data['last_name']}"
            route_from = data['origin'].split()[0] # ดึงแค่จังหวัด "ขอนแก่น"
            route_to = data['dest']
            date_str = data['date'].toString("yyyy-MM-dd")
            seat_str = ", ".join(seat_list)
            
            cur.execute("""
                INSERT INTO bookings(
                    ticket_no, customer_name, route_from, route_to, date, status,
                    phone, email, seat, price, vat, slip_path, dep_time, arr_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_no,
                customer_name,
                route_from,
                route_to,
                date_str,
                "รอดำเนินการ", 
                data['phone'],
                data['email'],
                seat_str,
                subtotal,
                vat,
                data.get('slip_path', ''),
                data['dep_time'],
                data['arr_time']
            ))
            con.commit()
    except Exception as e:
        print(f"Admin DB Save Error: {e}")

# 🚨 ฟังก์ชันนี้ถูกประกาศใน Global Scope 🚨
def get_booked_seats(qdate: QDate, dep_time: str, dest: str) -> set[str]:
    """ดึงที่นั่งที่ถูกจองแล้วสำหรับเที่ยวรถและวันที่เฉพาะ"""
    dstr = qdate.toString("yyyy-MM-dd")
    
    dest_part = f'"dest": "{dest}"' 
    dep_time_part = f'"dep_time": "{dep_time}"' 
    
    with db_connect_user() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT seat_code FROM passenger_bookings 
            WHERE travel_date = ? 
            AND trip_info_json LIKE ? 
            AND trip_info_json LIKE ? 
            AND is_booked = 1
        """, (
            dstr, 
            f'%{dest_part}%',
            f'%{dep_time_part}%'
        ))
        return {r[0] for r in cur.fetchall()}

# 🚨 ฟังก์ชันนี้ถูกประกาศใน Global Scope 🚨
def save_new_booking(data: dict, seat_list: list[str], ticket_no: str):
    """บันทึกการจองใหม่ลงในตาราง passenger_bookings"""
    
    trip_data = {
        "origin": data['origin'],
        "dest": data['dest'],
        "dep_time": data['dep_time'],
        "arr_time": data['arr_time'],
        "price": data['price_each']
    }
    trip_info_json = json.dumps(trip_data)
    travel_date = data['date'].toString("yyyy-MM-dd") 
    
    with db_connect_user() as con:
        cur = con.cursor()
        booking_id = None
        for seat in seat_list:
            cur.execute("""
            INSERT OR IGNORE INTO passenger_bookings (
                first_name, last_name, phone, citizen_id, email, travel_date, trip_info_json, seat_code, ticket_no
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['first_name'], 
                data['last_name'], 
                data['phone'], 
                data['citizen_id'], 
                data['email'], 
                travel_date, 
                trip_info_json, 
                seat,
                ticket_no
            ))
            if booking_id is None:
                booking_id = cur.lastrowid
        con.commit()
        return booking_id if booking_id else -1

# ----------------------------------------------------

# ---------- Theme ----------
BG_MAIN     = "#fbf7f1"
BROWN       = "#8a663f"
PILL_BG     = "#dfddda"
BTN_BG      = "#eef4f5"
STEP_GREY   = "#d9d9d9"
TEXT_DARK   = "#111"
CARD_BLUE   = "#eaf3f6"
CARD_LT     = "#eef6fb"
INK         = "#2b2b2b"

CARD_BORDER = "#9fd0d8"
TEXT_SOFT   = "#3a3a3a"

# ---------- Route data Loading (แก้ไขส่วนนี้) ----------

# 1. ข้อมูล Fallback Hard-coded
HARDCODED_ROUTES = {
    "มหาสารคาม":{"price":70,"arrivals":["08:30","10:30","12:30"]},
    "กาฬสินธุ์":{"price":90,"arrivals":["08:45","10:45","12:45"]},
    "ร้อยเอ็ด":{"price":110,"arrivals":["09:15","11:15","13:15"]},
    "อุดรธานี":{"price":100,"arrivals":["09:00","11:00","13:00"]},
    "ชัยภูมิ":{"price":160,"arrivals":["09:30","11:30","13:30"]},
    "หนองบัวลำภู":{"price":170,"arrivals":["09:30","11:30","13:30"]},
    "หนองคาย":{"price":190,"arrivals":["10:00","12:00","14:00"]},
    "ยโสธร":{"price":200,"arrivals":["10:15","12:15","14:15"]},
    "บุรีรัมย์":{"price":250,"arrivals":["10:30","12:30","14:30"]},
    "นครราชสีมา":{"price":220,"arrivals":["10:15","12:15","14:15"]},
    "เลย":{"price":260,"arrivals":["11:00","13:00","15:00"]},
    "สุรินทร์":{"price":300,"arrivals":["11:30","13:30","15:30"]},
    "อำนาจเจริญ":{"price":350,"arrivals":["12:00","14:00","16:00"]},
    "สกลนคร":{"price":330,"arrivals":["11:30","13:30","15:30"]},
    "บึงกาฬ":{"price":380,"arrivals":["12:00","14:00","16:00"]},
    "มุกดาหาร":{"price":290,"arrivals":["10:30","12:30","14:30"]},
    "นครพนม":{"price":380,"arrivals":["11:00","13:00","15:00"]},
    "ศรีสะเกษ":{"price":350,"arrivals":["12:00","14:00","16:00"]},
    "อุบลราชธานี":{"price":330,"arrivals":["12:30","14:30","16:30"]},
}

# 2. ดึงข้อมูลจาก DB ทั้งหมด
admin_routes = get_routes_from_admin_db()
old_routes = get_all_routes_from_db()

# 3. รวมข้อมูล: ให้ Admin Routes (ใหม่) มีความสำคัญก่อน
ROUTE_INFO = old_routes.copy()
ROUTE_INFO.update(admin_routes) # ข้อมูลจาก admin_routes จะเขียนทับ old_routes หากมีปลายทางซ้ำกัน

# 4. ใช้ Hardcoded Fallback ถ้ายังไม่มีข้อมูล
if not ROUTE_INFO:
    ROUTE_INFO = HARDCODED_ROUTES.copy()
    
# ค่าเริ่มต้น (ใช้สำหรับกรณีที่ข้อมูล DB ไม่สมบูรณ์)
DEFAULT_PRICE   = 70
DEFAULT_ARRIVAL = ["08:30","10:30","12:30"]

# ** ใช้ Keys จาก ROUTE_INFO ที่ถูกโหลดแล้ว **
ISAN_PROV = list(ROUTE_INFO.keys()) + ["ขอนแก่น"]
DEST_OPTIONS = [p for p in ISAN_PROV if p != "ขอนแก่น"]


# ---------- Fonts ----------
def load_fonts():
    for p in (RUBIK_REG, RUBIK_BOLD, FC_MINIMAL):
        if os.path.exists(p):
            QFontDatabase.addApplicationFont(p)

def T(p: QPainter, txt: str, fam: str, size_px: int, weight: int, color: str, x: int, y: int, align="left"):
    p.setPen(QColor(color))
    p.setFont(QFont(fam, size_px, weight))
    
    if align == "center":
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(txt)
        x_center = x - tw / 2
        p.drawText(int(x_center), int(y), txt)
    elif align == "right":
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(txt)
        x_right = x - tw
        p.drawText(int(x_right), int(y), txt)
    else:
        p.drawText(int(x), int(y), txt)

# =========================================================
class App(QWidget):
    def __init__(self):
        super().__init__()
        load_fonts()
        self.fn_en = "Rubik"
        self.fn_th = "FC Minimal"

        self.setWindowTitle(f"Go with CREPE — Home — {CURRENT_USER}")
        self.resize(1366, 768)
        self.setStyleSheet(f"background:{BG_MAIN}; color:{TEXT_DARK};")

        # ------- STATE -------
        self.search_state = {"origin":"ขอนแก่น บขส.3","dest":None,"date":QDate.currentDate()}
        self.trip_selected = None
        self.trip_id = None 
        self.passenger_name = ""
        self.pax_limit = 1
        self.selected_seats = set()
        self.slip_uploaded = False
        self.slip_path = ""
        self.booking_id = None 
        self._used_ticket_numbers = set()
        self.passenger_data = {"first_name":"", "last_name":"", "phone":"", "citizen_id":"", "email":""}

        # ------- UI: Header -------
        root = QVBoxLayout(self); root.setContentsMargins(32,24,32,24); root.setSpacing(18)

        header = QHBoxLayout(); header.setSpacing(18)
        self.logo = QLabel()
        if os.path.exists(LOGO_IMG):
            pix = QPixmap(LOGO_IMG).scaled(210,210, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(pix)
        self.logo.setFixedSize(230,130)
        header.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)

        self.nav = QFrame(objectName="nav")
        self.nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.nav.setStyleSheet(f"""
            QFrame#nav {{background:{BROWN};border-radius:28px;padding:6px;}}
            QPushButton[role="nav"] {{
                border:none;border-radius:18px;padding:6px 18px;min-height:34px;color:white;
                font-family:{self.fn_en};font-size:15px;font-weight:700;background:transparent;
            }}
            QPushButton[role="nav"][active="true"] {{ background:#eaf4f7; color:#000; }}
            QPushButton[role="nav"]:hover {{ background:#9b7447; }}
            QPushButton[role="nav"]:disabled {{ background:transparent; color:#c9c9c9; }}
        """)
        nav_row = QHBoxLayout(self.nav); nav_row.setContentsMargins(10,4,10,4); nav_row.setSpacing(6)
        self.btn_home    = QPushButton("HOME PAGE")
        # ❌ ลบ self.btn_sched ออก
        self.btn_book    = QPushButton("BOOKING")
        self.btn_pay     = QPushButton("PAYMENT")
        self.btn_about = QPushButton("ABOUT ME")
        
        # ❌ เพิ่มปุ่มที่เหลือ
        for b in (self.btn_home, self.btn_book, self.btn_pay, self.btn_about):
            b.setProperty("role","nav"); nav_row.addWidget(b); b.clicked.connect(self._on_nav_clicked)
        
        self._set_active_tab(self.btn_home)

        header.addStretch(1)
        header.addWidget(self.nav, alignment=Qt.AlignmentFlag.AlignTop)

        self.profile_btn = self._build_profile_badge()
        header.addWidget(self.profile_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        # ------- Pages -------
        self.stack = QStackedWidget(); root.addWidget(self.stack)
        self.page_home       = self._build_home()
        self.page_booking    = self._build_booking_page()
        self.page_passenger = self._build_passenger_page()
        self.page_seat      = self._build_seat_page()
        self.page_payment    = self._build_payment_page()
        for p in (self.page_home,self.page_booking,self.page_passenger,self.page_seat,self.page_payment):
            self.stack.addWidget(p)
        self.stack.setCurrentWidget(self.page_home)

        # ล็อกเมนูเริ่มต้น
        self._set_nav_access("home")

        # โหลดภาพโปรไฟล์
        saved = self._load_saved_profile()
        if saved:
            self._apply_profile_pixmap(self.profile_btn, saved)

    # ---------------- NAV CONTROL ----------------
    def _style_nav(self, btn: QPushButton, active: bool):
        btn.setProperty("active", "true" if active else "false")
        btn.style().unpolish(btn); btn.style().polish(btn); btn.update()

    def _set_active_tab(self, active_btn: QPushButton):
        # ❌ ปรับรายการปุ่ม
        for b in (self.btn_home, self.btn_book, self.btn_pay, self.btn_about):
            self._style_nav(b, b is active_btn)

    def _set_nav_access(self, stage: str):
        # ❌ ปรับการเปิด/ปิด
        if stage == "home":
            # self.btn_sched.setEnabled(True) # ❌ ลบออก
            self.btn_about.setEnabled(True)
            self.btn_book.setEnabled(False)
            self.btn_pay.setEnabled(False)
        elif stage == "booking":
            # self.btn_sched.setEnabled(True) # ❌ ลบออก
            self.btn_book.setEnabled(True)
            self.btn_pay.setEnabled(False)
            self.btn_about.setEnabled(False)
        elif stage == "payment":
            # self.btn_sched.setEnabled(True) # ❌ ลบออก
            self.btn_book.setEnabled(True)
            self.btn_pay.setEnabled(True)
            self.btn_about.setEnabled(True)

    def _on_nav_clicked(self):
        sender = self.sender()
        if not sender.isEnabled():
            return
        mapping = {
            self.btn_home: self.page_home,
            self.btn_book: self.page_booking,
            # self.btn_sched: self.page_booking, # ❌ ลบออก
            self.btn_pay:  self.page_payment,
            self.btn_about: self.page_payment
        }
        self.stack.setCurrentWidget(mapping.get(sender, self.page_home))
        self._set_active_tab(sender)
        if sender in (self.btn_pay, self.btn_about):
            self._fill_payment_summary()

    # ------ Profile UI ------
    def _build_profile_badge(self) -> QPushButton:
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(56, 56)
        btn.setStyleSheet("""
            QPushButton { border: none; background: #e7eef1; border-radius: 28px; }
            QPushButton:hover { background: #dfe8ec; }
        """)
        btn.clicked.connect(self._choose_profile_image)
        self._apply_profile_pixmap(btn, self._load_saved_profile() or None)
        return btn

    def _choose_profile_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "เลือกภาพโปรไฟล์", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path: return
        os.makedirs(PROFILE_DIR, exist_ok=True)
        pix = QPixmap(path)
        if not pix or pix.isNull():
            QMessageBox.warning(self, "ไฟล์รูปภาพ", "ไม่สามารถเปิดไฟล์รูปภาพนี้ได้"); return
        size = min(pix.width(), pix.height())
        cropped = pix.copy(int((pix.width()-size)/2), int((pix.height()-size)/2), size, size)
        cropped = cropped.scaled(56, 56, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        path_circle = QPainterPath(); path_circle.addEllipse(0, 0, 56, 56)
        rounded = QPixmap(56, 56); rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded); painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipPath(path_circle); painter.drawPixmap(0, 0, cropped); painter.end()
        rounded.save(PROFILE_PATH); self._apply_profile_pixmap(self.profile_btn, rounded)

    def _load_saved_profile(self) -> QPixmap | None:
        if os.path.exists(PROFILE_PATH):
            pix = QPixmap(PROFILE_PATH)
            if not pix.isNull():
                return pix
        return None

    def _apply_profile_pixmap(self, btn: QPushButton, pixmap: QPixmap | None):
        if pixmap and not pixmap.isNull():
            btn.setIconSize(btn.size()); btn.setIcon(QIcon(pixmap))
        else:
            initials = "U"
            if getattr(self, "passenger_name", "").strip():
                parts = self.passenger_name.strip().split()
                initials = (parts[0][:1] + (parts[1][:1] if len(parts) >= 2 else "")).upper()
            elif CURRENT_USER and CURRENT_USER != "guest":
                initials = CURRENT_USER[:2].upper()
            canvas = QPixmap(56, 56); canvas.fill(Qt.GlobalColor.transparent)
            p = QPainter(canvas); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setBrush(QColor("#cfe0e6")); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(0, 0, 56, 56)
            p.setPen(QColor("#1c2b33")); p.setFont(QFont(self.fn_en, 20, QFont.Weight.Black))
            fm = p.fontMetrics(); tw = fm.horizontalAdvance(initials); th = fm.ascent()
            p.drawText(int((56 - tw) / 2), int((56 + th) / 2) - 2, initials); p.end()
            btn.setIconSize(btn.size()); btn.setIcon(QIcon(canvas))

    # ================= HOME =================
    def _build_home(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(22); v.setContentsMargins(0,0,0,0)
        welcome = QLabel(f"สวัสดี {CURRENT_USER}" if CURRENT_USER != "guest" else "สวัสดีผู้เยี่ยมชม")
        welcome.setFont(QFont(self.fn_th, 22, QFont.Weight.Bold))
        v.addWidget(welcome, 0, Qt.AlignmentFlag.AlignLeft)
        box = QFrame(); box.setMaximumWidth(1180)
        wrap = QVBoxLayout(box); wrap.setSpacing(20)
        grid = QGridLayout(); grid.setHorizontalSpacing(28); grid.setVerticalSpacing(8)
        LABEL_TH, INPUT_TH, PILL_H, INPUT_W = 28, 22, 52, 340
        l_origin = QLabel("ต้นทาง"); l_dest = QLabel("ปลายทาง"); l_date = QLabel("วันที่เดินทาง")
        for lb in (l_origin,l_dest,l_date):
            lb.setFont(QFont(self.fn_th, LABEL_TH)); lb.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(l_origin,0,0); grid.addWidget(l_dest,0,1); grid.addWidget(l_date,0,2)
        self.home_origin = QLabel("ขอนแก่น")
        self.home_origin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.home_origin.setFont(QFont(self.fn_th, INPUT_TH))
        self.home_origin.setFixedSize(INPUT_W, PILL_H)
        self.home_origin.setStyleSheet(f"QLabel{{background:{PILL_BG};border-radius:{PILL_H//2}px;padding:0 16px;}}")
        self.home_dest = QComboBox()
        self.home_dest.addItem("— เลือกปลายทาง —")
        # ใช้ DEST_OPTIONS ที่โหลดมาจาก DB/Fallback
        self.home_dest.addItems(DEST_OPTIONS)
        self.home_dest.setFixedSize(INPUT_W, PILL_H)
        self.home_dest.setStyleSheet(f"""
            QComboBox {{
                background:{PILL_BG}; border:none; border-radius:{PILL_H//2}px;
                padding:0 16px; font-family:{self.fn_th}; font-size:{INPUT_TH}px;
            }}
            QComboBox::drop-down {{ width:26px; border:none; }}
        """)
        self.home_date = QDateEdit()
        self.home_date.setCalendarPopup(True)
        self.home_date.setLocale(QLocale(QLocale.Language.Thai, QLocale.Country.Thailand))
        today = QDate.currentDate()
        self.home_date.setDate(today)
        self.home_date.setMinimumDate(today)
        self.home_date.setFixedSize(INPUT_W, PILL_H)
        self.home_date.setStyleSheet(f"""
            QDateEdit {{
                background:{PILL_BG}; border:none; border-radius:{PILL_H//2}px;
                padding:0 16px; font-family:{self.fn_th}; font-size:{INPUT_TH}px;
            }}
        """)
        grid.addWidget(self.home_origin,1,0)
        grid.addWidget(self.home_dest,  1,1)
        grid.addWidget(self.home_date,  1,2)
        wrap.addLayout(grid)
        self.btn_search = QPushButton("ค้นหา")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setFixedSize(260,60)
        self.btn_search.setFont(QFont(self.fn_th,26))
        self.btn_search.setStyleSheet(f"QPushButton{{background:{BTN_BG};border:none;border-radius:22px;}}")
        self.btn_search.clicked.connect(self._go_booking_from_home)
        wrap.addSpacing(18)
        wrap.addWidget(self.btn_search, alignment=Qt.AlignmentFlag.AlignHCenter)
        center = QHBoxLayout(); center.addStretch(1); center.addWidget(box); center.addStretch(1)
        v.addLayout(center); v.addStretch(1)
        return w

    # ================= BOOKING =================
    def _build_booking_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page); root.setSpacing(18); root.setContentsMargins(0,0,0,0)
        root.addLayout(self._build_stepper(active_index=1))
        self.date_bar = QHBoxLayout(); self.date_bar.setSpacing(10)
        self.btn_dates = []
        for _ in range(4):
            b = QPushButton("d/M/yyyy"); b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton{background:#eaf3f6;border:0;border-radius:10px;padding:10px 16px;font-weight:700;}
                QPushButton:checked{background:white;border:2px solid #c9c9c9;}
            """)
            b.clicked.connect(self._on_date_clicked)
            self.btn_dates.append(b); self.date_bar.addWidget(b,1)
        root.addLayout(self.date_bar)
        self.route_bar = QFrame(); self.route_bar.setStyleSheet(f"QFrame{{background:{CARD_BLUE};border-radius:10px;}}")
        rb = QHBoxLayout(self.route_bar); rb.setContentsMargins(16,10,16,10); rb.setSpacing(8)
        self.lb_route = QLabel(""); self.lb_route.setFont(QFont(self.fn_th,22))
        rb.addWidget(self.lb_route); rb.addStretch(1)
        root.addWidget(self.route_bar)
        root.addSpacing(8)
        self.trip_row = QHBoxLayout(); self.trip_row.setSpacing(18)
        self.cards = []
        for i in range(3):
            c = self._make_trip_card(i); self.cards.append(c); self.trip_row.addWidget(c,1)
        root.addLayout(self.trip_row)
        root.addStretch(1)
        return page

    def _make_trip_card(self, idx:int) -> QFrame:
        card = QFrame(); card.setStyleSheet(f"QFrame{{background:{CARD_LT};border-radius:14px;}}")
        v = QVBoxLayout(card); v.setContentsMargins(18,16,18,16); v.setSpacing(10)
        lb_time  = QLabel("—:— – —:—"); lb_time.setFont(QFont(self.fn_th,26,QFont.Weight.Black)); v.addWidget(lb_time)
        lb_ft    = QLabel("ขอนแก่น บขส.3 – —"); lb_ft.setFont(QFont(self.fn_th,20)); v.addWidget(lb_ft)
        lb_price = QLabel("ราคา — บาท"); lb_price.setFont(QFont(self.fn_th,22)); v.addWidget(lb_price)
        v.addStretch(1)
        row = QHBoxLayout(); row.addStretch(1)
        btn = QPushButton("เลือกเที่ยวนี้"); btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton{background:#8a663f;color:white;border:none;border-radius:12px;padding:8px 14px;font-weight:800;}
            QPushButton:hover{background:#9b7447;}
        """)
        btn.clicked.connect(lambda _=False, i=idx: self._select_trip(i)); row.addWidget(btn); v.addLayout(row)
        card._lb_time = lb_time; card._lb_ft = lb_ft; card._lb_price = lb_price; card._btn = btn
        return card

    # ================= PASSENGER =================
    def _build_passenger_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page); root.setSpacing(18); root.setContentsMargins(0,0,0,0)
        root.addLayout(self._build_stepper(active_index=2))
        body = QHBoxLayout(); body.setSpacing(24)
        left = QFrame(); left.setStyleSheet(f"QFrame{{background:{CARD_BLUE};border-radius:8px;}}")
        lf = QVBoxLayout(left); lf.setContentsMargins(24,16,24,24); lf.setSpacing(12)
        title = QLabel("ข้อมูลผู้โดยสาร"); title.setFont(QFont(self.fn_th,28,QFont.Weight.Bold))
        lf.addWidget(title); sep = QFrame(); sep.setFixedHeight(2); sep.setStyleSheet("background:#d1d1d1;"); lf.addWidget(sep)
        grid = QGridLayout(); grid.setHorizontalSpacing(24); grid.setVerticalSpacing(18)
        def pill(ph:str) -> QLineEdit:
            e = QLineEdit(); e.setPlaceholderText(ph); e.setFixedHeight(56)
            e.setStyleSheet(f"QLineEdit{{background:#fff7ef;border:none;border-radius:12px;padding:0 16px;font-family:{self.fn_th};font-size:22px;}}")
            return e
        self.in_name, self.in_surname = pill("ชื่อ"), pill("นามสกุล")
        self.in_phone, self.in_idcard = pill("หมายเลขโทรศัพท์ (ตัวเลขเท่านั้น)"), pill("เลขบัตรประชาชน 13 หลัก")
        self.in_email = pill("อีเมล (ตัวอักษรอังกฤษ/ตัวเลขเท่านั้น)")
        self.in_phone.textChanged.connect(lambda: self._filter_digits(self.in_phone,10))
        self.in_idcard.textChanged.connect(lambda: self._filter_digits(self.in_idcard,13))
        self.in_email.textChanged.connect(lambda: self._filter_email_chars(self.in_email))
        self.in_pax = QComboBox(); self.in_pax.addItems([str(i) for i in range(1,11)]); self.in_pax.setFixedHeight(56)
        self.in_pax.setStyleSheet(f"QComboBox{{background:#fff7ef;border:none;border-radius:12px;padding:0 16px;font-family:{self.fn_th};font-size:22px;}} QComboBox::drop-down{{width:26px;border:none;}}")
        self.in_pax.currentIndexChanged.connect(self._update_total)
        grid.addWidget(self.in_name,0,0); grid.addWidget(self.in_surname,0,1)
        grid.addWidget(self.in_phone,1,0); grid.addWidget(self.in_idcard,1,1)
        grid.addWidget(self.in_email,2,0); grid.addWidget(self.in_pax,2,1)
        lf.addLayout(grid); body.addWidget(left,2)
        right = QFrame(); right.setStyleSheet(f"QFrame{{background:{CARD_BLUE};border-radius:8px;}}")
        rf = QVBoxLayout(right); rf.setContentsMargins(24,16,24,24); rf.setSpacing(12)
        r_title = QLabel("สรุปราคา"); r_title.setFont(QFont(self.fn_th,28,QFont.Weight.Bold)); rf.addWidget(r_title)
        r_sep = QFrame(); r_sep.setFixedHeight(2); r_sep.setStyleSheet("background:#d1d1d1;"); rf.addWidget(r_sep)
        self.r_route = QLabel("—"); self.r_route.setFont(QFont(self.fn_th,22)); rf.addWidget(self.r_route)
        self.r_date  = QLabel("—"); self.r_date.setFont(QFont(self.fn_th,22)); rf.addWidget(self.r_date)
        self.r_t1 = QLabel(""); self.r_t2 = QLabel("")
        for lb in (self.r_t1,self.r_t2): lb.setFont(QFont(self.fn_th,24,QFont.Weight.Black))
        tcol = QVBoxLayout(); tcol.addWidget(self.r_t1); tcol.addWidget(self.r_t2); rf.addLayout(tcol)
        row_price = QHBoxLayout()
        self.r_price = QLabel("ราคา"); self.r_price.setFont(QFont(self.fn_th,22)); row_price.addWidget(self.r_price); row_price.addStretch(1)
        self.r_price_val = QLabel("— บาท"); self.r_price_val.setFont(QFont(self.fn_th,22)); row_price.addWidget(self.r_price_val); rf.addLayout(row_price)
        total_bar = QFrame(); total_bar.setStyleSheet("QFrame{background:#dedbd7;border-radius:8px;}")
        tb = QHBoxLayout(total_bar); tb.setContentsMargins(16,10,16,10)
        lb_total = QLabel("ทั้งหมด"); lb_total.setFont(QFont(self.fn_th,24,QFont.Weight.Black))
        self.r_total_val = QLabel("— บาท"); self.r_total_val.setFont(QFont(self.fn_th,24,QFont.Weight.Black))
        tb.addWidget(lb_total); tb.addStretch(1); tb.addWidget(self.r_total_val); rf.addWidget(total_bar)
        body.addWidget(right,1); root.addLayout(body)
        btn_row = QHBoxLayout(); btn_row.addStretch(1)
        self.btn_next = QPushButton("next"); self.btn_next.setFixedSize(260,70)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("""
            QPushButton{background:#a9c5cf;border:none;border-radius:28px;color:white;font-family:Rubik;font-weight:800;font-size:28px;}
            QPushButton:hover{background:#b7d1da;}
        """)
        self.btn_next.clicked.connect(self._validate_and_go_seat)
        btn_row.addWidget(self.btn_next); btn_row.addStretch(1); root.addLayout(btn_row)
        return page

    # ================= SEAT =================
    def _build_seat_page(self) -> QWidget:
        page = QWidget(); root = QVBoxLayout(page)
        root.setContentsMargins(0,0,0,0); root.setSpacing(8)
        root.addLayout(self._build_stepper(active_index=3))
        body = QHBoxLayout(); body.setSpacing(16); body.setContentsMargins(0,0,0,0)
        left = QFrame(); left.setStyleSheet(f"QFrame{{background:{CARD_LT};border-radius:10px;}}")
        lf = QVBoxLayout(left); lf.setContentsMargins(16,10,16,16); lf.setSpacing(10)
        seat_title = QLabel("ที่นั่ง"); seat_title.setFont(QFont(self.fn_th,26,QFont.Weight.Bold)); lf.addWidget(seat_title)
        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(8)
        self.seat_buttons = {}
        def make_seat_btn(text:str):
            b = QPushButton(text); b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedSize(56,50)
            b.setStyleSheet("""
                QPushButton{background:#ffffff;border:2px solid #86b6bf;border-radius:12px;font-weight:800;}
                QPushButton:checked{background:#a9c5cf;color:white;border-color:#a9c5cf;}
                QPushButton:disabled{background:#e3e3e3;color:#9b9b9b;border-color:#cfcfcf;}
            """)
            b.toggled.connect(lambda checked, s=text: self._toggle_seat(s, checked)) # Fix signal to use seat code
            return b
        rows = 7; AISLE_W = 40
        for r in range(1, rows+1):
            row_label = QLabel(str(r)); row_label.setFont(QFont(self.fn_th,18)); row_label.setFixedWidth(20)
            row_label.setAlignment(Qt.AlignmentFlag.AlignCenter); grid.addWidget(row_label, r-1, 0)
            for c_idx, c in enumerate(["A","B"]):
                code = f"{r}{c}"; btn = make_seat_btn(code)
                self.seat_buttons[code] = btn; grid.addWidget(btn, r-1, 1 + c_idx)
            grid.addItem(QSpacerItem(AISLE_W,1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum), r-1, 3)
            for c_idx, c in enumerate(["C","D"]):
                code = f"{r}{c}"; btn = make_seat_btn(code)
                self.seat_buttons[code] = btn; grid.addWidget(btn, r-1, 4 + c_idx)
        lf.addLayout(grid); body.addWidget(left,2)
        right = QFrame(); right.setStyleSheet(f"QFrame{{background:{CARD_BLUE};border-radius:10px;}}")
        rf = QVBoxLayout(right); rf.setContentsMargins(16,10,16,16); rf.setSpacing(10)
        title = QLabel("สรุปราคา"); title.setFont(QFont(self.fn_th,28,QFont.Weight.Bold)); rf.addWidget(title)
        r_sep = QFrame(); r_sep.setFixedHeight(2); r_sep.setStyleSheet("background:#d1d1d1;"); rf.addWidget(r_sep)
        self.s_route = QLabel("—"); self.s_date = QLabel("—")
        for lb in (self.s_route,self.s_date): lb.setFont(QFont(self.fn_th,22)); rf.addWidget(lb)
        self.s_t1 = QLabel(""); self.s_t2 = QLabel("")
        for lb in (self.s_t1,self.s_t2): lb.setFont(QFont(self.fn_th,24,QFont.Weight.Black)); rf.addWidget(lb)
        self.s_user = QLabel(""); self.s_user.setFont(QFont(self.fn_th,22,QFont.Weight.Bold)); rf.addWidget(self.s_user)
        row_price = QHBoxLayout()
        self.s_price = QLabel("ราคา"); self.s_price.setFont(QFont(self.fn_th,22)); row_price.addWidget(self.s_price); row_price.addStretch(1)
        self.s_price_val = QLabel("— บาท"); self.s_price_val.setFont(QFont(self.fn_th,22)); row_price.addWidget(self.s_price_val); rf.addLayout(row_price)
        row_cnt = QHBoxLayout()
        self.s_cnt = QLabel("ที่นั่ง"); self.s_cnt.setFont(QFont(self.fn_th,22)); row_cnt.addWidget(self.s_cnt); row_cnt.addStretch(1)
        self.s_cnt_val = QLabel("0"); self.s_cnt_val.setFont(QFont(self.fn_th,22)); row_cnt.addWidget(self.s_cnt_val); rf.addLayout(row_cnt)
        total_bar = QFrame(); total_bar.setStyleSheet("QFrame{background:#dedbd7;border-radius:8px;}")
        tb = QHBoxLayout(total_bar); tb.setContentsMargins(12,8,12,8)
        lb_total = QLabel("ทั้งหมด"); lb_total.setFont(QFont(self.fn_th,24,QFont.Weight.Bold))
        self.s_total_val = QLabel("— บาท"); self.s_total_val.setFont(QFont(self.fn_th,24,QFont.Weight.Bold))
        tb.addWidget(lb_total); tb.addStretch(1); tb.addWidget(self.s_total_val); rf.addWidget(total_bar)
        btn_row = QHBoxLayout(); btn_row.addStretch(1)
        self.btn_seat_next = QPushButton("next"); self.btn_seat_next.setFixedSize(260,70)
        self.btn_seat_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_seat_next.setStyleSheet("""
            QPushButton{background:#a9c5cf;border:none;border-radius:28px;color:white;font-family:Rubik;font-weight:800;font-size:28px;}
            QPushButton:hover{background:#b7d1da;}
        """)
        self.btn_seat_next.clicked.connect(self._go_payment_page)
        btn_row.addWidget(self.btn_seat_next); btn_row.addStretch(1); rf.addLayout(btn_row)
        body.addWidget(right,1); root.addLayout(body)
        return page

    # ================= PAYMENT =================
    def _build_payment_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page); root.setContentsMargins(0,0,0,0); root.setSpacing(8)
        root.addLayout(self._build_stepper(active_index=4))
        body_center = QHBoxLayout(); body_center.setSpacing(16); body_center.setContentsMargins(0,0,0,0)

        left = QFrame(); left.setStyleSheet(f"QFrame{{background:{CARD_BLUE};border-radius:10px;}}")
        left.setMaximumWidth(520)
        lf = QVBoxLayout(left); lf.setContentsMargins(16,10,16,16); lf.setSpacing(8)
        title = QLabel("รายละเอียดการชำระเงิน"); title.setFont(QFont(self.fn_th,26,QFont.Weight.Bold))
        lf.addWidget(title)
        line = QFrame(); line.setFixedHeight(2); line.setStyleSheet("background:#d1d1d1;"); lf.addWidget(line)
        self.p_route  = QLabel("—"); self.p_date = QLabel("—")
        for lb in (self.p_route,self.p_date): lb.setFont(QFont(self.fn_th,22)); lf.addWidget(lb)
        self.p_dep_time = QLabel(""); self.p_arr_time = QLabel("")
        for lb in (self.p_dep_time,self.p_arr_time): lb.setFont(QFont(self.fn_th,24,QFont.Weight.Black))
        lf.addWidget(self.p_dep_time); lf.addWidget(self.p_arr_time)
        self.p_user = QLabel(""); self.p_user.setFont(QFont(self.fn_th,22,QFont.Weight.Bold)); lf.addWidget(self.p_user)
        self.p_seats = QLabel("ที่นั่ง -"); self.p_price_each = QLabel("ราคา - บาท")
        for lb in (self.p_seats,self.p_price_each): lb.setFont(QFont(self.fn_th,22))
        lf.addWidget(self.p_seats); lf.addWidget(self.p_price_each)

        sum_box = QFrame(); sum_box.setStyleSheet("QFrame{background:#dedbd7;border-radius:8px;}")
        sb = QGridLayout(sum_box); sb.setContentsMargins(12,8,12,8); sb.setHorizontalSpacing(12); sb.setVerticalSpacing(6)
        lb_sub = QLabel("Subtotal"); lb_vat = QLabel("VAT 7%"); lb_tot = QLabel("ทั้งหมด")
        for lb in (lb_sub, lb_vat, lb_tot): lb.setFont(QFont(self.fn_th,20,QFont.Weight.Bold))
        self.p_subtotal = QLabel("— บาท"); self.p_vat = QLabel("— บาท"); self.p_total = QLabel("— บาท")
        for lb in (self.p_subtotal, self.p_vat, self.p_total): lb.setFont(QFont(self.fn_th,20,QFont.Weight.Bold))
        sb.addWidget(lb_sub,0,0); sb.addWidget(self.p_subtotal,0,1)
        sb.addWidget(lb_vat,1,0); sb.addWidget(self.p_vat,1,1)
        sb.addWidget(lb_tot,2,0); sb.addWidget(self.p_total,2,1)
        lf.addWidget(sum_box)

        right_col = QFrame(); right_col.setStyleSheet("QFrame{background:transparent;}"); right_col.setMaximumWidth(440)
        rc = QVBoxLayout(right_col); rc.setContentsMargins(0,0,0,0); rc.setSpacing(8)
        qr_wrap = QFrame(); qr_wrap.setStyleSheet("QFrame{background:white;border-radius:10px;}"); qr_wrap.setFixedWidth(420)
        qw = QVBoxLayout(qr_wrap); qw.setContentsMargins(10,10,10,10); qw.setSpacing(6)
        self.qr_lbl = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(QR_IMG):
            self.qr_lbl.setPixmap(QPixmap(QR_IMG).scaled(300,300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        qw.addWidget(self.qr_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        acct = QLabel("ชื่อบัญชี : นางสาวภูษิตา เขื่อนแก้ว\nเลขบัญชี : 1243548140 ธนาคารกรุงไทย")
        acct.setFont(QFont(self.fn_th,20)); acct.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        qw.addWidget(acct)
        rc.addWidget(qr_wrap, alignment=Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        slip_wrap = QFrame(); slip_wrap.setStyleSheet("QFrame{background:#dfeaec;border-radius:12px;}"); slip_wrap.setFixedWidth(360)
        sw = QVBoxLayout(slip_wrap); sw.setContentsMargins(12,8,12,8); sw.setSpacing(4)
        self.btn_upload = QPushButton("แนบหลักฐานการชำระเงิน")
        self.btn_upload.setFixedHeight(42)
        self.btn_upload.setFont(QFont(self.fn_th,22,QFont.Weight.Bold))
        self.btn_upload.setStyleSheet("QPushButton{background:transparent;border:0;color:#111;} QPushButton:hover{opacity:0.85;}")
        self.btn_upload.clicked.connect(self._upload_slip)
        sw.addWidget(self.btn_upload, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.slip_info = QLabel(""); self.slip_info.setFont(QFont(self.fn_th,18)); self.slip_info.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sw.addWidget(self.slip_info)
        rc.addWidget(slip_wrap, alignment=Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop)
        btn_row = QHBoxLayout(); btn_row.addStretch(1)
        self.btn_pay_next = QPushButton("บันทึก")
        self.btn_pay_next.setFixedSize(260,70)
        self.btn_pay_next.setStyleSheet(
            f"QPushButton{{background:#a9c5cf;border:none;border-radius:28px;color:white;font-family:'{self.fn_th}';font-weight:800;font-size:28px;}}"
            "QPushButton:hover{background:#b7d1da;}"
        )
        self.btn_pay_next.clicked.connect(self._save_receipt_pdf)
        btn_row.addWidget(self.btn_pay_next); btn_row.addStretch(1)
        rc.addLayout(btn_row)
        body_center.addWidget(left, 0, Qt.AlignmentFlag.AlignTop)
        body_center.addSpacing(16)
        body_center.addWidget(right_col, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(body_center)
        return page

    # ---------- Stepper ----------
    def _build_stepper(self, active_index:int) -> QHBoxLayout:
        step = QHBoxLayout(); step.setSpacing(28)
        def dot(i):
            d = QLabel(); d.setFixedSize(14,14)
            d.setStyleSheet(f"background:{BROWN if i<=active_index else '#bdbdbd'};border-radius:7px;"); return d
        def line():
            ln = QFrame(); ln.setFixedHeight(4); ln.setFixedWidth(110)
            ln.setStyleSheet(f"background:{STEP_GREY};border-radius:2px;"); return ln
        def stext(t): lb = QLabel(t); lb.setFont(QFont(self.fn_th,22)); return lb
        labels = ["ค้นหา","เที่ยวบริการ","ผู้โดยสาร","ที่นั่ง","ชำระเงิน"]
        for i, name in enumerate(labels):
            step.addWidget(dot(i)); step.addWidget(stext(name))
            if i < 4: step.addWidget(line())
        step.addStretch(1); return step

    # ---------- Input helpers ----------
    def _filter_digits(self, line_edit:QLineEdit, max_len:int=None):
        txt = ''.join(ch for ch in line_edit.text() if ch.isdigit())
        if max_len is not None: txt = txt[:max_len]
        if txt != line_edit.text():
            pos = line_edit.cursorPosition(); line_edit.setText(txt); line_edit.setCursorPosition(min(pos, len(txt)))

    def _filter_email_chars(self, line_edit: QLineEdit):
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._%+-@")
        txt = ''.join(ch for ch in line_edit.text() if ch in allowed)
        if txt != line_edit.text():
            pos = line_edit.cursorPosition(); line_edit.setText(txt); line_edit.setCursorPosition(min(pos, len(txt)))

    def _email_valid(self, email:str)->bool:
        if any('\u0E00' <= ch <= '\u0E7F' for ch in email): return False
        return re.match(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", email) is not None

    # ---------- Flow control ----------
    def _go_booking_from_home(self):
        # 🚨 NOTE: ROUTE_INFO ถูกโหลดที่ __init__ แล้ว
        if not DEST_OPTIONS:
             QMessageBox.warning(self, "ค้นหา", "ไม่พบเส้นทางเดินรถ กรุณาตรวจสอบฐานข้อมูล"); return

        if self.home_dest.currentIndex() <= 0:
            QMessageBox.warning(self, "ค้นหา", "กรุณาเลือกปลายทาง"); return
        dest = self.home_dest.currentText(); date = self.home_date.date()
        self.search_state["dest"] = dest; self.search_state["date"] = date
        self.stack.setCurrentWidget(self.page_booking); self._set_active_tab(self.btn_book)
        self._set_nav_access("booking")
        today = QDate.currentDate()
        dates = [date.addDays(-1), date, date.addDays(1), date.addDays(2)]
        for i, d in enumerate(dates):
            self.btn_dates[i].setText(d.toString("d/M/yyyy"))
            self.btn_dates[i].setChecked(i==1)
            self.btn_dates[i].setEnabled(d >= today)
        self.lb_route.setText(f"จุดขึ้นรถ ขอนแก่น บขส.3 → {dest} • {date.toString('d/M/yyyy')}")
        
        # 🌟 แก้ไข: ดึงข้อมูลเที่ยวรถที่ถูกบันทึกมาใช้
        info = ROUTE_INFO.get(dest, {"price":DEFAULT_PRICE,"arrivals":DEFAULT_ARRIVAL})
        arrivals, price = info.get("arrivals", DEFAULT_ARRIVAL), info.get("price", DEFAULT_PRICE)
        
        # ใช้จำนวนเที่ยวที่ดึงมาจริง (หรือสูงสุด 3 เที่ยวตามการออกแบบ UI)
        num_trips_to_show = min(len(arrivals), 3) 
        
        for idx, card in enumerate(self.cards):
            if idx < num_trips_to_show:
                dep = arrivals[idx]
                
                # NOTE: เนื่องจากไม่มี Duration ในตาราง routes เดิม จึงใช้ DEFAULT_ARRIVAL สำหรับ Arr Time
                arr = DEFAULT_ARRIVAL[min(idx, len(DEFAULT_ARRIVAL) - 1)] 

                card._lb_time.setText(f"{dep} – {arr}")
                card._lb_ft.setText(f"ขอนแก่น บขส.3 – {dest}")
                card._lb_price.setText(f"ราคา {price} บาท")
                card.show()
            else:
                card.hide() # ซ่อนการ์ดที่ไม่มีข้อมูลเที่ยว

        self._update_trip_cards_enabled()

    def _on_date_clicked(self):
        for b in self.btn_dates: b.setChecked(b is self.sender())
        parts = self.lb_route.text().split("•")
        if len(parts) == 2:
            left = parts[0].strip(); self.lb_route.setText(f"{left} • {self.sender().text()}")
        try:
            d,m,y = self.sender().text().split("/")
            self.search_state["date"] = QDate(int(y),int(m),int(d))
        except: pass
        self._update_trip_cards_enabled()

    def _update_trip_cards_enabled(self):
        today = QDate.currentDate()
        sel_date = self.search_state.get("date", today)
        allow = (sel_date >= today)
        for card in self.cards:
            card._btn.setEnabled(allow and card.isVisible()) # ตรวจสอบ isVisible ด้วย

    def _select_trip(self, idx:int):
        dest = self.search_state["dest"]; date = self.search_state["date"]
        # 🌟 แก้ไข: ดึงข้อมูลเที่ยวที่ถูกเลือกจาก ROUTE_INFO ที่ถูกโหลดแล้ว 🌟
        info = ROUTE_INFO.get(dest, {"price":DEFAULT_PRICE,"arrivals":DEFAULT_ARRIVAL})
        arrivals = info.get("arrivals", DEFAULT_ARRIVAL)
        price = info.get("price", DEFAULT_PRICE)
        
        if idx >= len(arrivals):
            QMessageBox.warning(self, "ข้อผิดพลาด", "ไม่พบข้อมูลเที่ยวรถที่ถูกเลือก"); return
            
        dep = arrivals[idx]
        arr = DEFAULT_ARRIVAL[min(idx, len(DEFAULT_ARRIVAL) - 1)] # ใช้ค่า arr_time เดิม (ถ้าไม่มี duration ใน DB)

        self.trip_selected = {"dep":dep,"arr":arr,"price":price}
        
        self.stack.setCurrentWidget(self.page_passenger); self._set_active_tab(self.btn_book)
        self.r_route.setText(f"{self.search_state['origin']} – {dest}")
        thai = QLocale(QLocale.Language.Thai, QLocale.Country.Thailand)
        self.r_date.setText(thai.toString(date, "ddddที่ d MMMM yyyy"))
        self.r_t1.setText(f"{dep}    ขอนแก่น บขส.3")
        self.r_t2.setText(f"{arr}    {dest}")
        self.r_price_val.setText(f"{price} บาท")
        self.in_pax.setCurrentIndex(0); self._update_total()
        self._fill_seat_summary()
        self._apply_seat_locks()

    def _fill_seat_summary(self):
        if not (self.trip_selected and self.search_state["dest"]): return
        dest = self.search_state["dest"]; date = self.search_state["date"]
        dep, arr, price = self.trip_selected["dep"], self.trip_selected["arr"], int(self.trip_selected["price"])
        self.s_route.setText(f"{self.search_state['origin']} – {dest}")
        thai = QLocale(QLocale.Language.Thai, QLocale.Country.Thailand)
        self.s_date.setText(thai.toString(date, "ddddที่ d MMMM yyyy"))
        self.s_t1.setText(f"{dep}    ขอนแก่น บขส.3"); self.s_t2.setText(f"{arr}    {dest}")
        self.s_price_val.setText(f"{price} บาท"); self.s_user.setText(f"คุณ {self.passenger_name}" if self.passenger_name else "")
        self._refresh_seat_summary()

    def _validate_and_go_seat(self):
        name, surname = self.in_name.text().strip(), self.in_surname.text().strip()
        phone, cid, email = self.in_phone.text().strip(), self.in_idcard.text().strip(), self.in_email.text().strip()
        missing = []
        if not name: missing.append("ชื่อ")
        if not surname: missing.append("นามสกุล")
        if not phone: missing.append("หมายเลขโทรศัพท์")
        if not cid: missing.append("เลขบัตรประชาชน")
        if not email: missing.append("อีเมล")
        if missing:
            QMessageBox.warning(self, "กรอกข้อมูลไม่ครบ", f"กรุณากรอก: {', '.join(missing)}"); return
        if not (phone.isdigit() and len(phone)==10):
            QMessageBox.warning(self, "หมายเลขโทรศัพท์", "เบอร์โทรต้องเป็นตัวเลข 10 หลัก"); return
        if not (cid.isdigit() and len(cid)==13):
            QMessageBox.warning(self, "เลขบัตรประชาชน", "เลขบัตรประชาชนต้องเป็นตัวเลข 13 หลัก"); return
        if not self._email_valid(email):
            QMessageBox.warning(self, "อีเมลไม่ถูกต้อง", "อีเมลต้องไม่ใช่อักษรไทยและอยู่ในรูปแบบที่ถูกต้อง"); return
            
        # บันทึกข้อมูลผู้โดยสาร
        self.passenger_name = f"{name} {surname}".strip()
        self.passenger_data = {"first_name":name, "last_name":surname, "phone":phone, "citizen_id":cid, "email":email}
        
        self.pax_limit = int(self.in_pax.currentText())
        if not os.path.exists(PROFILE_PATH):
            self._apply_profile_pixmap(self.profile_btn, None)
            
        self._go_seat_page()

    def _go_seat_page(self):
        self.stack.setCurrentWidget(self.page_seat); self._set_active_tab(self.btn_book)
        self._fill_seat_summary()
        self._apply_seat_locks()

    def _apply_seat_locks(self):
        if not self.trip_selected: return
        
        locked = get_booked_seats(
            qdate=self.search_state["date"], 
            dep_time=self.trip_selected["dep"], 
            dest=self.search_state["dest"]
        )
        
        for code, btn in self.seat_buttons.items():
            btn.setEnabled(code not in locked)
            if code in locked and btn.isChecked():
                btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
                self.selected_seats.discard(code)
        self._refresh_seat_summary()

    def _toggle_seat(self, code:str, checked:bool):
        if checked and len(self.selected_seats) >= getattr(self, "pax_limit", 1):
            btn = self.seat_buttons.get(code)
            if btn:
                btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
            QMessageBox.information(self, "เลือกเกินจำนวน", f"เลือกได้ไม่เกิน {self.pax_limit} ที่นั่ง"); return
        if checked: self.selected_seats.add(code)
        else: self.selected_seats.discard(code)
        self._refresh_seat_summary()

    def _refresh_seat_summary(self):
        cnt = len(self.selected_seats)
        if hasattr(self, "s_cnt_val"): self.s_cnt_val.setText(str(cnt))
        if self.trip_selected:
            price = int(self.trip_selected["price"]); total = price * cnt
            if hasattr(self, "s_total_val"): self.s_total_val.setText(f"{total} บาท")
            if hasattr(self, "s_price_val"): self.s_price_val.setText(f"{price} บาท")

    def _go_payment_page(self):
        cnt = len(self.selected_seats); need = getattr(self, "pax_limit", 1)
        if cnt == 0:
            QMessageBox.information(self, "ยังไม่ได้เลือกที่นั่ง", "กรุณาเลือกที่นั่งอย่างน้อย 1 ที่นั่ง"); return
        if cnt < need:
            QMessageBox.information(self, "เลือกที่นั่งไม่ครบ", f"คุณเลือกที่นั่งมา {cnt} ที่นั่ง กรุณาเลือกให้ครบ {need} ที่นั่ง"); return
        self._fill_payment_summary()
        self.stack.setCurrentWidget(self.page_payment); self._set_active_tab(self.btn_pay)
        self._set_nav_access("payment")

    def _fill_payment_summary(self):
        if not (self.trip_selected and self.search_state["dest"]): return
        dest = self.search_state["dest"]; date = self.search_state["date"]
        dep, arr, price = self.trip_selected["dep"], self.trip_selected["arr"], int(self.trip_selected["price"])
        thai = QLocale(QLocale.Language.Thai, QLocale.Country.Thailand)
        self.p_route.setText(f"ขอนแก่น – {dest}")
        self.p_date.setText(thai.toString(date, "วันddddที่ d MMMM yyyy"))
        self.p_dep_time.setText(f"{dep.replace(':','.')}      ขอนแก่น บขส.3")
        self.p_arr_time.setText(f"{arr.replace(':','.')}      {dest}")
        self.p_user.setText(f"คุณ {self.passenger_name}" if self.passenger_name else "")
        seat_list = ", ".join(sorted(self.selected_seats)) if self.selected_seats else "-"
        self.p_seats.setText(f"ที่นั่ง {seat_list}")
        self.p_price_each.setText(f"ราคา {price} บาท/ที่นั่ง")
        qty = max(1, len(self.selected_seats))
        subtotal = float(price * qty)
        vat = round(subtotal * 0.07, 2)
        total = round(subtotal + vat, 2)
        self.p_subtotal.setText(f"{subtotal:,.2f} บาท")
        self.p_vat.setText(f"{vat:,.2f} บาท")
        self.p_total.setText(f"{total:,.2f} บาท")
        self.slip_uploaded = False; self.slip_path = ""; self.slip_info.setText("")

    def _upload_slip(self):
        path, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์สลิป", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.slip_uploaded = True; self.slip_path = path
            self.slip_info.setText(f"อัปโหลดแล้ว: {os.path.basename(path)}")

    # ---------- PDF Drawing Functions (Revised for direct PDF) ----------
    
    def _random_ticket_no(self) -> str:
        while True:
            num = "".join([str(random.randint(0,9)) for _ in range(8)])
            if num[0] != "0" and num not in self._used_ticket_numbers:
                self._used_ticket_numbers.add(num); return num
    
    def _draw_ticket_content(self, p:QPainter, rect:QRectF, data:dict):
        # ฟังก์ชันวาดตั๋ว (หน้า 1) ที่ปรับให้ตรงกับรูปภาพ 'ตั๋ว.png'
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.fillRect(rect, QColor("#ffffff"))

        OUT = 100 
        CARD = QRectF(rect.left()+OUT, rect.top()+OUT, rect.width()-OUT*2, rect.height()-OUT*2.2) 
        
        # วาดเงาและกรอบ
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(0,0,0,14))
        p.drawRoundedRect(CARD.adjusted(2,4,2,4), 16, 16)
        p.setBrush(QColor("#ffffff")); p.setPen(QPen(QColor(CARD_BORDER), 3))
        p.drawRoundedRect(CARD, 16, 16)

        pad = 32
        xL_base = CARD.left() + pad + 6
        
        # --- HEADER (สำหรับลูกค้า + โลโก้) ---
        y_cursor = CARD.top() + pad
        
        # สำหรับลูกค้า (ขวาบน)
        T(p, "(สำหรับลูกค้า)", self.fn_th, 20, QFont.Weight.DemiBold, TEXT_SOFT, int(CARD.right()-pad-6), int(y_cursor+4), align="right")
        
        # โลโก้ (ขวาบน)
        if os.path.exists(LOGO_IMG):
            logo_width, logo_height = 50, 50
            logo = QPixmap(LOGO_IMG).scaled(logo_width, logo_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(CARD.right()-pad-logo_width), int(y_cursor + 28), logo)
        
        # --- BLOCK 1: เลขที่ตั๋วและรายละเอียดผู้โดยสาร ---
        
        y_cursor = CARD.top() + pad + 15 # ตำแหน่งเริ่มต้นใกล้เคียงกับรูป
        
        # ------------------- เลขที่ตั๋ว -------------------
        T(p, "เลขที่ตั๋ว", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, int(xL_base), int(y_cursor))
        y_cursor += 30 
        T(p, data["ticket_no"], self.fn_en, 26, QFont.Weight.Bold, TEXT_DARK, int(xL_base), int(y_cursor))
        y_cursor += 40

        # ------------------- ชื่อ -------------------
        T(p, "ชื่อ :", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, int(xL_base), int(y_cursor))
        T(p, (data["passenger_name"] or "-"), self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, int(xL_base + 60), int(y_cursor))
        y_cursor += 36

        # ------------------- เบอร์โทร -------------------
        T(p, "เบอร์โทร :", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, int(xL_base), int(y_cursor))
        T(p, (data["phone"] or "-"), self.fn_en, 22, QFont.Weight.Bold, TEXT_DARK, int(xL_base + 100), int(y_cursor))
        y_cursor += 36
        
        # ------------------- ที่นั่ง -------------------
        T(p, "ที่นั่ง :", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, int(xL_base), int(y_cursor))
        T(p, (data["seat_list_text"] or "-"), self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, int(xL_base + 70), int(y_cursor))
        y_cursor += 36
        
        # ------------------- ราคาต่อที่นั่ง (ว่างเปล่าตามรูป) -------------------
        T(p, "ราคา :", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, int(xL_base), int(y_cursor))
        # T(p, f"{data['price_each']} บาท/ที่นั่ง", self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, int(xL_base + 70), int(y_cursor))
        y_cursor += 40

        # --- BLOCK 2: กรอบรายละเอียดการเดินทาง ---
        
        box_top_y = y_cursor
        box_height = 200
        box = QRectF(CARD.left()+pad, box_top_y, CARD.width()-pad*2, box_height) 
        
        p.setPen(QPen(QColor("#2b2b2b"), 2)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(box)

        bx_inner = int(box.left()+20)
        by_inner = int(box.top()+28)
        line_height = 36
        
        # ขึ้นรถที่
        T(p, "ขึ้นรถที่", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, bx_inner, by_inner) 
        T(p, f"ขอนแก่น เท่านั้น", self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, bx_inner+90, by_inner) 
        by_inner += line_height
        
        # ลงรถที่
        T(p, "ลงรถที่", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, bx_inner, by_inner)
        T(p, f"  {data['dest']}", self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, bx_inner+90, by_inner)
        by_inner += line_height
        
        # วันที่
        T(p, "วันที่", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, bx_inner, by_inner)
        T(p, f"  {data['date_full_th']}", self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, bx_inner+60, by_inner)
        by_inner += line_height
        
        # เวลา
        T(p, "เวลา", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, bx_inner, by_inner)
        T(p, f"  {data['dep_time']}", self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, bx_inner+60, by_inner)
        by_inner += line_height
        
        # ราคาต่อหน่วยในกรอบ
        T(p, "ราคา", self.fn_th, 22, QFont.Weight.Normal, TEXT_DARK, bx_inner, by_inner)
        T(p, f"  {data['price_each']} บาท/ที่นั่ง", self.fn_th, 22, QFont.Weight.Bold, TEXT_DARK, bx_inner+60, by_inner)
        
        y_cursor = box.bottom() + 30

        # --- BLOCK 3: ขอบคุณ, Bar Code, หมายเหตุ ---
        
        T(p, "ขอบคุณที่ใช้บริการ", self.fn_th, 24, QFont.Weight.DemiBold, TEXT_DARK, int(CARD.center().x()), int(y_cursor), align="center")
        y_cursor += 30

        # วาด Bar Code Mockup (ส่วนที่แก้ไข)
        bc_top = int(y_cursor); bc_left = int(CARD.left()+pad+16); bc_right = int(CARD.right()-pad-16); bc_h = 70
        p.setPen(QPen(QColor("#444"), 1.6))
        rng = random.Random(data["ticket_no"]); x = bc_left
        while x < bc_right:
            w = rng.choice([1,2,3,4])
            # ใช้ p.drawLine(int, int, int, int)
            p.drawLine(int(x), bc_top, int(x), bc_top + bc_h)
            x += w + 1
        y_cursor += bc_h + 30
        
        # หมายเหตุ
        T(p, "โปรดแสดงตั๋วนี้แก่พนักงานในวันที่เดินทาง", self.fn_th, 20, QFont.Weight.Normal, TEXT_SOFT, int(CARD.center().x()), int(y_cursor), align="center")
        
    def _draw_invoice_content(self, p: QPainter, rect: QRectF, data: dict):
        # ฟังก์ชันวาดใบเสร็จ (หน้า 2)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.fillRect(rect, QColor("#ffffff"))

        MM_TO_PX = rect.width() / 210
        def mm_to_px(mm_val): return mm_val * MM_TO_PX
        
        margin_px = mm_to_px(15) 
        card_x = rect.left() + margin_px
        card_y = rect.top() + mm_to_px(15)
        card = QRectF(card_x, card_y, rect.width() - 2*margin_px, rect.height() - 2*mm_to_px(15))
        
        header_h = mm_to_px(20)
        header = QRectF(card.left(), card.top(), card.width(), header_h) 
        p.setBrush(QColor(CARD_BLUE)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(header, 18, 18)
        
        T(p, "ใบยืนยันการรับเงิน", self.fn_th, 30, QFont.Weight.Bold, "#000", int(header.center().x()), int(header.center().y() + mm_to_px(3)), align="center")
        
        T(p, f"วันที่ทำรายการ {data['date_long_th']}", self.fn_th, 20, QFont.Weight.Normal, BROWN, int(card.right() - mm_to_px(5)), int(header.center().y() + mm_to_px(3)), align="right")

        y_cursor = header.bottom() + mm_to_px(10)

        # --- Address Block ---
        bx, by = int(card.left() + mm_to_px(1)), int(y_cursor)
        
        T(p, "GO WITH CREPE COMPANY", self.fn_en, 16, QFont.Weight.Bold, "#000", bx, by)
        by += mm_to_px(4); T(p, "Baan Suksabai Park Co., Ltd. (Building B)", self.fn_en, 12, QFont.Weight.Normal, "#000", bx, by)
        by += mm_to_px(4); T(p, "775 Moo 12, Sila Subdistrict,", self.fn_en, 12, QFont.Weight.Normal, "#000", bx, by)
        by += mm_to_px(4); T(p, "Mueang District, Khon Kaen Province 40000,", self.fn_en, 12, QFont.Weight.Normal, "#000", bx, by)
        by += mm_to_px(4); T(p, "Thailand", self.fn_en, 12, QFont.Weight.Normal, "#000", bx, by)
        by += mm_to_px(4); T(p, "Tax ID: 0486739765823", self.fn_en, 12, QFont.Weight.Normal, "#000", bx, by)
        
        y_cursor = by + mm_to_px(10)

        # --- Summary Table (Placeholder) ---
        row_h = mm_to_px(8.5)
        
        # Header Row
        T(p, "Description", self.fn_en, 12, QFont.Weight.Bold, "#000", int(card.left() + mm_to_px(10)), int(y_cursor + mm_to_px(3)))
        T(p, "Amount(THB)", self.fn_en, 12, QFont.Weight.Bold, "#000", int(card.right() - mm_to_px(30)), int(y_cursor + mm_to_px(3)), align="right")
        
        y_cursor += row_h
        p.setPen(QPen(QColor("#d9d9d9"), 1)); p.drawLine(card.left(), y_cursor, card.right(), y_cursor)
        
        y_cursor += row_h
        T(p, f"Payment of : Bus Ticket No. {data['ticket_no']} ({data['qty']} seats)", self.fn_en, 12, QFont.Weight.Bold, "#000", int(card.left() + mm_to_px(10)), int(y_cursor + mm_to_px(3)))
        y_cursor += row_h
        
        # Financial Summary
        y_cursor += mm_to_px(20)
        p.setPen(QPen(QColor("#b9d4db"), 2)); p.drawRect(card.right() - mm_to_px(70), y_cursor, mm_to_px(70), row_h * 3.5)
        
        T(p, "Subtotal:", self.fn_th, 16, QFont.Weight.Normal, INK, int(card.right() - mm_to_px(65)), int(y_cursor + mm_to_px(6)))
        T(p, f"{data['subtotal']:,.2f}", self.fn_en, 16, QFont.Weight.Normal, INK, int(card.right() - mm_to_px(5)), int(y_cursor + mm_to_px(6)), align="right")
        
        y_cursor += row_h
        T(p, "VAT 7%:", self.fn_th, 16, QFont.Weight.Normal, INK, int(card.right() - mm_to_px(65)), int(y_cursor + mm_to_px(6)))
        T(p, f"{data['vat']:,.2f}", self.fn_en, 16, QFont.Weight.Normal, INK, int(card.right() - mm_to_px(5)), int(y_cursor + mm_to_px(6)), align="right")
        
        y_cursor += row_h
        T(p, "TOTAL:", self.fn_th, 18, QFont.Weight.Black, BROWN, int(card.right() - mm_to_px(65)), int(y_cursor + mm_to_px(8)))
        T(p, f"{data['grand_total']:,.2f}", self.fn_th, 18, QFont.Weight.Black, BROWN, int(card.right() - mm_to_px(5)), int(y_cursor + mm_to_px(8)), align="right")
        
    def _save_receipt_pdf(self):
        
        if not self.slip_uploaded:
            QMessageBox.information(self, "ยังไม่ได้อัปโหลดสลิป", "กรุณาแนบหลักฐานการชำระเงินก่อนบันทึก"); return
        if not (self.trip_selected and self.search_state["dest"]):
            QMessageBox.warning(self, "ยังไม่เลือกเที่ยว", "กรุณาเลือกเที่ยวเดินทางก่อน"); return
        
        # --- 1. เตรียมข้อมูลทั้งหมด (Data Payload) ---
        try:
            # 1.1 สร้างเลขที่ตั๋ว
            ticket_no = self._random_ticket_no()
            
            # 1.2 ตรวจสอบว่าที่นั่งถูกจองไปก่อนหน้าหรือไม่
            seats_to_book = sorted(list(self.selected_seats))
            
            if not seats_to_book:
                QMessageBox.warning(self, "ยังไม่ได้เลือกที่นั่ง", "กรุณาเลือกที่นั่งก่อน"); return
            
            # ตรวจสอบซ้ำกับ DB
            locked_seats = get_booked_seats(
                qdate=self.search_state["date"], 
                dep_time=self.trip_selected["dep"], 
                dest=self.search_state["dest"]
            )
            booked_before = set(seats_to_book).intersection(locked_seats)
            if booked_before:
                QMessageBox.warning(self, "ที่นั่งถูกจองแล้ว", f"ที่นั่ง {', '.join(booked_before)} ถูกจองไปก่อนหน้า กรุณาอัปเดตหน้าและเลือกใหม่"); 
                self._apply_seat_locks(); return

            price = int(self.trip_selected["price"])
            qty = max(1, len(seats_to_book))
            subtotal = float(price * qty)
            vat = round(subtotal * 0.07, 2)
            total = round(subtotal + vat, 2)
            
            date = self.search_state["date"]
            thai = QLocale(QLocale.Language.Thai, QLocale.Country.Thailand)

            data_payload = {
                "ticket_no": ticket_no,
                "passenger_name": self.passenger_name,
                "first_name": self.passenger_data["first_name"],
                "last_name": self.passenger_data["last_name"],
                "phone": self.passenger_data["phone"],
                "citizen_id": self.passenger_data["citizen_id"],
                "email": self.passenger_data["email"],
                "seat_list": seats_to_book,
                "seat_list_text": ", ".join(seats_to_book),
                "qty": qty,
                "price_each": price,
                "dep_time": self.trip_selected["dep"],
                "arr_time": self.trip_selected["arr"],
                "origin": self.search_state['origin'],
                "dest": self.search_state["dest"],
                "date_full_th": thai.toString(date, "วันddddที่ d MMMM yyyy"),
                "date_long_th": thai.toString(date, "d MMM yyyy"),
                "date_short": date.toString("dd/MM/yyyy"),
                "date": date,
                "subtotal": subtotal,
                "vat": vat,
                "grand_total": total,
                "slip_path": self.slip_path
            }
        except Exception as e:
            QMessageBox.critical(self, "ข้อผิดพลาด", f"ไม่สามารถเตรียมข้อมูลสำหรับตั๋วได้: {e}"); return

        # --- 2. บันทึกเป็น PDF โดยตรง (และบันทึก DB) ---
        try:
            out_dir = DB_DIR
            os.makedirs(out_dir, exist_ok=True)
            
            default_name = f"receipt_{data_payload['ticket_no']}.pdf"
            out_path, _ = QFileDialog.getSaveFileName(self, "บันทึกตั๋วและใบเสร็จ", 
                                                         os.path.join(out_dir, default_name), 
                                                         "PDF Files (*.pdf)")
            if not out_path: return

            # *** บันทึกข้อมูลการจองลง DB ***
            save_new_booking(data_payload, seats_to_book, ticket_no)
            _admin_db_save_booking_summary(data_payload, seats_to_book, ticket_no)

            # --- สร้าง PDF ---
            writer = QPdfWriter(out_path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setResolution(300)
            writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)

            p = QPainter()
            if not p.begin(writer): raise RuntimeError("ไม่สามารถเริ่มเขียน PDF ได้")

            page_rect = QRectF(0, 0, writer.width(), writer.height())

            # หน้า 1: ตั๋ว (Ticket) - ใช้ฟังก์ชันที่ปรับปรุงแล้ว
            self._draw_ticket_content(p, page_rect, data_payload)

            writer.newPage()

            # หน้า 2: ใบเสร็จ (Invoice)
            self._draw_invoice_content(p, page_rect, data_payload)

            p.end()

            # --- ล็อกที่นั่งและเปิดไฟล์ ---
            self._apply_seat_locks()
            QMessageBox.information(self, "บันทึกสำเร็จ", f"ไฟล์ถูกบันทึกที่:\n{out_path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_path))

        except Exception as e:
            QMessageBox.critical(self, "บันทึกไม่สำเร็จ", f"เกิดข้อผิดพลาดระหว่างสร้างไฟล์/บันทึก DB:\n{e}")

    def _update_total(self):
        if not self.trip_selected:
            self.r_total_val.setText("— บาท")
            return
        pax = int(self.in_pax.currentText())
        price = int(self.trip_selected["price"])
        total = pax * price
        self.r_total_val.setText(f"{total} บาท")

# ---------------- run ----------------
if __name__ == "__main__":
    init_db()  
    app = QApplication(sys.argv)
    w = App()
    w.show()
    sys.exit(app.exec())