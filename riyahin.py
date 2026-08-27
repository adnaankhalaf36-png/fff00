import csv
import html
import os
import sqlite3
import tkinter as tk
import webbrowser
import calendar
from datetime import date, datetime
from tkinter import messagebox, ttk

DB = "riyahin_taiba.db"
CURRENCIES = ("IQD", "USD", "SAR")
COMPANY = "رياحين طيبة للحج والعمرة"
MANAGER = "إبراهيم الحمداني"


def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def number(value):
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def money(value, currency):
    return f"{number(value):,.2f} {currency}"


def init_db():
    connection = db()
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL,
            total REAL DEFAULT 0, paid REAL DEFAULT 0, company TEXT DEFAULT '',
            notes TEXT DEFAULT '', currency TEXT DEFAULT 'IQD', payment_type TEXT DEFAULT 'نقدي',
            down_payment REAL DEFAULT 0, months_count INTEGER DEFAULT 1,
            installment_amount REAL DEFAULT 0, due_date TEXT DEFAULT '', created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, due REAL DEFAULT 0,
            paid REAL DEFAULT 0, notes TEXT DEFAULT '', currency TEXT DEFAULT 'IQD',
            trans_type TEXT DEFAULT 'سحب', created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS company_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT NOT NULL,
            service_type TEXT NOT NULL, total_amount REAL DEFAULT 0, paid_amount REAL DEFAULT 0,
            currency TEXT DEFAULT 'IQD', notes TEXT DEFAULT '', created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, receipt_no TEXT DEFAULT '', kind TEXT NOT NULL,
            name TEXT NOT NULL, phone TEXT DEFAULT '', amount REAL DEFAULT 0, note TEXT DEFAULT '',
            currency TEXT DEFAULT 'IQD', created TEXT NOT NULL
        );
    """)
    for column, definition in (("customer_total", "REAL DEFAULT 0"), ("paid_before", "REAL DEFAULT 0"), ("remaining_after", "REAL DEFAULT 0"), ("next_due_date", "TEXT DEFAULT ''"), ("receipt_time", "TEXT DEFAULT ''")):
        try:
            connection.execute(f"ALTER TABLE payments ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass
    connection.commit()
    connection.close()


def receipt(number_id):
    return f"REC-{1000 + int(number_id)}"


def next_month(value):
    try:
        current = date.fromisoformat(value)
    except (TypeError, ValueError):
        current = date.today()
    month = current.month + 1
    year = current.year
    if month == 13:
        month = 1
        year += 1
    return date(year, month, min(current.day, calendar.monthrange(year, month)[1])).isoformat()


def customer_payment_totals(total, paid_before, payment):
    total = max(number(total), 0)
    paid_before = min(max(number(paid_before), 0), total)
    payment = min(max(number(payment), 0), total - paid_before)
    return total, paid_before, payment, max(total - paid_before - payment, 0)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{COMPANY} | النظام المحاسبي")
        self.geometry("1360x820")
        self.minsize(1120, 700)
        self.colors = {"navy": "#102A43", "blue": "#1976A8", "cyan": "#DFF3F5", "bg": "#F4F7F9", "text": "#243B53", "muted": "#627D98", "line": "#D9E2EC", "green": "#16866A", "red": "#B54745", "gold": "#C88927"}
        self.configure(bg=self.colors["bg"])
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=34, font=("Segoe UI", 10), background="white", fieldbackground="white", foreground=self.colors["text"])
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#E7EEF3", foreground=self.colors["text"])
        self.style.map("Treeview", background=[("selected", self.colors["blue"])], foreground=[("selected", "white")])
        self.style.configure("TCombobox", padding=5)
        self.style.configure("Primary.TButton", background=self.colors["blue"], foreground="white", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        self.style.configure("Danger.TButton", background="#FDECEC", foreground=self.colors["red"], padding=(12, 8))
        init_db()
        self.build_shell()
        self.show_home()

    def build_shell(self):
        header = tk.Frame(self, bg=self.colors["navy"], height=82)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="رياحين طيبة", bg=self.colors["navy"], fg="white", font=("Segoe UI", 22, "bold")).pack(side="right", padx=28, pady=8)
        tk.Label(header, text="نظام إدارة الحج والعمرة", bg=self.colors["navy"], fg="#B9D7E0", font=("Segoe UI", 10)).pack(side="right", pady=15)
        details = tk.Frame(header, bg=self.colors["navy"])
        details.pack(side="left", padx=28, pady=13)
        tk.Label(details, text=f"المدير المالي: {MANAGER}", bg=self.colors["navy"], fg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(details, text=f"{COMPANY}  |  {date.today().year}", bg=self.colors["navy"], fg="#B9D7E0", font=("Segoe UI", 9)).pack(anchor="w")
        self.navbar = tk.Frame(self, bg="#173F59", height=48)
        self.navbar.pack(fill="x")
        self.navbar.pack_propagate(False)
        self.nav_buttons = {}
        pages = (("الرئيسية", self.show_home), ("الزبائن والأقساط", self.show_customers), ("إنشاء وصل قبض", self.show_receipt_creator), ("حركات الشركات", self.show_companies), ("المدفوعات والوصولات", self.show_payments), ("التقارير", self.show_reports))
        for label, command in pages:
            button = tk.Button(self.navbar, text=label, command=command, bg="#173F59", fg="white", activebackground=self.colors["blue"], activeforeground="white", bd=0, padx=20, pady=13, font=("Segoe UI", 10, "bold"), cursor="hand2")
            button.pack(side="right")
            self.nav_buttons[label] = button
        self.body = tk.Frame(self, bg=self.colors["bg"])
        self.body.pack(fill="both", expand=True)

    def clear_body(self, active):
        for child in self.body.winfo_children(): child.destroy()
        for name, button in self.nav_buttons.items(): button.configure(bg=self.colors["blue"] if name == active else "#173F59")

    def title_block(self, title, subtitle):
        block = tk.Frame(self.body, bg=self.colors["bg"])
        block.pack(fill="x", padx=28, pady=(22, 10))
        tk.Label(block, text=title, bg=self.colors["bg"], fg=self.colors["navy"], font=("Segoe UI", 20, "bold")).pack(anchor="e")
        tk.Label(block, text=subtitle, bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="e", pady=3)

    def card(self, parent, title, value, currency, color):
        frame = tk.Frame(parent, bg="white", highlightbackground=self.colors["line"], highlightthickness=1, height=112)
        frame.grid_propagate(False)
        tk.Frame(frame, bg=color, width=6).pack(side="right", fill="y")
        inner = tk.Frame(frame, bg="white")
        inner.pack(fill="both", expand=True, padx=15, pady=12)
        tk.Label(inner, text=title, bg="white", fg=self.colors["muted"], font=("Segoe UI", 10, "bold")).pack(anchor="e")
        tk.Label(inner, text=money(value, currency), bg="white", fg=self.colors["navy"], font=("Segoe UI", 17, "bold")).pack(anchor="e", pady=7)
        return frame

    def sums(self, currency):
        connection = db()
        customer = connection.execute("SELECT COALESCE(SUM(total-paid),0) value FROM customers WHERE currency=?", (currency,)).fetchone()["value"]
        debt = connection.execute("SELECT COALESCE(SUM(total_amount-paid_amount),0) value FROM company_debts WHERE currency=?", (currency,)).fetchone()["value"]
        credit = connection.execute("SELECT COALESCE(SUM(paid),0) value FROM companies WHERE currency=?", (currency,)).fetchone()["value"]
        received = connection.execute("SELECT COALESCE(SUM(amount),0) value FROM payments WHERE currency=?", (currency,)).fetchone()["value"]
        connection.close()
        return customer, max(debt - credit, 0), credit, received

    def show_home(self):
        self.clear_body("الرئيسية")
        self.title_block("لوحة التحكم المالية", "ملخص موحد لجميع العملات والحسابات المستحقة")
        grid = tk.Frame(self.body, bg=self.colors["bg"])
        grid.pack(fill="x", padx=28)
        for column in range(3): grid.columnconfigure(column, weight=1)
        labels = {"IQD": "الدينار العراقي", "USD": "الدولار الأمريكي", "SAR": "الريال السعودي"}
        for index, currency in enumerate(CURRENCIES):
            box = tk.LabelFrame(grid, text=f"  {labels[currency]} ({currency})  ", bg=self.colors["bg"], fg=self.colors["blue"], font=("Segoe UI", 11, "bold"), padx=12, pady=12)
            box.grid(row=0, column=index, sticky="nsew", padx=7)
            values = self.sums(currency)
            for row, (label, value, color) in enumerate((("باقي حسابات الزبائن", values[0], self.colors["blue"]), ("المتبقي من ديون شركتنا", values[1], self.colors["red"]), ("رصيدنا عند الشركات", values[2], self.colors["green"]), ("إجمالي المدفوعات", values[3], self.colors["gold"]))):
                self.card(box, label, value, currency, color).grid(row=row, column=0, sticky="ew", pady=5)
            box.columnconfigure(0, weight=1)
        note = tk.Frame(self.body, bg=self.colors["cyan"], highlightbackground="#B6DDE1", highlightthickness=1)
        note.pack(fill="x", padx=35, pady=24)
        tk.Label(note, text="المتبقي من الديون = إجمالي الدين - الدفعات المسددة - الإيداعات الموجودة كرصيد لنا", bg=self.colors["cyan"], fg=self.colors["navy"], font=("Segoe UI", 11, "bold"), pady=13).pack()

    def table(self, parent, columns, headings, widths):
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

    def toolbar(self, title, add_text, add_command):
        bar = tk.Frame(self.body, bg=self.colors["bg"])
        bar.pack(fill="x", padx=28, pady=8)
        ttk.Button(bar, text=add_text, style="Primary.TButton", command=add_command).pack(side="right")
        tk.Label(bar, text=title, bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 11, "bold")).pack(side="left")
        return bar

    def show_customers(self):
        self.clear_body("الزبائن والأقساط")
        self.title_block("الزبائن والأقساط", "إدارة النقدي والأقساط ومتابعة المتبقي لكل زبون")
        bar = self.toolbar("قائمة الزبائن", "+ إضافة زبون / قسط", self.customer_form)
        ttk.Button(bar, text="تعديل المحدد", command=lambda: self.edit_customer(tree)).pack(side="right", padx=5)
        ttk.Button(bar, text="حذف المحدد", style="Danger.TButton", command=lambda: self.delete_customer(tree)).pack(side="right", padx=5)
        name_filter = tk.StringVar(value="الكل"); type_filter = tk.StringVar(value="الكل")
        ttk.Combobox(bar, textvariable=type_filter, values=("الكل", "نقدي", "اقساط"), state="readonly", width=12).pack(side="left", padx=5)
        ttk.Combobox(bar, textvariable=name_filter, values=["الكل"] + self.names("customers"), state="readonly", width=22).pack(side="left", padx=5)
        tk.Label(bar, text="النوع", bg=self.colors["bg"], fg=self.colors["muted"]).pack(side="left")
        tk.Label(bar, text="الاسم", bg=self.colors["bg"], fg=self.colors["muted"]).pack(side="left", padx=(12, 0))
        columns = ("name", "phone", "payment_type", "total", "paid", "remain", "months", "due", "currency")
        tree = self.table(self.body, columns, {"name":"اسم الزبون", "phone":"الهاتف", "payment_type":"نوع الدفع", "total":"الكلي", "paid":"الواصل", "remain":"المتبقي", "months":"الأقساط", "due":"الاستحقاق", "currency":"العملة"}, {"name":190, "phone":130, "payment_type":100, "total":130, "paid":130, "remain":130, "months":80, "due":110, "currency":80})
        def load(*_):
            tree.delete(*tree.get_children())
            connection = db(); query = "SELECT * FROM customers WHERE 1=1"; args = []
            if name_filter.get() != "الكل": query += " AND name=?"; args.append(name_filter.get())
            if type_filter.get() != "الكل": query += " AND payment_type=?"; args.append(type_filter.get())
            for row in connection.execute(query + " ORDER BY id DESC", args):
                tree.insert("", "end", iid=row["id"], values=(row["name"], row["phone"], row["payment_type"], money(row["total"], row["currency"]), money(row["paid"], row["currency"]), money(row["total"]-row["paid"], row["currency"]), row["months_count"], row["due_date"] or "-", row["currency"]))
            connection.close()
        name_filter.trace_add("write", load); type_filter.trace_add("write", load); load()

    def delete_customer(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب", "حدد زبونًا أولًا.", parent=self); return
        if messagebox.askyesno("تأكيد الحذف", "هل تريد حذف الزبون وجميع بياناته؟", parent=self):
            connection = db(); connection.execute("DELETE FROM customers WHERE id=?", (selected[0],)); connection.commit(); connection.close(); self.show_customers()

    def edit_customer(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب", "حدد زبونًا أولًا.", parent=self); return
        connection = db(); row = connection.execute("SELECT * FROM customers WHERE id=?", (selected[0],)).fetchone(); connection.close()
        win = tk.Toplevel(self); win.title("تعديل بيانات الزبون"); win.geometry("470x420"); win.configure(bg="white")
        fields = {}
        for index, (key, label) in enumerate((("name", "اسم الزبون"), ("phone", "رقم الهاتف"), ("total", "المبلغ الكلي"), ("paid", "المبلغ المسدد"))):
            tk.Label(win, text=label, bg="white", font=("Segoe UI", 10, "bold")).grid(row=index, column=1, padx=15, pady=10, sticky="e")
            field = tk.Entry(win, width=28, justify="right"); field.insert(0, str(row[key])); field.grid(row=index, column=0, padx=15, pady=10); fields[key] = field
        payment_type = ttk.Combobox(win, values=("نقدي", "اقساط"), state="readonly", width=26); payment_type.set(row["payment_type"]); payment_type.grid(row=4, column=0); tk.Label(win, text="نوع الدفع", bg="white").grid(row=4, column=1)
        currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=26); currency.set(row["currency"]); currency.grid(row=5, column=0); tk.Label(win, text="العملة", bg="white").grid(row=5, column=1)
        def save():
            total, paid = number(fields["total"].get()), number(fields["paid"].get())
            if not fields["name"].get().strip() or total <= 0 or paid < 0 or paid > total: messagebox.showwarning("بيانات غير صحيحة", "تأكد من الاسم والمبلغ المسدد وألا يتجاوز المسدد الإجمالي.", parent=win); return
            connection = db(); connection.execute("UPDATE customers SET name=?, phone=?, total=?, paid=?, payment_type=?, currency=? WHERE id=?", (fields["name"].get().strip(), fields["phone"].get().strip(), total, paid, payment_type.get(), currency.get(), row["id"])); connection.commit(); connection.close(); win.destroy(); self.show_customers()
        ttk.Button(win, text="حفظ التعديل", style="Primary.TButton", command=save).grid(row=6, column=0, columnspan=2, pady=18)

    def names(self, table):
        connection = db(); rows = connection.execute(f"SELECT DISTINCT name FROM {table} WHERE name!='' ORDER BY name").fetchall(); connection.close(); return [row[0] for row in rows]

    def customer_form(self):
        win = tk.Toplevel(self); win.title("إضافة زبون أو قسط"); win.geometry("500x520"); win.configure(bg="white")
        fields = {}
        definitions = (("name", "اسم الزبون"), ("phone", "رقم الهاتف"), ("company", "الشركة المرتبطة"), ("total", "المبلغ الكلي"), ("down", "المبلغ الواصل"), ("months", "عدد الأقساط"))
        for row, (key, label) in enumerate(definitions):
            tk.Label(win, text=label, bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=row, column=1, padx=16, pady=9, sticky="e")
            field = tk.Entry(win, width=32, justify="right", font=("Segoe UI", 10)); field.grid(row=row, column=0, padx=16, pady=9); fields[key] = field
        tk.Label(win, text="نوع الدفع", bg="white").grid(row=6, column=1, padx=16, pady=9, sticky="e"); payment_type = ttk.Combobox(win, values=("نقدي", "اقساط"), state="readonly", width=30); payment_type.set("نقدي"); payment_type.grid(row=6, column=0); fields["type"] = payment_type
        tk.Label(win, text="العملة", bg="white").grid(row=7, column=1, padx=16, pady=9, sticky="e"); currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=30); currency.set("IQD"); currency.grid(row=7, column=0); fields["currency"] = currency
        def save():
            total, down = number(fields["total"].get()), number(fields["down"].get()); months = max(1, int(number(fields["months"].get()) or 1)); name = fields["name"].get().strip()
            if not name or not fields["phone"].get().strip() or total <= 0: messagebox.showwarning("بيانات ناقصة", "أدخل الاسم والهاتف والمبلغ الكلي.", parent=win); return
            paid = down if fields["type"].get() == "اقساط" else total
            connection = db(); cur = connection.cursor(); cur.execute("INSERT INTO customers(name,phone,total,paid,company,currency,payment_type,down_payment,months_count,installment_amount,due_date,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (name, fields["phone"].get().strip(), total, paid, fields["company"].get().strip(), currency.get(), fields["type"].get(), down, months, max(total-down, 0)/months if fields["type"].get() == "اقساط" else 0, date.today().isoformat(), date.today().isoformat())); connection.commit(); connection.close(); win.destroy(); self.show_customers()
        ttk.Button(win, text="حفظ بيانات الزبون", style="Primary.TButton", command=save).grid(row=8, column=0, columnspan=2, pady=18)

    def show_companies(self):
        self.clear_body("حركات الشركات"); self.title_block("حركات الشركات", "الإيداع رصيد لنا، والسحب مبلغ مستحق علينا للشركات")
        bar = self.toolbar("الحركات الخارجية", "+ إضافة حركة شركة", self.company_form); name_filter = tk.StringVar(value="الكل"); type_filter = tk.StringVar(value="الكل")
        ttk.Button(bar, text="تعديل المحدد", command=lambda: self.edit_company(tree)).pack(side="right", padx=5)
        ttk.Button(bar, text="حذف المحدد", style="Danger.TButton", command=lambda: self.delete_company(tree)).pack(side="right", padx=5)
        ttk.Combobox(bar, textvariable=type_filter, values=("الكل", "سحب", "إيداع"), state="readonly", width=12).pack(side="left", padx=5); ttk.Combobox(bar, textvariable=name_filter, values=["الكل"] + self.names("companies"), state="readonly", width=22).pack(side="left", padx=5)
        ttk.Button(bar, text="طباعة الوصل", command=lambda: self.print_company(tree)).pack(side="right", padx=5); ttk.Button(bar, text="طباعة جميع الحركات", command=self.print_all_companies).pack(side="right", padx=5)
        columns = ("created", "name", "type", "due", "paid", "currency", "notes"); tree = self.table(self.body, columns, {"created":"التاريخ", "name":"اسم الشركة", "type":"نوع الحركة", "due":"سحب / علينا", "paid":"إيداع / لنا", "currency":"العملة", "notes":"ملاحظات"}, {"name":220, "notes":240})
        def load(*_):
            tree.delete(*tree.get_children()); connection = db(); query = "SELECT * FROM companies WHERE 1=1"; args=[]
            if name_filter.get() != "الكل": query += " AND name=?"; args.append(name_filter.get())
            if type_filter.get() != "الكل": query += " AND trans_type=?"; args.append(type_filter.get())
            for row in connection.execute(query + " ORDER BY id DESC", args): tree.insert("", "end", iid=row["id"], values=(row["created"], row["name"], row["trans_type"], money(row["due"], row["currency"]), money(row["paid"], row["currency"]), row["currency"], row["notes"] or "-"))
            connection.close()
        name_filter.trace_add("write", load); type_filter.trace_add("write", load); load()

    def delete_company(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب", "حدد حركة شركة أولًا.", parent=self); return
        if messagebox.askyesno("تأكيد الحذف", "هل تريد حذف الحركة المحددة؟", parent=self):
            connection = db(); connection.execute("DELETE FROM companies WHERE id=?", (selected[0],)); connection.commit(); connection.close(); self.show_companies()

    def edit_company(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب", "حدد حركة شركة أولًا.", parent=self); return
        connection = db(); row = connection.execute("SELECT * FROM companies WHERE id=?", (selected[0],)).fetchone(); connection.close()
        win = tk.Toplevel(self); win.title("تعديل حركة الشركة"); win.geometry("440x380"); win.configure(bg="white")
        fields = {}
        for index, (key, label, value) in enumerate((("name", "اسم الشركة", row["name"]), ("amount", "المبلغ", row["due"] or row["paid"]), ("notes", "ملاحظات", row["notes"] or ""))):
            tk.Label(win, text=label, bg="white", font=("Segoe UI", 10, "bold")).grid(row=index, column=1, padx=15, pady=10, sticky="e")
            field = tk.Entry(win, width=28, justify="right"); field.insert(0, str(value)); field.grid(row=index, column=0, padx=15, pady=10); fields[key] = field
        trans_type = ttk.Combobox(win, values=("سحب", "إيداع"), state="readonly", width=26); trans_type.set(row["trans_type"]); trans_type.grid(row=3, column=0); tk.Label(win, text="نوع الحركة", bg="white").grid(row=3, column=1)
        currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=26); currency.set(row["currency"]); currency.grid(row=4, column=0); tk.Label(win, text="العملة", bg="white").grid(row=4, column=1)
        def save():
            amount = number(fields["amount"].get())
            if not fields["name"].get().strip() or amount <= 0: messagebox.showwarning("بيانات غير صحيحة", "أدخل اسم الشركة والمبلغ.", parent=win); return
            connection = db(); connection.execute("UPDATE companies SET name=?, due=?, paid=?, notes=?, currency=?, trans_type=? WHERE id=?", (fields["name"].get().strip(), amount if trans_type.get() == "سحب" else 0, amount if trans_type.get() == "إيداع" else 0, fields["notes"].get().strip(), currency.get(), trans_type.get(), row["id"])); connection.commit(); connection.close(); win.destroy(); self.show_companies()
        ttk.Button(win, text="حفظ التعديل", style="Primary.TButton", command=save).grid(row=5, column=0, columnspan=2, pady=18)

    def company_form(self):
        win = tk.Toplevel(self); win.title("إضافة حركة شركة"); win.geometry("440x380"); win.configure(bg="white"); fields={}
        for row, (key, label) in enumerate((("name","اسم الشركة"),("amount","المبلغ"),("notes","ملاحظات"))):
            tk.Label(win,text=label,bg="white",font=("Segoe UI",10,"bold")).grid(row=row,column=1,padx=15,pady=12,sticky="e"); field=tk.Entry(win,width=28,justify="right"); field.grid(row=row,column=0,padx=15,pady=12); fields[key]=field
        type_box=ttk.Combobox(win,values=("سحب","إيداع"),state="readonly",width=26); type_box.set("سحب"); type_box.grid(row=3,column=0); fields["type"]=type_box; curr=ttk.Combobox(win,values=CURRENCIES,state="readonly",width=26); curr.set("IQD"); curr.grid(row=4,column=0); fields["currency"]=curr
        tk.Label(win,text="نوع الحركة",bg="white").grid(row=3,column=1); tk.Label(win,text="العملة",bg="white").grid(row=4,column=1)
        def save():
            if not fields["name"].get().strip() or number(fields["amount"].get()) <= 0: messagebox.showwarning("بيانات ناقصة","أدخل اسم الشركة والمبلغ.",parent=win); return
            amount=number(fields["amount"].get()); connection=db(); connection.execute("INSERT INTO companies(name,due,paid,notes,currency,trans_type,created) VALUES(?,?,?,?,?,?,?)",(fields["name"].get().strip(),amount if type_box.get()=="سحب" else 0,amount if type_box.get()=="إيداع" else 0,fields["notes"].get().strip(),curr.get(),type_box.get(),date.today().isoformat())); connection.commit(); connection.close(); win.destroy(); self.show_companies()
        ttk.Button(win,text="حفظ الحركة",style="Primary.TButton",command=save).grid(row=5,column=0,columnspan=2,pady=18)

    def print_company(self, tree):
        selected=tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب","حدد حركة شركة أولًا.",parent=self); return
        connection=db(); row=connection.execute("SELECT * FROM companies WHERE id=?",(selected[0],)).fetchone(); connection.close()
        voucher_type = "وصل قبض" if row["trans_type"] == "سحب" else "وصل إيداع"
        amount = row["due"] if row["trans_type"] == "سحب" else row["paid"]
        body = f"""
        <div class="voucher-title">{voucher_type}</div>
        <div class="voucher-meta"><span>رقم الوصل: <b>COMP-{row['id']:04d}</b></span><span>تاريخ الإصدار: <b>{row['created']}</b></span></div>
        <table class="details">
            <tr><th>اسم الشركة</th><td colspan="3"><b>{html.escape(row['name'])}</b></td></tr>
            <tr><th>نوع العملية</th><td>{'مبلغ مستحق على الشركة' if row['trans_type'] == 'سحب' else 'مبلغ مودع في حساب الشركة'}</td><th>العملة</th><td><b>{row['currency']}</b></td></tr>
            <tr><th>المبلغ بالأرقام</th><td colspan="3" class="amount-cell">{money(amount, row['currency'])}</td></tr>
            <tr><th>البيان</th><td colspan="3">{html.escape(row['notes'] or 'حركة مالية حسب السجل')}</td></tr>
        </table>
        <div class="amount-words">المبلغ المستلم / المودع أعلاه مثبت في سجلات الشركة بنفس العملة الموضحة.</div>
        <div class="signatures"><div><b>اسم المحاسب</b><br>{html.escape(MANAGER)}<br><span class="line"></span></div><div><b>توقيع المستلم / المودع</b><br><br><span class="line"></span></div><div><b>ختم الشركة</b><br><br><span class="stamp">ختم رسمي</span></div></div>
        """
        self.print_html(voucher_type, body, f"COMP-{row['id']:04d}")

    def print_all_companies(self):
        connection=db(); rows=connection.execute("SELECT * FROM companies ORDER BY id DESC").fetchall(); connection.close()
        body="<table><tr><th>التاريخ</th><th>الشركة</th><th>النوع</th><th>السحب</th><th>الإيداع</th><th>العملة</th></tr>" + "".join(f"<tr><td>{r['created']}</td><td>{html.escape(r['name'])}</td><td>{r['trans_type']}</td><td>{money(r['due'],r['currency'])}</td><td>{money(r['paid'],r['currency'])}</td><td>{r['currency']}</td></tr>" for r in rows) + "</table>"; self.print_html("كشف جميع حركات الشركات", body)

    def show_payments(self):
        self.clear_body("المدفوعات والوصولات"); self.title_block("سجل المدفوعات والوصولات", "حدد عدة سجلات ثم اطبعها في كشف واحد")
        bar=self.toolbar("الوصولات", "+ تسجيل دفعة", self.payment_form); name_filter=tk.StringVar(value="الكل"); type_filter=tk.StringVar(value="الكل")
        ttk.Button(bar, text="تعديل المحدد", command=lambda: self.edit_payment(tree)).pack(side="right", padx=5)
        ttk.Button(bar, text="حذف المحدد", style="Danger.TButton", command=lambda: self.delete_payment(tree)).pack(side="right", padx=5)
        ttk.Combobox(bar,textvariable=type_filter,values=("الكل","زبون","شركة","تسديد دين شركة"),state="readonly",width=18).pack(side="left",padx=5); ttk.Combobox(bar,textvariable=name_filter,values=["الكل"]+self.names("payments"),state="readonly",width=22).pack(side="left",padx=5); ttk.Button(bar,text="طباعة وصل رسمي",command=lambda:self.print_single_payment(tree)).pack(side="right",padx=5); ttk.Button(bar,text="طباعة المحدد كجدول",command=lambda:self.print_payments(tree)).pack(side="right")
        cols=("receipt","created","kind","name","amount","currency","note"); tree=self.table(self.body,cols,{"receipt":"رقم الوصل","created":"التاريخ","kind":"النوع","name":"الاسم","amount":"المبلغ","currency":"العملة","note":"الملاحظة"},{"name":230,"note":260})
        def load(*_):
            tree.delete(*tree.get_children()); c=db(); q="SELECT * FROM payments WHERE 1=1"; args=[]
            if name_filter.get()!="الكل":q+=" AND name=?";args.append(name_filter.get())
            if type_filter.get()!="الكل":q+=" AND kind=?";args.append(type_filter.get())
            for r in c.execute(q+" ORDER BY id DESC",args):tree.insert("","end",iid=r["id"],values=(r["receipt_no"] or receipt(r["id"]),r["created"],r["kind"],r["name"],money(r["amount"],r["currency"]),r["currency"],r["note"] or "-"))
            c.close()
        name_filter.trace_add("write",load);type_filter.trace_add("write",load);load()

    def delete_payment(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب", "حدد وصلاً أولًا.", parent=self); return
        if messagebox.askyesno("تأكيد الحذف", "هل تريد حذف الوصل المحدد؟", parent=self):
            connection = db(); connection.execute("DELETE FROM payments WHERE id=?", (selected[0],)); connection.commit(); connection.close(); self.show_payments()

    def edit_payment(self, tree):
        selected = tree.selection()
        if not selected: messagebox.showwarning("اختيار مطلوب", "حدد وصلاً أولًا.", parent=self); return
        connection = db(); row = connection.execute("SELECT * FROM payments WHERE id=?", (selected[0],)).fetchone(); connection.close()
        win = tk.Toplevel(self); win.title("تعديل الوصل"); win.geometry("440x400"); win.configure(bg="white")
        fields = {}
        for index, (key, label) in enumerate((("name", "اسم الدافع"), ("phone", "الهاتف"), ("amount", "المبلغ"), ("note", "البيان"))):
            tk.Label(win, text=label, bg="white", font=("Segoe UI", 10, "bold")).grid(row=index, column=1, padx=15, pady=10, sticky="e")
            field = tk.Entry(win, width=28, justify="right"); field.insert(0, str(row[key] or "")); field.grid(row=index, column=0, padx=15, pady=10); fields[key] = field
        kind = ttk.Combobox(win, values=("زبون", "شركة", "تسديد دين شركة"), state="readonly", width=26); kind.set(row["kind"]); kind.grid(row=4, column=0); tk.Label(win, text="النوع", bg="white").grid(row=4, column=1)
        currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=26); currency.set(row["currency"]); currency.grid(row=5, column=0); tk.Label(win, text="العملة", bg="white").grid(row=5, column=1)
        def save():
            amount = number(fields["amount"].get())
            if not fields["name"].get().strip() or amount <= 0: messagebox.showwarning("بيانات غير صحيحة", "أدخل الاسم والمبلغ.", parent=win); return
            connection = db(); connection.execute("UPDATE payments SET kind=?, name=?, phone=?, amount=?, note=?, currency=? WHERE id=?", (kind.get(), fields["name"].get().strip(), fields["phone"].get().strip(), amount, fields["note"].get().strip(), currency.get(), row["id"])); connection.commit(); connection.close(); win.destroy(); self.show_payments()
        ttk.Button(win, text="حفظ التعديل", style="Primary.TButton", command=save).grid(row=6, column=0, columnspan=2, pady=18)

    def show_receipt_creator(self):
        self.clear_body("إنشاء وصل قبض")
        self.title_block("إنشاء وصل قبض", "استيراد معلومات الزبون وإصدار وصل قبض رسمي")
        panel = tk.Frame(self.body, bg="white", highlightbackground=self.colors["line"], highlightthickness=1)
        panel.pack(fill="x", padx=150, pady=20)
        panel.columnconfigure(1, weight=1)
        fields = {}
        customer_var = tk.StringVar(value="اختر الزبون")
        customers = db()
        customer_rows = customers.execute("SELECT * FROM customers ORDER BY name").fetchall()
        customers.close()
        customer_names = [row["name"] for row in customer_rows]
        tk.Label(panel, text="الزبون", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=0, column=1, padx=20, pady=14, sticky="e")
        customer_box = ttk.Combobox(panel, textvariable=customer_var, values=customer_names, state="readonly", width=38)
        customer_box.grid(row=0, column=0, padx=20, pady=14, sticky="ew")
        for row, key in enumerate(("الهاتف", "الشركة", "العملة", "الإجمالي", "المدفوع سابقًا", "المتبقي", "دفعة القبض الآن"), 1):
            tk.Label(panel, text=key, bg="white", fg=self.colors["muted"], font=("Segoe UI", 10, "bold")).grid(row=row, column=1, padx=20, pady=9, sticky="e")
            if key == "العملة":
                field = ttk.Combobox(panel, values=CURRENCIES, state="readonly", width=38)
            else:
                field = tk.Entry(panel, width=40, justify="right", font=("Segoe UI", 10), state="readonly" if key != "دفعة القبض الآن" else "normal")
            field.grid(row=row, column=0, padx=20, pady=9, sticky="ew")
            fields[key] = field
        note = tk.Entry(panel, width=40, justify="right", font=("Segoe UI", 10)); note.grid(row=8, column=0, padx=20, pady=9, sticky="ew")
        tk.Label(panel, text="بيان الوصل", bg="white", fg=self.colors["muted"], font=("Segoe UI", 10, "bold")).grid(row=8, column=1, padx=20, pady=9, sticky="e")
        fields["بيان الوصل"] = note
        selected_customer = {"row": None}

        def set_field(key, value):
            fields[key].configure(state="normal")
            fields[key].delete(0, tk.END)
            fields[key].insert(0, value)
            if key != "دفعة القبض الآن": fields[key].configure(state="readonly")

        def load_customer(*_):
            row = next((item for item in customer_rows if item["name"] == customer_var.get()), None)
            selected_customer["row"] = row
            if not row: return
            remaining = max(row["total"] - row["paid"], 0)
            for key, value in (("الهاتف", row["phone"]), ("الشركة", row["company"] or "-"), ("الإجمالي", money(row["total"], row["currency"])), ("المدفوع سابقًا", money(row["paid"], row["currency"])), ("المتبقي", money(remaining, row["currency"]))): set_field(key, value)
            fields["العملة"].set(row["currency"])
            fields["دفعة القبض الآن"].delete(0, tk.END)
            fields["دفعة القبض الآن"].insert(0, str(remaining if row["payment_type"] == "نقدي" else row["installment_amount"] or remaining))
            fields["بيان الوصل"].delete(0, tk.END)
            fields["بيان الوصل"].insert(0, "قبض دفعة من حساب الزبون")
        customer_box.bind("<<ComboboxSelected>>", load_customer)

        def save_receipt():
            row = selected_customer["row"]
            amount = number(fields["دفعة القبض الآن"].get()) if row else 0
            remaining = max(row["total"] - row["paid"], 0) if row else 0
            if not row: messagebox.showwarning("اختيار مطلوب", "اختر الزبون أولًا.", parent=self); return
            if amount <= 0 or amount > remaining: messagebox.showwarning("مبلغ غير صحيح", "يجب أن يكون مبلغ القبض أكبر من صفر ولا يتجاوز المتبقي.", parent=self); return
            total_amount, paid_before, amount, remaining_after = customer_payment_totals(row["total"], row["paid"], amount)
            if row["payment_type"] == "اقساط" and remaining_after > 0:
                next_due_date = next_month(row["due_date"] or date.today().isoformat())
                next_months = max(int(row["months_count"] or 1) - 1, 0)
                next_installment = remaining_after / next_months if next_months else remaining_after
            else:
                next_due_date = ""
                next_months = 0
                next_installment = 0
            connection = db(); cursor = connection.cursor()
            cursor.execute("UPDATE customers SET paid=?, months_count=?, installment_amount=?, due_date=? WHERE id=?", (paid_before + amount, next_months, next_installment, next_due_date, row["id"]))
            receipt_currency = fields["العملة"].get() or row["currency"]
            cursor.execute("INSERT INTO payments(kind,name,phone,amount,note,currency,created,customer_total,paid_before,remaining_after,next_due_date,receipt_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ("زبون", row["name"], row["phone"], amount, fields["بيان الوصل"].get().strip(), receipt_currency, date.today().isoformat(), total_amount, paid_before, remaining_after, next_due_date, datetime.now().strftime("%H:%M:%S")))
            payment_id = cursor.lastrowid; receipt_no = receipt(payment_id)
            cursor.execute("UPDATE payments SET receipt_no=? WHERE id=?", (receipt_no, payment_id))
            connection.commit(); connection.close()
            messagebox.showinfo("تم إنشاء الوصل", f"تم تسجيل القبض بنجاح. رقم الوصل: {receipt_no}", parent=self)
            self.print_payment_record(payment_id)
            self.show_receipt_creator()

        ttk.Button(panel, text="حفظ وإصدار وصل قبض رسمي", style="Primary.TButton", command=save_receipt).grid(row=9, column=0, columnspan=2, pady=22)

    def print_payment_record(self, payment_id):
        connection = db(); row = connection.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone(); connection.close()
        voucher_type = "وصل قبض"
        body = f"""
        <div class="voucher-title">{voucher_type}</div>
        <div class="voucher-meta"><span>رقم الوصل: <b>{html.escape(row['receipt_no'] or receipt(row['id']))}</b></span><span>تاريخ الإصدار: <b>{row['created']}</b></span></div>
        <table class="details">
            <tr><th>اسم المستفيد</th><td colspan="3"><b>{html.escape(COMPANY)}</b></td></tr>
            <tr><th>اسم الدافع</th><td><b>{html.escape(row['name'])}</b></td><th>رقم الهاتف</th><td>{html.escape(row['phone'] or '-')}</td></tr>
            <tr><th>العملة</th><td colspan="3"><b>{row['currency']}</b></td></tr>
            <tr><th>المبلغ الكلي</th><td>{money(row['customer_total'], row['currency'])}</td><th>المدفوع قبل الدفعة</th><td>{money(row['paid_before'], row['currency'])}</td></tr>
            <tr><th>الدفعة الحالية</th><td class="amount-cell">{money(row['amount'], row['currency'])}</td><th>المتبقي بعد الدفعة</th><td class="amount-cell">{money(row['remaining_after'], row['currency'])}</td></tr>
            <tr><th>تاريخ استحقاق الدفعة التالية</th><td colspan="3"><b>{row['next_due_date'] or 'لا توجد دفعة تالية - تم السداد الكامل'}</b></td></tr>
            <tr><th>البيان</th><td colspan="3">{html.escape(row['note'] or 'قبض دفعة من حساب الزبون')}</td></tr>
        </table>
        <div class="amount-words">استلمت من السيد - {html.escape(row['name'])} - بتاريخ {row['created']} الساعة {row['receipt_time'] or 'غير مسجل'} المبلغ الموضح أعلاه، وتم تسجيله لحساب شركة رياحين طيبة للحج والعمرة.</div>
        <div class="signatures"><div><b>اسم المحاسب</b><br>{html.escape(MANAGER)}<br><span class="line"></span></div><div><b>توقيع الدافع</b><br><br><span class="line"></span></div><div><b>ختم المستفيد</b><br><br><span class="stamp">ختم رسمي</span></div></div>
        """
        self.print_html(voucher_type, body, row["receipt_no"] or receipt(row["id"]))

    def payment_form(self):
        win=tk.Toplevel(self);win.title("تسجيل دفعة");win.geometry("430x370");win.configure(bg="white");fields={}
        for i,(key,label) in enumerate((("name","اسم المستلم / الدافع"),("phone","رقم الهاتف"),("amount","المبلغ"),("note","الملاحظة"))):tk.Label(win,text=label,bg="white").grid(row=i,column=1,padx=15,pady=11,sticky="e");fields[key]=tk.Entry(win,width=28,justify="right");fields[key].grid(row=i,column=0,padx=15,pady=11)
        kind=ttk.Combobox(win,values=("زبون","شركة","تسديد دين شركة"),state="readonly",width=26);kind.set("زبون");kind.grid(row=4,column=0);curr=ttk.Combobox(win,values=CURRENCIES,state="readonly",width=26);curr.set("IQD");curr.grid(row=5,column=0);tk.Label(win,text="النوع",bg="white").grid(row=4,column=1);tk.Label(win,text="العملة",bg="white").grid(row=5,column=1)
        def save():
            if not fields["name"].get().strip() or number(fields["amount"].get())<=0:messagebox.showwarning("بيانات ناقصة","أدخل الاسم والمبلغ.",parent=win);return
            c=db();cur=c.cursor();cur.execute("INSERT INTO payments(kind,name,phone,amount,note,currency,created,receipt_time) VALUES(?,?,?,?,?,?,?,?)",(kind.get(),fields["name"].get().strip(),fields["phone"].get().strip(),number(fields["amount"].get()),fields["note"].get().strip(),curr.get(),date.today().isoformat(),datetime.now().strftime("%H:%M:%S")));cur.execute("UPDATE payments SET receipt_no=? WHERE id=?",(receipt(cur.lastrowid),cur.lastrowid));c.commit();c.close();win.destroy();self.show_payments()
        ttk.Button(win,text="حفظ وتوليد الوصل",style="Primary.TButton",command=save).grid(row=6,column=0,columnspan=2,pady=18)

    def print_payments(self, tree):
        selected=tree.selection()
        if not selected:messagebox.showwarning("اختيار مطلوب","حدد وصولًا واحدًا أو أكثر.",parent=self);return
        c=db();rows=[c.execute("SELECT * FROM payments WHERE id=?",(item,)).fetchone() for item in selected];c.close();body="<table><tr><th>الوصل</th><th>التاريخ</th><th>النوع</th><th>الاسم</th><th>المبلغ</th><th>العملة</th></tr>"+"".join(f"<tr><td>{r['receipt_no'] or receipt(r['id'])}</td><td>{r['created']}</td><td>{r['kind']}</td><td>{html.escape(r['name'])}</td><td>{money(r['amount'],r['currency'])}</td><td>{r['currency']}</td></tr>"for r in rows)+"</table>";self.print_html("كشف المدفوعات والوصولات المحددة",body)

    def print_single_payment(self, tree):
        selected = tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("اختيار واحد مطلوب", "حدد وصلًا واحدًا لطباعة الوصل الرسمي.", parent=self)
            return
        connection = db()
        row = connection.execute("SELECT * FROM payments WHERE id=?", (selected[0],)).fetchone()
        connection.close()
        voucher_type = "وصل إيداع" if row["kind"] in ("شركة", "تسديد دين شركة") else "وصل قبض"
        customer_details = ""
        if row["kind"] == "زبون":
            customer_total = row["customer_total"]
            paid_before = row["paid_before"]
            remaining_after = row["remaining_after"]
            next_due = row["next_due_date"]
            if not customer_total:
                customer = db()
                customer_row = customer.execute("SELECT * FROM customers WHERE name=? AND currency=? ORDER BY id DESC LIMIT 1", (row["name"], row["currency"])).fetchone()
                customer.close()
                if customer_row:
                    customer_total = customer_row["total"]
                    paid_before = max(customer_row["paid"] - row["amount"], 0)
                    remaining_after = max(customer_row["total"] - customer_row["paid"], 0)
                    next_due = customer_row["due_date"] or "لا توجد دفعة تالية - تم السداد الكامل"
            if customer_total:
                customer_details = f"<tr><th>المبلغ الكلي</th><td>{money(customer_total, row['currency'])}</td><th>المدفوع قبل الدفعة</th><td>{money(paid_before, row['currency'])}</td></tr><tr><th>الدفعة الحالية</th><td class=\"amount-cell\">{money(row['amount'], row['currency'])}</td><th>المتبقي بعد الدفعة</th><td class=\"amount-cell\">{money(remaining_after, row['currency'])}</td></tr><tr><th>استحقاق الدفعة التالية</th><td colspan=\"3\"><b>{next_due or 'لا توجد دفعة تالية - تم السداد الكامل'}</b></td></tr>"
        body = f"""
        <div class="voucher-title">{voucher_type}</div>
        <div class="voucher-meta"><span>رقم الوصل: <b>{html.escape(row['receipt_no'] or receipt(row['id']))}</b></span><span>تاريخ الإصدار: <b>{row['created']}</b></span></div>
        <table class="details">
            <tr><th>اسم المستفيد</th><td colspan="3"><b>{html.escape(COMPANY)}</b></td></tr>
            <tr><th>اسم الدافع</th><td><b>{html.escape(row['name'])}</b></td><th>نوع السجل</th><td>{html.escape(row['kind'])}</td></tr>
            <tr><th>العملة</th><td colspan="3"><b>{row['currency']}</b></td></tr>
            <tr><th>المبلغ</th><td colspan="3" class="amount-cell">{money(row['amount'], row['currency'])}</td></tr>
            {customer_details}
            <tr><th>البيان</th><td colspan="3">{html.escape(row['note'] or 'دفعة مالية مثبتة في سجلات الشركة')}</td></tr>
        </table>
        <div class="amount-words">استلمت من السيد - {html.escape(row['name'])} - بتاريخ {row['created']} الساعة {row['receipt_time'] or 'غير مسجل'} المبلغ الموضح أعلاه، وتم تسجيله لحساب شركة رياحين طيبة للحج والعمرة.</div>
        <div class="signatures"><div><b>اسم المحاسب</b><br>{html.escape(MANAGER)}<br><span class="line"></span></div><div><b>توقيع الدافع</b><br><br><span class="line"></span></div><div><b>ختم المستفيد</b><br><br><span class="stamp">ختم رسمي</span></div></div>
        """
        self.print_html(voucher_type, body, row["receipt_no"] or receipt(row["id"]))

    def show_reports(self):
        self.clear_body("التقارير");self.title_block("التقارير الشاملة","اختر التقرير ثم اطبعه كاملًا من زر الطباعة")
        box=tk.Frame(self.body,bg="white",highlightbackground=self.colors["line"],highlightthickness=1);box.pack(fill="x",padx=28,pady=10);choice=ttk.Combobox(box,values=("ملخص الديون والعملات","تقرير الزبائن والأقساط","تقرير حركات الشركات","تقرير المدفوعات والوصولات"),state="readonly",width=32);choice.set("ملخص الديون والعملات");choice.pack(side="right",padx=15,pady=15);preview=tk.Text(self.body,height=18,bg="white",fg=self.colors["text"],font=("Segoe UI",11),padx=20,pady=20);preview.pack(fill="both",expand=True,padx=28,pady=10)
        def render():
            preview.delete("1.0",tk.END);c=db();selected=choice.get()
            if selected=="ملخص الديون والعملات":text="التقرير الموحد للديون والأرصدة\n\n"+"\n".join(f"{curr}: باقي الزبائن {money(self.sums(curr)[0],curr)} | المتبقي من ديون شركتنا {money(self.sums(curr)[1],curr)} | رصيدنا عند الشركات {money(self.sums(curr)[2],curr)}"for curr in CURRENCIES)
            elif selected=="تقرير الزبائن والأقساط":text="\n".join(f"{r['name']} | {r['payment_type']} | المتبقي {money(r['total']-r['paid'],r['currency'])}"for r in c.execute("SELECT * FROM customers ORDER BY id DESC"))
            elif selected=="تقرير حركات الشركات":text="\n".join(f"{r['name']} | {r['trans_type']} | {money(r['due'] or r['paid'],r['currency'])}"for r in c.execute("SELECT * FROM companies ORDER BY id DESC"))
            else:text="\n".join(f"{r['receipt_no'] or receipt(r['id'])} | {r['name']} | {money(r['amount'],r['currency'])}"for r in c.execute("SELECT * FROM payments ORDER BY id DESC"))
            c.close();preview.insert("1.0",text)
        ttk.Button(box,text="عرض التقرير",style="Primary.TButton",command=render).pack(side="right",pady=15);ttk.Button(box,text="طباعة التقرير المحدد",command=lambda:self.print_html(choice.get(),"<pre style='white-space:pre-wrap'>"+html.escape(preview.get("1.0",tk.END))+"</pre>")).pack(side="right",padx=8,pady=15);render()

    def print_html(self,title,body,number_text=""):
        path=os.path.abspath("riyahin_print.html")
        with open(path,"w",encoding="utf-8") as file:
            file.write(f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 10mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #edf1ef; color: #263c36; font-family: "Segoe UI", Tahoma, sans-serif; }}
.sheet {{ max-width: 794px; min-height: 1060px; margin: 18px auto; padding: 40px 46px 110px; background: #fff; border: 1px solid #d2dbd6; box-shadow: 0 10px 32px #173f3525; position: relative; overflow: hidden; }}
.topline {{ height: 10px; background: linear-gradient(90deg, #c69c4b 0 24%, #0d5c4a 24% 100%); position: absolute; top: 0; right: 0; left: 0; }}
.company-header {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0 21px; border-bottom: 1px solid #c69c4b; }}
.brand {{ display: flex; align-items: center; gap: 12px; }}
.logo {{ width: 58px; height: 58px; border: 2px solid #c69c4b; color: #0d5c4a; border-radius: 50%; display: grid; place-items: center; font-size: 27px; font-weight: 800; background: #f8f3e8; }}
.company-name {{ font-size: 22px; font-weight: 800; color: #0d5c4a; }}
.company-sub {{ color: #71847d; font-size: 11px; margin-top: 5px; }}
.document-label {{ text-align: left; color: #0d5c4a; font-size: 12px; font-weight: 700; line-height: 1.8; }}
.document-label::before {{ content: "نسخة أصلية"; display: inline-block; margin-bottom: 4px; padding: 2px 8px; border: 1px solid #c69c4b; border-radius: 3px; color: #a27b36; font-size: 9px; }}
.voucher-title {{ margin: 25px auto 16px; width: 280px; padding: 12px; text-align: center; border: 2px solid #0d5c4a; color: #0d5c4a; font-size: 24px; font-weight: 800; letter-spacing: .3px; border-radius: 4px; background: #f5faf8; }}
.voucher-meta {{ display: flex; justify-content: space-between; background: #f5f3ed; padding: 12px 16px; border-right: 5px solid #c69c4b; font-size: 12px; color: #52665f; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 19px; border: 1px solid #cdd9d3; border-radius: 4px; overflow: hidden; }} th,td {{ border-left: 1px solid #d8e1dc; border-bottom: 1px solid #d8e1dc; padding: 13px; text-align: right; font-size: 13px; }} tr:last-child th,tr:last-child td {{ border-bottom: 0; }} th:last-child,td:last-child {{ border-left: 0; }} th {{ width: 22%; background: #eef5f1; color: #34554b; }} .amount-cell {{ color: #0d5c4a; font-size: 21px; font-weight: 800; background: #fbfaf6; }}
.amount-words {{ margin-top: 18px; padding: 14px 16px; border: 1px solid #decda7; border-right: 4px solid #c69c4b; color: #52665f; background: #fffdf7; font-size: 12px; line-height: 1.8; }}
.signatures {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 22px; margin-top: 92px; padding-top: 18px; border-top: 1px solid #d8e1dc; text-align: center; font-size: 12px; color: #34554b; }} .line {{ display: inline-block; width: 132px; border-bottom: 1px solid #71847d; margin-top: 25px; }} .stamp {{ display: inline-block; border: 2px dashed #0d5c4a; color: #0d5c4a; border-radius: 50%; padding: 17px 12px; margin-top: 8px; font-size: 11px; background: #f5faf8; }}
.footer {{ position: absolute; bottom: 25px; right: 46px; left: 46px; padding-top: 13px; border-top: 2px solid #c69c4b; text-align: center; color: #52665f; font-size: 11px; line-height: 1.9; }}
.footer::before {{ content: "رياحين طيبة للحج والعمرة"; display: block; color: #0d5c4a; font-weight: 800; font-size: 12px; }}
.print {{ display: block; margin: 0 auto 15px; padding: 10px 28px; background: #0d5c4a; color: white; border: 0; border-radius: 4px; font-weight: 700; cursor: pointer; }}
@media print {{ body {{ background: white; }} .sheet {{ margin: 0; border: 0; box-shadow: none; max-width: none; min-height: 277mm; }} .print {{ display: none; }} }}
</style></head><body><button class="print" onclick="window.print()">طباعة الوصل</button><main class="sheet"><div class="topline"></div><header class="company-header"><div class="brand"><div class="logo">ر</div><div><div class="company-name">{html.escape(COMPANY)}</div><div class="company-sub">نظام الحسابات والمدفوعات الرسمي</div></div></div><div class="document-label">مستند مالي رسمي<br>المدير المالي: {html.escape(MANAGER)}</div></header>{body}<footer class="footer">العراق - كركوك - طريق بغداد / مجاور محطة وقود بابا كركر<br>هاتف: +9647702733587 &nbsp; | &nbsp; +9647719230276</footer></main></body></html>""")
        webbrowser.open(f"file://{path}")


if __name__ == "__main__":
    App().mainloop()
