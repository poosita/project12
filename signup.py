# signup.py — Go with CREPE (PyQt6)
# Updated: Phone number = 10 digits only

import os, sys
from PyQt6.QtCore import Qt, QSize, QRegularExpression
from PyQt6.QtGui import (
    QFontDatabase, QFont, QPixmap, QPainter, QBrush, QPen, QRegularExpressionValidator
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QFileDialog,
    QHBoxLayout, QVBoxLayout, QMessageBox, QFrame
)

# ---------- PATHS ----------
BUS_IMG   = r"C:\Users\LOQ\OneDrive - Khon Kaen University\Desktop\project python\picture\sign up.png"
RUBIK_REG = r"C:\Users\LOQ\OneDrive - Khon Kaen University\Desktop\project python\font\Rubik-Regular.ttf"
RUBIK_BOLD= r"C:\Users\LOQ\OneDrive - Khon Kaen University\Desktop\project python\font\Rubik-Bold.ttf"

def load_rubik():
    fam = None
    if os.path.exists(RUBIK_REG):
        fid = QFontDatabase.addApplicationFont(RUBIK_REG)
        fs  = QFontDatabase.applicationFontFamilies(fid)
        if fs: fam = fs[0]
    if os.path.exists(RUBIK_BOLD):
        QFontDatabase.addApplicationFont(RUBIK_BOLD)
    return fam or "Rubik"

app = QApplication(sys.argv)
family = load_rubik()
app.setFont(QFont(family, 11))

# ---------- WINDOW ----------
win = QWidget()
win.setWindowTitle("Go with CREPE — Sign Up")
win.resize(1366, 768)

root = QHBoxLayout(win)
root.setContentsMargins(0,0,0,0)
root.setSpacing(0)

# ===== LEFT =====
left = QFrame()
left.setStyleSheet("background:#f8f5ef;")
lbox = QVBoxLayout(left)
lbox.setContentsMargins(0,0,0,0)
bus_lbl = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
bus_pix = QPixmap(BUS_IMG) if os.path.exists(BUS_IMG) else QPixmap()
lbox.addWidget(bus_lbl)
root.addWidget(left, 3)

def fit_left():
    if bus_pix.isNull(): return
    w, h = max(1,left.width()), max(1,left.height())
    bus_lbl.setPixmap(bus_pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
def _rz(ev):
    fit_left()
    QWidget.resizeEvent(win, ev)
win.resizeEvent = _rz
fit_left()

# ===== RIGHT =====
right = QFrame(objectName="pane")
right.setStyleSheet("""
    QFrame#pane{ background:#8a663f; }
    QPushButton.tab {
        border:none; border-radius:28px; padding:12px 26px;
        font-size:24px; font-weight:800;
    }
""")
r = QVBoxLayout(right)
r.setContentsMargins(64,48,64,64)
r.setSpacing(16)

# --- top tabs ---
tabs = QHBoxLayout()
tabs.setSpacing(24)
btn_signin_tab = QPushButton("SIGN IN")
btn_signup_tab = QPushButton("SIGN UP")
for b in (btn_signin_tab, btn_signup_tab):
    b.setProperty("class", "tab")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFont(QFont(family, 22, QFont.Weight.Bold))
    b.setFixedHeight(60)
    b.setMinimumWidth(220)

def style_active(btn: QPushButton):
    btn.setStyleSheet("background:#7aa8ac; color:white; border-radius:28px;")
def style_inactive(btn: QPushButton):
    btn.setStyleSheet("background:#e6d9cb; color:#7aa8ac; border-radius:28px;")

style_inactive(btn_signin_tab)
style_active(btn_signup_tab)

def go_signin():
    QMessageBox.information(win, "Switch", "กลับไปหน้า Sign In (ในระบบจริงจะเชื่อมต่อไปหน้า Login)")

btn_signin_tab.clicked.connect(go_signin)

tabs.addWidget(btn_signin_tab)
tabs.addWidget(btn_signup_tab)
tabs.addStretch(1)

# --- avatar upload ---
avatar = QLabel()
AV_SIZE = 180
avatar.setFixedSize(AV_SIZE, AV_SIZE)
avatar.setStyleSheet(f"background:#ddd; border-radius:{AV_SIZE//2}px;")
avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
avatar.setText("")

def set_avatar_from_path(path: str):
    pix = QPixmap(path)
    if pix.isNull():
        QMessageBox.warning(win, "Upload", "เปิดรูปไม่ได้")
        return
    s = AV_SIZE
    pix = pix.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(s, s)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(pix))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, s, s)
    p.end()
    avatar.setPixmap(out)

