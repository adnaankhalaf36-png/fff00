"""
نظام إدارة حسابات الحج والعمرة - الإصدار المحسّن
تطبيق Tkinter متقدم مع ممارسات أفضل وإدارة أفضل للموارد
"""
import csv
import html
import os
import sqlite3
import tkinter as tk
import webbrowser
import calendar
import logging
from contextlib import contextmanager
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Optional, Dict, List, Tuple, Any

# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== الثوابت ====================
DB = "riyahin_taiba.db"
CURRENCIES = ("IQD", "USD", "SAR")
COMPANY = "رياحين طيبة للحج والعمرة"
MANAGER = "إبراهيم الحمداني"

# قاموس الألوان
COLORS = {
    "navy": "#102A43",
    "blue": "#1976A8",
    "cyan": "#DFF3F5",
    "bg": "#F4F7F9",
    "text": "#243B53",
    "muted": "#627D98",
    "line": "#D9E2EC",
    "green": "#16866A",
    "red": "#B54745",
    "gold": "#C69C4B",
    "dark_green": "#0D5C4A"
}

# قاموس الخطوط
FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "heading": ("Segoe UI", 11, "bold"),
    "normal": ("Segoe UI", 10),
    "bold": ("Segoe UI", 10, "bold"),
    "small": ("Segoe UI", 9),
    "large_bold": ("Segoe UI", 17, "bold"),
    "header": ("Segoe UI", 22, "bold"),
}

# حدود النافذة
WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 820
MIN_WIDTH = 1120
MIN_HEIGHT = 700

# ==================== إدارة قاعدة البيانات ====================

@contextmanager
def get_db():
    """Context manager لإدارة اتصالات قاعدة البيانات بكفاءة"""
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    except Exception as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        raise
    finally:
        connection.close()


# ==================== دوال المساعدة ====================

def number(value: Any) -> float:
    """تحويل القيمة إلى رقم عشري مع معالجة الأخطاء"""
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except (ValueError, AttributeError):
        logger.warning(f"قيمة رقمية غير صالحة: {value}")
        return 0.0


def money(value: Any, currency: str) -> str:
    """تنسيق القيمة المالية مع العملة"""
    return f"{number(value):,.2f} {currency}"


def format_number_input(value: Any) -> str:
    """تنسيق الإدخال الرقمي مع فاصلة آلاف"""
    try:
        n = number(value)
        return f"{n:,.2f}"
    except Exception as e:
        logger.error(f"خطأ في تنسيق الرقم: {e}")
        return str(value)


