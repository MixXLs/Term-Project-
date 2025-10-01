# car_rent_crud.py
# ------------------------------------------------------------
# Fixed-length binary CRUD with struct (customers, cars, rentals)
# Menus: Add / Update / Delete / View (+submenus) / Generate Report
# Standard Library only.
# ------------------------------------------------------------
import os, struct, sys, io
from datetime import datetime, date
from textwrap import dedent

# ===== Paths =====
CUST_PATH = "Customer.dat"
CAR_PATH  = "car.dat"
RENT_PATH = "Rentals.dat"
REPORT_PATH = "report.txt"
LOG_PATH = "activity.log"

# ===== Struct layouts (Little-Endian, fixed-length strings) =====
# Customer: i id | 15s id_card | 60s name | 12s tel
CUSTOMER_FMT   = "<i15s60s12s"
CUSTOMER_SIZE  = struct.calcsize(CUSTOMER_FMT)
CUSTOMER_FIELDS= ("customer_id","id_card","name","tel")

# Car: i id | 12s plate | 12s brand | 16s model | i year | i rate | i status | i is_rented
CAR_FMT   = "<i12s12s16siiii"
CAR_SIZE  = struct.calcsize(CAR_FMT)
CAR_FIELDS= ("car_id","plate","brand","model","year","rate","status","is_rented")

# Rental: i rental_id | i car_id | i customer_id | I start_ymd | I end_ymd | i total_days | i status | f total_amount
RENT_FMT   = "<iiiIIiif"
RENT_SIZE  = struct.calcsize(RENT_FMT)
RENT_FIELDS= ("rental_id","car_id","customer_id","start_ymd","end_ymd","total_days","status","total_amount")

# ===== Status conventions =====
CAR_ACTIVE, CAR_INACTIVE = 1, 0
RENT_OPEN, RENT_CLOSED, RENT_DELETED = 1, 0, -1

# ===== Utilities =====
def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{ts} {msg}\n")

def ensure_files():
    for p in (CUST_PATH, CAR_PATH, RENT_PATH):
        if not os.path.exists(p):
            open(p, "wb").close()

def fit_bytes(s: str, n: int) -> bytes:
    """UTF-8 encode then hard-trim/pad to n bytes (avoid broken multibyte)."""
    b = s.encode("utf-8", errors="ignore")
    if len(b) <= n:
        return b.ljust(n, b" ")
    # trim carefully
    view = b[:n]
    while True:
        try:
            view.decode("utf-8")
            break
        except UnicodeDecodeError:
            view = view[:-1]
    return view.ljust(n, b" ")

def b2s(b: bytes) -> str:
    return b.split(b"\x00",1)[0].decode("utf-8","ignore").rstrip()

def ymd(i: int) -> date:
    y = i // 10000; m = (i//100)%100; d = i%100
    return date(y,m,d)

def ask_int(prompt: str, minv=None, maxv=None) -> int:
    while True:
        try:
            v = int(input(prompt).strip())
            if minv is not None and v < minv: raise ValueError
            if maxv is not None and v > maxv: raise ValueError
            return v
        except ValueError:
            print("  ! ใส่จำนวนเต็มถูกช่วง")

def ask_str(prompt: str, max_bytes: int) -> str:
    s = input(prompt)
    # แค่เตือนเรื่องความยาวตาม byte จริง
    if len(s.encode("utf-8")) > max_bytes:
        print(f"  * จะถูกตัดให้พอดี {max_bytes} ไบต์ (UTF-8)")
    return s

def ask_ymd(prompt: str) -> int:
    while True:
        raw = input(prompt+" (YYYY-MM-DD): ").strip()
        try:
            y,m,d = map(int, raw.split("-"))
            date(y,m,d)  # validate
            return y*10000 + m*100 + d
        except Exception:
            print("  ! รูปแบบวันที่ไม่ถูกต้อง")

