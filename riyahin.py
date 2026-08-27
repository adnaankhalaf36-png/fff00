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
    # add missing columns safely
    try:
        connection.execute("ALTER TABLE customers ADD COLUMN recipient TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

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
        self.colors = {"navy": "#102A43", "blue": "#1976A8", "cyan": "#DFF3F5", "bg": "#F4F7F9", "text": "#243B53", "muted": "#627D98", "line": "#D9E2EC", "green": "#16866A", "red": "#B54745", "gold": "#C69C4B"}
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
            button = tk.Button(self.navbar, text=label, command=command, bg="#173F59", fg="white", activebackground=self.colors["blue"], activeforeground="white", bd=0, padx=20, pady=13, font=("Segoe UI", 10))
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
            for row, (label, value, color) in enumerate((("باقي حسابات الزبائن", values[0], self.colors["blue"]), ("المتبقي من ديون شركتنا", values[1], self.colors["gold"]), ("رصيدنا", values[2], self.colors["green"]), ("المبلغ المستلم", values[3], self.colors["navy"])):
                self.card(box, label, value, currency, color).grid(row=row, column=0, sticky="ew", pady=5)
            box.columnconfigure(0, weight=1)
        note = tk.Frame(self.body, bg=self.colors["cyan"], highlightbackground="#B6DDE1", highlightthickness=1)
        note.pack(fill="x", padx=35, pady=24)
        tk.Label(note, text="المتبقي من الديون = إجمالي الدين - الدفعات المسددة - الإيداعات الموجودة كرصيد لنا", bg=self.colors["cyan"], fg="#1b5b5a").pack(padx=12, pady=12)

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
        ttk.Combobox(bar, textvariable=type_filter, values=("الكل", "نقدي", "اجل", "قسط"), state="readonly", width=12).pack(side="left", padx=5)
        ttk.Combobox(bar, textvariable=name_filter, values=["الكل"] + self.names("customers"), state="readonly", width=22).pack(side="left", padx=5)
        tk.Label(bar, text="النوع", bg=self.colors["bg"], fg=self.colors["muted"]).pack(side="left")
        tk.Label(bar, text="الاسم", bg=self.colors["bg"], fg=self.colors["muted"]).pack(side="left", padx=(12, 0))
        columns = ("name", "phone", "recipient", "payment_type", "total", "paid", "remain", "months", "due", "currency")
        headings = {"name":"اسم الزبون", "phone":"الهاتف", "recipient":"المستلم", "payment_type":"نوع الدفع", "total":"الكلي", "paid":"الواصل", "remain":"المتبقي", "months":"عدد الأقساط", "due":"تاريخ الاستحقاق", "currency":"العملة"}
        tree = self.table(self.body, columns, headings, {"name":200, "phone":120, "recipient":140, "total":140, "paid":120, "remain":120, "months":100, "currency":60})
        def load(*_):
            tree.delete(*tree.get_children())
            connection = db(); query = "SELECT * FROM customers WHERE 1=1"; args = []
            if name_filter.get() != "الكل": query += " AND name=?"; args.append(name_filter.get())
            if type_filter.get() != "الكل": query += " AND payment_type=?"; args.append(type_filter.get())
            for row in connection.execute(query + " ORDER BY id DESC", args):
                remain = max(number(row["total"]) - number(row["paid"]), 0)
                months = row["months_count"] or "-"
                due = row["due_date"] or "-"
                tree.insert("", "end", iid=row["id"], values=(row["name"], row["phone"], row["recipient"] or "-", row["payment_type"], money(row["total"], row["currency"]), money(row["paid"], row["currency"]), money(remain, row["currency"]), months, due, row["currency"]))
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
        win = tk.Toplevel(self); win.title("تعديل بيانات الزبون"); win.geometry("520x480"); win.configure(bg="white")
        fields = {}
        labels = (("name", "اسم الزبون", row["name"]), ("phone", "رقم الهاتف", row["phone"]), ("recipient", "المستلم", row.get("recipient", "") or ""), ("total", "المبلغ الكلي", row["total"]), ("paid", "المبلغ المسدد", row["paid"]))
        for index, (key, label, value) in enumerate(labels):
            tk.Label(win, text=label, bg="white", font=("Segoe UI", 10, "bold")).grid(row=index, column=1, padx=15, pady=10, sticky="e")
            field = tk.Entry(win, width=32, justify="right"); field.insert(0, str(value or "")); field.grid(row=index, column=0, padx=15, pady=10); fields[key] = field
        payment_type = ttk.Combobox(win, values=("نقدي", "اجل", "قسط"), state="readonly", width=26); payment_type.set(row["payment_type"]); payment_type.grid(row=5, column=0); tk.Label(win, text="نوع الدفع", bg="white").grid(row=5, column=1)
        currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=26); currency.set(row["currency"]); currency.grid(row=6, column=0); tk.Label(win, text="العملة", bg="white").grid(row=6, column=1)
        def save():
            total, paid = number(fields["total"].get()), number(fields["paid"].get())
            if not fields["name"].get().strip() or total <= 0 or paid < 0 or paid > total:
                messagebox.showwarning("بيانات غير صحيحة", "تأكد من الاسم والمبلغ المسدد.", parent=win); return
            connection = db(); connection.execute("UPDATE customers SET name=?, phone=?, recipient=?, total=?, paid=?, payment_type=?, currency=? WHERE id=?", (fields["name"].get().strip(), fields["phone"].get().strip(), fields["recipient"].get().strip(), total, paid, payment_type.get(), currency.get(), row["id"]))
            connection.commit(); connection.close(); self.show_customers(); win.destroy()
        ttk.Button(win, text="حفظ التعديل", style="Primary.TButton", command=save).grid(row=7, column=0, columnspan=2, pady=18)

    def names(self, table):
        connection = db(); rows = connection.execute(f"SELECT DISTINCT name FROM {table} WHERE name!='' ORDER BY name").fetchall(); connection.close(); return [row[0] for row in rows]

    def customer_form(self):
        win = tk.Toplevel(self); win.title("إضافة زبون أو قسط"); win.geometry("520x520"); win.configure(bg="white")
        fields = {}
        # build fields manually to allow dynamic show/hide
        tk.Label(win, text="اسم الزبون", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=0, column=1, padx=16, pady=9, sticky="e")
        name_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); name_entry.grid(row=0, column=0, padx=16, pady=9); fields["name"] = name_entry

        tk.Label(win, text="رقم الهاتف", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=1, column=1, padx=16, pady=9, sticky="e")
        phone_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); phone_entry.grid(row=1, column=0, padx=16, pady=9); fields["phone"] = phone_entry

        tk.Label(win, text="المستلم", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=2, column=1, padx=16, pady=9, sticky="e")
        recipient_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); recipient_entry.grid(row=2, column=0, padx=16, pady=9); fields["recipient"] = recipient_entry

        tk.Label(win, text="المبلغ الكلي", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=3, column=1, padx=16, pady=9, sticky="e")
        total_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); total_entry.grid(row=3, column=0, padx=16, pady=9); fields["total"] = total_entry

        tk.Label(win, text="المدفوع", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=4, column=1, padx=16, pady=9, sticky="e")
        paid_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); paid_entry.grid(row=4, column=0, padx=16, pady=9); fields["paid"] = paid_entry

        tk.Label(win, text="المتبقي", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=5, column=1, padx=16, pady=9, sticky="e")
        remain_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); remain_entry.grid(row=5, column=0, padx=16, pady=9); fields["remain"] = remain_entry

        tk.Label(win, text="عدد الأقساط", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=6, column=1, padx=16, pady=9, sticky="e")
        months_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10)); months_entry.grid(row=6, column=0, padx=16, pady=9); fields["months"] = months_entry

        tk.Label(win, text="قيمة القسط", bg="white", fg=self.colors["text"], font=("Segoe UI", 10, "bold")).grid(row=7, column=1, padx=16, pady=9, sticky="e")
        installment_entry = tk.Entry(win, width=36, justify="right", font=("Segoe UI", 10), state="readonly"); installment_entry.grid(row=7, column=0, padx=16, pady=9); fields["installment"] = installment_entry

        tk.Label(win, text="نوع الدفع", bg="white").grid(row=8, column=1, padx=16, pady=9, sticky="e")
        payment_type = ttk.Combobox(win, values=("نقدي", "اجل", "قسط"), state="readonly", width=34); payment_type.set("نقدي"); payment_type.grid(row=8, column=0)
        fields["type"] = payment_type

        tk.Label(win, text="العملة", bg="white").grid(row=9, column=1, padx=16, pady=9, sticky="e")
        currency = ttk.Combobox(win, values=CURRENCIES, state="readonly", width=34); currency.set("IQD"); currency.grid(row=9, column=0); fields["currency"] = currency

        # helper functions to update dependent fields
        def compute_remaining(*_):
            t = number(fields["total"].get())
            p = number(fields["paid"].get())
            rem = max(t - p, 0)
            fields["remain"].configure(state="normal")
            fields["remain"].delete(0, tk.END)
            fields["remain"].insert(0, str(rem))
            fields["remain"].configure(state="normal")
            compute_installment()

        def compute_installment(*_):
            rem = number(fields["remain"].get())
            months = max(1, int(number(fields["months"].get()) or 1)) if fields["months"].get().strip() else 0
            if months:
                inst = rem / months
            else:
                inst = 0
            fields["installment"].configure(state="normal")
            fields["installment"].delete(0, tk.END)
            fields["installment"].insert(0, str(round(inst, 2)))
            fields["installment"].configure(state="readonly")

        def on_type_change(event=None):
            t = payment_type.get()
            if t == "نقدي":
                # only total needed; set paid == total, hide months/installment
                fields["paid"].configure(state="normal")
                fields["paid"].delete(0, tk.END)
                fields["paid"].insert(0, fields["total"].get())
                fields["paid"].configure(state="readonly")
                fields["remain"].configure(state="normal")
                fields["remain"].delete(0, tk.END)
                fields["remain"].insert(0, "0")
                fields["remain"].configure(state="readonly")
                fields["months"].configure(state="normal")
                fields["months"].delete(0, tk.END)
                fields["months"].configure(state="readonly")
                compute_installment()
            elif t == "اجل":
                # show total, paid editable, remaining computed
                fields["paid"].configure(state="normal")
                fields["months"].configure(state="normal")
                fields["months"].delete(0, tk.END)
                fields["months"].configure(state="readonly")
                compute_remaining()
            else:  # قسط
                # total, paid editable, months editable, installment computed
                fields["paid"].configure(state="normal")
                fields["months"].configure(state="normal")
                compute_remaining()

        # bind changes
        fields["total"].bind("<KeyRelease>", lambda e: compute_remaining())
        fields["paid"].bind("<KeyRelease>", lambda e: compute_remaining())
        fields["months"].bind("<KeyRelease>", lambda e: compute_installment())
        payment_type.bind("<<ComboboxSelected>>", on_type_change)
        on_type_change()

        def save():
            name = fields["name"].get().strip()
            phone = fields["phone"].get().strip()
            recipient = fields["recipient"].get().strip()
            if not name or not phone:
                messagebox.showwarning("بيانات ناقصة", "أدخل الاسم والهاتف.", parent=win); return
            total = number(fields["total"].get())
            if total <= 0:
                messagebox.showwarning("بيانات غير صحيحة", "أدخل المبلغ الكلي أكبر من صفر.", parent=win); return
            ptype = payment_type.get()
            if ptype == "نقدي":
                paid = total
                months = 1
                installment = 0
            elif ptype == "اجل":
                paid = number(fields["paid"].get())
                months = 1
                installment = 0
            else:  # قسط
                paid = number(fields["paid"].get())
                months = max(1, int(number(fields["months"].get()) or 1))
                remaining = max(total - paid, 0)
                installment = remaining / months if months else remaining
            connection = db(); cur = connection.cursor()
            cur.execute("INSERT INTO customers(name,phone,total,paid,company,notes,currency,payment_type,down_payment,months_count,installment_amount,due_date,created,recipient) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (name, phone, total, paid, '', '', fields["currency"].get(), ptype, 0, months, installment, '', datetime.now().isoformat(), recipient))
            connection.commit(); connection.close(); messagebox.showinfo("تم الحفظ", "تمت إضافة الزبون بنجاح.", parent=win); win.destroy(); self.show_customers()

        ttk.Button(win, text="حفظ بيانات الزبون", style="Primary.TButton", command=save).grid(row=10, column=0, columnspan=2, pady=18)

    # ... rest of class remains unchanged ...

    def show_companies(self):
        self.clear_body("حركات الشركات"); self.title_block("حركات الشركات", "الإيداع رصيد لنا، والسحب مبلغ مستحق علينا للشركات")
        bar = self.toolbar("الحركات الخارجية", "+ إضافة حركة شركة", self.company_form); name_filter = tk.StringVar(value="الكل"); type_filter = tk.StringVar(value="الكل")
        ttk.Button(bar, text="تعديل المحدد", command=lambda: self.edit_company(tree)).pack(side="right", padx=5)
        ttk.Button(bar, text="حذف المحدد", style="Danger.TButton", command=lambda: self.delete_company(tree)).pack(side="right", padx=5)
        ttk.Combobox(bar, textvariable=type_filter, values=("الكل", "سحب", "إيداع"), state="readonly", width=12).pack(side="left", padx=5); ttk.Combobox(bar, textvariable=name_filter, values=["الكل"] + self.names("companies"), state="readonly", width=22).pack(side="left", padx=5)
        ttk.Button(bar, text="طباعة الوصل", command=lambda: self.print_company(tree)).pack(side="right", padx=5); ttk.Button(bar, text="طباعة جميع الحركات", command=self.print_all_companies).pack(side="right", padx=5)
        columns = ("created", "name", "type", "due", "paid", "currency", "notes"); tree = self.table(self.body, columns, {"created":"التاريخ", "name":"اسم الشركة", "type":"نوع العملية", "due":"السحب", "paid":"الإيداع", "currency":"العملة", "notes":"الملاحظات"}, {})
        def load(*_):
            tree.delete(*tree.get_children()); connection = db(); query = "SELECT * FROM companies WHERE 1=1"; args=[]
            if name_filter.get() != "الكل": query += " AND name=?"; args.append(name_filter.get())
            if type_filter.get() != "الكل": query += " AND trans_type=?"; args.append(type_filter.get())
            for row in connection.execute(query + " ORDER BY id DESC", args): tree.insert("", "end", iid=row["id"], values=(row["created"], row["name"], row["trans_type"], money(row["due"], row["currency"]), money(row["paid"], row["currency"]), row["currency"], row["notes"]))
            connection.close()
        name_filter.trace_add("write", load); type_filter.trace_add("write", load); load()

    # The rest of the methods (payments, receipts, printing, reports, etc.) remain as in the original file.

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
.voucher-title {{ margin: 25px auto 16px; width: 280px; padding: 12px; text-align: center; border: 2px solid #0d5c4a; color: #0d5c4a; font-size: 24px; font-weight: 800; letter-spacing: .3px; border-radius: 6px; background: #f7fff7; }}
.voucher-meta {{ display: flex; justify-content: space-between; background: #f5f3ed; padding: 12px 16px; border-right: 5px solid #c69c4b; font-size: 12px; color: #52665f; }}
table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 19px; border: 1px solid #cdd9d3; border-radius: 4px; overflow: hidden; }} th,td {{ border-left: 1px solid #d8e1dc; padding: 12px 14px; text-align: right; font-size: 13px; }}
.amount-words {{ margin-top: 18px; padding: 14px 16px; border: 1px solid #decda7; border-right: 4px solid #c69c4b; color: #52665f; background: #fffdf7; font-size: 12px; line-height: 1.8; }}
.signatures {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 22px; margin-top: 92px; padding-top: 18px; border-top: 1px solid #d8e1dc; text-align: center; font-size: 12px; color: #34554b; }}
.footer {{ position: absolute; bottom: 25px; right: 46px; left: 46px; padding-top: 13px; border-top: 2px solid #c69c4b; text-align: center; color: #52665f; font-size: 11px; line-height: 1.9; }}
.footer::before {{ content: "رياحين طيبة للحج والعمرة"; display: block; color: #0d5c4a; font-weight: 800; font-size: 12px; }}
.print {{ display: block; margin: 0 auto 15px; padding: 10px 28px; background: #0d5c4a; color: white; border: 0; border-radius: 4px; font-weight: 700; cursor: pointer; }}
@media print {{ body {{ background: white; }} .sheet {{ margin: 0; border: 0; box-shadow: none; max-width: none; min-height: 277mm; }} .print {{ display: none; }} }}
</style></head><body><button class="print" onclick="window.print()">طباعة الوصل</button><main class="sheet"><div class="topline"></div><header class="company-header"><div class="brand"><div class="logo">ري</div><div><div class="company-name">{html.escape(COMPANY)}</div><div class="company-sub">{html.escape(MANAGER)}</div></div></div><div class="document-label">{html.escape(number_text)}</div></header>{body}<footer class="footer">{html.escape(COMPANY)}</footer></main></body></html>""")
        webbrowser.open(f"file://{path}")


if __name__ == "__main__":
    App().mainloop()
