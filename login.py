# login.py — Go with CREPE (users.db) + Free-move Crop (Qt6-safe wheelEvent)
# - Sign In / Sign Up
# - Password ASCII-only + eye button "ㆅ"
# - Upload -> Crop: ลากกรอบได้อิสระ (ขึ้น/ลง/ซ้าย/ขวา), ซูมรูป (นอกกรอบ), ปรับขนาดกรอบด้วยล้อ (บนกรอบ)
# - เซฟอวาตาร์วงกลมเป็น ./profiles/<username>.png

import os, sys, re, sqlite3


BUS_SIGNIN = r"picture\sign innn.png"
BUS_SIGNUP = r"picture\sign up.png"
RUBIK_REG  = r"font\Rubik-Regular.ttf"
RUBIK_BOLD = r"font\Rubik-Bold.ttf"
HOME_PY    = r"code\home.py"
ADMIN_PY   = r"code\admin.py"

# คำนวณ APP_DIR จาก Path ของไฟล์อื่น
APP_DIR    = os.path.dirname(os.path.dirname(HOME_PY)) # ชี้ไปที่ '...project python'
# *** DB_PATH: ใช้ relative path ก่อน แล้วจะไปสร้าง DB ใน Documents โดย home.py/admin.py
DB_PATH_REL = "passenger_bookings" 
# DB Path จริงจะถูกตั้งค่าโดย home.py/admin.py ในโฟลเดอร์ Documents/GoWithCREPE
DB_PATH_ABS = os.path.join(os.path.expanduser("~"), "Documents", "GoWithCREPE", DB_PATH_REL)
AVATAR_DIR = os.path.join(APP_DIR, "profiles")
os.makedirs(AVATAR_DIR, exist_ok=True) 

# ---------- PyQt6 ----------
from PyQt6.QtCore import Qt, QRegularExpression, QTimer, QProcess, QRectF, QPointF
from PyQt6.QtGui import (
    QFontDatabase, QFont, QPixmap, QRegularExpressionValidator,
    QPainter, QBrush, QColor, QPen, QPainterPath, QCursor
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
    QHBoxLayout, QVBoxLayout, QMessageBox, QFrame, QStackedWidget,
    QDialog, QDialogButtonBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGraphicsRectItem
)

# ---------- Optional libs ----------
bcrypt = None
try:
    import bcrypt as _bcrypt; bcrypt = _bcrypt
except Exception:
    pass

try:
    from PIL import Image, ImageDraw, ImageQt
    PIL_ok = True
except Exception:
    PIL_ok = False

# ---------- Helpers ----------
def warn_missing_libs(parent=None):
    miss = []
    if bcrypt is None: miss.append("bcrypt")
    if not PIL_ok:      miss.append("Pillow")
    if miss:
        QMessageBox.warning(parent, "Missing libraries",
            "ยังไม่ได้ติดตั้ง:\n- " + "\n- ".join(miss) + "\n\npip install " + " ".join(miss))

def load_rubik():
    fam = None
    try:
        if os.path.exists(RUBIK_REG):
            fid = QFontDatabase.addApplicationFont(RUBIK_REG)
            fams = QFontDatabase.applicationFontFamilies(fid); fam = fams[0] if fams else None
        if os.path.exists(RUBIK_BOLD):
            QFontDatabase.addApplicationFont(RUBIK_BOLD)
    except Exception:
        pass
    return fam or "Rubik"

def is_valid_password(p: str) -> bool:
    return len(p) >= 9 and any(ch.isupper() for ch in p)

def hash_password(plain: str) -> tuple[str, str]:
    if bcrypt is None: return plain, ""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8"), salt.decode("utf-8")

def check_password(plain: str, pw_hash: str) -> bool:
    if bcrypt is None: return plain == pw_hash
    try:    return bcrypt.checkpw(plain.encode("utf-8"), pw_hash.encode("utf-8"))
    except: return plain == pw_hash

# ---------- DB (เชื่อมต่อและสร้างตาราง users) ----------
def db_connect(db_path:str): return sqlite3.connect(db_path)