# ===== Low-level IO =====
def read_all(path: str, fmt: str, fields: tuple, rec_size: int) -> list[dict]:
    out = []
    with open(path, "rb") as f:
        while True:
            blob = f.read(rec_size)
            if not blob: break
            if len(blob) != rec_size: break
            vals = list(struct.unpack(fmt, blob))
            for i,v in enumerate(vals):
                if isinstance(v,(bytes,bytearray)):
                    vals[i] = b2s(v)
            out.append(dict(zip(fields, vals)))
    return out

def append_record(path: str, fmt: str, tup: tuple):
    with open(path,"ab") as f:
        f.write(struct.pack(fmt, *tup))

def write_record_by_index(path: str, fmt: str, tup: tuple, rec_size: int, index: int):
    with open(path,"r+b") as f:
        f.seek(index*rec_size)
        f.write(struct.pack(fmt, *tup))

# ===== Converters dict<->tuple with fixed fields =====
def pack_customer(d: dict) -> tuple:
    return (
        int(d["customer_id"]),
        fit_bytes(d["id_card"],15),
        fit_bytes(d["name"],60),
        fit_bytes(d["tel"],12),
    )

def pack_car(d: dict) -> tuple:
    return (
        int(d["car_id"]),
        fit_bytes(d["plate"],12),
        fit_bytes(d["brand"],12),
        fit_bytes(d["model"],16),
        int(d["year"]), int(d["rate"]), int(d["status"]), int(d["is_rented"])
    )

def pack_rent(d: dict) -> tuple:
    return (
        int(d["rental_id"]), int(d["car_id"]), int(d["customer_id"]),
        int(d["start_ymd"]), int(d["end_ymd"]),
        int(d["total_days"]), int(d["status"]), float(d["total_amount"])
    )

# ===== In-memory indexes =====
def index_by_key(rows: list[dict], key: str) -> dict:
    return {r[key]: (i,r) for i,r in enumerate(rows)}

# ===== Pretty print =====
def print_table(headers: list[str], rows: list[list[str]]):
    widths = [len(h) for h in headers]
    for r in rows:
        for i,c in enumerate(r):
            widths[i] = max(widths[i], len(str(c)))
    line = "-".join("-"*w for w in widths)
    print(" | ".join(h.ljust(widths[i]) for i,h in enumerate(headers)))
    print(line)
    for r in rows:
        print(" | ".join(str(c).ljust(widths[i]) for i,c in enumerate(r)))

# ===== CRUD helpers for each entity =====
def add_customer():
    customers = read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)
    idx = index_by_key(customers, "customer_id")
    cid = ask_int("Customer ID: ", 1)
    if cid in idx:
        print("  ! ซ้ำ"); return
    d = {
        "customer_id": cid,
        "id_card": ask_str("ID Card (15B): ", 15),
        "name": ask_str("Name (60B): ", 60),
        "tel": ask_str("Tel (12B): ", 12),
    }
    append_record(CUST_PATH, CUSTOMER_FMT, pack_customer(d))
    log(f"ADD customer {cid}")
    print("  ✓ บันทึกแล้ว")

def add_car():
    cars = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
    idx = index_by_key(cars, "car_id")
    cid = ask_int("Car ID: ", 1)
    if cid in idx:
        print("  ! ซ้ำ"); return
    d = {
        "car_id": cid,
        "plate": ask_str("License plate (12B): ",12),
        "brand": ask_str("Brand (12B): ",12),
        "model": ask_str("Model (16B): ",16),
        "year": ask_int("Year: ", 1900, 2100),
        "rate": ask_int("Rate (THB/Day): ", 0),
        "status": CAR_ACTIVE,
        "is_rented": 0
    }
    append_record(CAR_PATH, CAR_FMT, pack_car(d))
    log(f"ADD car {cid}")
    print("  ✓ บันทึกแล้ว")

