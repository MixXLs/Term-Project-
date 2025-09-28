#!/usr/bin/env python3
"""
Car Rental Management System
ระบบจัดการรถเช่า - Binary File Storage with Python struct

Author: Car Rental System
Version: 1.0
Python: 3.10+
Endianness: Little-Endian ('<')

Binary Files:
- cars.dat: Main car records (fixed-length)
- operations.dat: Operation logs 
- sequence.dat: ID sequence tracking
- report.txt: Text report output

CRUD Operations:
1. Add (เพิ่ม)
2. Update (แก้ไข) 
3. Delete (ลบ)
4. View (ดู)
5. Generate Report (สร้างรายงาน)
0. Exit (ออก)
"""

import struct
import os
import io
import datetime
import textwrap
import argparse
from typing import Optional, List, Dict, Any

# ========== CONFIGURATION ==========
# Fixed-length record sizes (bytes)
CAR_RECORD_SIZE = 72  # Total size per car record
OPERATION_RECORD_SIZE = 32  # Total size per operation record
SEQUENCE_RECORD_SIZE = 4   # ID sequence (integer)

# Struct format strings (Little-Endian)
CAR_STRUCT_FORMAT = '<I12s12s16sIfIBBII'  # Car record format
OPERATION_STRUCT_FORMAT = '<IIcI20s'       # Operation log format
SEQUENCE_STRUCT_FORMAT = '<I'              # Sequence format

# File names
CARS_FILE = 'cars.dat'
OPERATIONS_FILE = 'operations.dat' 
SEQUENCE_FILE = 'sequence.dat'
REPORT_FILE = 'report.txt'

# Status constants
STATUS_ACTIVE = 1
STATUS_DELETED = 0

class CarRecord:
    """
    Car record structure (Fixed-length: 72 bytes)
    
    Fields:
    - car_id: I (4 bytes) - รหัสรถ
    - license_plate: 12s (12 bytes) - ทะเบียนรถ
    - brand: 12s (12 bytes) - ยี่ห้อ
    - model: 16s (16 bytes) - รุ่น
    - year: I (4 bytes) - ปี
    - daily_rate: f (4 bytes) - ค่าเช่า/วัน
    - odometer: I (4 bytes) - เลขไมล์
    - status: B (1 byte) - สถานะ (1=Active, 0=Deleted)
    - is_rented: B (1 byte) - เช่าอยู่ (1=Yes, 0=No)
    - created_at: I (4 bytes) - วันที่สร้าง (timestamp)
    - updated_at: I (4 bytes) - วันที่แก้ไข (timestamp)
    """
    
    def __init__(self, car_id: int = 0, license_plate: str = "", brand: str = "", 
                 model: str = "", year: int = 0, daily_rate: float = 0.0, 
                 odometer: int = 0, status: int = STATUS_ACTIVE, 
                 is_rented: int = 0, created_at: int = 0, updated_at: int = 0):
        self.car_id = car_id
        self.license_plate = license_plate[:12]  # Truncate to fit
        self.brand = brand[:12]
        self.model = model[:16]
        self.year = year
        self.daily_rate = daily_rate
        self.odometer = odometer
        self.status = status
        self.is_rented = is_rented
        self.created_at = created_at or int(datetime.datetime.now().timestamp())
        self.updated_at = updated_at or int(datetime.datetime.now().timestamp())
    
    def pack(self) -> bytes:
        """Pack car record to binary format"""
        return struct.pack(
            CAR_STRUCT_FORMAT,
            self.car_id,
            self.license_plate.encode('utf-8')[:12].ljust(12, b'\x00'),
            self.brand.encode('utf-8')[:12].ljust(12, b'\x00'),
            self.model.encode('utf-8')[:16].ljust(16, b'\x00'),
            self.year,
            self.daily_rate,
            self.odometer,
            self.status,
            self.is_rented,
            self.created_at,
            self.updated_at
        )
    
    @classmethod
    def unpack(cls, data: bytes) -> 'CarRecord':
        """Unpack binary data to car record"""
        unpacked = struct.unpack(CAR_STRUCT_FORMAT, data)
        return cls(
            car_id=unpacked[0],
            license_plate=unpacked[1].rstrip(b'\x00').decode('utf-8', errors='ignore'),
            brand=unpacked[2].rstrip(b'\x00').decode('utf-8', errors='ignore'),
            model=unpacked[3].rstrip(b'\x00').decode('utf-8', errors='ignore'),
            year=unpacked[4],
            daily_rate=unpacked[5],
            odometer=unpacked[6],
            status=unpacked[7],
            is_rented=unpacked[8],
            created_at=unpacked[9],
            updated_at=unpacked[10]
        )
    
    def __str__(self) -> str:
        status_text = "Active" if self.status == STATUS_ACTIVE else "Deleted"
        rented_text = "เช่าอยู่" if self.is_rented else "ว่าง"
        created_date = datetime.datetime.fromtimestamp(self.created_at).strftime('%Y-%m-%d %H:%M')
        updated_date = datetime.datetime.fromtimestamp(self.updated_at).strftime('%Y-%m-%d %H:%M')
        
        return f"""
Car ID: {self.car_id}
ทะเบียนรถ: {self.license_plate}
ยี่ห้อ: {self.brand}
รุ่น: {self.model}
ปี: {self.year}
ค่าเช่า/วัน: ฿{self.daily_rate:,.2f}
เลขไมล์: {self.odometer:,} กม.
สถานะ: {status_text}
การเช่า: {rented_text}
สร้างเมื่อ: {created_date}
แก้ไขล่าสุด: {updated_date}
"""