def init_db(db_path:str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = db_connect(db_path); c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE,
            email       TEXT UNIQUE,
            pw_hash     TEXT,
            pw_salt     TEXT,
            role        TEXT DEFAULT 'user',
            image_path  TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # สร้าง Admin default ถ้ายังไม่มี
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        pw_hash, pw_salt = hash_password("Admin1234")
        c.execute("INSERT INTO users(username, email, pw_hash, pw_salt, role) VALUES(?,?,?,?,?)",
                  ("admin", "admin@crepe.com", pw_hash, pw_salt, "admin"))
    
    conn.commit(); conn.close()

def load_user_for_login(login_name: str):
    # ใช้ DB_PATH_ABS แทน DB_PATH_REL เพื่อให้ชี้ไปที่ไฟล์ DB ที่ถูกต้อง
    try:
        init_db(DB_PATH_ABS) # ตรวจสอบและสร้าง DB อีกครั้งก่อนใช้
        conn = db_connect(DB_PATH_ABS); c = conn.cursor()
        c.execute("""SELECT id, username, email, pw_hash, pw_salt, role, image_path
                      FROM users WHERE username=? OR email=?""", (login_name, login_name))
        row = c.fetchone(); conn.close(); return row
    except Exception as e:
        QMessageBox.critical(None, "DB Error", f"ไม่สามารถโหลดผู้ใช้ได้: {e}"); return None

def register_user(username: str, email: str, password: str, image_path: str|None):
    try:
        init_db(DB_PATH_ABS) # ตรวจสอบและสร้าง DB อีกครั้งก่อนใช้
        conn = db_connect(DB_PATH_ABS); c = conn.cursor()
        pw_hash, pw_salt = hash_password(password)
        c.execute("""INSERT INTO users(username,email,pw_hash,pw_salt,role,image_path)
                      VALUES (?,?,?,?,?,?)""",
                  (username, email, pw_hash, pw_salt, "user", image_path))
        conn.commit(); ok, msg = True, "สมัครสมาชิกสำเร็จ"
    except sqlite3.IntegrityError as e:
        ok = False; msg = "บันทึกผู้ใช้ไม่ได้"
        if "username" in str(e).lower(): msg = "Username นี้ถูกใช้แล้ว"
        elif "email" in str(e).lower(): msg = "อีเมลนี้ถูกใช้งานแล้ว"
    except Exception as e:
        ok = False; msg = f"DB Error: {e}"
    finally:
        if 'conn' in locals() and conn: conn.close()
    return ok, msg

# =========================================================
#   CROP UI — free-move with Qt6-safe wheelEvent (ตัดทอนเพื่อความกระชับ)
# =========================================================
class DraggableCropRect(QGraphicsRectItem):
    # ... (โค้ดเดิม)
    def __init__(self, rect: QRectF, scene_rect: QRectF, min_side=120, max_side_factor=0.90):
        super().__init__(rect)
        self.setZValue(10)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.scene_rect = scene_rect
        self.min_side = float(min_side)
        self.max_side_factor = float(max_side_factor)

    def hoverEnterEvent(self, e):
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.unsetCursor()
        super().hoverLeaveEvent(e)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            r = QRectF(new_pos, self.rect().size())
            if r.left() < self.scene_rect.left():  new_pos.setX(self.scene_rect.left())
            if r.top()  < self.scene_rect.top():   new_pos.setY(self.scene_rect.top())
            if r.right()> self.scene_rect.right(): new_pos.setX(self.scene_rect.right() - r.width())
            if r.bottom()>self.scene_rect.bottom(): new_pos.setY(self.scene_rect.bottom() - r.height())
            return new_pos
        return super().itemChange(change, value)

    def wheelEvent(self, event):
        step = 0
        if hasattr(event, "delta"):
            try:
                step = event.delta()
            except Exception:
                step = 0
        if step == 0 and hasattr(event, "angleDelta"):
            try:
                ad = event.angleDelta()
                step = ad.y()
            except Exception:
                step = 0
        factor = 1.08 if step > 0 else (1/1.08 if step < 0 else 1.0)

        old = self.rect()
        side = old.width() * factor
        max_side = min(self.scene_rect.width(), self.scene_rect.height()) * self.max_side_factor
        side = max(self.min_side, min(side, max_side))
        center = old.center()
        new_rect = QRectF(0, 0, side, side); new_rect.moveCenter(center)
        if new_rect.left() < self.scene_rect.left():  new_rect.moveLeft(self.scene_rect.left())
        if new_rect.top()  < self.scene_rect.top():   new_rect.moveTop(self.scene_rect.top())
        if new_rect.right()> self.scene_rect.right(): new_rect.moveRight(self.scene_rect.right())
        if new_rect.bottom()>self.scene_rect.bottom(): new_rect.moveBottom(self.scene_rect.bottom())
        self.setRect(new_rect)
        event.accept()

class _CropView(QGraphicsView):
    # ... (โค้ดเดิม)
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor("#2b2b2b")))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.crop_item: DraggableCropRect | None = None
        self._drag_on_item = False

    def _point_in_hole(self, pos):
        if not self.crop_item: return False
        r_scene = self.crop_item.mapRectToScene(self.crop_item.rect())
        center = r_scene.center()
        radius = r_scene.width() / 2.0
        
        point_scene = self.mapToScene(pos.toPoint())
        
        # Simple distance check for the circular hole
        dist_sq = (point_scene.x() - center.x())**2 + (point_scene.y() - center.y())**2
        return dist_sq < radius**2

    def mousePressEvent(self, ev):
        self._drag_on_item = self._point_in_hole(ev.position())
        self.setDragMode(QGraphicsView.DragMode.NoDrag if self._drag_on_item
                             else QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._drag_on_item = False
        super().mouseReleaseEvent(ev)

    def wheelEvent(self, ev):
        if self.crop_item and self._point_in_hole(ev.position()):
            # Pass the wheel event to the crop item to resize it
            return self.crop_item.wheelEvent(ev)
        
        # Scale the view (zoom the image)
        factor = 1.15 if ev.angleDelta().y() > 0 else 1/1.15
        self.scale(factor, factor)

    def drawForeground(self, painter, rect):
        if not self.crop_item: return
        vrect = self.viewport().rect()
        r_scene = self.crop_item.mapRectToScene(self.crop_item.rect())
        tl = self.mapFromScene(r_scene.topLeft())
        br = self.mapFromScene(r_scene.bottomRight())
        hole = QRectF(QPointF(tl), QPointF(br)).normalized()
        painter.save()
        outer = QPainterPath(); outer.addRect(QRectF(vrect))
        inner = QPainterPath(); inner.addEllipse(hole)
        painter.fillPath(outer.subtracted(inner), QColor(0,0,0,120))
        painter.setPen(QPen(QColor(255,255,255,230), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(hole)
        painter.restore()

class ImageCropDialog(QDialog):
    # ... (โค้ดเดิม)
    def __init__(self, src_path: str, target_px: int = 256, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop profile"); self.resize(900, 620)
        self.target_px = target_px

        self.scene = QGraphicsScene(self)
        self.view  = _CropView(self.scene, self)

        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                     QDialogButtonBox.StandardButton.Cancel, parent=self)
        self.btns.accepted.connect(self.accept); self.btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self); lay.setContentsMargins(8,8,8,8)
        lay.addWidget(self.view); lay.addWidget(self.btns)

        norm = os.path.normpath(src_path)
        if not os.path.exists(norm):
            QMessageBox.critical(self, "Image", "ไม่พบไฟล์รูปที่จะครอป"); self.reject(); return
        self.pix = QPixmap(norm)
        if self.pix.isNull():
            QMessageBox.critical(self, "Image", "เปิดรูปไม่สำเร็จ"); self.reject(); return

        self.item = QGraphicsPixmapItem(self.pix)
        self.item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene.addItem(self.item)
        self.scene.setSceneRect(self.item.boundingRect())
        self._did_fit = False

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._did_fit:
            self.view.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)
            self.view.centerOn(self.item)
            iw, ih = self.pix.width(), self.pix.height()
            side = int(min(iw, ih) * 0.55)
            side = max(140, min(side, int(min(iw, ih) * 0.88)))
            rect_img = QRectF((iw - side)/2, (ih - side)/2, side, side)
            self.view.crop_item = DraggableCropRect(
                rect=rect_img,
                scene_rect=self.item.boundingRect(),
                min_side=100, max_side_factor=0.88
            )
            self.scene.addItem(self.view.crop_item); self.scene.update()
            self._did_fit = True

    def get_cropped_qimage(self):
        r = self.view.crop_item.rect() if self.view.crop_item else self.item.boundingRect()
        r = r & self.item.boundingRect()
        x, y = max(0, int(r.x())), max(0, int(r.y()))
        w, h = max(1, int(r.width())), max(1, int(r.height()))
        qimg = self.pix.toImage().copy(x, y, w, h)
        return qimg.scaled(self.target_px, self.target_px,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)

# =========================================================
#   UI helpers (ตัดทอนเพื่อความกระชับ)
# =========================================================
def style_tab_active(btn: QPushButton):
    btn.setStyleSheet("background:#7aa8ac; color:white; border:none; border-radius:28px;")
def style_tab_inactive(btn: QPushButton):
    btn.setStyleSheet("background:#e6d9cb; color:#7aa8ac; border:none; border-radius:28px;")
def pill_lineedit(ph, height=56):
    le = QLineEdit(); le.setPlaceholderText(ph); le.setFixedHeight(height)
    le.setStyleSheet(f"""
        QLineEdit {{
            background:#F8F3ED; color:#3E3E3E;
            border:1.5px solid #E4D9CC; border-radius:{height//2}px;
            padding:0 22px; selection-background-color:#7aa8ac;
        }}
        QLineEdit:focus {{ border:2px solid #7aa8ac; background:#FBF8F4; }}
        QLineEdit::placeholder {{ color:#b7ada2; }}
    """); return le

def make_eye_button(for_lineedit: QLineEdit) -> QPushButton:
    btn = QPushButton("ㆅ", for_lineedit)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setToolTip("Show/Hide password")
    btn.setFixedSize(28, 28)
    btn.setStyleSheet("""
        QPushButton{
            border:none; background:transparent; color:#6d8f93;
            font-size:18px; font-weight:900;
        }
        QPushButton:hover{ color:#88aeb3; }
    """)
    def reposition():
        x = for_lineedit.width() - 22 - btn.width()
        y = (for_lineedit.height() - btn.height()) // 2
        btn.move(x, y)
    old_resize = for_lineedit.resizeEvent
    def new_resize(ev):
        if old_resize: old_resize(ev)
        reposition()
    for_lineedit.resizeEvent = new_resize
    reposition()
    def toggle():
        is_hidden = (for_lineedit.echoMode() == QLineEdit.EchoMode.Password)
        for_lineedit.setEchoMode(QLineEdit.EchoMode.Normal if is_hidden else QLineEdit.EchoMode.Password)
    btn.clicked.connect(toggle); return btn

# =========================================================
#   Pages (Sign In / Sign Up) (ตัดทอนเพื่อความกระชับ)
# =========================================================
def build_signin_page(family: str):
    page = QFrame()
    root = QHBoxLayout(page); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

    left = QFrame(); left.setStyleSheet("background:#f8f5ef;")
    lbox = QVBoxLayout(left); lbox.setContentsMargins(0,0,0,0)
    bus_lbl = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
    bus_src = QPixmap(BUS_SIGNIN) if os.path.exists(BUS_SIGNIN) else QPixmap()
    if not bus_src.isNull(): bus_lbl.setPixmap(bus_src)
    lbox.addWidget(bus_lbl); root.addWidget(left, 3)

    def _left_resize(ev):
        if not bus_src.isNull():
            w, h = max(1,left.width()), max(1,left.height())
            scaled = bus_src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                            Qt.TransformationMode.SmoothTransformation)
            x = max(0,(scaled.width()-w)//2); y=max(0,(scaled.height()-h)//2)
            bus_lbl.setPixmap(scaled.copy(x,y,w,h))
        QFrame.resizeEvent(left, ev)
    left.resizeEvent = _left_resize

    right = QFrame(objectName="pane")
    right.setStyleSheet("""
        QFrame#pane{ background:#8a663f; }
        QLabel[h1="true"]{ color:#FFF4E8; font-size:28px; font-weight:700; letter-spacing:2px; }
        QLabel[h0="true"]{ color:#FFF4E8; font-size:54px; font-weight:800; letter-spacing:2px; }
    """)
    r = QVBoxLayout(right); r.setContentsMargins(64,64,64,64); r.setSpacing(18)

    t1 = QLabel("WELCOME TO"); t1.setProperty("h1", True); t1.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    t2 = QLabel("GO WITH CREPE"); t2.setProperty("h0", True); t2.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    t1.setFont(QFont(family, 28, int(QFont.Weight.Bold))); t2.setFont(QFont(family, 54, int(QFont.Weight.Black)))

    tabs = QHBoxLayout(); tabs.setSpacing(22)
    btn_signin = QPushButton("SIGN IN"); btn_signup = QPushButton("SIGN UP")
    for b in (btn_signin, btn_signup):
        b.setCursor(Qt.CursorShape.PointingHandCursor); b.setFixedHeight(58); b.setMinimumWidth(210)
        b.setFont(QFont(family, 26, int(QFont.Weight.Bold)))
    style_tab_active(btn_signin); style_tab_inactive(btn_signup)
    tabs.addWidget(btn_signin); tabs.addWidget(btn_signup); tabs.addStretch(1)

    user = pill_lineedit("Username or Email address")
    pwd  = pill_lineedit("Password"); pwd.setEchoMode(QLineEdit.EchoMode.Password)
    user.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9@._-]*$")))
    pwd.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[\x20-\x7E]*$")))
    make_eye_button(pwd)

    forgot = QLabel('<a href="#">FORGOT YOUR PASSWORD?</a>')
    forgot.setOpenExternalLinks(False); forgot.setStyleSheet("color:#D3C8BE; font-size:16px; text-decoration: underline;")
    forgot.setAlignment(Qt.AlignmentFlag.AlignRight)
    forgot.linkActivated.connect(lambda _: QMessageBox.information(page, "Forgot", "ฟีเจอร์กำลังพัฒนา"))

    btn_signin_bottom = QPushButton("SIGN IN"); btn_signin_bottom.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_signin_bottom.setFixedHeight(64); btn_signin_bottom.setFixedWidth(230)
    btn_signin_bottom.setStyleSheet("""
        QPushButton{ background:#7aa8ac; color:#ffffff; border:none; border-radius:24px; font-size:26px; font-weight:800; }
        QPushButton:hover{ background:#86b1b5; } QPushButton:pressed{ background:#6f9aa0; }
    """); btn_signin_bottom.setFont(QFont(family, 26, int(QFont.Weight.Bold)))

    def _open_next(py_file: str, username: str):
        if not os.path.exists(py_file): QMessageBox.critical(page,"Open",f"ไม่พบไฟล์:\n{py_file}"); return
        proc = QProcess(page); proc.setProgram(sys.executable); proc.setArguments([py_file, "--user", username])
        ok = proc.startDetached()
        if ok: QTimer.singleShot(200, page.window().close)
        else:  QMessageBox.critical(page,"Open",f"เปิดไฟล์ไม่สำเร็จ:\n{py_file}")

    def do_signin():
        u, p = user.text().strip(), pwd.text()
        if not u or not p: QMessageBox.warning(page,"Sign in","กรุณากรอก Username/Email และ Password"); return
        if not QRegularExpression(r"^[A-Za-z0-9@._-]+$").match(u).hasMatch():
            QMessageBox.warning(page,"Sign in","Username/Email ใช้ได้เฉพาะ A–Z a–z 0–9 @ . _ -"); return
        if not QRegularExpression(r"^[\x20-\x7E]+$").match(p).hasMatch():
            QMessageBox.warning(page,"Sign in","รหัสผ่านรับเฉพาะอักขระภาษาอังกฤษ/ตัวเลข (ASCII)"); return
        
        row = load_user_for_login(u)
        
        if not row: QMessageBox.warning(page,"Sign in","ไม่พบบัญชีนี้"); return
        
        _, uname, _, pw_hash, _, role, _ = row
        
        if not check_password(p, pw_hash): QMessageBox.warning(page,"Sign in","รหัสผ่านไม่ถูกต้อง"); return
        
        # เปิด Admin.py ถ้าเป็น Admin
        if role == 'admin' and os.path.exists(ADMIN_PY):
             _open_next(ADMIN_PY, uname)
        # เปิด Home.py ถ้าเป็น User
        elif role == 'user' and os.path.exists(HOME_PY):
             _open_next(HOME_PY, uname)
        else:
             QMessageBox.critical(page, "Error", f"ไม่พบไฟล์ระบบสำหรับ {role}"); return
             
    btn_signin.clicked.connect(do_signin); btn_signin_bottom.clicked.connect(do_signin)

    r.addWidget(t1); r.addWidget(t2); r.addSpacing(10)
    r.addLayout(tabs); r.addSpacing(18)
    r.addWidget(user); r.addSpacing(12)
    r.addWidget(pwd);  r.addSpacing(6)
    r.addWidget(forgot); r.addSpacing(20)
    r.addWidget(btn_signin_bottom, alignment=Qt.AlignmentFlag.AlignHCenter); r.addStretch(1)
    root.addWidget(right, 2)

    page.btn_tab_signin = btn_signin; page.btn_tab_signup = btn_signup
    return page