def add_rental():
    cars = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
    customers = read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)
    rents = read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)

    car_idx = index_by_key(cars,"car_id")
    cust_idx= index_by_key(customers,"customer_id")
    rent_ids= set(r["rental_id"] for r in rents)

    rid = ask_int("Rental ID: ",1)
    if rid in rent_ids:
        print("  ! ซ้ำ"); return
    car_id = ask_int("Car ID: ",1)
    cust_id= ask_int("Customer ID: ",1)
    if car_id not in car_idx: print("  ! car_id ไม่พบ"); return
    if cust_id not in cust_idx: print("  ! customer_id ไม่พบ"); return

    start = ask_ymd("Start date")
    end   = ask_ymd("End date")
    sd, ed = ymd(start), ymd(end)
    if ed < sd:
        print("  ! end < start"); return
    days = (ed - sd).days + 1
    rate = car_idx[car_id][1]["rate"]
    total = float(days * rate)

    d = {
        "rental_id": rid, "car_id": car_id, "customer_id": cust_id,
        "start_ymd": start, "end_ymd": end,
        "total_days": days, "status": RENT_OPEN, "total_amount": total
    }
    append_record(RENT_PATH, RENT_FMT, pack_rent(d))
    log(f"ADD rental {rid}")
    print("  ✓ บันทึกแล้ว (Amount %.2f)" % total)

def update_entity(entity: str):
    if entity=="customer":
        rows = read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)
        idx = index_by_key(rows, "customer_id")
        if not rows: print("  (ว่าง)"); return
        k = ask_int("Customer ID ที่จะแก้: ",1)
        if k not in idx: print("  ! ไม่พบ"); return
        i, cur = idx[k]
        # แก้เฉพาะช่องที่พิมพ์ค่า (เว้นว่าง = คงเดิม)
        name = input(f"Name [{cur['name']}]: ").strip() or cur["name"]
        tel  = input(f"Tel  [{cur['tel']}]: ").strip() or cur["tel"]
        cur["name"], cur["tel"] = name, tel
        write_record_by_index(CUST_PATH, CUSTOMER_FMT, pack_customer(cur), CUSTOMER_SIZE, i)
        log(f"UPDATE customer {k}")
        print("  ✓ อัปเดตแล้ว")
    elif entity=="car":
        rows = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
        idx = index_by_key(rows, "car_id")
        if not rows: print("  (ว่าง)"); return
        k = ask_int("Car ID ที่จะแก้: ",1)
        if k not in idx: print("  ! ไม่พบ"); return
        i, cur = idx[k]
        brand = input(f"Brand [{cur['brand']}]: ").strip() or cur["brand"]
        model = input(f"Model [{cur['model']}]: ").strip() or cur["model"]
        year  = input(f"Year  [{cur['year']}]: ").strip()
        rate  = input(f"Rate  [{cur['rate']}]: ").strip()
        status= input(f"Status(1=Active,0=Inactive) [{cur['status']}]: ").strip()
        if year:  cur["year"]  = int(year)
        if rate:  cur["rate"]  = int(rate)
        if status!="": cur["status"] = int(status)
        cur["brand"], cur["model"] = brand, model
        write_record_by_index(CAR_PATH, CAR_FMT, pack_car(cur), CAR_SIZE, i)
        log(f"UPDATE car {k}")
        print("  ✓ อัปเดตแล้ว")
    elif entity=="rental":
        rows = read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)
        idx = index_by_key(rows, "rental_id")
        if not rows: print("  (ว่าง)"); return
        k = ask_int("Rental ID ที่จะแก้: ",1)
        if k not in idx: print("  ! ไม่พบ"); return
        i, cur = idx[k]
        status = input(f"Status(1=Open,0=Closed,-1=Deleted) [{cur['status']}]: ").strip()
        if status!="":
            cur["status"] = int(status)
        # ถ้าปิด ให้คำนวณ amount ใหม่ (เผื่อแก้วันที่)
        s_in = input(f"Start [{ymd(cur['start_ymd'])} YYYY-MM-DD or blank]: ").strip()
        e_in = input(f"End   [{ymd(cur['end_ymd'])} YYYY-MM-DD or blank]: ").strip()
        if s_in:
            y,m,d = map(int, s_in.split("-")); cur["start_ymd"] = y*10000+m*100+d
        if e_in:
            y,m,d = map(int, e_in.split("-")); cur["end_ymd"] = y*10000+m*100+d
        sd, ed = ymd(cur["start_ymd"]), ymd(cur["end_ymd"])
        cur["total_days"] = (ed-sd).days + 1
        # lookup rate
        cars = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
        car_idx = index_by_key(cars, "car_id")
        rate = car_idx.get(cur["car_id"],(None,{"rate":0}))[1]["rate"]
        cur["total_amount"] = float(cur["total_days"] * rate)
        write_record_by_index(RENT_PATH, RENT_FMT, pack_rent(cur), RENT_SIZE, i)
        log(f"UPDATE rental {k}")
        print("  ✓ อัปเดตแล้ว")

