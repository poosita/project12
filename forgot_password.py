# forgot_password.py — Go with CREPE (PyQt6)
# Forgot Password page: Username + Email validators, pill inputs, NEXT button
import os, sys
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QFontDatabase, QFont, QPixmap, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QMessageBox,
    QHBoxLayout, QVBoxLayout, QFrame
)

# ---------- PATHS (แก้ตามเครื่อง) ----------
BUS_IMG   = r"C:\Users\LOQ\OneDrive - Khon Kaen University\Desktop\project python\picture\forgot.png"
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

def make_pill_lineedit(ph: str) -> QLineEdit:
    le = QLineEdit(); le.setPlaceholderText(ph)
    H = 56
    le.setFixedHeight(H)
    le.setStyleSheet(f"""
        QLineEdit {{
            background:#F8F3ED; color:#3E3E3E;
            border:1.5px solid #E4D9CC;
            border-radius:{H//2}px; padding:0 22px;
            font-size:20px;
        }}
        QLineEdit:focus {{ border:2px solid #7aa8ac; background:#FBF8F4; }}
        QLineEdit::placeholder {{ color:#b7ada2; }}
    """)
    return le

class ForgotWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.family = load_rubik()
        self.setWindowTitle("Go with CREPE — Forgot Password")
        self.resize(1366, 768)
        self.setFont(QFont(self.family, 11))

        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # LEFT (ภาพ)
        self.left = QFrame(); self.left.setStyleSheet("background:#f8f5ef;")
        lbox = QVBoxLayout(self.left); lbox.setContentsMargins(0,0,0,0)
        self.bus_lbl = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.bus_pix = QPixmap(BUS_IMG) if os.path.exists(BUS_IMG) else QPixmap()
        lbox.addWidget(self.bus_lbl)
        root.addWidget(self.left, 3)

        # RIGHT (กึ่งกลางแนวตั้ง)
        right = QFrame(objectName="pane")
        right.setStyleSheet("""
            QFrame#pane{ background:#8a663f; }
            QLabel[hero="true"]{
                color:#6c9ea3; font-size:40px; font-weight:900;
                background:#d9d1c7; padding:10px 26px; border-radius:28px;
            }
            QLabel[sub="true"]{ color:#1e3a4a; font-size:22px; font-weight:700; }
        """)
        r = QVBoxLayout(right); r.setContentsMargins(64,48,64,64); r.setSpacing(0)

        # กลุ่มคอนเทนท์ฝั่งขวา (จะถูกจัดให้อยู่กลางแนวตั้ง)
        content = QVBoxLayout(); content.setSpacing(18)

        title = QLabel("FORGOT PASSWORD"); title.setProperty("hero", True)
        subtitle = QLabel("Enter your email and reset a new password"); subtitle.setProperty("sub", True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.user  = make_pill_lineedit("Username")
        self.email = make_pill_lineedit("Email address")
        # Validators
        self.user.setValidator(QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9._-]*$")))
        self.email_rx = QRegularExpression(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
        self.email.setValidator(QRegularExpressionValidator(self.email_rx))

        self.btn_next = QPushButton("NEXT")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setFixedHeight(60); self.btn_next.setFixedWidth(180)
        self.btn_next.setStyleSheet("""
            QPushButton{
                background:#7aa8ac; color:#ffffff; border:none;
                border-radius:24px; font-size:24px; font-weight:900;
            }
            QPushButton:hover{ background:#86b1b5; }
            QPushButton:pressed{ background:#6f9aa0; }
        """)
        self.btn_next.clicked.connect(self.do_next)

        # เติมคอนเทนท์เข้า layout ตรงกลาง
        content.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        content.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)
        content.addSpacing(6)
        content.addWidget(self.user)
        content.addWidget(self.email)
        content.addSpacing(12)
        content.addWidget(self.btn_next, alignment=Qt.AlignmentFlag.AlignHCenter)

        # จัดให้ 'กึ่งกลางแนวตั้ง' ด้วย stretch บน-ล่าง
        r.addStretch(1)
        r.addLayout(content)
        r.addStretch(1)

        root.addWidget(right, 2)

        # unify font
        for w in (title, subtitle, self.user, self.email, self.btn_next):
            f = w.font(); f.setFamily(self.family); w.setFont(f)

        self._fit_left()

    def resizeEvent(self, ev):
        self._fit_left()
        return super().resizeEvent(ev)

    def _fit_left(self):
        if self.bus_pix.isNull(): return
        # ใช้ความกว้างจริงของ panel ซ้าย เพื่อสเกลภาพให้พอดี (contain)
        w = max(1, self.left.width())
        h = max(1, self.height())
        self.bus_lbl.setPixmap(self.bus_pix.scaled(
            w, h, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def do_next(self):
        u = self.user.text().strip()
        e = self.email.text().strip()
        if not u or not QRegularExpression(r"^[A-Za-z0-9._-]+$").match(u).hasMatch():
            QMessageBox.warning(self, "Forgot Password",
                                "Username ใช้ได้เฉพาะ A–Z, a–z, 0–9, . _ -"); return
        if not e or not self.email_rx.match(e).hasMatch():
            QMessageBox.warning(self, "Forgot Password",
                                "กรุณากรอกอีเมลให้ถูกต้อง เช่น name@example.com"); return
        QMessageBox.information(self, "Forgot Password",
                                f"เราได้ส่งลิงก์รีเซ็ตรหัสผ่านไปที่\n{e}\nโปรดตรวจอีเมลของคุณ")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ForgotWindow()
    w.show()
    sys.exit(app.exec())