def build_signup_page(family: str):
    page = QFrame()
    root = QHBoxLayout(page); root.setContentsMargins(0,0,0,0)

    left = QFrame(); left.setStyleSheet("background:#f8f5ef;")
    lbox = QVBoxLayout(left); lbox.setContentsMargins(0,0,0,0)
    bus_pix = QPixmap(BUS_SIGNUP) if os.path.exists(BUS_SIGNUP) else QPixmap()
    bus_lbl = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
    if not bus_pix.isNull(): bus_lbl.setPixmap(bus_pix)
    lbox.addWidget(bus_lbl); root.addWidget(left, 3)

    def _l_resize(ev):
        if not bus_pix.isNull():
            w, h = max(1,left.width()), max(1,left.height())
            bus_lbl.setPixmap(bus_pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        QFrame.resizeEvent(left, ev)
    left.resizeEvent = _l_resize

    right = QFrame(objectName="pane"); right.setStyleSheet("QFrame#pane{ background:#8a663f; }")
    r = QVBoxLayout(right); r.setContentsMargins(64,48,64,64); r.setSpacing(16)

    tabs = QHBoxLayout(); tabs.setSpacing(24)
    btn_si = QPushButton("SIGN IN"); btn_su = QPushButton("SIGN UP")
    for b in (btn_si, btn_su):
        b.setCursor(Qt.CursorShape.PointingHandCursor); b.setFont(QFont(load_rubik(), 22, int(QFont.Weight.Bold)))
        b.setFixedHeight(60); b.setMinimumWidth(220)
    style_tab_inactive(btn_si); style_tab_active(btn_su)
    tabs.addWidget(btn_si); tabs.addWidget(btn_su); tabs.addStretch(1)

    # Avatar preview (circle)
    avatar = QLabel(); AV = 180
    avatar.setFixedSize(AV, AV)
    avatar.setStyleSheet(f"background:#ddd; border-radius:{AV//2}px;")
    avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    page._profile_path = None

    def _set_avatar_from_qimage(qimg):
        s = AV
        src_pix = QPixmap.fromImage(qimg)
        scaled = src_pix.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
        if scaled.width() > s or scaled.height() > s:
            x = max(0,(scaled.width()-s)//2); y=max(0,(scaled.height()-s)//2)
            scaled = scaled.copy(x, y, s, s)
        out = QPixmap(s, s); out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath(); path.addEllipse(0,0,s,s); p.setClipPath(path)
        p.drawPixmap(0,0,scaled); p.end()
        avatar.setPixmap(out)

    btn_upload = QPushButton("UPLOAD PROFILE"); btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_upload.setStyleSheet("""
        QPushButton{ background:#7aa8ac; color:white; border:none; border-radius:10px; font-weight:800; padding:8px 16px; }
        QPushButton:hover{ background:#86b1b5; }
    """)
    def _upload():
        path, _ = QFileDialog.getOpenFileName(page, "เลือกภาพโปรไฟล์", "", "Images (*.png *.jpg *.jpeg)")
        if not path: return
        dlg = ImageCropDialog(path, target_px=512, parent=page)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        qimg = dlg.get_cropped_qimage()
        _set_avatar_from_qimage(qimg)
        prof = os.path.join(AVATAR_DIR, "_tmp_preview.png")
        try:
            if PIL_ok:
                img = ImageQt.fromqimage(qimg).convert("RGBA").resize((512,512))
                mask = Image.new("L", (512,512), 0); ImageDraw.Draw(mask).ellipse((0,0,512,512), fill=255)
                out = Image.new("RGBA", (512,512), (0,0,0,0)); out.paste(img, (0,0), mask); out.save(prof, optimize=True)
            else:
                qimg.save(prof, "PNG")
            page._profile_path = prof
        except Exception as e:
            QMessageBox.warning(page, "Upload", f"บันทึกรูปไม่สำเร็จ\n{e}"); page._profile_path = None

    btn_upload.clicked.connect(_upload)

    inp_username = pill_lineedit("Username")
    inp_email    = pill_lineedit("Email address")
    inp_password = pill_lineedit("Password (≥9 chars, 1 Uppercase)")
    inp_password.setEchoMode(QLineEdit.EchoMode.Password)
    inp_password.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[\x20-\x7E]*$")))
    make_eye_button(inp_password)
    inp_username.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9._-]*$")))
    inp_email.setValidator(QRegularExpressionValidator(QRegularExpression(
        r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )))

    btn_signup = QPushButton("SIGN UP"); btn_signup.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_signup.setFixedHeight(60); btn_signup.setFixedWidth(240)
    btn_signup.setStyleSheet("""
        QPushButton{ background:#7aa8ac; color:#ffffff; border:none; border-radius:24px; font-size:24px; font-weight:900; }
        QPushButton:hover{ background:#86b1b5; } QPushButton:pressed{ background:#6f9aa0; }
    """)
    def do_signup():
        u = inp_username.text().strip(); e = inp_email.text().strip(); p = inp_password.text()
        if not u or not e or not p: QMessageBox.warning(page,"Sign Up","กรุณากรอกข้อมูลให้ครบ"); return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", u): QMessageBox.warning(page,"Sign Up","Username ใช้ A–Z a–z 0–9 . _ -"); return
        if not QRegularExpression(r"^[\x20-\x7E]+$").match(p).hasMatch():
            QMessageBox.warning(page,"Sign Up","Password รับเฉพาะอักขระภาษาอังกฤษ/ตัวเลข (ASCII)"); return
        if not is_valid_password(p): QMessageBox.warning(page,"Sign Up","Password ≥ 9 ตัว และมีตัวพิมพ์ใหญ่ ≥ 1"); return
        
        prof_out = None
        if page._profile_path:
            prof_out = os.path.join(AVATAR_DIR, f"{u}.png")
            try: os.replace(page._profile_path, prof_out)
            except: prof_out = page._profile_path

        ok, msg = register_user(u, e, p, prof_out)
        QMessageBox.information(page, "Sign Up", msg)
        if ok: page.parent().parent().switch_to("signin")

    btn_signup.clicked.connect(do_signup)

    r.addLayout(tabs); r.addSpacing(10)
    r.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignHCenter)
    r.addWidget(btn_upload, alignment=Qt.AlignmentFlag.AlignHCenter)
    r.addSpacing(10)
    r.addWidget(inp_username); r.addWidget(inp_email); r.addWidget(inp_password)
    r.addSpacing(12); r.addWidget(btn_signup, alignment=Qt.AlignmentFlag.AlignHCenter); r.addStretch(1)
    root.addWidget(right, 2)

    page.btn_tab_signin = btn_si; page.btn_tab_signup = btn_su
    return page