def delete_entity(entity: str):
    # ใช้แนวคิด "soft delete" เฉพาะ rentals (status=-1); customer/car ไม่ลบทิ้งจริงเพื่อความง่าย
    if entity=="rental":
        rows = read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)
        idx = index_by_key(rows, "rental_id")
        if not rows: print("  (ว่าง)"); return
        k = ask_int("Rental ID ที่จะลบ: ",1)
        if k not in idx: print("  ! ไม่พบ"); return
        i, cur = idx[k]
        cur["status"] = RENT_DELETED
        write_record_by_index(RENT_PATH, RENT_FMT, pack_rent(cur), RENT_SIZE, i)
        log(f"DELETE rental {k}")
        print("  ✓ ทำเครื่องหมายลบแล้ว (-1)")
    else:
        print("  ! ตัวอย่างนี้รองรับลบจริงเฉพาะ Rentals (ป้องกัน orphan keys)")

def view_menu():
    print(dedent("""
      ---- View Submenu ----
      1) ดูรายการเดียว
      2) ดูทั้งหมด
      3) ดูแบบกรอง
      4) สถิติโดยสรุป
      0) กลับ
    """))
    return ask_int("เลือก: ",0,4)

def view_one():
    ent = ask_int("เลือกชนิด 1=Customer 2=Car 3=Rental: ",1,3)
    if ent==1:
        rows = read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)
        idx = index_by_key(rows,"customer_id")
        k = ask_int("Customer ID: ",1)
        r = idx.get(k)
        if not r: print("  ! ไม่พบ"); return
        _, row = r
        print(row)
    elif ent==2:
        rows = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
        idx = index_by_key(rows,"car_id")
        k = ask_int("Car ID: ",1)
        r = idx.get(k)
        if not r: print("  ! ไม่พบ"); return
        print(r[1])
    else:
        rows = read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)
        idx = index_by_key(rows,"rental_id")
        k = ask_int("Rental ID: ",1)
        r = idx.get(k)
        if not r: print("  ! ไม่พบ"); return
        row = r[1].copy()
        row["start"], row["end"] = ymd(row["start_ymd"]), ymd(row["end_ymd"])
        print(row)

def view_all():
    ent = ask_int("เลือกชนิด 1=Customer 2=Car 3=Rental: ",1,3)
    if ent==1:
        rows = read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)
        headers = ["ID","ID Card","Name","Tel"]
        data = [[r["customer_id"], r["id_card"], r["name"], r["tel"]] for r in rows]
    elif ent==2:
        rows = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
        headers = ["ID","Plate","Brand","Model","Year","Rate","Status","Rented"]
        data = [[r["car_id"],r["plate"],r["brand"],r["model"],r["year"],r["rate"],r["status"],r["is_rented"]] for r in rows]
    else:
        rows = read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)
        headers = ["RID","Car","Cust","Start","End","Days","Status","Amount"]
        data = [[r["rental_id"], r["car_id"], r["customer_id"], ymd(r["start_ymd"]), ymd(r["end_ymd"]), r["total_days"], r["status"], int(r["total_amount"])] for r in rows]
    if not rows: print("  (ว่าง)"); return
    print_table(headers, data)