def init_db() -> None:
    """تهيئة قاعدة البيانات مع التحقق من الأعمدة والفهارس"""
    with get_db() as connection:
        # إنشاء الجداول
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                total REAL DEFAULT 0,
                paid REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                currency TEXT DEFAULT 'IQD',
                payment_type TEXT DEFAULT 'نقدي',
                down_payment REAL DEFAULT 0,
                months_count INTEGER DEFAULT 1,
                installment_amount REAL DEFAULT 0,
                due_date TEXT DEFAULT '',
                created TEXT NOT NULL,
                recipient TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                due REAL DEFAULT 0,
                paid REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                currency TEXT DEFAULT 'IQD',
                trans_type TEXT DEFAULT 'سحب',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS company_debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                service_type TEXT NOT NULL,
                total_amount REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0,
                currency TEXT DEFAULT 'IQD',
                notes TEXT DEFAULT '',
                created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_no TEXT DEFAULT '',
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                amount REAL DEFAULT 0,
                note TEXT DEFAULT '',
                currency TEXT DEFAULT 'IQD',
                created TEXT NOT NULL,
                recipient TEXT DEFAULT '',
                customer_total REAL DEFAULT 0,
                paid_before REAL DEFAULT 0,
                remaining_after REAL DEFAULT 0,
                next_due_date TEXT DEFAULT ''
            );
        """)

        # إنشاء فهارس لتحسين الأداء
        try:
            connection.execute("CREATE INDEX IF NOT EXISTS idx_customers_currency ON customers(currency)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_companies_currency ON companies(currency)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_payments_currency ON payments(currency)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_company_debts_currency ON company_debts(currency)")
            connection.commit()
            logger.info("تم إنشاء الفهارس بنجاح")
        except sqlite3.OperationalError:
            logger.info("الفهارس موجودة بالفعل")


def receipt(number_id: int) -> str:
    """توليد رقم وصل فريد"""
    return f"REC-{1000 + int(number_id)}"


def next_month(value: str) -> str:
    """حساب الشهر التالي مع الحفاظ على اليوم"""
    try:
        current = date.fromisoformat(value)
    except (TypeError, ValueError):
        current = date.today()

    month = current.month + 1
    year = current.year

    if month == 13:
        month = 1
        year += 1

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(current.day, last_day)).isoformat()


def customer_payment_totals(total: float, paid_before: float, payment: float) -> Tuple[float, float, float, float]:
    """حساب إجماليات الدفع مع التحقق من الصحة"""
    total = max(number(total), 0)
    paid_before = min(max(number(paid_before), 0), total)
    payment = min(max(number(payment), 0), total - paid_before)
    remaining = max(total - paid_before - payment, 0)
    return total, paid_before, payment, remaining


# ==================== فئات المدراء ====================

class DatabaseManager:
    """مدير قاعدة البيانات المركزي"""

    @staticmethod
    def get_sums(currency: str) -> Tuple[float, float, float, float]:
        """الحصول على الإجماليات لعملة محددة"""
        with get_db() as connection:
            customer = connection.execute(
                "SELECT COALESCE(SUM(total-paid), 0) value FROM customers WHERE currency=?",
                (currency,)
            ).fetchone()["value"]

            debt = connection.execute(
                "SELECT COALESCE(SUM(total_amount-paid_amount), 0) value FROM company_debts WHERE currency=?",
                (currency,)
            ).fetchone()["value"]

            credit = connection.execute(
                "SELECT COALESCE(SUM(paid), 0) value FROM companies WHERE currency=?",
                (currency,)
            ).fetchone()["value"]

            received = connection.execute(
                "SELECT COALESCE(SUM(amount), 0) value FROM payments WHERE currency=?",
                (currency,)
            ).fetchone()["value"]

        return customer, max(debt - credit, 0), credit, received

    @staticmethod
    def get_distinct_names(table: str) -> List[str]:
        """الحصول على أسماء فريدة من جدول محدد"""
        with get_db() as connection:
            rows = connection.execute(
                f"SELECT DISTINCT name FROM {table} WHERE name != '' ORDER BY name"
            ).fetchall()
        return [row[0] for row in rows]

    @staticmethod
    def add_customer(data: Dict[str, Any]) -> None:
        """إضافة زبون جديد"""
        with get_db() as connection:
            connection.execute(
                """INSERT INTO customers
                (name, phone, total, paid, currency, payment_type, down_payment,
                months_count, installment_amount, due_date, created, recipient, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["name"], data["phone"], data["total"], data["paid"],
                    data["currency"], data["payment_type"], data.get("down_payment", 0),
                    data.get("months_count", 1), data.get("installment_amount", 0),
                    data.get("due_date", ""), datetime.now().isoformat(),
                    data.get("recipient", ""), data.get("notes", "")
                )
            )
            connection.commit()
            logger.info(f"تمت إضافة زبون: {data['name']}")

    @staticmethod
    def update_customer(customer_id: int, data: Dict[str, Any]) -> None:
        """تحديث بيانات زبون"""
        with get_db() as connection:
            connection.execute(
                """UPDATE customers
                SET name=?, phone=?, recipient=?, total=?, paid=?,
                payment_type=?, currency=?, months_count=?, installment_amount=?
                WHERE id=?""",
                (
                    data["name"], data["phone"], data["recipient"], data["total"],
                    data["paid"], data["payment_type"], data["currency"],
                    data.get("months_count", 1), data.get("installment_amount", 0),
                    customer_id
                )
            )
            connection.commit()
            logger.info(f"تم تحديث الزبون: {customer_id}")

    @staticmethod
    def delete_customer(customer_id: int) -> None:
        """حذف زبون"""
        with get_db() as connection:
            connection.execute("DELETE FROM customers WHERE id=?", (customer_id,))
            connection.commit()
            logger.info(f"تم حذف الزبون: {customer_id}")

    @staticmethod
    def get_customer(customer_id: int) -> Optional[sqlite3.Row]:
        """الحصول على بيانات زبون"""
        with get_db() as connection:
            return connection.execute(
                "SELECT * FROM customers WHERE id=?", (customer_id,)
            ).fetchone()

    @staticmethod
    def get_customers(filters: Dict[str, str]) -> List[sqlite3.Row]:
        """الحصول على قائمة الزبائن مع الفلاتر"""
        query = "SELECT * FROM customers WHERE 1=1"
        args = []

        if filters.get("name") and filters["name"] != "الكل":
            query += " AND name=?"
            args.append(filters["name"])

        if filters.get("payment_type") and filters["payment_type"] != "الكل":
            query += " AND payment_type=?"
            args.append(filters["payment_type"])

        query += " ORDER BY id DESC"

        with get_db() as connection:
            return connection.execute(query, args).fetchall()