# =========================================================
#   Main Window (ตัดทอนเพื่อความกระชับ)
# =========================================================
class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Go with CREPE — Authentication"); self.resize(1366, 768)
        self.family = load_rubik(); QApplication.instance().setFont(QFont(self.family, 11))

        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.stack = QStackedWidget()
        self.page_signin = build_signin_page(self.family)
        self.page_signup = build_signup_page(self.family)
        self.stack.addWidget(self.page_signin); self.stack.addWidget(self.page_signup)
        root.addWidget(self.stack)

        self.page_signin.btn_tab_signup.clicked.connect(lambda: self.switch_to("signup"))
        self.page_signin.btn_tab_signin.clicked.connect(lambda: self.switch_to("signin"))
        self.page_signup.btn_tab_signup.clicked.connect(lambda: self.switch_to("signup"))
        self.page_signup.btn_tab_signin.clicked.connect(lambda: self.switch_to("signin"))

        self._apply_font(self)

    def _apply_font(self, w: QWidget):
        f = w.font(); f.setFamily(self.family); w.setFont(f)
        for child in w.findChildren(QWidget):
            ff = child.font(); ff.setFamily(self.family); child.setFont(ff)

    def switch_to(self, name: str):
        self.stack.setCurrentIndex(0 if name == "signin" else 1)

# =========================================================
#   Run
# =========================================================
if __name__ == "__main__":
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
        
    app.setQuitOnLastWindowClosed(False)
    warn_missing_libs(None)
    try:
        # Initial DB setup for users table and admin account
        init_db(DB_PATH_ABS)
    except Exception as e:
        QMessageBox.critical(None, "Database Error", f"ไม่สามารถเตรียมฐานข้อมูลได้:\n{e}"); sys.exit(1)

    if not os.path.exists(HOME_PY):
        QMessageBox.warning(None, "Path Warning", "ไม่พบไฟล์ปลายทางสำหรับผู้ใช้:\n" + HOME_PY)
    if not os.path.exists(ADMIN_PY):
        QMessageBox.warning(None, "Path Warning", "ไม่พบไฟล์ปลายทางสำหรับ Admin:\n" + ADMIN_PY)

    win = AuthWindow(); win.show()
    sys.exit(app.exec())