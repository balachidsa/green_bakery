"""Bakery Orders - Kivy app (develop on Windows, build APK with Buildozer)."""
import os
import sqlite3
from datetime import datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.utils import platform

# ----------------------------------------------------------------- settings
REMINDER_HOUR = 9          # day-before reminder fires at 9:00 AM
PAY_CHECK_DELAY_MIN = 30   # payment notification, minutes after delivery time
PAY_OFFSET = 1_000_000     # notification key offset for payment alerts
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ----------------------------------------------------------------- database
class DB:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS customers(
                phone TEXT PRIMARY KEY, name TEXT, house TEXT, apartment TEXT);
            CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT, name TEXT, house TEXT, apartment TEXT,
                flavour TEXT, weight TEXT,
                delivery_date TEXT, delivery_time TEXT,
                message TEXT, custom TEXT,
                paid INTEGER DEFAULT 0, created TEXT);
        """)
        self.con.commit()

    def customer(self, phone):
        return self.con.execute(
            "SELECT * FROM customers WHERE phone=?", (phone,)).fetchone()

    def add_order(self, d):
        # customer base is built/updated from every order
        self.con.execute(
            "INSERT OR REPLACE INTO customers(phone,name,house,apartment) "
            "VALUES(?,?,?,?)", (d["phone"], d["name"], d["house"], d["apartment"]))
        cur = self.con.execute(
            "INSERT INTO orders(phone,name,house,apartment,flavour,weight,"
            "delivery_date,delivery_time,message,custom,paid,created) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,0,?)",
            (d["phone"], d["name"], d["house"], d["apartment"], d["flavour"],
             d["weight"], d["delivery_date"], d["delivery_time"], d["message"],
             d["custom"], datetime.now().isoformat(timespec="seconds")))
        self.con.commit()
        return cur.lastrowid

    def order(self, oid):
        return self.con.execute(
            "SELECT * FROM orders WHERE id=?", (oid,)).fetchone()

    def orders(self, show_all):
        sql = "SELECT * FROM orders"
        args = ()
        if not show_all:
            sql += " WHERE delivery_date >= ? OR paid = 0"
            args = (datetime.now().strftime("%Y-%m-%d"),)
        sql += " ORDER BY delivery_date, delivery_time"
        return self.con.execute(sql, args).fetchall()

    def unpaid_due(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return self.con.execute(
            "SELECT * FROM orders WHERE paid=0 AND "
            "delivery_date || ' ' || delivery_time <= ? "
            "ORDER BY delivery_date, delivery_time", (now,)).fetchall()

    def set_paid(self, oid):
        self.con.execute("UPDATE orders SET paid=1 WHERE id=?", (oid,))
        self.con.commit()

    def delete(self, oid):
        self.con.execute("DELETE FROM orders WHERE id=?", (oid,))
        self.con.commit()


# ------------------------------------------------------------------ helpers
def delivery_dt(r):
    return datetime.strptime(
        f"{r['delivery_date']} {r['delivery_time']}", "%Y-%m-%d %H:%M")


def pretty_date(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%a, %d %b %Y")


def pretty_time(hhmm):
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def address(r):
    parts = [p for p in (r["house"], r["apartment"]) if p]
    return ", ".join(parts) if parts else "-"


def cake_line(r):
    return f"{r['flavour']} cake, {r['weight']}"


def full_details(r):
    lines = [
        f"Order #{r['id']}",
        f"Customer: {r['name']}  ({r['phone']})",
        f"Address: {address(r)}",
        f"Cake: {cake_line(r)}",
        f"Delivery: {pretty_date(r['delivery_date'])}, {pretty_time(r['delivery_time'])}",
        f"Message on cake: {r['message'] or '-'}",
        f"Customization: {r['custom'] or '-'}",
        f"Payment: {'PAID' if r['paid'] else 'NOT PAID'}",
    ]
    return "\n".join(lines)


# ------------------------------------------------- Android notifications
def _context():
    from jnius import autoclass
    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    return activity.getApplicationContext()


def notify_at(key, when, title, text):
    """Schedule a notification (WorkManager) - survives app close/reboot."""
    if platform != "android":
        print("[notify]", key, when, title, text)
        return
    try:
        from jnius import autoclass
        sched = autoclass("org.bakery.bakeryapp.ReminderScheduler")
        delay_ms = max(int((when - datetime.now()).total_seconds() * 1000), 5000)
        sched.schedule(_context(), int(key), title, text, delay_ms)
    except Exception as exc:  # never crash the app because of a reminder
        print("schedule failed:", exc)


def cancel_notification(key):
    if platform != "android":
        return
    try:
        from jnius import autoclass
        autoclass("org.bakery.bakeryapp.ReminderScheduler").cancel(
            _context(), int(key))
    except Exception as exc:
        print("cancel failed:", exc)


def schedule_for_order(r):
    dt = delivery_dt(r)
    now = datetime.now()
    if dt <= now:
        return
    # 1) reminder the day before the delivery
    remind = dt.replace(hour=REMINDER_HOUR, minute=0, second=0) - timedelta(days=1)
    fire = max(remind, now)
    word = "tomorrow" if fire.date() + timedelta(days=1) == dt.date() else "today"
    notify_at(
        r["id"], fire, f"Cake delivery {word}",
        f"{pretty_time(r['delivery_time'])} - {cake_line(r)} for {r['name']} "
        f"({address(r)}). Message: {r['message'] or '-'}")
    # 2) payment check shortly after the delivery time
    notify_at(
        r["id"] + PAY_OFFSET, dt + timedelta(minutes=PAY_CHECK_DELAY_MIN),
        "Payment check",
        f"Has {r['name']} paid for the {cake_line(r)}? Tap to confirm.")


# ----------------------------------------------------------------- widgets
class OrderCard(ButtonBehavior, BoxLayout):
    bg = ListProperty([1, 1, 1, 1])
    head = StringProperty("")
    badge = StringProperty("")
    body = StringProperty("")


class DashboardScreen(Screen):
    show_all = False

    def toggle_all(self):
        self.show_all = not self.show_all
        self.ids.toggle.text = "Show upcoming" if self.show_all else "Show all"
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        box = self.ids.box
        box.clear_widgets()
        today = datetime.now().date()
        n_today = n_tom = n_unpaid = 0
        rows = app.db.orders(self.show_all)
        for r in rows:
            d = datetime.strptime(r["delivery_date"], "%Y-%m-%d").date()
            diff = (d - today).days
            paid = bool(r["paid"])
            if not paid:
                n_unpaid += 1
            if diff == 0:
                n_today += 1
            if diff == 1:
                n_tom += 1

            if diff < 0 and not paid:
                bg, tag = (1, 0.80, 0.78, 1), "PAYMENT PENDING"
            elif diff < 0:
                bg, tag = (0.85, 0.94, 0.85, 1), "DONE"
            elif diff == 0:
                bg, tag = (1, 0.86, 0.62, 1), "TODAY"
            elif diff == 1:
                bg, tag = (1, 0.95, 0.70, 1), "TOMORROW"
            else:
                bg, tag = (1, 1, 1, 1), f"IN {diff} DAYS"
            tag += "  |  PAID" if paid else "  |  UNPAID"

            card = OrderCard(
                bg=bg,
                head=f"{pretty_date(r['delivery_date'])}   {pretty_time(r['delivery_time'])}",
                badge=tag,
                body=(f"{r['name']}  ({r['phone']})\n{address(r)}\n"
                      f"{cake_line(r)}"))
            card.bind(on_release=lambda _w, oid=r["id"]: app.show_detail(oid))
            box.add_widget(card)

        if not rows:
            box.add_widget(Label(text="No orders yet. Tap '+ New Order'.",
                                 size_hint_y=None, height=dp(80)))
        self.ids.summary.text = (f"Today: {n_today}   Tomorrow: {n_tom}   "
                                 f"Unpaid: {n_unpaid}")


class NewOrderScreen(Screen):
    def reset(self):
        ids = self.ids
        for k in ("phone", "name", "house", "apartment", "flavour", "weight",
                  "message", "custom"):
            ids[k].text = ""
        ids.status.text = ""
        now = datetime.now()
        ids.d_day.values = [str(i) for i in range(1, 32)]
        ids.d_mon.values = MONTHS
        ids.d_year.values = [str(now.year + i) for i in range(0, 3)]
        ids.t_hour.values = [str(i) for i in range(1, 13)]
        ids.t_min.values = [f"{m:02d}" for m in range(0, 60, 5)]
        ids.t_ampm.values = ["AM", "PM"]
        tom = now + timedelta(days=1)
        ids.d_day.text = str(tom.day)
        ids.d_mon.text = MONTHS[tom.month - 1]
        ids.d_year.text = str(tom.year)
        ids.t_hour.text = "10"
        ids.t_min.text = "00"
        ids.t_ampm.text = "AM"

    @staticmethod
    def clean_phone(text):
        digits = "".join(c for c in text if c.isdigit())
        return digits[-10:] if len(digits) > 10 else digits

    def lookup(self, text):
        """Auto-fill from the customer base when the contact number matches."""
        phone = self.clean_phone(text)
        row = App.get_running_app().db.customer(phone) if phone else None
        if row:
            self.ids.name.text = row["name"] or ""
            self.ids.house.text = row["house"] or ""
            self.ids.apartment.text = row["apartment"] or ""
            self.ids.status.text = "Existing customer - details filled in."
        else:
            self.ids.status.text = ""

    def save(self):
        ids = self.ids
        phone = self.clean_phone(ids.phone.text)
        if len(phone) != 10:
            ids.status.text = "Enter a valid 10-digit customer number."
            return
        for key, label in (("name", "customer name"), ("flavour", "cake flavour"),
                           ("weight", "cake weight")):
            if not ids[key].text.strip():
                ids.status.text = f"Please enter the {label}."
                return
        try:
            hour = int(ids.t_hour.text) % 12 + (12 if ids.t_ampm.text == "PM" else 0)
            when = datetime(int(ids.d_year.text),
                            MONTHS.index(ids.d_mon.text) + 1,
                            int(ids.d_day.text), hour, int(ids.t_min.text))
        except ValueError:
            ids.status.text = "That delivery date does not exist."
            return
        if when < datetime.now():
            ids.status.text = "Delivery date/time is in the past."
            return

        app = App.get_running_app()
        oid = app.db.add_order({
            "phone": phone,
            "name": ids.name.text.strip(),
            "house": ids.house.text.strip(),
            "apartment": ids.apartment.text.strip(),
            "flavour": ids.flavour.text.strip(),
            "weight": ids.weight.text.strip(),
            "delivery_date": when.strftime("%Y-%m-%d"),
            "delivery_time": when.strftime("%H:%M"),
            "message": ids.message.text.strip(),
            "custom": ids.custom.text.strip(),
        })
        schedule_for_order(app.db.order(oid))
        app.go_dash()


# ---------------------------------------------------------------------- KV
KV = """
#:import sp kivy.metrics.sp
#:import dp kivy.metrics.dp