class OperationRecord:
    """
    Operation log record structure (Fixed-length: 32 bytes)
    
    Fields:
    - operation_id: I (4 bytes) - รหัสการทำงาน
    - car_id: I (4 bytes) - รหัสรถที่เกี่ยวข้อง
    - operation_type: c (1 byte) - ประเภทการทำงาน (A=Add, U=Update, D=Delete, V=View)
    - timestamp: I (4 bytes) - เวลาดำเนินการ
    - details: 20s (20 bytes) - รายละเอียดเพิ่มเติม
    """
    
    def __init__(self, operation_id: int, car_id: int, operation_type: str, 
                 timestamp: int = 0, details: str = ""):
        self.operation_id = operation_id
        self.car_id = car_id
        self.operation_type = operation_type
        self.timestamp = timestamp or int(datetime.datetime.now().timestamp())
        self.details = details[:20]  # Truncate to fit
    
    def pack(self) -> bytes:
        """Pack operation record to binary format"""
        return struct.pack(
            OPERATION_STRUCT_FORMAT,
            self.operation_id,
            self.car_id,
            self.operation_type.encode('ascii')[:1],
            self.timestamp,
            self.details.encode('utf-8')[:20].ljust(20, b'\x00')
        )
    
    @classmethod
    def unpack(cls, data: bytes) -> 'OperationRecord':
        """Unpack binary data to operation record"""
        unpacked = struct.unpack(OPERATION_STRUCT_FORMAT, data)
        return cls(
            operation_id=unpacked[0],
            car_id=unpacked[1],
            operation_type=unpacked[2].decode('ascii'),
            timestamp=unpacked[3],
            details=unpacked[4].rstrip(b'\x00').decode('utf-8', errors='ignore')
        )