def view_filtered():
    print("กรอง Rentals: 1=Open 2=Closed 3=Deleted 4=By Car 5=By Customer")
    choice = ask_int("เลือก: ",1,5)
    rows = read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)
    if choice==1: rows = [r for r in rows if r["status"]==RENT_OPEN]
    elif choice==2: rows = [r for r in rows if r["status"]==RENT_CLOSED]
    elif choice==3: rows = [r for r in rows if r["status"]==RENT_DELETED]
    elif choice==4:
        cid = ask_int("Car ID: ",1); rows = [r for r in rows if r["car_id"]==cid]
    else:
        uid = ask_int("Customer ID: ",1); rows = [r for r in rows if r["customer_id"]==uid]
    if not rows: print("  (ไม่พบ)"); return
    headers = ["RID","Car","Cust","Start","End","Days","Status","Amount"]
    data = [[r["rental_id"], r["car_id"], r["customer_id"], ymd(r["start_ymd"]), ymd(r["end_ymd"]), r["total_days"], r["status"], int(r["total_amount"])] for r in rows]
    print_table(headers, data)

def view_stats():
    # สรุปจำนวนระเบียน Active/Deleted/ฯลฯ + activity ล่าสุด
    cars = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
    rents= read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)
    custs= read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)

    car_active = sum(1 for c in cars if c["status"]==CAR_ACTIVE)
    car_inact  = sum(1 for c in cars if c["status"]==CAR_INACTIVE)
    rent_open  = sum(1 for r in rents if r["status"]==RENT_OPEN)
    rent_close = sum(1 for r in rents if r["status"]==RENT_CLOSED)
    rent_del   = sum(1 for r in rents if r["status"]==RENT_DELETED)

    print("\n--- Summary Stats ---")
    print(f"Customers : {len(custs)}")
    print(f"Cars      : {len(cars)} (Active {car_active}, Inactive {car_inact})")
    print(f"Rentals   : {len(rents)} (Open {rent_open}, Closed {rent_close}, Deleted {rent_del})")

    print("\nRecent Activities:")
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH,"r",encoding="utf-8") as f:
            lines = f.readlines()[-10:]
        for ln in lines: print("  -", ln.rstrip())
    else:
        print("  (no activity)")

