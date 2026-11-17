import asyncio
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.models.dividend import Dividend

def parse_dhan_file(file_path):
    with zipfile.ZipFile(file_path) as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                tree = ET.parse(f)
                for si in tree.getroot():
                    text_val = "".join(t.text for t in si.iter() if t.tag.endswith('t') and t.text)
                    shared_strings.append(text_val)

        sheet_rows = []
        with z.open('xl/worksheets/sheet1.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                row_vals = []
                for cell in row.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    val = ""
                    t_attr = cell.attrib.get('t')
                    v_elem = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    if v_elem is not None and v_elem.text is not None:
                        val = v_elem.text
                        if t_attr == 's':
                            val = shared_strings[int(val)]
                    row_vals.append(val)
                if any(row_vals):
                    sheet_rows.append(row_vals)

        header_idx = None
        for i, r in enumerate(sheet_rows):
            if len(r) >= 5 and r[0] == 'Date' and r[1] == 'Name':
                header_idx = i
                break

        records = []
        for r in sheet_rows[header_idx + 1:]:
            if len(r) < 5 or not r[0] or not r[1]:
                continue
            date_str = r[0] # e.g. '13-08-2026'
            dt = datetime.strptime(date_str, "%d-%m-%Y").date()
            name = r[1]
            dps = Decimal(str(r[2])) if r[2] else Decimal("0")
            qty = Decimal(str(r[3])) if r[3] else Decimal("0")
            paid = Decimal(str(r[4])) if r[4] else Decimal("0")
            records.append({
                "date": dt,
                "name": name,
                "dps": dps,
                "qty": qty,
                "paid": paid
            })
        return records

async def seed_database():
    records = parse_dhan_file('/tmp/Dhan-Dividend.csv')
    print(f"Parsed {len(records)} records from Dhan export.")
    
    async with AsyncSessionLocal() as db:
        # Clear previous dividend records for clean sync
        await db.execute(text("DELETE FROM dividends WHERE broker_account_id = 1"))
        await db.commit()
        print("Cleaned existing dividend records.")

        total_amount = Decimal("0")
        unique_stocks = set()

        for r in records:
            div = Dividend(
                broker_account_id=1,
                symbol=r["name"][:15].upper().replace(" ", "").replace("-", ""),
                company_name=r["name"],
                ex_date=r["date"],
                payment_date=r["date"],
                dividend_per_share=r["dps"],
                quantity=r["qty"],
                total_dividend=r["paid"],
                tax_deducted=Decimal("0"),
                net_dividend=r["paid"],
            )
            db.add(div)
            total_amount += r["paid"]
            unique_stocks.add(r["name"])

        await db.commit()
        print(f"Imported {len(records)} records successfully!")
        print(f"Unique Stocks: {len(unique_stocks)}")
        print(f"Total Net Dividend: {total_amount}")

if __name__ == '__main__':
    asyncio.run(seed_database())