class CarRentalSystem:
    """Main Car Rental Management System Class"""
    
    def __init__(self):
        self.initialize_files()
    
    def initialize_files(self):
        """Initialize binary files if they don't exist"""
        # Initialize sequence file
        if not os.path.exists(SEQUENCE_FILE):
            with open(SEQUENCE_FILE, 'wb') as f:
                f.write(struct.pack(SEQUENCE_STRUCT_FORMAT, 1000))  # Start from 1001
        
        # Initialize empty files if they don't exist
        for filename in [CARS_FILE, OPERATIONS_FILE]:
            if not os.path.exists(filename):
                with open(filename, 'wb') as f:
                    pass  # Create empty file
        
        # Add sample data if cars.dat is empty
        if os.path.getsize(CARS_FILE) == 0:
            self._add_sample_data()
    
    def _add_sample_data(self):
        """Add sample car data"""
        sample_cars = [
            CarRecord(
                car_id=1001,
                license_plate="กธ 4821",
                brand="Toyota",
                model="Camry",
                year=2025,
                daily_rate=1100.00,
                odometer=42850,
                status=STATUS_ACTIVE,
                is_rented=0
            ),
            CarRecord(
                car_id=1002,
                license_plate="งธ 9127", 
                brand="Honda",
                model="Accord",
                year=2005,
                daily_rate=1250.00,
                odometer=156000,
                status=STATUS_ACTIVE,
                is_rented=1
            )
        ]
        
        for car in sample_cars:
            self._write_car_record(car)
            self._log_operation(car.car_id, 'A', 'Sample data')
        
        # Update sequence
        with open(SEQUENCE_FILE, 'wb') as f:
            f.write(struct.pack(SEQUENCE_STRUCT_FORMAT, 1002))
    
    def _get_next_car_id(self) -> int:
        """Get next available car ID"""
        with open(SEQUENCE_FILE, 'rb') as f:
            data = f.read(SEQUENCE_RECORD_SIZE)
            if data:
                current_id = struct.unpack(SEQUENCE_STRUCT_FORMAT, data)[0]
            else:
                current_id = 1000
        
        next_id = current_id + 1
        
        # Update sequence file
        with open(SEQUENCE_FILE, 'wb') as f:
            f.write(struct.pack(SEQUENCE_STRUCT_FORMAT, next_id))
        
        return next_id
    
    def _write_car_record(self, car: CarRecord):
        """Write car record to binary file"""
        with open(CARS_FILE, 'ab') as f:
            f.write(car.pack())
    
    def _update_car_record(self, car_id: int, car: CarRecord) -> bool:
        """Update existing car record in binary file"""
        records = self._read_all_cars()
        updated = False
        
        with open(CARS_FILE, 'wb') as f:
            for existing_car in records:
                if existing_car.car_id == car_id:
                    car.car_id = car_id  # Ensure ID stays the same
                    car.updated_at = int(datetime.datetime.now().timestamp())
                    f.write(car.pack())
                    updated = True
                else:
                    f.write(existing_car.pack())
        
        return updated
    
    def _read_all_cars(self) -> List[CarRecord]:
        """Read all car records from binary file"""
        cars = []
        if not os.path.exists(CARS_FILE):
            return cars
        
        with open(CARS_FILE, 'rb') as f:
            while True:
                data = f.read(CAR_RECORD_SIZE)
                if not data or len(data) < CAR_RECORD_SIZE:
                    break
                cars.append(CarRecord.unpack(data))
        
        return cars
    
    def _find_car_by_id(self, car_id: int) -> Optional[CarRecord]:
        """Find car by ID"""
        cars = self._read_all_cars()
        for car in cars:
            if car.car_id == car_id:
                return car
        return None
    
    def _log_operation(self, car_id: int, operation_type: str, details: str = ""):
        """Log operation to binary file"""
        # Get next operation ID
        operation_id = 1
        if os.path.exists(OPERATIONS_FILE):
            with open(OPERATIONS_FILE, 'rb') as f:
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                if file_size > 0:
                    operation_id = (file_size // OPERATION_RECORD_SIZE) + 1
        
        operation = OperationRecord(operation_id, car_id, operation_type, details=details)
        
        with open(OPERATIONS_FILE, 'ab') as f:
            f.write(operation.pack())
    
    def _read_operations(self, limit: int = 10) -> List[OperationRecord]:
        """Read recent operations from binary file"""
        operations = []
        if not os.path.exists(OPERATIONS_FILE):
            return operations
        
        with open(OPERATIONS_FILE, 'rb') as f:
            # Read from end of file
            f.seek(0, 2)
            file_size = f.tell()
            
            # Calculate how many records to read
            total_records = file_size // OPERATION_RECORD_SIZE
            start_record = max(0, total_records - limit)
            
            f.seek(start_record * OPERATION_RECORD_SIZE)
            
            while True:
                data = f.read(OPERATION_RECORD_SIZE)
                if not data or len(data) < OPERATION_RECORD_SIZE:
                    break
                operations.append(OperationRecord.unpack(data))
        
        return list(reversed(operations))  # Most recent first
    
    def add_car(self):
        """Add new car (CRUD: Create)"""
        print("\n" + "="*50)
        print("เพิ่มรถใหม่ (Add New Car)")
        print("="*50)
        
        try:
            # Input validation
            license_plate = input("ทะเบียนรถ (License Plate): ").strip()
            if not license_plate or len(license_plate) > 12:
                print("❌ ทะเบียนรถไม่ถูกต้อง (ต้องไม่เกิน 12 ตัวอักษร)")
                return
            
            # Check duplicate license plate
            cars = self._read_all_cars()
            for car in cars:
                if car.license_plate == license_plate and car.status == STATUS_ACTIVE:
                    print("❌ ทะเบียนรถนี้มีอยู่แล้ว")
                    return
            
            brand = input("ยี่ห้อ (Brand): ").strip()
            if not brand or len(brand) > 12:
                print("❌ ยี่ห้อไม่ถูกต้อง (ต้องไม่เกิน 12 ตัวอักษร)")
                return
            
            model = input("รุ่น (Model): ").strip()
            if not model or len(model) > 16:
                print("❌ รุ่นไม่ถูกต้อง (ต้องไม่เกิน 16 ตัวอักษร)")
                return
            
            year = int(input("ปี (Year): "))
            if year < 1900 or year > datetime.datetime.now().year + 2:
                print("❌ ปีไม่ถูกต้อง")
                return
            
            daily_rate = float(input("ค่าเช่า/วัน (Daily Rate): "))
            if daily_rate <= 0 or daily_rate > 99999.99:
                print("❌ ค่าเช่าไม่ถูกต้อง")
                return
            
            odometer = int(input("เลขไมล์ (Odometer): "))
            if odometer < 0 or odometer > 9999999:
                print("❌ เลขไมล์ไม่ถูกต้อง")
                return
            
            is_rented_input = input("เช่าอยู่หรือไม่? (y/n): ").strip().lower()
            is_rented = 1 if is_rented_input == 'y' else 0
            
            # Create new car record
            car_id = self._get_next_car_id()
            car = CarRecord(
                car_id=car_id,
                license_plate=license_plate,
                brand=brand,
                model=model,
                year=year,
                daily_rate=daily_rate,
                odometer=odometer,
                status=STATUS_ACTIVE,
                is_rented=is_rented
            )
            
            # Save to binary file
            self._write_car_record(car)
            self._log_operation(car_id, 'A', f'Added {brand} {model}')
            
            print(f"\n✅ เพิ่มรถสำเร็จ! Car ID: {car_id}")
            print(car)
            
        except ValueError:
            print("❌ ข้อมูลไม่ถูกต้อง กรุณาใส่ตัวเลข")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
    
    def update_car(self):
        """Update existing car (CRUD: Update)"""
        print("\n" + "="*50)
        print("แก้ไขข้อมูลรถ (Update Car)")
        print("="*50)
        
        try:
            car_id = int(input("รหัสรถที่ต้องการแก้ไข (Car ID): "))
            car = self._find_car_by_id(car_id)
            
            if not car:
                print("❌ ไม่พบรถที่มี ID นี้")
                return
            
            if car.status == STATUS_DELETED:
                print("❌ ไม่สามารถแก้ไขรถที่ถูกลบแล้ว")
                return
            
            print("\nข้อมูลปัจจุบัน:")
            print(car)
            
            print("\nกรอกข้อมูลใหม่ (Enter เพื่อข้ามการแก้ไข):")
            
            # Update fields
            license_plate = input(f"ทะเบียนรถ [{car.license_plate}]: ").strip()
            if license_plate and len(license_plate) <= 12:
                car.license_plate = license_plate
            
            brand = input(f"ยี่ห้อ [{car.brand}]: ").strip()
            if brand and len(brand) <= 12:
                car.brand = brand
            
            model = input(f"รุ่น [{car.model}]: ").strip()
            if model and len(model) <= 16:
                car.model = model
            
            year_input = input(f"ปี [{car.year}]: ").strip()
            if year_input:
                year = int(year_input)
                if 1900 <= year <= datetime.datetime.now().year + 2:
                    car.year = year
            
            rate_input = input(f"ค่าเช่า/วัน [{car.daily_rate}]: ").strip()
            if rate_input:
                daily_rate = float(rate_input)
                if 0 < daily_rate <= 99999.99:
                    car.daily_rate = daily_rate
            
            odometer_input = input(f"เลขไมล์ [{car.odometer}]: ").strip()
            if odometer_input:
                odometer = int(odometer_input)
                if 0 <= odometer <= 9999999:
                    car.odometer = odometer
            
            rented_input = input(f"เช่าอยู่? (y/n) [{'y' if car.is_rented else 'n'}]: ").strip().lower()
            if rented_input in ['y', 'n']:
                car.is_rented = 1 if rented_input == 'y' else 0
            
            # Update record
            if self._update_car_record(car_id, car):
                self._log_operation(car_id, 'U', f'Updated {car.brand} {car.model}')
                print("\n✅ แก้ไขข้อมูลสำเร็จ!")
                print(car)
            else:
                print("❌ ไม่สามารถแก้ไขข้อมูลได้")
                
        except ValueError:
            print("❌ กรุณาใส่รหัสรถเป็นตัวเลข")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
    
    def delete_car(self):
        """Delete car (CRUD: Delete - Soft delete)"""
        print("\n" + "="*50)
        print("ลบรถ (Delete Car)")
        print("="*50)
        
        try:
            car_id = int(input("รหัสรถที่ต้องการลบ (Car ID): "))
            car = self._find_car_by_id(car_id)
            
            if not car:
                print("❌ ไม่พบรถที่มี ID นี้")
                return
            
            if car.status == STATUS_DELETED:
                print("❌ รถนี้ถูกลบไปแล้ว")
                return
            
            print("\nข้อมูลรถที่จะลบ:")
            print(car)
            
            confirm = input("\nยืนยันการลบ? (y/n): ").strip().lower()
            if confirm != 'y':
                print("ยกเลิกการลบ")
                return
            
            # Soft delete - change status
            car.status = STATUS_DELETED
            
            if self._update_car_record(car_id, car):
                self._log_operation(car_id, 'D', f'Deleted {car.brand} {car.model}')
                print("✅ ลบรถสำเร็จ!")
            else:
                print("❌ ไม่สามารถลบรถได้")
                
        except ValueError:
            print("❌ กรุณาใส่รหัสรถเป็นตัวเลข")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
    
    def view_menu(self):
        """View submenu (CRUD: Read)"""
        while True:
            print("\n" + "="*50)
            print("เมนูดูข้อมูล (View Menu)")
            print("="*50)
            print("1. ดูรายการเดียว (View Single)")
            print("2. ดูทั้งหมด (View All)")
            print("3. ดูแบบกรอง (View Filtered)")
            print("4. สถิติโดยสรุป (Summary Statistics)")
            print("0. กลับ (Back)")
            
            choice = input("\nเลือก (1-4, 0): ").strip()
            
            if choice == '1':
                self.view_single()
            elif choice == '2':
                self.view_all()
            elif choice == '3':
                self.view_filtered()
            elif choice == '4':
                self.view_statistics()
            elif choice == '0':
                break
            else:
                print("❌ กรุณาเลือก 1-4 หรือ 0")
    
    def view_single(self):
        """View single car record"""
        print("\n" + "="*50)
        print("ดูรายการเดียว (View Single Car)")
        print("="*50)
        
        try:
            car_id = int(input("รหัสรถ (Car ID): "))
            car = self._find_car_by_id(car_id)
            
            if not car:
                print("❌ ไม่พบรถที่มี ID นี้")
                return
            
            print(car)
            self._log_operation(car_id, 'V', 'Viewed single record')
            
        except ValueError:
            print("❌ กรุณาใส่รหัสรถเป็นตัวเลข")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
    
    def view_all(self):
        """View all car records"""
        print("\n" + "="*50)
        print("รายการรถทั้งหมด (All Cars)")
        print("="*50)
        
        cars = self._read_all_cars()
        if not cars:
            print("ไม่มีข้อมูลรถ")
            return
        
        # Table header
        print(f"{'ID':<6} {'ทะเบียน':<12} {'ยี่ห้อ':<12} {'รุ่น':<16} {'ปี':<6} {'ค่าเช่า':<10} {'สถานะ':<8} {'เช่า':<6}")
        print("-" * 80)
        
        active_count = 0
        deleted_count = 0
        
        for car in cars:
            status_text = "Active" if car.status == STATUS_ACTIVE else "Deleted"
            rented_text = "เช่าอยู่" if car.is_rented else "ว่าง"
            
            print(f"{car.car_id:<6} {car.license_plate:<12} {car.brand:<12} {car.model:<16} "
                  f"{car.year:<6} {car.daily_rate:<10.2f} {status_text:<8} {rented_text:<6}")
            
            if car.status == STATUS_ACTIVE:
                active_count += 1
            else:
                deleted_count += 1
        
        print("-" * 80)
        print(f"รวม: {len(cars)} คัน | Active: {active_count} คัน | Deleted: {deleted_count} คัน")
        
        # Log operation for first car (if any)
        if cars:
            self._log_operation(0, 'V', 'Viewed all records')
    
    def view_filtered(self):
        """View filtered car records"""
        print("\n" + "="*50)
        print("ดูแบบกรอง (Filtered View)")
        print("="*50)
        
        print("เลือกเงื่อนไขการกรอง:")
        print("1. สถานะ (Status)")
        print("2. การเช่า (Rental Status)")
        print("3. ยี่ห้อ (Brand)")
        print("4. ช่วงปี (Year Range)")
        
        filter_choice = input("เลือกการกรอง (1-4): ").strip()
        
        cars = self._read_all_cars()
        filtered_cars = []
        
        try:
            if filter_choice == '1':
                status_filter = input("สถานะ (active/deleted): ").strip().lower()
                status = STATUS_ACTIVE if status_filter == 'active' else STATUS_DELETED
                filtered_cars = [car for car in cars if car.status == status]
                
            elif filter_choice == '2':
                rental_filter = input("การเช่า (rented/available): ").strip().lower()
                is_rented = 1 if rental_filter == 'rented' else 0
                filtered_cars = [car for car in cars if car.is_rented == is_rented and car.status == STATUS_ACTIVE]
                
            elif filter_choice == '3':
                brand_filter = input("ยี่ห้อ: ").strip()
                filtered_cars = [car for car in cars if brand_filter.lower() in car.brand.lower()]
                
            elif filter_choice == '4':
                min_year = int(input("ปีเริ่มต้น: "))
                max_year = int(input("ปีสิ้นสุด: "))
                filtered_cars = [car for car in cars if min_year <= car.year <= max_year]
                
            else:
                print("❌ เลือกไม่ถูกต้อง")
                return
            
            if not filtered_cars:
                print("ไม่พบข้อมูลที่ตรงกับเงื่อนไข")
                return
            
            # Display filtered results
            print(f"\nผลการกรอง ({len(filtered_cars)} คัน):")
            print(f"{'ID':<6} {'ทะเบียน':<12} {'ยี่ห้อ':<12} {'รุ่น':<16} {'ปี':<6} {'ค่าเช่า':<10} {'สถานะ':<8} {'เช่า':<6}")
            print("-" * 80)
            
            for car in filtered_cars:
                status_text = "Active" if car.status == STATUS_ACTIVE else "Deleted"
                rented_text = "เช่าอยู่" if car.is_rented else "ว่าง"
                
                print(f"{car.car_id:<6} {car.license_plate:<12} {car.brand:<12} {car.model:<16} "
                      f"{car.year:<6} {car.daily_rate:<10.2f} {status_text:<8} {rented_text:<6}")
            
            # Log operation
            if filtered_cars:
                self._log_operation(0, 'V', f'Filtered view: {len(filtered_cars)} cars')
                
        except ValueError:
            print("❌ ข้อมูลไม่ถูกต้อง")
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
    
    def view_statistics(self):
        """View summary statistics"""
        print("\n" + "="*50)
        print("สถิติโดยสรุป (Summary Statistics)")
        print("="*50)
        
        cars = self._read_all_cars()
        if not cars:
            print("ไม่มีข้อมูลรถ")
            return
        
        # Calculate statistics
        total_cars = len(cars)
        active_cars = [car for car in cars if car.status == STATUS_ACTIVE]
        deleted_cars = [car for car in cars if car.status == STATUS_DELETED]
        rented_cars = [car for car in active_cars if car.is_rented]
        available_cars = [car for car in active_cars if not car.is_rented]
        
        print(f"จำนวนรถทั้งหมด: {total_cars} คัน")
        print(f"รถที่ใช้งาน (Active): {len(active_cars)} คัน")
        print(f"รถที่ลบแล้ว (Deleted): {len(deleted_cars)} คัน")
        print(f"รถที่เช่าอยู่: {len(rented_cars)} คัน")
        print(f"รถว่าง: {len(available_cars)} คัน")
        
        if active_cars:
            rates = [car.daily_rate for car in active_cars]
            avg_rate = sum(rates) / len(rates)
            min_rate = min(rates)
            max_rate = max(rates)
            
            print(f"\nสถิติค่าเช่า (รถที่ใช้งานเท่านั้น):")
            print(f"ค่าเช่าเฉลี่ย: ฿{avg_rate:,.2f}")
            print(f"ค่าเช่าต่ำสุด: ฿{min_rate:,.2f}")
            print(f"ค่าเช่าสูงสุด: ฿{max_rate:,.2f}")
            
            # Brand statistics
            brands = {}
            for car in active_cars:
                brands[car.brand] = brands.get(car.brand, 0) + 1
            
            print(f"\nรถแยกตามยี่ห้อ (Active only):")
            for brand, count in sorted(brands.items()):
                print(f"- {brand}: {count} คัน")
        
        # System capacity (simulated)
        total_slots = 1000
        available_slots = total_slots - total_cars
        print(f"\nความจุระบบ:")
        print(f"ความจุทั้งหมด: {total_slots} คัน")
        print(f"ใช้งานแล้ว: {total_cars} คัน")
        print(f"ช่องว่าง: {available_slots} คัน")
        
        # Recent operations
        operations = self._read_operations(5)
        if operations:
            print(f"\nการทำงานล่าสุด:")
            for op in operations:
                op_time = datetime.datetime.fromtimestamp(op.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                op_type_map = {'A': 'ADD', 'U': 'UPDATE', 'D': 'DELETE', 'V': 'VIEW'}
                op_type = op_type_map.get(op.operation_type, op.operation_type)
                print(f"- {op_time} | {op_type} | Car ID: {op.car_id} | {op.details}")
        
        # Log this view operation
        self._log_operation(0, 'V', 'Viewed statistics')
    
    def generate_report(self):
        """Generate text report to file"""
        print("\n" + "="*50)
        print("สร้างรายงาน (Generate Report)")
        print("="*50)
        
        try:
            cars = self._read_all_cars()
            operations = self._read_operations(10)
            
            now = datetime.datetime.now()
            
            # Calculate statistics
            total_cars = len(cars)
            active_cars = [car for car in cars if car.status == STATUS_ACTIVE]
            deleted_cars = [car for car in cars if car.status == STATUS_DELETED]
            rented_cars = [car for car in active_cars if car.is_rented]
            available_cars = [car for car in active_cars if not car.is_rented]
            
            report_content = f"""Car Rental System - Summary Report (Sample)
Generated at: {now.strftime('%Y-%m-%d %H:%M:%S')}
App Version: 1.0
Endianness: Little-Endian
Encoding: UTF-8 (Fixed-length)

{'='*60}
SUMMARY STATISTICS
{'='*60}
Total Cars (รวมรถทั้งหมด): {total_cars}
Active Cars (รถที่ใช้งาน): {len(active_cars)}
Deleted Cars (รถที่ลบแล้ว): {len(deleted_cars)}
Available Cars (รถว่าง): {len(available_cars)}
Rented Cars (รถที่เช่าอยู่): {len(rented_cars)}

Rate Statistics (THB/day, Active only):
"""
            
            if active_cars:
                rates = [car.daily_rate for car in active_cars]
                avg_rate = sum(rates) / len(rates)
                min_rate = min(rates)
                max_rate = max(rates)
                
                report_content += f"""- Min: {min_rate:.2f}
- Max: {max_rate:.2f}
- Avg: {avg_rate:.2f}

Cars by Brand (Active only):
"""
                
                brands = {}
                for car in active_cars:
                    brands[car.brand] = brands.get(car.brand, 0) + 1
                
                for brand, count in sorted(brands.items()):
                    report_content += f"- {brand}: {count}\n"
            
            report_content += f"""
{'='*60}
RECENT OPERATIONS
{'='*60}
"""
            
            for op in operations:
                op_time = datetime.datetime.fromtimestamp(op.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                op_type_map = {'A': 'ADD', 'U': 'UPDATE', 'D': 'DELETE', 'V': 'VIEW'}
                op_type = op_type_map.get(op.operation_type, op.operation_type)
                report_content += f"{op_time} | {op_type:<8} | Car ID: {op.car_id} | {op.details}\n"
            
            report_content += f"""
{'='*60}
System Status: Running
Available Slots: {1000 - total_cars}
Last Updated: {now.strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # Write to text file
            with open(REPORT_FILE, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            print(f"✅ สร้างรายงานสำเร็จ! ไฟล์: {REPORT_FILE}")
            print(f"ขนาดไฟล์: {os.path.getsize(REPORT_FILE)} bytes")
            
            # Show preview
            preview = input("\nดูตัวอย่างรายงาน? (y/n): ").strip().lower()
            if preview == 'y':
                print("\n" + "="*60)
                print("PREVIEW REPORT")
                print("="*60)
                print(report_content[:1000] + "..." if len(report_content) > 1000 else report_content)
            
            # Log operation
            self._log_operation(0, 'V', 'Generated report')
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
    
    def display_main_menu(self):
        """Display main menu"""
        print("\n" + "="*60)
        print("ระบบจัดการรถเช่า (Car Rental Management System)")
        print("Binary File Storage with Python struct")
        print("="*60)
        print("1) Add (เพิ่ม)")
        print("2) Update (แก้ไข)")
        print("3) Delete (ลบ)")
        print("4) View (ดู)")
        print("   - ดูรายการเดียว")
        print("   - ดูทั้งหมด")
        print("   - ดูแบบกรอง")
        print("   - สถิติโดยสรุป")
        print("5) Generate Report (.txt)")
        print("0) Exit (ออก)")
        print("="*60)
    
    def run(self):
        """Main program loop"""
        print("🚗 ระบบจัดการรถเช่า - Car Rental Management System")
        print("📁 Binary File Storage with Python struct module")
        print("🔧 Python 3.10+ | Little-Endian | Fixed-length Records")
        
        while True:
            self.display_main_menu()
            
            choice = input("\nเลือกการทำงาน (1-5, 0): ").strip()
            
            if choice == '1':
                self.add_car()
            elif choice == '2':
                self.update_car()
            elif choice == '3':
                self.delete_car()
            elif choice == '4':
                self.view_menu()
            elif choice == '5':
                self.generate_report()
            elif choice == '0':
                print("\n🔒 ปิดโปรแกรมอย่างปลอดภัย...")
                print("💾 Flushing buffers and syncing data...")
                
                # Safe shutdown - ensure all data is written
                try:
                    # Force sync all files
                    for filename in [CARS_FILE, OPERATIONS_FILE, SEQUENCE_FILE]:
                        if os.path.exists(filename):
                            with open(filename, 'r+b') as f:
                                f.flush()
                                os.fsync(f.fileno())
                    
                    # Generate final report automatically
                    print("📄 Auto-generating final report...")
                    self.generate_report()
                    
                    print("✅ ข้อมูลทั้งหมดถูกบันทึกแล้ว")
                    print("👋 ขอบคุณที่ใช้งาน Car Rental Management System")
                    
                except Exception as e:
                    print(f"⚠️  Warning during shutdown: {e}")
                
                break
            else:
                print("❌ กรุณาเลือก 1-5 หรือ 0")
                
def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Car Rental Management System with Binary File Storage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
        Examples:
          python car_rental_system.py          # Run interactive mode
          
        Binary Files:
          - cars.dat:        Main car records (72 bytes/record)
          - operations.dat:  Operation logs (32 bytes/record)  
          - sequence.dat:    ID sequence tracking (4 bytes)
          - report.txt:      Text report output
          
        Struct Formats:
          - Car: '<I12s12s16sIfIBBII' (Little-Endian, 72 bytes)
          - Operation: '<IIcI20s' (Little-Endian, 32 bytes)
          - Sequence: '<I' (Little-Endian, 4 bytes)
        ''')
    )
    
    parser.add_argument('--version', action='version', version='Car Rental System 1.0')
    parser.add_argument('--info', action='store_true', help='Show system information')
    
    args = parser.parse_args()
    
    if args.info:
        print("Car Rental Management System")
        print("="*40)
        print("Version: 1.0")
        print("Python: 3.10+")
        print("Platform: Terminal")
        print("Storage: Binary Files (struct)")
        print("Endianness: Little-Endian")
        print("Records: Fixed-length")
        print("Files:")
        print("  - cars.dat (72 bytes/record)")
        print("  - operations.dat (32 bytes/record)")
        print("  - sequence.dat (4 bytes)")
        print("  - report.txt (text output)")
        return
    
    # Run the system
    try:
        system = CarRentalSystem()
        system.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  โปรแกรมถูกหยุดโดย Ctrl+C")
        print("💾 บันทึกข้อมูลฉุกเฉิน...")
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาดร้าย: {e}")
        print("📝 กรุณาตรวจสอบไฟล์ข้อมูลและเริ่มโปรแกรมใหม่")

if __name__ == "__main__":
    main()