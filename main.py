# -*- coding: utf-8 -*-
# ระบบเช่ารถแบบไฟล์ไบนารี fixed-length (Little-Endian) ใช้เฉพาะ Python Stdlib
# CRUD: Add/Update/Delete/View และสร้างรายงาน report.txt

import os, struct, time, unicodedata
from datetime import datetime
from textwrap import dedent

# ---------- พาธไฟล์ ----------
CARS_PATH = "cars.dat"
CUSTOMERS_PATH = "customers.dat"
RENT_A_CAR_PATH = "rentals.dat"
REPORT_PATH = "report.txt"

# ---------- โครงสร้างระเบียน (Little-Endian, fixed-length) ----------
# cars.dat:
#   i car_id | 12s plate | 12s brand | 16s model | i year | f rate |
#   i status(1=active,0=inactive) | i is_rented | i created_at | i updated_at
CAR_FMT = "<i12s12s16sifiiii"
CAR_SIZE = struct.calcsize(CAR_FMT)

# customers.dat:
#   i customer_id | 15s id_card | 60s name | 12s phone | i status | i created_at | i updated_at
CUST_FMT = "<i15s60s12siii"
CUST_SIZE = struct.calcsize(CUST_FMT)

# rentals.dat:
#   i rental_id | i car_id | i customer_id | i start_ts | i end_ts |
#   i total_days | f total_amount | i status(1=open,0=closed,-1=deleted) | i created_at | i updated_at
RENT_FMT = "<iiiiiifiii"  # 6*i + f + 3*i = 10 ฟิลด์
RENT_SIZE = struct.calcsize(RENT_FMT)


# ---------- Utils ----------
def _pad(s: str, length: int) -> bytes:
    """ตัด/เติม NUL ให้สายอักขระยาวคงที่"""
    b = (s or "").encode("utf-8")
    return (b[:length] + b"\x00" * max(0, length - len(b))) if len(b) != length else b


def _unpad(b: bytes) -> str:
    """ตัด NUL ด้านท้าย"""
    return b.rstrip(b"\x00").decode("utf-8", errors="ignore")


def now_ts() -> int:
    """UNIX timestamp (วินาที)"""
    return int(time.time())


def ts2dmy(ts: int) -> str:
    """แปลง timestamp -> DD/MM/YYYY (ถ้า 0 คืน '-')"""
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "-"


def create_file():
    """สร้างไฟล์เปล่าหากยังไม่มี"""
    for path in (CARS_PATH, CUSTOMERS_PATH, RENT_A_CAR_PATH):
        if not os.path.exists(path):
            open(path, "wb").close()


# --- ตัวช่วยรับอินพุตตัวเลข ---
def input_int(msg: str, allow_blank=False, min_val=None, max_val=None) -> int | None:
    """รับจำนวนเต็ม + ตรวจช่วงค่า"""
    while True:
        s = input(msg).strip()
        if allow_blank and s == "":
            return None
        if not (s and s.lstrip("-").isdigit()):
            print("กรุณาใส่จำนวนเต็ม")
            continue
        v = int(s)
        if min_val is not None and v < min_val:
            print(f"กรุณาใส่ค่าตั้งแต่ {min_val} ขึ้นไป")
            continue
        if max_val is not None and v > max_val:
            print(f"กรุณาใส่ค่าน้อยกว่าหรือเท่ากับ {max_val}")
            continue
        return v


def input_float(
    msg: str, allow_blank=False, min_val=None, max_val=None
) -> float | None:
    """รับจำนวนจริง + ตรวจช่วงค่า"""
    while True:
        s = input(msg).strip()
        if allow_blank and s == "":
            return None
        try:
            v = float(s)
        except ValueError:
            print("กรุณาใส่จำนวนจริง")
            continue
        if min_val is not None and v < min_val:
            print(f"กรุณาใส่ค่าตั้งแต่ {min_val} ขึ้นไป")
            continue
        if max_val is not None and v > max_val:
            print(f"กรุณาใส่ค่าน้อยกว่าหรือเท่ากับ {max_val}")
            continue
        return v