<Label>:
    color: 0.25, 0.14, 0.08, 1

<Button>:
    background_normal: ''
    background_down: ''
    background_color: 0.80, 0.40, 0.18, 1
    color: 1, 1, 1, 1
    bold: True

<TextInput>:
    multiline: False
    size_hint_y: None
    height: dp(44)
    padding: dp(10), dp(12)
    font_size: sp(16)

<FieldLabel@Label>:
    size_hint_y: None
    height: dp(22)
    text_size: self.width, None
    halign: 'left'
    bold: True
    font_size: sp(13)

<OrderCard>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(12)
    spacing: dp(3)
    canvas.before:
        Color:
            rgba: self.bg
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    Label:
        text: root.head
        bold: True
        font_size: sp(17)
        size_hint_y: None
        text_size: self.width, None
        height: self.texture_size[1]
        halign: 'left'
    Label:
        text: root.badge
        bold: True
        font_size: sp(12)
        color: 0.65, 0.2, 0.1, 1
        size_hint_y: None
        text_size: self.width, None
        height: self.texture_size[1]
        halign: 'left'
    Label:
        text: root.body
        font_size: sp(15)
        size_hint_y: None
        text_size: self.width, None
        height: self.texture_size[1]
        halign: 'left'

<DashboardScreen>:
    name: 'dash'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(8)
        BoxLayout:
            size_hint_y: None
            height: dp(64)
            spacing: dp(10)
            Image:
                source: app.logo
                size_hint_x: None
                width: dp(56)
            Label:
                text: 'The Green Bakery'
                font_size: sp(24)
                bold: True
                halign: 'left'
                valign: 'middle'
                text_size: self.size
        Label:
            id: summary
            size_hint_y: None
            height: dp(24)
            bold: True
            halign: 'left'
            text_size: self.size
        ScrollView:
            GridLayout:
                id: box
                cols: 1
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            spacing: dp(8)
            Button:
                text: '+ New Order'
                on_release: app.open_new()
            Button:
                id: toggle
                text: 'Show all'
                on_release: root.toggle_all()

