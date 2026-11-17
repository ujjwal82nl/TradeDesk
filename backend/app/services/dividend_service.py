"""Dividend service."""
import calendar
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import delete, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.broker import BrokerAccount, BrokerProvider
from app.models.dividend import Dividend
from app.schemas.dividend import CreateDividendRequest

logger = logging.getLogger(__name__)


class DividendService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dividends(
        self,
        user_id: int,
        page: int,
        page_size: int,
        broker_account_id: Optional[int],
        symbol: Optional[str],
    ) -> dict:
        base_q = (
            select(Dividend, BrokerProvider.display_name)
            .join(BrokerAccount, Dividend.broker_account_id == BrokerAccount.id)
            .join(BrokerProvider, BrokerAccount.broker_id == BrokerProvider.id)
            .where(BrokerAccount.user_id == user_id)
        )
        if broker_account_id:
            base_q = base_q.where(Dividend.broker_account_id == broker_account_id)
        if symbol:
            base_q = base_q.where(Dividend.symbol.ilike(f"%{symbol}%"))

        count_q = select(func.count()).select_from(base_q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        rows_q = (
            base_q.order_by(
                func.coalesce(Dividend.payment_date, Dividend.ex_date).desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(rows_q)
        rows = result.all()

        items = [
            {
                "id": d.id,
                "broker_name": broker_name,
                "broker_account_id": d.broker_account_id,
                "symbol": d.symbol,
                "company_name": d.company_name or d.symbol,
                "isin": d.isin,
                "ex_date": d.ex_date,
                "payment_date": d.payment_date,
                "dividend_per_share": float(d.dividend_per_share or 0),
                "quantity": float(d.quantity or 0),
                "total_dividend": float(d.total_dividend or 0),
                "tax_deducted": float(d.tax_deducted or 0),
                "net_dividend": float(d.net_dividend or 0),
            }
            for d, broker_name in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def create_dividend(
        self, user_id: int, data: CreateDividendRequest
    ) -> dict:
        stmt = (
            select(BrokerAccount)
            .options(selectinload(BrokerAccount.broker))
            .where(
                BrokerAccount.id == data.broker_account_id,
                BrokerAccount.user_id == user_id,
            )
        )
        acc = (await self.db.execute(stmt)).scalar_one_or_none()
        if not acc:
            raise ValueError("Broker account not found or access denied.")

        qty = Decimal(str(data.quantity))
        dps = Decimal(str(data.dividend_per_share))
        gross = (
            Decimal(str(data.total_dividend))
            if data.total_dividend is not None
            else (qty * dps)
        )
        tax = Decimal(str(data.tax_deducted or 0))
        net = (
            Decimal(str(data.net_dividend))
            if data.net_dividend is not None
            else (gross - tax)
        )

        div = Dividend(
            broker_account_id=acc.id,
            symbol=data.symbol.upper().strip(),
            company_name=data.company_name or data.symbol.upper().strip(),
            isin=data.isin,
            ex_date=data.ex_date,
            payment_date=data.payment_date or data.ex_date or date.today(),
            dividend_per_share=dps,
            quantity=qty,
            total_dividend=gross,
            tax_deducted=tax,
            net_dividend=net,
        )
        self.db.add(div)
        await self.db.commit()
        await self.db.refresh(div)

        bname = acc.broker.display_name if acc.broker else acc.account_name
        return {
            "id": div.id,
            "broker_name": bname,
            "broker_account_id": div.broker_account_id,
            "symbol": div.symbol,
            "company_name": div.company_name,
            "isin": div.isin,
            "ex_date": div.ex_date,
            "payment_date": div.payment_date,
            "dividend_per_share": float(div.dividend_per_share or 0),
            "quantity": float(div.quantity or 0),
            "total_dividend": float(div.total_dividend or 0),
            "tax_deducted": float(div.tax_deducted or 0),
            "net_dividend": float(div.net_dividend or 0),
        }

    async def delete_dividend(self, user_id: int, dividend_id: int) -> bool:
        stmt = (
            select(Dividend)
            .join(BrokerAccount, Dividend.broker_account_id == BrokerAccount.id)
            .where(Dividend.id == dividend_id, BrokerAccount.user_id == user_id)
        )
        div = (await self.db.execute(stmt)).scalar_one_or_none()
        if not div:
            raise ValueError(f"Dividend record {dividend_id} not found.")
        await self.db.delete(div)
        await self.db.commit()
        return True

    async def sync_dividends_from_broker(
        self, user_id: int, broker_account_id: Optional[int] = None
    ) -> int:
        from app.services.broker_service import BrokerService

        broker_svc = BrokerService(self.db)
        accounts = await broker_svc.get_user_accounts(user_id)
        if broker_account_id:
            accounts = [a for a in accounts if a.id == broker_account_id]

        total_synced = 0
        to_date = date.today().strftime("%Y-%m-%d")
        from_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

        for acc in accounts:
            if not acc.broker or "dhan" not in acc.broker.name.lower():
                continue

            try:
                adapter = await broker_svc.get_broker_instance(acc.id, user_id)
                raw = await adapter._run(
                    adapter._dhan.ledger_report, from_date, to_date
                )
                data = raw.get("data", []) if isinstance(raw, dict) else []

                for item in data:
                    narr = str(item.get("narration", "")).lower()
                    desc = str(item.get("voucherdesc", "")).lower()
                    if "dividend" not in narr and "dividend" not in desc:
                        continue

                    credit_str = item.get("credit", "0")
                    credit = float(credit_str) if credit_str else 0.0
                    if credit <= 0:
                        continue

                    vdate_str = str(item.get("voucherdate", ""))
                    pay_date = None
                    try:
                        pay_date = datetime.strptime(vdate_str, "%b %d, %Y").date()
                    except Exception:
                        try:
                            pay_date = datetime.fromisoformat(vdate_str).date()
                        except Exception:
                            pay_date = date.today()

                    symbol = "DIVIDEND"
                    comp_name = item.get("narration") or "Dividend Credit"
                    if "slb" in narr or "slbm" in str(item.get("exchange", "")).lower():
                        symbol = "SLB-DIV"
                        comp_name = "Securities Lending (SLB) Dividend"

                    # Check if already exists in DB
                    check_stmt = select(Dividend).where(
                        Dividend.broker_account_id == acc.id,
                        Dividend.payment_date == pay_date,
                        Dividend.net_dividend == Decimal(str(credit)),
                    )
                    exists = (await self.db.execute(check_stmt)).scalars().first()
                    if exists:
                        continue

                    div = Dividend(
                        broker_account_id=acc.id,
                        symbol=symbol,
                        company_name=comp_name,
                        ex_date=pay_date,
                        payment_date=pay_date,
                        dividend_per_share=Decimal("0"),
                        quantity=Decimal("1"),
                        total_dividend=Decimal(str(credit)),
                        tax_deducted=Decimal("0"),
                        net_dividend=Decimal(str(credit)),
                    )
                    self.db.add(div)
                    total_synced += 1

                if total_synced > 0:
                    await self.db.commit()
            except Exception as exc:
                logger.warning(
                    "sync_dividends error for account %s: %s", acc.id, exc
                )

        return total_synced

    async def get_monthly_income(self, user_id: int, year: Optional[int]) -> list:
        import calendar
        q = (
            select(
                extract("year", Dividend.payment_date).label("year"),
                extract("month", Dividend.payment_date).label("month"),
                func.sum(Dividend.net_dividend).label("total"),
                func.count(Dividend.id).label("count"),
            )
            .join(BrokerAccount)
            .where(BrokerAccount.user_id == user_id)
            .group_by("year", "month")
            .order_by("year", "month")
        )
        if year:
            q = q.where(extract("year", Dividend.payment_date) == year)
        result = await self.db.execute(q)
        return [
            {
                "year": int(r.year), "month": int(r.month),
                "month_name": calendar.month_abbr[int(r.month)],
                "total_income": float(r.total or 0),
                "dividend_count": r.count,
            }
            for r in result.all()
        ]

    async def get_annual_income(self, user_id: int) -> list:
        result = await self.db.execute(
            select(
                extract("year", Dividend.payment_date).label("year"),
                func.sum(Dividend.net_dividend).label("total"),
                func.count(Dividend.id).label("count"),
            )
            .join(BrokerAccount)
            .where(BrokerAccount.user_id == user_id)
            .group_by("year")
            .order_by("year")
        )
        return [
            {"year": int(r.year), "total_income": float(r.total or 0), "count": r.count}
            for r in result.all()
        ]

    async def get_by_stock(self, user_id: int) -> list:
        result = await self.db.execute(
            select(
                Dividend.symbol, Dividend.company_name,
                func.sum(Dividend.net_dividend).label("total"),
                func.max(func.coalesce(Dividend.payment_date, Dividend.ex_date)).label("last_date"),
                func.count(Dividend.id).label("count"),
                func.max(Dividend.quantity).label("quantity"),
            )
            .join(BrokerAccount)
            .where(BrokerAccount.user_id == user_id)
            .group_by(Dividend.symbol, Dividend.company_name)
            .order_by(func.max(func.coalesce(Dividend.payment_date, Dividend.ex_date)).desc())
        )
        return [
            {
                "symbol": r.symbol, "company_name": r.company_name,
                "total_received": float(r.total or 0), "last_dividend_date": r.last_date,
                "quantity": float(r.quantity or 0),
                "yield_on_cost": None,  # Requires avg cost data
            }
            for r in result.all()
        ]

    async def import_dividends_csv(
        self, user_id: int, content_bytes: bytes, broker_account_id: Optional[int] = None
    ) -> int:
        import csv
        import io
        import zipfile
        import xml.etree.ElementTree as ET

        # Find user's broker account
        acc_id = broker_account_id
        if not acc_id:
            acc_stmt = (
                select(BrokerAccount.id)
                .where(BrokerAccount.user_id == user_id, BrokerAccount.is_active.is_(True))
                .order_by(BrokerAccount.is_default.desc(), BrokerAccount.created_at)
            )
            acc_id = (await self.db.execute(acc_stmt)).scalars().first()
            if not acc_id:
                raise ValueError("No active broker account found to associate imported dividends.")

        rows_to_process = []

        # Check if it's an Excel workbook (.xlsx / ZIP container, e.g. Dhan, Zerodha Console, Groww)
        if content_bytes.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    with z.open("xl/sharedStrings.xml") as f:
                        tree = ET.parse(f)
                        for si in tree.getroot():
                            text_val = "".join(t.text for t in si.iter() if t.tag.endswith("t") and t.text)
                            shared_strings.append(text_val)

                # Find first worksheet
                sheet_names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
                sheet_name = sheet_names[0] if sheet_names else "xl/worksheets/sheet1.xml"

                sheet_rows = []
                with z.open(sheet_name) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for row in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                        row_vals = []
                        for cell in row.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                            val = ""
                            t_attr = cell.attrib.get("t")
                            v_elem = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                            if v_elem is not None and v_elem.text is not None:
                                val = v_elem.text
                                if t_attr == "s":
                                    val = shared_strings[int(val)]
                            row_vals.append(val)
                        if any(row_vals):
                            sheet_rows.append(row_vals)

                # Dynamically locate header row across any broker export
                header_idx = None
                for i, r in enumerate(sheet_rows):
                    r_lower = [str(c).strip().lower() for c in r if c]
                    has_date = any("date" in c for c in r_lower)
                    has_stock = any(any(k in c for k in ["name", "symbol", "stock", "company", "isin", "scrip"]) for c in r_lower)
                    has_amount = any(any(k in c for k in ["dividend", "amount", "paid", "rate", "payout", "value"]) for c in r_lower)
                    if has_date and (has_stock or has_amount):
                        header_idx = i
                        break

                if header_idx is not None:
                    headers = [str(h).strip().lower() for h in sheet_rows[header_idx]]
                    for r in sheet_rows[header_idx + 1:]:
                        if len(r) >= 2 and any(r):
                            row_dict = {headers[idx]: str(r[idx]).strip() for idx in range(min(len(headers), len(r))) if idx < len(headers) and headers[idx]}
                            rows_to_process.append(row_dict)
        else:
            text_str = content_bytes.decode("utf-8-sig", errors="replace")
            # If there are preamble rows, find header row
            lines = text_str.strip().splitlines()
            start_line_idx = 0
            for idx, line in enumerate(lines[:20]):
                line_lower = line.lower()
                if "date" in line_lower and ("symbol" in line_lower or "name" in line_lower or "dividend" in line_lower or "company" in line_lower):
                    start_line_idx = idx
                    break

            reader = csv.DictReader(io.StringIO("\n".join(lines[start_line_idx:])))
            for row in reader:
                rows_to_process.append({k.strip().lower(): str(v).strip() for k, v in row.items() if k})

        imported = 0
        for row_norm in rows_to_process:
            # 1. Date resolution
            date_val = None
            for dkey in ["date", "posting date", "posting_date", "payment_date", "payment date", "transactiondate", "trans_date", "voucherdate", "record_date"]:
                if dkey in row_norm and row_norm[dkey]:
                    raw_d = row_norm[dkey].split("T")[0].strip()
                    for fmt in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%m/%d/%Y"]:
                        try:
                            date_val = datetime.strptime(raw_d, fmt).date()
                            break
                        except Exception:
                            pass
                    if date_val:
                        break
            if not date_val:
                date_val = date.today()

            # 2. Company / Symbol name
            name_val = ""
            for nkey in ["name", "stockname", "stock name", "company", "company name", "scrip name", "scrip_name", "symbol", "security"]:
                if nkey in row_norm and row_norm[nkey]:
                    name_val = row_norm[nkey]
                    break
            if not name_val:
                continue

            # ISIN
            isin_val = None
            for isinkey in ["isin", "isin code", "isin_code"]:
                if isinkey in row_norm and row_norm[isinkey]:
                    isin_val = row_norm[isinkey].upper()
                    break

            # 3. Dividend per share (DPS)
            dps_val = Decimal("0")
            for dpkey in ["dividend / share", "dividend/share", "dividend per share", "dividend_per_share", "rate", "dividend rate", "corpactionvalue", "dps", "amount per share"]:
                if dpkey in row_norm and row_norm[dpkey]:
                    try:
                        clean_num = row_norm[dpkey].replace(",", "").replace("₹", "").replace("Rs", "").strip()
                        dps_val = Decimal(clean_num)
                        break
                    except Exception:
                        pass

            # 4. Quantity
            qty_val = Decimal("1")
            for qkey in ["quantity", "qty", "no. of shares", "shares", "units"]:
                if qkey in row_norm and row_norm[qkey]:
                    try:
                        clean_qty = row_norm[qkey].replace(",", "").strip()
                        qty_val = Decimal(clean_qty)
                        break
                    except Exception:
                        pass

            # 5. Dividend Paid (Amount)
            amt_val = Decimal("0")
            for akey in ["dividend paid", "dividend_paid", "net dividend amount", "net_dividend_amount", "net dividend", "net_dividend", "total dividend", "total_dividend", "amount", "transactedamount", "gross amount"]:
                if akey in row_norm and row_norm[akey]:
                    try:
                        clean_amt = row_norm[akey].replace(",", "").replace("₹", "").replace("Rs", "").strip()
                        amt_val = Decimal(clean_amt)
                        break
                    except Exception:
                        pass

            if amt_val <= Decimal("0") and dps_val > Decimal("0") and qty_val > Decimal("0"):
                amt_val = dps_val * qty_val

            if amt_val <= Decimal("0"):
                continue

            # Deduplication check
            dup_stmt = select(Dividend).where(
                Dividend.broker_account_id == acc_id,
                Dividend.company_name == name_val,
                Dividend.payment_date == date_val,
                Dividend.net_dividend == amt_val,
            )
            exists = (await self.db.execute(dup_stmt)).scalars().first()
            if exists:
                continue

            # Resolve ticker symbol
            symbol_code = name_val[:15].upper().replace(" ", "").replace("-", "")
            if "symbol" in row_norm and row_norm["symbol"]:
                symbol_code = row_norm["symbol"].upper().strip()

            div = Dividend(
                broker_account_id=acc_id,
                symbol=symbol_code,
                company_name=name_val,
                isin=isin_val,
                ex_date=date_val,
                payment_date=date_val,
                dividend_per_share=dps_val,
                quantity=qty_val,
                total_dividend=amt_val,
                tax_deducted=Decimal("0"),
                net_dividend=amt_val,
            )
            self.db.add(div)
            imported += 1

        if imported > 0:
            await self.db.commit()

        return imported

    async def get_by_broker(self, user_id: int) -> list:
        result = await self.db.execute(
            select(
                BrokerProvider.display_name,
                func.sum(Dividend.net_dividend).label("total"),
                func.count(Dividend.id).label("count"),
            )
            .join(BrokerAccount, Dividend.broker_account_id == BrokerAccount.id)
            .join(BrokerProvider, BrokerAccount.broker_id == BrokerProvider.id)
            .where(BrokerAccount.user_id == user_id)
            .group_by(BrokerProvider.display_name)
        )
        return [
            {"broker": r.display_name, "total_income": float(r.total or 0), "count": r.count}
            for r in result.all()
        ]

    async def get_upcoming_calendar(self, user_id: int, days_ahead: int) -> list:
        today = date.today()
        future = today + timedelta(days=days_ahead)
        result = await self.db.execute(
            select(Dividend, BrokerProvider.display_name)
            .join(BrokerAccount, Dividend.broker_account_id == BrokerAccount.id)
            .join(BrokerProvider, BrokerAccount.broker_id == BrokerProvider.id)
            .where(
                BrokerAccount.user_id == user_id,
                Dividend.ex_date >= today,
                Dividend.ex_date <= future,
            )
            .order_by(Dividend.ex_date)
        )
        return [
            {
                "id": d.id, "broker_name": bn, "symbol": d.symbol,
                "company_name": d.company_name, "ex_date": d.ex_date,
                "payment_date": d.payment_date,
                "dividend_per_share": float(d.dividend_per_share or 0),
                "quantity": float(d.quantity or 0), "total_dividend": float(d.total_dividend or 0),
                "net_dividend": float(d.net_dividend or 0),
            }
            for d, bn in result.all()
        ]