def generate_report():
    # ตารางตามตัวอย่าง + ส่วนหัว + summary
    customers = read_all(CUST_PATH, CUSTOMER_FMT, CUSTOMER_FIELDS, CUSTOMER_SIZE)
    cars = read_all(CAR_PATH, CAR_FMT, CAR_FIELDS, CAR_SIZE)
    rents= read_all(RENT_PATH, RENT_FMT, RENT_FIELDS, RENT_SIZE)

    cust_by = {c["customer_id"]: c for c in customers}
    car_by  = {c["car_id"]: c for c in cars}

    headers = ["Rental_ID","Customer name","Tel.","License_plate","Brand","Model","Rate","Date Rent","Return date","Rental Day","Total Price"]
    table = []
    for r in sorted(rents, key=lambda x:x["rental_id"]):
        if r["status"]==RENT_DELETED: continue
        cu = cust_by.get(r["customer_id"],{})
        ca = car_by.get(r["car_id"],{})
        sd, ed = ymd(r["start_ymd"]), ymd(r["end_ymd"])
        table.append([
            r["rental_id"],
            cu.get("name",""),
            cu.get("tel",""),
            ca.get("plate",""),
            ca.get("brand",""),
            ca.get("model",""),
            f"{ca.get('rate',0):,}",
            sd.strftime("%-m/%-d/%Y") if sys.platform!="win32" else sd.strftime("%m/%d/%Y"),
            ed.strftime("%-m/%-d/%Y") if sys.platform!="win32" else ed.strftime("%m/%d/%Y"),
            r["total_days"],
            f"{int(r['total_amount']):,}"
        ])

    # widths
    widths = [len(h) for h in headers]
    for row in table:
        for i,c in enumerate(row):
            widths[i] = max(widths[i], len(str(c)))
    def fmt_row(cols): return " | ".join(str(c).ljust(widths[i]) for i,c in enumerate(cols))

    # rate stats (active cars only)
    act_rates = [c["rate"] for c in cars if c["status"]==CAR_ACTIVE]
    minr = min(act_rates) if act_rates else 0
    maxr = max(act_rates) if act_rates else 0
    avgr = int(sum(act_rates)/len(act_rates)) if act_rates else 0

    # brand count
    from collections import Counter
    brand_cnt = Counter(c["brand"] for c in cars)

    buf = io.StringIO()
    buf.write("Car Rent System - Summary Report\n")
    buf.write(f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    buf.write("App Version: 1.0\nEndianness: Little-Endian\nEncoding: UTF-8 (fixed-length)\n\n")
    buf.write(fmt_row(headers)+"\n")
    buf.write("-"*(sum(widths)+3*(len(widths)-1))+"\n")
    for row in table: buf.write(fmt_row(row)+"\n")

    # counters
    rent_open  = sum(1 for r in rents if r["status"]==RENT_OPEN)
    rent_close = sum(1 for r in rents if r["status"]==RENT_CLOSED)
    rent_del   = sum(1 for r in rents if r["status"]==RENT_DELETED)

    buf.write("\n--- Summary ---\n\n")
    buf.write(f"Customers : {len(customers)}\n")
    buf.write(f"Cars      : {len(cars)} (Active {sum(1 for c in cars if c['status']==CAR_ACTIVE)}, Inactive {sum(1 for c in cars if c['status']==CAR_INACTIVE)})\n")
    buf.write(f"Rentals   : {len(rents)} (Open {rent_open}, Closed {rent_close}, Deleted {rent_del})\n\n")

    buf.write("Rate Statistics (Active cars only)\n")
    buf.write(f"- Min Rate : {minr:,}\n- Max Rate : {maxr:,}\n- Avg Rate : {avgr:,}\n\n")

    buf.write("Cars by Brand\n")
    for b,n in sorted(brand_cnt.items()):
        buf.write(f"- {b} : {n}\n")

    # last activities
    buf.write("\nRecent Activities\n")
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH,"r",encoding="utf-8") as f:
            for ln in f.readlines()[-10:]:
                buf.write(f"- {ln}")
    else:
        buf.write("- (no activity)\n")

    with open(REPORT_PATH,"w",encoding="utf-8") as f:
        f.write(buf.getvalue())
    print(f"✓ สร้างรายงานแล้ว -> {REPORT_PATH}")
    log("GENERATE report")

# ===== Main menus =====
def main_menu():
    print(dedent("""
      ===== Car Rent (Fixed-Length Binary) =====
      1) Add (เพิ่ม)
      2) Update (แก้ไข)
      3) Delete (ลบ)
      4) View (ดู)
      5) Generate Report (.txt)
      0) Exit
    """))

def entity_select() -> int:
    return ask_int("เลือกชนิด 1=Customer 2=Car 3=Rental: ",1,3)

def main():
    ensure_files()
    while True:
        main_menu()
        choice = ask_int("เลือก: ",0,5)
        if choice==0:
            print("กำลังปิดโปรแกรมอย่างปลอดภัย ...")
            # อาจสร้างรายงานอัตโนมัติ
            generate_report()
            print("บาย!"); break
        elif choice==1:   # Add
            ent = entity_select()
            (add_customer if ent==1 else add_car if ent==2 else add_rental)()
        elif choice==2:   # Update
            ent = entity_select()
            update_entity("customer" if ent==1 else "car" if ent==2 else "rental")
        elif choice==3:   # Delete
            ent = entity_select()
            delete_entity("customer" if ent==1 else "car" if ent==2 else "rental")
        elif choice==4:   # View with submenus
            while True:
                sub = view_menu()
                if sub==0: break
                if sub==1: view_one()
                elif sub==2: view_all()
                elif sub==3: view_filtered()
                else: view_stats()
        else:             # Report
            generate_report()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n^C"); sys.exit(0)