<NewOrderScreen>:
    name: 'new'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(6)
        Label:
            text: 'New Order'
            font_size: sp(22)
            bold: True
            size_hint_y: None
            height: dp(36)
        ScrollView:
            GridLayout:
                cols: 1
                spacing: dp(4)
                size_hint_y: None
                height: self.minimum_height
                FieldLabel:
                    text: 'Customer Number'
                TextInput:
                    id: phone
                    input_filter: 'int'
                    input_type: 'number'
                    hint_text: '10-digit mobile number'
                    on_text: root.lookup(self.text)
                Label:
                    id: status
                    size_hint_y: None
                    height: dp(20)
                    font_size: sp(12)
                    color: 0.1, 0.5, 0.2, 1
                    text_size: self.width, None
                    halign: 'left'
                FieldLabel:
                    text: 'Customer Name'
                TextInput:
                    id: name
                FieldLabel:
                    text: 'Villa / House Number'
                TextInput:
                    id: house
                FieldLabel:
                    text: 'Apartment'
                TextInput:
                    id: apartment
                FieldLabel:
                    text: 'Cake Flavour'
                TextInput:
                    id: flavour
                    hint_text: 'e.g. Chocolate truffle'
                FieldLabel:
                    text: 'Cake Weight'
                TextInput:
                    id: weight
                    hint_text: 'e.g. 1 kg'
                FieldLabel:
                    text: 'Delivery Date'
                BoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(6)
                    Spinner:
                        id: d_day
                    Spinner:
                        id: d_mon
                    Spinner:
                        id: d_year
                FieldLabel:
                    text: 'Delivery Time'
                BoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(6)
                    Spinner:
                        id: t_hour
                    Spinner:
                        id: t_min
                    Spinner:
                        id: t_ampm
                FieldLabel:
                    text: 'Message on Cake'
                TextInput:
                    id: message
                FieldLabel:
                    text: 'Additional Customization'
                TextInput:
                    id: custom
                    multiline: True
                    height: dp(90)
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            spacing: dp(8)
            Button:
                text: 'Cancel'
                background_color: 0.5, 0.5, 0.5, 1
                on_release: app.go_dash()
            Button:
                text: 'Save Order'
                on_release: root.save()