def read_date(prompt: str) -> tuple[int, int, int]:
    """รับวันที่รูปแบบเดียว 'YYYY MM DD' และ validate"""
    while True:
        s = input(prompt).strip()
        parts = s.split()
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            print("กรุณาใส่วันที่ในรูปแบบ 'YYYY MM DD' เช่น 2025 10 01")
            continue
        y, m, d = map(int, parts)
        try:
            datetime(y, m, d)
            return y, m, d
        except ValueError:
            print("วันที่ไม่ถูกต้อง กรุณาลองใหม่")


def days_between(start_ts: int, end_ts: int) -> int:
    """คืนจำนวนวัน (อย่างน้อย 1) ถ้า end >= start"""
    if end_ts < start_ts:
        return 0
    d = (end_ts - start_ts) // 86400
    return 1 if d == 0 else int(d)


# ---------- Thai-safe ASCII table ----------
def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", "" if s is None else str(s))


def _char_width(ch: str) -> int:
    return 0 if unicodedata.combining(ch) else 1


def display_width(s: str) -> int:
    return sum(_char_width(ch) for ch in _nfc(s))


def cut_to_width(s: str, width: int) -> str:
    """ตัดสตริงตามความกว้างแสดงผล เลี่ยงจบด้วยวรรณยุกต์/สระลอย"""
    s = _nfc(s)
    w = 0
    out = []
    for ch in s:
        cw = _char_width(ch)
        if w + cw > width:
            break
        out.append(ch)
        w += cw
    while out and unicodedata.combining(out[-1]):
        out.pop()
    return "".join(out)