class FormValidator:
    """التحقق من صحة نماذج الإدخال"""

    @staticmethod
    def validate_customer_form(name: str, phone: str, total: float) -> Tuple[bool, str]:
        """التحقق من صحة بيانات الزبون"""
        if not name or not name.strip():
            return False, "أدخل اسم الزبون"

        if not phone or not phone.strip():
            return False, "أدخل رقم الهاتف"

        if total <= 0:
            return False, "يجب أن يكون المبلغ الكلي أكبر من صفر"

        return True, "صحيح"

    @staticmethod
    def validate_installment_form(total: float, months: int) -> Tuple[bool, str]:
        """التحقق من صحة بيانات الأقساط"""
        if months <= 0:
            return False, "عدد الأقساط يجب أن يكون أكبر من صفر"

        if total < 0:
            return False, "المبلغ الكلي لا يمكن أن يكون سالباً"

        return True, "صحيح"


# ==================== تطبيق Tkinter ====================

class App(tk.Tk):
    """تطبيق إدارة الحسابات الرئيسي"""

    def __init__(self):
        super().__init__()
        self.title(f"{COMPANY} | النظام المحاسبي")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

        self.colors = COLORS
        self.fonts = FONTS

        self.configure(bg=self.colors["bg"])
        self._setup_styles()
        init_db()
        self.build_shell()
        self.show_home()

    def _setup_styles(self) -> None:
        """إعداد أنماط TTK"""
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.style.configure("Treeview", rowheight=34, font=self.fonts["normal"],
                           background="white", fieldbackground="white",
                           foreground=self.colors["text"])
        self.style.configure("Treeview.Heading", font=self.fonts["bold"],
                           background="#E7EEF3", foreground=self.colors["text"])
        self.style.map("Treeview", background=[("selected", self.colors["blue"])],
                      foreground=[("selected", "white")])
        self.style.configure("TCombobox", padding=5)
        self.style.configure("Primary.TButton", background=self.colors["blue"],
                           foreground="white", padding=(12, 8), font=self.fonts["bold"])
        self.style.configure("Danger.TButton", background="#FDECEC",
                           foreground=self.colors["red"], padding=(12, 8))

    def build_shell(self) -> None:
        """بناء واجهة التطبيق الرئيسية"""
        # رأس الصفحة
        header = tk.Frame(self, bg=self.colors["navy"], height=82)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="رياحين طيبة", bg=self.colors["navy"], fg="white",
                font=self.fonts["header"]).pack(side="right", padx=28, pady=8)
        tk.Label(header, text="نظام إدارة الحج والعمرة", bg=self.colors["navy"],
                fg="#B9D7E0", font=self.fonts["normal"]).pack(side="right", pady=15)

        details = tk.Frame(header, bg=self.colors["navy"])
        details.pack(side="left", padx=28, pady=13)
        tk.Label(details, text=f"المدير المالي: {MANAGER}", bg=self.colors["navy"],
                fg="white", font=self.fonts["bold"]).pack(anchor="w")
        tk.Label(details, text=f"{COMPANY}  |  {date.today().year}",
                bg=self.colors["navy"], fg="#B9D7E0", font=self.fonts["small"]).pack(anchor="w")

        # شريط التنقل
        self.navbar = tk.Frame(self, bg="#173F59", height=48)
        self.navbar.pack(fill="x")
        self.navbar.pack_propagate(False)
        self.nav_buttons = {}

        pages = (
            ("الرئيسية", self.show_home),
            ("الزبائن والأقساط", self.show_customers),
            ("إنشاء وصل قبض", self.show_receipt_creator),
            ("حركات الشركات", self.show_companies),
        )

        for label, command in pages:
            button = tk.Button(self.navbar, text=label, command=command, bg="#173F59",
                              fg="white", activebackground=self.colors["blue"],
                              activeforeground="white", bd=0, padx=20, pady=13,
                              font=self.fonts["bold"])
            button.pack(side="right")
            self.nav_buttons[label] = button

        # جسم الصفحة
        self.body = tk.Frame(self, bg=self.colors["bg"])
        self.body.pack(fill="both", expand=True)

    def clear_body(self, active: str) -> None:
        """تنظيف محتوى الصفحة وتحديث الزر النشط"""
        for child in self.body.winfo_children():
            child.destroy()

        for name, button in self.nav_buttons.items():
            button.configure(bg=self.colors["blue"] if name == active else "#173F59")

    def title_block(self, title: str, subtitle: str) -> None:
        """إنشاء كتلة عنوان"""
        block = tk.Frame(self.body, bg=self.colors["bg"])
        block.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(block, text=title, bg=self.colors["bg"], fg=self.colors["navy"],
                font=self.fonts["title"]).pack(anchor="e")
        tk.Label(block, text=subtitle, bg=self.colors["bg"], fg=self.colors["muted"],
                font=self.fonts["normal"]).pack(anchor="e", pady=3)

    def card(self, parent: tk.Widget, title: str, value: float, currency: str, color: str) -> tk.Frame:
        """إنشاء بطاقة معلومات"""
        frame = tk.Frame(parent, bg="white", highlightbackground=self.colors["line"],
                        highlightthickness=1, height=112)
        frame.grid_propagate(False)
        tk.Frame(frame, bg=color, width=6).pack(side="right", fill="y")

        inner = tk.Frame(frame, bg="white")
        inner.pack(fill="both", expand=True, padx=15, pady=12)
        tk.Label(inner, text=title, bg="white", fg=self.colors["muted"],
                font=self.fonts["bold"]).pack(anchor="e")
        tk.Label(inner, text=money(value, currency), bg="white", fg=self.colors["navy"],
                font=self.fonts["large_bold"]).pack(anchor="e", pady=7)
        return frame

    def show_home(self) -> None:
        """عرض لوحة التحكم الرئيسية"""
        self.clear_body("الرئيسية")
        self.title_block("لوحة التحكم المالية",
                        "ملخص موحد لجميع العملات والحسابات المستحقة")

        grid = tk.Frame(self.body, bg=self.colors["bg"])
        grid.pack(fill="x", padx=28)

        for column in range(3):
            grid.columnconfigure(column, weight=1)

        labels = {
            "IQD": "الدينار العراقي",
            "USD": "الدولار الأمريكي",
            "SAR": "الريال السعودي"
        }

        for index, currency in enumerate(CURRENCIES):
            box = tk.LabelFrame(grid, text=f"  {labels[currency]} ({currency})  ",
                               bg=self.colors["bg"], fg=self.colors["blue"],
                               font=self.fonts["heading"], padx=12, pady=12)
            box.grid(row=0, column=index, sticky="nsew", padx=7)

            values = DatabaseManager.get_sums(currency)
            card_data = [
                ("باقي حسابات الزبائن", values[0], self.colors["blue"]),
                ("المتبقي من ديون شركتنا", values[1], self.colors["red"]),
                ("الرصيد لدينا", values[2], self.colors["green"]),
                ("المبالغ المستلمة", values[3], self.colors["gold"])
            ]

            for row, (label, value, color) in enumerate(card_data):
                self.card(box, label, value, currency, color).grid(row=row, column=0,
                                                                  sticky="ew", pady=5)

            box.columnconfigure(0, weight=1)

        # ملاحظة توضيحية
        note = tk.Frame(self.body, bg=self.colors["cyan"], highlightbackground="#B6DDE1",
                       highlightthickness=1)
        note.pack(fill="x", padx=35, pady=24)
        tk.Label(note, text="المتبقي من الديون = إجمالي الدين - الدفعات المسددة - الإيداعات الموجودة كرصيد لنا",
                bg=self.colors["cyan"], fg=self.colors["text"], font=self.fonts["normal"]).pack(padx=12, pady=8)

    def table(self, parent: tk.Widget, columns: Tuple, headings: Dict, widths: Dict) -> ttk.Treeview:
        """إنشاء جدول"""
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")

        for column in columns:
            tree.heading(column, text=headings[column], anchor="center")
            tree.column(column, width=widths.get(column, 120), anchor="center")

        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="right", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

        return tree

    def toolbar(self, title: str, add_text: str, add_command) -> tk.Frame:
        """إنشاء شريط أدوات"""
        bar = tk.Frame(self.body, bg=self.colors["bg"])
        bar.pack(fill="x", padx=28, pady=8)
        ttk.Button(bar, text=add_text, style="Primary.TButton",
                  command=add_command).pack(side="right")
        tk.Label(bar, text=title, bg=self.colors["bg"], fg=self.colors["muted"],
                font=self.fonts["heading"]).pack(side="left")
        return bar

    def show_customers(self) -> None:
        """عرض صفحة الزبائن والأقساط"""
        self.clear_body("الزبائن والأقساط")
        self.title_block("الزبائن والأقساط",
                        "إدارة النقدي والأقساط ومتابعة المتبقي لكل زبون")

        bar = self.toolbar("قائمة الزبائن", "+ إضافة زبون / قسط", self.customer_form)

        name_filter = tk.StringVar(value="الكل")
        type_filter = tk.StringVar(value="الكل")

        columns = ("name", "phone", "recipient", "payment_type", "total", "paid", "remain", "months", "currency")
        headings = {
            "name": "اسم الزبون",
            "phone": "الهاتف",
            "recipient": "المستلم",
            "payment_type": "نوع الدفع",
            "total": "الكلي",
            "paid": "الواصل",
            "remain": "المتبقي",
            "months": "الأقساط",
            "currency": "العملة"
        }

        tree = self.table(self.body, columns, headings,
                         {"name": 200, "phone": 120, "recipient": 140, "total": 140,
                          "paid": 120, "remain": 120, "months": 100, "currency": 60})

        def load_data(*_):
            tree.delete(*tree.get_children())
            filters = {"name": name_filter.get(), "payment_type": type_filter.get()}
            customers = DatabaseManager.get_customers(filters)

            for row in customers:
                remain = max(number(row["total"]) - number(row["paid"]), 0)
                months = row.get("months_count") or "-"
                tree.insert("", "end", iid=row["id"],
                          values=(row["name"], row["phone"], row.get("recipient") or "-",
                                row["payment_type"], money(row["total"], row["currency"]),
                                money(row["paid"], row["currency"]), money(remain, row["currency"]),
                                months, row["currency"]))

        # الفلاتر
        ttk.Label(bar, text="النوع", background=self.colors["bg"]).pack(side="left", padx=(12, 0))
        ttk.Combobox(bar, textvariable=type_filter,
                    values=("الكل", "نقدي", "اجل", "قسط"),
                    state="readonly", width=12).pack(side="left", padx=5)

        ttk.Label(bar, text="الاسم", background=self.colors["bg"]).pack(side="left")
        ttk.Combobox(bar, textvariable=name_filter,
                    values=["الكل"] + DatabaseManager.get_distinct_names("customers"),
                    state="readonly", width=22).pack(side="left", padx=5)

        # أزرار الأفعال
        ttk.Button(bar, text="تعديل المحدد",
                  command=lambda: self.edit_customer(tree)).pack(side="right", padx=5)
        ttk.Button(bar, text="حذف المحدد", style="Danger.TButton",
                  command=lambda: self.delete_customer(tree)).pack(side="right", padx=5)

        name_filter.trace_add("write", load_data)
        type_filter.trace_add("write", load_data)
        load_data()

    def delete_customer(self, tree: ttk.Treeview) -> None:
        """حذف زبون مع تأكيد"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("اختيار مطلوب", "حدد زبونًا أولًا.", parent=self)
            return

        if messagebox.askyesno("تأكيد الحذف", "هل تريد حذف الزبون وجميع بياناته؟", parent=self):
            try:
                DatabaseManager.delete_customer(selected[0])
                self.show_customers()
                messagebox.showinfo("تم", "تم حذف الزبون بنجاح", parent=self)
            except Exception as e:
                logger.error(f"خطأ في حذف الزبون: {e}")
                messagebox.showerror("خطأ", "فشل حذف الزبون", parent=self)

    def edit_customer(self, tree: ttk.Treeview) -> None:
        """تعديل بيانات زبون"""
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("اختيار مطلوب", "حدد زبونًا أولًا.", parent=self)
            return

        row = DatabaseManager.get_customer(selected[0])
        if not row:
            messagebox.showerror("خطأ", "لم يتم العثور على الزبون", parent=self)
            return

        self._open_customer_form(row, is_edit=True)

    def customer_form(self) -> None:
        """فتح نموذج إضافة زبون جديد"""
        self._open_customer_form(is_edit=False)

    def _open_customer_form(self, row=None, is_edit: bool = False) -> None:
        """فتح نموذج الزبون (إضافة أو تعديل)"""
        win = tk.Toplevel(self)
        win.title("تعديل بيانات الزبون" if is_edit else "إضافة زبون أو قسط")
        win.geometry("520x540")
        win.configure(bg="white")

        fields = self._create_customer_fields(win, row)
        self._setup_customer_validations(fields, win)
        self._bind_customer_events(fields)

        # دالة الحفظ
        def save():
            is_valid, message = FormValidator.validate_customer_form(
                fields["name"].get(),
                fields["phone"].get(),
                number(fields["total"].get())
            )

            if not is_valid:
                messagebox.showwarning("بيانات ناقصة", message, parent=win)
                return

            data = {
                "name": fields["name"].get().strip(),
                "phone": fields["phone"].get().strip(),
                "recipient": fields["recipient"].get().strip(),
                "total": number(fields["total"].get()),
                "currency": fields["currency"].get(),
                "notes": ""
            }

            ptype = fields["payment_type"].get()
            if ptype == "نقدي":
                data["paid"] = data["total"]
                data["months_count"] = 1
                data["installment_amount"] = 0
            elif ptype == "اجل":
                data["paid"] = number(fields["paid"].get())
                data["months_count"] = 1
                data["installment_amount"] = 0
            else:  # قسط
                data["paid"] = number(fields["paid"].get())
                months = int(fields["months"].get()) if fields["months"].get().isdigit() else 0
                is_valid, message = FormValidator.validate_installment_form(data["total"], months)
                if not is_valid:
                    messagebox.showwarning("بيانات غير صحيحة", message, parent=win)
                    return
                data["months_count"] = months
                data["installment_amount"] = (data["total"] - data["paid"]) / months if months else 0

            data["payment_type"] = ptype

            try:
                if is_edit:
                    DatabaseManager.update_customer(row["id"], data)
                    messagebox.showinfo("تم", "تم تحديث بيانات الزبون بنجاح", parent=win)
                else:
                    DatabaseManager.add_customer(data)
                    messagebox.showinfo("تم", "تمت إضافة الزبون بنجاح", parent=win)

                win.destroy()
                self.show_customers()
            except Exception as e:
                logger.error(f"خطأ في حفظ الزبون: {e}")
                messagebox.showerror("خطأ", f"فشل في حفظ البيانات: {e}", parent=win)

        ttk.Button(win, text="حفظ بيانات الزبون", style="Primary.TButton",
                  command=save).grid(row=10, column=0, columnspan=2, pady=18)

    def _create_customer_fields(self, win: tk.Toplevel, row=None) -> Dict:
        """إنشاء حقول نموذج الزبون"""
        fields = {}

        field_specs = [
            ("name", "اسم الزبون", False),
            ("phone", "رقم الهاتف", False),
            ("recipient", "المستلم", False),
            ("total", "المبلغ الكلي", False),
            ("paid", "المدفوع", False),
            ("remain", "المتبقي", True),
            ("months", "عدد الأقساط", False),
            ("installment", "قيمة القسط", True),
        ]

        for idx, (key, label, is_readonly) in enumerate(field_specs):
            tk.Label(win, text=label, bg="white", font=self.fonts["bold"]).grid(
                row=idx, column=1, padx=15, pady=10, sticky="e")

            entry = tk.Entry(win, width=36, justify="right", font=self.fonts["normal"],
                            state="readonly" if is_readonly else "normal")

            if row and key in ("name", "phone", "recipient", "total", "paid", "months"):
                entry.configure(state="normal")
                value = row.get(key, "")
                if key in ("total", "paid"):
                    value = str(value)
                entry.insert(0, value)
                if is_readonly:
                    entry.configure(state="readonly")

            entry.grid(row=idx, column=0, padx=15, pady=10)
            fields[key] = entry

        # نوع الدفع والعملة
        tk.Label(win, text="نوع الدفع", bg="white").grid(row=8, column=1, padx=15, pady=10, sticky="e")
        payment_type = ttk.Combobox(win, values=("نقدي", "اجل", "قسط"),
                                   state="readonly", width=34)
        payment_type.set(row["payment_type"] if row else "نقدي")
        payment_type.grid(row=8, column=0)
        fields["payment_type"] = payment_type

        tk.Label(win, text="العملة", bg="white").grid(row=9, column=1, padx=15, pady=10, sticky="e")
        currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=34)
        currency.set(row["currency"] if row else "IQD")
        currency.grid(row=9, column=0)
        fields["currency"] = currency

        return fields

    def _setup_customer_validations(self, fields: Dict, win: tk.Toplevel) -> None:
        """إعداد التحقق من صحة الحقول"""
        def validate_months(P):
            return P.isdigit() or P == ""

        def validate_number(P):
            return P == "" or all(ch.isdigit() or ch in ".," for ch in P)

        vcmd_months = (win.register(validate_months), '%P')
        vcmd_number = (win.register(validate_number), '%P')

        fields["months"].configure(validate='key', validatecommand=vcmd_months)
        fields["total"].configure(validate='key', validatecommand=vcmd_number)
        fields["paid"].configure(validate='key', validatecommand=vcmd_number)

    def _bind_customer_events(self, fields: Dict) -> None:
        """ربط أحداث الحقول"""
        def compute_remaining(*_):
            t = number(fields["total"].get())
            p = number(fields["paid"].get())
            rem = max(t - p, 0)
            fields["remain"].configure(state="normal")
            fields["remain"].delete(0, tk.END)
            fields["remain"].insert(0, format_number_input(rem))
            fields["remain"].configure(state="readonly")
            compute_installment()

        def compute_installment(*_):
            rem = number(fields["remain"].get())
            months = int(fields["months"].get()) if fields["months"].get().isdigit() else 0
            inst = rem / months if months else 0
            fields["installment"].configure(state="normal")
            fields["installment"].delete(0, tk.END)
            fields["installment"].insert(0, format_number_input(inst))
            fields["installment"].configure(state="readonly")

        def on_type_change(*_):
            ptype = fields["payment_type"].get()
            if ptype == "نقدي":
                fields["paid"].configure(state="normal")
                fields["paid"].delete(0, tk.END)
                fields["paid"].insert(0, format_number_input(number(fields["total"].get())))
                fields["paid"].configure(state="readonly")
                fields["months"].grid_remove()
                fields["installment"].grid_remove()
            elif ptype == "اجل":
                fields["paid"].configure(state="normal")
                fields["months"].grid_remove()
                fields["installment"].grid_remove()
            else:  # قسط
                fields["paid"].configure(state="normal")
                fields["months"].grid()
                fields["installment"].grid()

            compute_remaining()

        fields["payment_type"].bind("<<ComboboxSelected>>", on_type_change)
        fields["total"].bind("<KeyRelease>", lambda e: compute_remaining())
        fields["paid"].bind("<KeyRelease>", lambda e: compute_remaining())
        fields["months"].bind("<KeyRelease>", lambda e: compute_installment())

        on_type_change()
        compute_remaining()

    def show_receipt_creator(self) -> None:
        """عرض صفحة إنشاء الوصولات - قيد التطوير"""
        self.clear_body("إنشاء وصل قبض")
        self.title_block("إنشاء وصل قبض", "تسجيل الدفعات والمدفوعات")
        tk.Label(self.body, text="⚙️ قيد التطوير", bg=self.colors["bg"],
                fg=self.colors["muted"], font=self.fonts["heading"]).pack(pady=20)

    def show_companies(self) -> None:
        """عرض صفحة حركات الشركات - قيد التطوير"""
        self.clear_body("حركات الشركات")
        self.title_block("حركات الشركات", "الإيداع رصيد لنا، والسحب مبلغ مستحق علينا للشركات")
        tk.Label(self.body, text="⚙️ قيد التطوير", bg=self.colors["bg"],
                fg=self.colors["muted"], font=self.fonts["heading"]).pack(pady=20)


# ==================== نقطة الدخول الرئيسية ====================

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        logger.critical(f"خطأ حرج في التطبيق: {e}")
        print(f"خطأ: {e}")