"""


# --------------------------------------------------------------------- app
class BakeryApp(App):
    logo = StringProperty("")

    def build(self):
        self.title = "Bakery Orders"
        self.logo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "logo.png")
        Window.clearcolor = (1, 0.97, 0.92, 1)
        Window.softinput_mode = "below_target"
        self.db = DB(os.path.join(self.user_data_dir, "bakery.db"))
        self.snoozed = set()
        self.prompt = None
        Builder.load_string(KV)
        self.sm = ScreenManager(transition=SlideTransition())
        self.sm.add_widget(DashboardScreen())
        self.sm.add_widget(NewOrderScreen(name="new"))
        Window.bind(on_keyboard=self.on_key)
        return self.sm

    # -- lifecycle
    def on_start(self):
        if platform == "android":
            try:
                from android.permissions import request_permissions
                request_permissions(["android.permission.POST_NOTIFICATIONS"])
            except Exception as exc:
                print("permission request failed:", exc)
        self.refresh()
        Clock.schedule_once(self.check_payments, 1.5)
        Clock.schedule_interval(self.check_payments, 300)

    def on_pause(self):
        return True

    def on_resume(self):
        self.refresh()
        Clock.schedule_once(self.check_payments, 0.5)

    # -- navigation
    def refresh(self):
        self.sm.get_screen("dash").refresh()

    def go_dash(self):
        self.sm.transition.direction = "right"
        self.sm.current = "dash"
        self.refresh()

    def open_new(self):
        self.sm.get_screen("new").reset()
        self.sm.transition.direction = "left"
        self.sm.current = "new"

    def on_key(self, _window, key, *_args):
        if key == 27 and self.sm.current != "dash":  # Android back button
            self.go_dash()
            return True
        return False

    # -- order details
    def show_detail(self, oid):
        r = self.db.order(oid)
        if not r:
            return
        body = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        lbl = Label(text=full_details(r), size_hint_y=None, halign="left",
                    valign="top")
        lbl.bind(width=lambda w, _v: setattr(w, "text_size", (w.width, None)),
                 texture_size=lambda w, ts: setattr(w, "height", ts[1]))
        sv = ScrollView()
        sv.add_widget(lbl)
        body.add_widget(sv)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        pop = Popup(title="Order details", content=body, size_hint=(0.94, 0.8))

        if not r["paid"]:
            b = Button(text="Mark Paid")
            b.bind(on_release=lambda *_: (self.mark_paid(oid), pop.dismiss()))
            row.add_widget(b)
        d = Button(text="Delete", background_color=(0.75, 0.2, 0.2, 1))

        def delete(btn):
            if btn.text == "Delete":
                btn.text = "Tap to confirm"
                return
            self.db.delete(oid)
            cancel_notification(oid)
            cancel_notification(oid + PAY_OFFSET)
            pop.dismiss()
            self.refresh()
        d.bind(on_release=delete)
        row.add_widget(d)
        c = Button(text="Close", background_color=(0.5, 0.5, 0.5, 1))
        c.bind(on_release=pop.dismiss)
        row.add_widget(c)
        body.add_widget(row)
        pop.open()

    def mark_paid(self, oid):
        self.db.set_paid(oid)
        cancel_notification(oid + PAY_OFFSET)
        self.refresh()

    # -- payment prompt (shows cake details for every unpaid delivered order)
    def check_payments(self, *_):
        if self.prompt is not None:
            return
        for r in self.db.unpaid_due():
            if r["id"] not in self.snoozed:
                self.ask_payment(r)
                return

    def ask_payment(self, r):
        oid = r["id"]
        body = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        lbl = Label(text=full_details(r) + "\n\nHas the payment been received?",
                    halign="left", valign="middle")
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        body.add_widget(lbl)
        row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        pop = Popup(title="Payment pending", content=body,
                    size_hint=(0.94, 0.75), auto_dismiss=False)
        self.prompt = pop

        def done(paid):
            if paid:
                self.mark_paid(oid)
            else:
                self.snoozed.add(oid)
            pop.dismiss()
            self.prompt = None
            self.refresh()
            Clock.schedule_once(self.check_payments, 0.4)

        yes = Button(text="Yes, paid")
        yes.bind(on_release=lambda *_: done(True))
        no = Button(text="Not yet", background_color=(0.5, 0.5, 0.5, 1))
        no.bind(on_release=lambda *_: done(False))
        row.add_widget(yes)
        row.add_widget(no)
        body.add_widget(row)
        pop.open()


if __name__ == "__main__":
    BakeryApp().run()