def make_ascii_table(headers, rows, widths, aligns) -> list[str]:
    """วาดตาราง ASCII (+---+) รองรับอักษรไทย"""

    def fmt_cell(text, w, a):
        text = cut_to_width("" if text is None else str(text), w)
        pad = w - display_width(text)
        if a == "r":
            return " " * pad + text
        if a == "c":
            return " " * (pad // 2) + text + " " * (pad - pad // 2)
        return text + " " * pad

    def rule(ch="-"):
        return "+" + "+".join(ch * (w + 2) for w in widths) + "+"

    out = [rule("-")]
    out.append(
        "|"
        + "|".join(" " + fmt_cell(h, w, "c") + " " for h, w in zip(headers, widths))
        + "|"
    )
    out.append(rule("="))
    for r in rows:
        out.append(
            "|"
            + "|".join(
                " " + fmt_cell(c, w, a) + " " for c, w, a in zip(r, widths, aligns)
            )
            + "|"
        )
    out.append(rule("-"))
    return out


# ---------- Binary I/O ----------
def append_record(path: str, blob: bytes) -> None:
    with open(path, "ab") as f:
        f.write(blob)


def write_record(path: str, index: int, rec_size: int, blob: bytes) -> None:
    with open(path, "r+b") as f:
        f.seek(index * rec_size)
        f.write(blob)


def read_records(path: str, rec_size: int) -> list[bytes]:
    out = []
    with open(path, "rb") as f:
        while True:
            b = f.read(rec_size)
            if not b or len(b) < rec_size:
                break
            out.append(b)
    return out


# ---------- Pack / Unpack ----------
def pack_car(d: dict) -> bytes:
    return struct.pack(
        CAR_FMT,
        d["car_id"],
        _pad(d["plate"], 12),
        _pad(d["brand"], 12),
        _pad(d["model"], 16),
        d["year"],
        float(d["rate"]),
        d["status"],
        d["is_rented"],
        d["created_at"],
        d["updated_at"],
    )


def unpack_car(b: bytes) -> dict:
    i, plate, brand, model, year, rate, st, is_rented, c_at, u_at = struct.unpack(
        CAR_FMT, b
    )
    return dict(
        car_id=i,
        plate=_unpad(plate),
        brand=_unpad(brand),
        model=_unpad(model),
        year=year,
        rate=round(rate, 2),
        status=st,
        is_rented=is_rented,
        created_at=c_at,
        updated_at=u_at,
    )


def pack_customer(d: dict) -> bytes:
    return struct.pack(
        CUST_FMT,
        d["customer_id"],
        _pad(d["id_card"], 15),
        _pad(d["name"], 60),
        _pad(d["phone"], 12),
        d["status"],
        d["created_at"],
        d["updated_at"],
    )


def unpack_customer(b: bytes) -> dict:
    i, idc, name, phone, st, c_at, u_at = struct.unpack(CUST_FMT, b)
    return dict(
        customer_id=i,
        id_card=_unpad(idc),
        name=_unpad(name),
        phone=_unpad(phone),
        status=st,
        created_at=c_at,
        updated_at=u_at,
    )


def pack_rental(d: dict) -> bytes:
    return struct.pack(
        RENT_FMT,
        d["rental_id"],
        d["car_id"],
        d["customer_id"],
        d["start_ts"],
        d["end_ts"],
        d["total_days"],
        float(d["total_amount"]),
        d["status"],
        d["created_at"],
        d["updated_at"],
    )


def unpack_rental(b: bytes) -> dict:
    rid, car_id, customer_id, s, e, days, amt, st, c_at, u_at = struct.unpack(
        RENT_FMT, b
    )
    return dict(
        rental_id=rid,
        car_id=car_id,
        customer_id=customer_id,
        start_ts=s,
        end_ts=e,
        total_days=days,
        total_amount=round(amt, 2),
        status=st,
        created_at=c_at,
        updated_at=u_at,
    )


# ---------- Loaders ----------
def load_cars() -> list[dict]:
    return [unpack_car(b) for b in read_records(CARS_PATH, CAR_SIZE)]


def load_customers() -> list[dict]:
    return [unpack_customer(b) for b in read_records(CUSTOMERS_PATH, CUST_SIZE)]


def load_rentals() -> list[dict]:
    return [unpack_rental(b) for b in read_records(RENT_A_CAR_PATH, RENT_SIZE)]


# ---------- Cars ----------
def car_add():
    cars = load_cars()
    car_id = input_int("car_id: ", min_val=1)
    if any(c["car_id"] == car_id for c in cars):
        print("car_id นี้มีอยู่แล้ว")
        return
    plate = input("ทะเบียนรถ: ").strip()
    brand = input("Brand: ").strip()
    model = input("Model: ").strip()
    year = input_int("ปีรถ: ", min_val=1900, max_val=datetime.now().year)
    rate = input_float("ค่าเช่าต่อวัน: ", min_val=0)
    ts = now_ts()
    d = dict(
        car_id=car_id,
        plate=plate,
        brand=brand,
        model=model,
        year=year,
        rate=rate,
        status=1,
        is_rented=0,
        created_at=ts,
        updated_at=ts,
    )
    append_record(CARS_PATH, pack_car(d))
    print("เพิ่มรถใหม่เรียบร้อย")


def car_update():
    cars = load_cars()
    car_id = input_int("car_id ที่จะแก้ไข: ", min_val=1)
    idx = next((i for i, c in enumerate(cars) if c["car_id"] == car_id), -1)
    if idx < 0:
        print("ไม่พบ car_id นี้")
        return
    car = cars[idx]
    print("Enter เพื่อข้าม ไม่แก้ไข")
    rate = input_float("rate ใหม่ (เว้นว่าง=คงเดิม): ", allow_blank=True, min_val=0)
    year = input_int(
        "year ใหม่ (เว้นว่าง=คงเดิม): ", allow_blank=True, min_val=1900, max_val=2100
    )
    plate = input("plate ใหม่ (เว้นว่าง=คงเดิม): ").strip()
    brand = input("brand ใหม่ (เว้นว่าง=คงเดิม): ").strip()
    model = input("model ใหม่ (เว้นว่าง=คงเดิม): ").strip()
    status = input_int(
        "status ใหม่ (1=active,0=inactive) (เว้นว่าง=คงเดิม): ",
        allow_blank=True,
        min_val=0,
        max_val=1,
    )
    if rate is not None:
        car["rate"] = rate
    if year is not None:
        car["year"] = year
    if plate:
        car["plate"] = plate
    if brand:
        car["brand"] = brand
    if model:
        car["model"] = model
    if status is not None:
        car["status"] = status
    car["updated_at"] = now_ts()
    write_record(CARS_PATH, idx, CAR_SIZE, pack_car(car))
    print("แก้ไขรถเรียบร้อย")


def car_delete():
    cars = load_cars()
    car_id = input_int("car_id ที่จะลบ (mark inactive): ", min_val=1)
    idx = next((i for i, c in enumerate(cars) if c["car_id"] == car_id), -1)
    if idx < 0:
        print("  * ไม่พบ")
        return
    car = cars[idx]
    car["status"] = 0
    car["updated_at"] = now_ts()
    write_record(CARS_PATH, idx, CAR_SIZE, pack_car(car))
    print("  * ตั้งสถานะ Inactive แล้ว")


def car_view():
    sub = input(
        dedent(
            """
        เลือกดูรายการรถ:
          1) รายการเดียว (car_id)
          2) ทั้งหมด
          3) เฉพาะ Active
        เลือก: """
        )
    ).strip()
    cars = load_cars()
    if sub == "1":
        x = input_int("car_id: ", min_val=1)
        for c in cars:
            if c["car_id"] == x:
                print(c)
                break
        else:
            print("  * ไม่พบ")
    elif sub == "2":
        for c in cars:
            print(c)
        print(f"รวม {len(cars)}")
    elif sub == "3":
        act = [c for c in cars if c["status"] == 1]
        for c in act:
            print(c)
        print(f"Active {len(act)} / {len(cars)}")


# ---------- Customers ----------
def cust_add():
    customers = load_customers()
    customer_id = input_int("customer_id: ", min_val=1)
    if any(c["customer_id"] == customer_id for c in customers):
        print("customer_id นี้มีอยู่แล้ว")
        return
    id_card = input("เลขใบอนุญาตขับรถ/บัตร: ").strip()
    name = input("ชื่อ: ").strip()
    phone = input("เบอร์โทรศัพท์: ").strip()
    ts = now_ts()
    d = dict(
        customer_id=customer_id,
        id_card=id_card,
        name=name,
        phone=phone,
        status=1,
        created_at=ts,
        updated_at=ts,
    )
    append_record(CUSTOMERS_PATH, pack_customer(d))
    print("เพิ่มลูกค้าใหม่เรียบร้อย")


def cust_update():
    customers = load_customers()
    customer_id = input_int("customer_id ที่จะแก้ไข: ", min_val=1)
    idx = next(
        (i for i, c in enumerate(customers) if c["customer_id"] == customer_id), -1
    )
    if idx < 0:
        print("ไม่พบ customer_id นี้")
        return
    cust = customers[idx]
    print("Enter เพื่อข้าม ไม่แก้ไข")
    id_card = input("เลขใบอนุญาต/บัตร ใหม่ (เว้นว่าง=คงเดิม): ").strip()
    name = input("ชื่อ ใหม่ (เว้นว่าง=คงเดิม): ").strip()
    phone = input("เบอร์โทรศัพท์ ใหม่ (เว้นว่าง=คงเดิม): ").strip()
    status = input_int(
        "status ใหม่ (1=active,0=inactive) (เว้นว่าง=คงเดิม): ",
        allow_blank=True,
        min_val=0,
        max_val=1,
    )
    if id_card:
        cust["id_card"] = id_card
    if name:
        cust["name"] = name
    if phone:
        cust["phone"] = phone
    if status is not None:
        cust["status"] = status
    cust["updated_at"] = now_ts()
    write_record(CUSTOMERS_PATH, idx, CUST_SIZE, pack_customer(cust))
    print("แก้ไขลูกค้าเรียบร้อย")


def cust_delete():
    customers = load_customers()
    customer_id = input_int("customer_id ที่จะลบ (mark inactive): ", min_val=1)
    idx = next(
        (i for i, c in enumerate(customers) if c["customer_id"] == customer_id), -1
    )
    if idx < 0:
        print("  * ไม่พบ")
        return
    cust = customers[idx]
    cust["status"] = 0
    cust["updated_at"] = now_ts()
    write_record(CUSTOMERS_PATH, idx, CUST_SIZE, pack_customer(cust))
    print("  * ตั้งสถานะ Inactive แล้ว")


def cust_view():
    sub = input(
        dedent(
            """
        เลือกดูข้อมูลลูกค้า:
          1) รายการเดียว 
          2) ทั้งหมด
          3) เฉพาะ Active
        เลือก: """
        )
    ).strip()
    customers = load_customers()
    if sub == "1":
        x = input_int("customer_id: ", min_val=1)
        for c in customers:
            if c["customer_id"] == x:
                print(c)
                break
        else:
            print("  * ไม่พบ")
    elif sub == "2":
        for c in customers:
            print(c)
        print(f"รวม {len(customers)}")
    elif sub == "3":
        act = [c for c in customers if c["status"] == 1]
        for c in act:
            print(c)
        print(f"Active {len(act)} / {len(customers)}")


# ---------- Rentals ----------
def rental_add():
    cars = load_cars()
    customers = load_customers()
    rentals = load_rentals()

    rental_id = input_int("rental_id: ", min_val=1)
    if any(r["rental_id"] == rental_id for r in rentals):
        print("rental_id นี้มีอยู่แล้ว")
        return

    car_id = input_int("car_id ที่จะเช่า: ", min_val=1)
    car = next((c for c in cars if c["car_id"] == car_id and c["status"] == 1), None)
    if not car:
        print("ไม่พบ car_id นี้ หรือ รถไม่ Active")
        return
    if car["is_rented"]:
        print("รถคันนี้ถูกเช่าไปแล้ว")
        return

    customer_id = input_int("customer_id: ", min_val=1)
    cust = next(
        (c for c in customers if c["customer_id"] == customer_id and c["status"] == 1),
        None,
    )
    if not cust:
        print("ไม่พบ customer_id นี้ หรือ ลูกค้าไม่ Active")
        return

    print("วันที่เริ่มเช่า (YYYY MM DD):")
    y, m, d = read_date("  เริ่มเช่า: ")
    print("วันที่คืน (YYYY MM DD):")
    y2, m2, d2 = read_date("  คืน: ")

    start = int(datetime(y, m, d).timestamp())
    end = int(datetime(y2, m2, d2).timestamp())
    if end < start:
        print("วันที่คืน ต้องไม่ก่อนวันที่เริ่มเช่า")
        return

    dd = days_between(start, end) or 1
    total_amount = round(dd * float(car["rate"]), 2)
    ts = now_ts()
    rec = dict(
        rental_id=rental_id,
        car_id=car_id,
        customer_id=customer_id,
        start_ts=start,
        end_ts=end,
        total_days=dd,
        total_amount=total_amount,
        status=1,
        created_at=ts,
        updated_at=ts,  # เปิดงานเช่า
    )
    append_record(RENT_A_CAR_PATH, pack_rental(rec))

    # ตั้งรถเป็นถูกเช่า
    idx = next(i for i, c in enumerate(cars) if c["car_id"] == car_id)
    car["is_rented"] = 1
    car["updated_at"] = ts
    write_record(CARS_PATH, idx, CAR_SIZE, pack_car(car))
    print("เพิ่มการเช่าเรียบร้อย")
    print(f"จำนวนวันเช่า: {dd} วัน")
    print(f"รวมค่าเช่า: {total_amount:.2f} บาท")


def rental_update_close():
    cars = load_cars()
    rentals = load_rentals()
    rental_id = input_int("rental_id ที่จะปิด: ", min_val=1)
    idx = next((i for i, r in enumerate(rentals) if r["rental_id"] == rental_id), -1)
    if idx < 0:
        print("ไม่พบ rental_id นี้")
        return
    rent = rentals[idx]
    if rent["status"] == -1:
        print("การเช่านี้ถูกลบไปแล้ว")
        return
    rent["status"] = 0
    rent["updated_at"] = now_ts()
    write_record(RENT_A_CAR_PATH, idx, RENT_SIZE, pack_rental(rent))
    # คืนรถ
    car_idx = next((i for i, c in enumerate(cars) if c["car_id"] == rent["car_id"]), -1)
    if car_idx >= 0:
        car = cars[car_idx]
        car["is_rented"] = 0
        car["updated_at"] = rent["updated_at"]
        write_record(CARS_PATH, car_idx, CAR_SIZE, pack_car(car))
    print("ปิดงานเช่าเรียบร้อย")


def rental_delete():
    rentals = load_rentals()
    rental_id = input_int("rental_id ที่จะลบ : ", min_val=1)
    idx = next((i for i, r in enumerate(rentals) if r["rental_id"] == rental_id), -1)
    if idx < 0:
        print("  * ไม่พบ")
        return
    rent = rentals[idx]
    # ถ้าถูกลบขณะเปิดอยู่ ให้คืนรถด้วย
    if rent["status"] == 1:
        cars = load_cars()
        car_idx = next(
            (i for i, c in enumerate(cars) if c["car_id"] == rent["car_id"]), -1
        )
        if car_idx >= 0:
            car = cars[car_idx]
            car["is_rented"] = 0
            car["updated_at"] = now_ts()
            write_record(CARS_PATH, car_idx, CAR_SIZE, pack_car(car))
    rent["status"] = -1
    rent["updated_at"] = now_ts()
    write_record(RENT_A_CAR_PATH, idx, RENT_SIZE, pack_rental(rent))
    print("  * ตั้งสถานะ Deleted แล้ว")


def rental_view():
    sub = input(
        dedent(
            """
        เลือกดูข้อมูลการเช่า:
          1) รายการเดียว 
          2) ทั้งหมด
          3) เฉพาะเปิดอยู่ (status=1)
          4) เฉพาะปิดแล้ว (status=0)
        เลือก: """
        )
    ).strip()
    rentals = load_rentals()
    if sub == "1":
        x = input_int("rental_id: ", min_val=1)
        for r in rentals:
            if r["rental_id"] == x:
                print(r)
                break
        else:
            print("  * ไม่พบ")
    elif sub == "2":
        for r in rentals:
            print(r)
        print(f"รวม {len(rentals)}")
    elif sub == "3":
        opn = [r for r in rentals if r["status"] == 1]
        for r in opn:
            print(r)
        print(f"เปิดอยู่ {len(opn)} / {len(rentals)}")
    elif sub == "4":
        closed = [r for r in rentals if r["status"] == 0]
        for r in closed:
            print(r)
        print(f"ปิดแล้ว {len(closed)} / {len(rentals)}")


# ---------- Report ----------
def generate_report():
    """รายงานรวมจาก cars/customers/rentals (ไม่ใช้ cars.log)"""
    cars = load_cars()
    customers = load_customers()
    rentals = load_rentals()

    # ลูกค้าไว้ lookup
    cust_by_id = {c["customer_id"]: c for c in customers}

    # การเช่าล่าสุดที่ไม่ถูกลบ ต่อรถหนึ่งคัน
    latest_by_car: dict[int, dict] = {}
    for r in rentals:
        if r["status"] < 0:  # ข้าม deleted
            continue
        p = latest_by_car.get(r["car_id"])
        if (p is None) or (r["updated_at"] > p["updated_at"]):
            latest_by_car[r["car_id"]] = r

    headers = [
        "Car ID",
        "License Plate",
        "Brand",
        "Model",
        "Year",
        "Rate (THB/Day)",
        "Car Status",
        "Is_Rented",
        "Customer ID",
        "Customer name",
        "Tel",
        "ID Card",
        "Rental ID",
        "Date_Rent",
        "Return_Date",
        "Rental Day",
        "Total Price",
        "Rental Status",
    ]
    widths = [6, 13, 12, 12, 6, 14, 11, 9, 12, 26, 14, 16, 10, 11, 11, 11, 12, 14]
    aligns = [
        "r",
        "l",
        "l",
        "l",
        "r",
        "r",
        "c",
        "c",
        "r",
        "l",
        "l",
        "l",
        "r",
        "c",
        "c",
        "r",
        "r",
        "c",
    ]

    def car_status_txt(x):
        return "Active" if x == 1 else "Inactive"

    def rental_status_txt(x):
        return (
            "Open"
            if x == 1
            else ("Closed" if x == 0 else ("Deleted" if x == -1 else "-"))
        )

    rows = []
    for c in sorted(cars, key=lambda x: x["car_id"]):
        cust_id = "-"
        cust_name = tel = id_card = "-"
        rid = "-"
        sdate = edate = "-"
        ddays = 0
        total = 0.0
        rstat = "-"
        r = latest_by_car.get(c["car_id"])
        if r:
            rid = str(r["rental_id"])
            sdate = ts2dmy(r["start_ts"])
            edate = ts2dmy(r["end_ts"])
            ddays = r["total_days"]
            total = r["total_amount"]
            rstat = rental_status_txt(r["status"])
            cu = cust_by_id.get(r["customer_id"])
            if cu and cu["status"] == 1:
                cust_id = str(cu["customer_id"])
                cust_name = cu["name"] or "-"
                tel = cu["phone"] or "-"
                id_card = cu["id_card"] or "-"

        rows.append(
            [
                str(c["car_id"]),
                c["plate"],
                c["brand"],
                c["model"],
                str(c["year"]),
                f"{float(c['rate']):.2f}",
                car_status_txt(c["status"]),
                ("Yes" if c["is_rented"] else "No"),
                cust_id,
                cust_name,
                tel,
                id_card,
                rid,
                sdate,
                edate,
                str(ddays),
                f"{total:.0f}",
                rstat,
            ]
        )

    # ส่วนหัวรายงาน
    lines = [
        "Car Rent System — Summary Report",
        f"Generated At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "App Version  : 1.0",
        "Endianness   : Little-Endian",
        "Encoding     : UTF-8 (fixed-length)",
        "",
    ]
    # ตารางหลัก
    lines += make_ascii_table(headers, rows, widths, aligns) + [""]

    # สรุปท้ายรายงาน (เฉพาะรถ Active)
    active = [x for x in cars if x["status"] == 1]
    rates = [x["rate"] for x in active]
    lines += [
        "Summary (เฉพาะรถสถานะ Active)",
        f"- Total Cars (records) : {len(cars)}",
        f"- Active Cars          : {len(active)}",
        f"- Inactive/Deleted     : {len(cars)-len(active)}",
        f"- Currently Rented     : {sum(1 for x in cars if x['is_rented']==1)}",
        f"- Available Now        : {sum(1 for x in active if x['is_rented']==0)}",
        "",
    ]
    if rates:
        lines += [
            "Rate Statistics (THB/day, Active only)",
            f"- Min : {min(rates):.2f}",
            f"- Max : {max(rates):.2f}",
            f"- Avg : {sum(rates)/len(rates):.2f}",
            "",
        ]
    by_brand = {}
    for x in active:
        by_brand[x["brand"]] = by_brand.get(x["brand"], 0) + 1
    lines.append("Cars by Brand (Active only)")
    for b, n in sorted(by_brand.items()):
        lines.append(f"- {b} : {n}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"> สร้างรายงานแล้ว: {REPORT_PATH}")


# ---------- เมนู ----------
MAIN_MENU = dedent(
    """
    ===================== MENU =====================
    1) Add (เพิ่ม)
    2) Update (แก้ไข)
    3) Delete (ลบ)
    4) View (ดู)
    5) Generate Report (.txt)
    0) Exit (ออก)
    ================================================
"""
)


def pick_table() -> str | None:
    s = input("เลือกตาราง: 1=cars  2=customers  3=rentals  (ยกเลิก=Enter): ").strip()
    return {"1": "cars", "2": "customers", "3": "rentals"}.get(s)


def run_menu():
    create_file()
    while True:
        print(MAIN_MENU)
        choice = input("เลือกเมนู: ").strip()
        if choice == "1":
            t = pick_table()
            if t == "cars":
                car_add()
            elif t == "customers":
                cust_add()
            elif t == "rentals":
                rental_add()
        elif choice == "2":
            t = pick_table()
            if t == "cars":
                car_update()
            elif t == "customers":
                cust_update()
            elif t == "rentals":
                rental_update_close()
        elif choice == "3":
            t = pick_table()
            if t == "cars":
                car_delete()
            elif t == "customers":
                cust_delete()
            elif t == "rentals":
                rental_delete()
        elif choice == "4":
            t = pick_table()
            if t == "cars":
                car_view()
            elif t == "customers":
                cust_view()
            elif t == "rentals":
                rental_view()
        elif choice == "5":
            generate_report()
        elif choice == "0":
            generate_report()
            print("ออกโปรแกรมแล้ว (สร้างรายงานอัตโนมัติ)")
            break
        else:
            print("  * เมนูไม่ถูกต้อง")


# ---------- จุดเริ่มโปรแกรม ----------
if __name__ == "__main__":
    run_menu()