btn_upload = QPushButton("UPLOAD PROFILE")
btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
btn_upload.setStyleSheet("""
    QPushButton{
        background:#7aa8ac; color:white; border:none; border-radius:10px;
        font-weight:800; padding:8px 16px;
    }
    QPushButton:hover{ background:#86b1b5; }
""")
btn_upload.clicked.connect(lambda: (path := QFileDialog.getOpenFileName(win, "เลือกภาพโปรไฟล์", "", "Images (*.png *.jpg *.jpeg)")[0]) and set_avatar_from_path(path))

# --- inputs (pill) ---
def pill_lineedit(ph):
    le = QLineEdit()
    le.setPlaceholderText(ph)
    PILL_H = 56
    le.setFixedHeight(PILL_H)
    le.setStyleSheet(f"""
        QLineEdit {{
            background:#F8F3ED; color:#3E3E3E;
            border:1.5px solid #E4D9CC;
            border-radius:{PILL_H//2}px;
            padding:0 22px;
        }}
        QLineEdit:focus {{
            border:2px solid #7aa8ac;
            background:#FBF8F4;
        }}
        QLineEdit::placeholder {{ color:#b7ada2; }}
    """)
    return le

inp_username = pill_lineedit("Username")
inp_email    = pill_lineedit("Email address")
inp_phone    = pill_lineedit("Phone number")

# --- Validators ---
inp_username.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9._-]*$")))
inp_email.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")))
# Phone number: ต้องเป็นตัวเลข 10 หลักพอดี
inp_phone.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,10}$")))

# --- Sign Up button ---
btn_signup = QPushButton("SIGN UP")
btn_signup.setCursor(Qt.CursorShape.PointingHandCursor)
btn_signup.setFixedHeight(60)
btn_signup.setFixedWidth(240)
btn_signup.setStyleSheet("""
    QPushButton{
        background:#7aa8ac; color:#ffffff; border:none;
        border-radius:24px; font-size:24px; font-weight:900;
    }
    QPushButton:hover{ background:#86b1b5; }
    QPushButton:pressed{ background:#6f9aa0; }
""")

def do_signup():
    u = inp_username.text().strip()
    e = inp_email.text().strip()
    p = inp_phone.text().strip()

    if not u or not QRegularExpression(r"^[A-Za-z0-9._-]+$").match(u).hasMatch():
        QMessageBox.warning(win, "Sign Up", "Username ใช้ได้เฉพาะ A–Z, a–z, 0–9, . _ -")
        return
    if not e or not QRegularExpression(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$").match(e).hasMatch():
        QMessageBox.warning(win, "Sign Up", "กรุณากรอกอีเมลให้ถูกต้อง เช่น name@example.com")
        return
    if not (len(p) == 10 and p.isdigit()):
        QMessageBox.warning(win, "Sign Up", "Phone number ต้องเป็นตัวเลข 10 หลักเท่านั้น")
        return

    QMessageBox.information(win, "Sign Up", f"สมัครสมาชิกสำเร็จ!\nUsername: {u}\nEmail: {e}\nPhone: {p}")

btn_signup.clicked.connect(do_signup)

# ---- layout compose ----
r.addLayout(tabs)
r.addSpacing(10)
r.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignHCenter)
r.addWidget(btn_upload, alignment=Qt.AlignmentFlag.AlignHCenter)
r.addSpacing(10)
r.addWidget(inp_username)
r.addWidget(inp_email)
r.addWidget(inp_phone)
r.addSpacing(12)
r.addWidget(btn_signup, alignment=Qt.AlignmentFlag.AlignHCenter)
r.addStretch(1)

root.addWidget(right, 2)

# enforce font
for w in (btn_signin_tab, btn_signup_tab, btn_upload, btn_signup,
          inp_username, inp_email, inp_phone):
    f = w.font()
    f.setFamily(family)
    w.setFont(f)

win.show()
sys.exit(app.exec())
