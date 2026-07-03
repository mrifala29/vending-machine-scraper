"""
ClickHouse storage client.
Inserts scraped data directly into ClickHouse, one table per submenu.
"""
import clickhouse_connect
from datetime import datetime, date, timezone
from typing import List, Optional

from models.sales_data import SalesStatisticData
from models.machine_data import MachineScrapingResult
from utils.logging_setup import logger


# Map from Chinese column names (as scraped) to English ClickHouse column names,
# grouped by submenu/table name.
_COLUMN_MAP: dict[str, dict[str, str]] = {
    "deliverydetail": {
        "设备ID": "device_id",
        "设备名称": "device_name",
        "货道": "aisle",
        "商品名称": "product_name",
        "商品品牌": "product_brand",
        "销售金额": "sales_amount",
        "支付类型": "payment_type",
        "销售时间": "sales_time",
        "返回码": "return_code",
    },
    "paydetail": {
        "序号": "seq_no",
        "系统订单号": "system_order_no",
        "支付渠道流水号": "payment_channel_no",
        "设备ID": "device_id",
        "设备名称": "device_name",
        "货道": "aisle",
        "持有人": "holder",
        "商品名称": "product_name",
        "支付方式": "payment_method",
        "支付金额": "payment_amount",
        "购买数量": "purchase_qty",
        "商品进价": "cost_price",
        "付款人": "payer",
        "支付时间": "payment_time",
        "支付状态": "payment_status",
        "退款状态": "refund_status",
        "出货状态": "delivery_status",
        "出货详情": "delivery_detail",
        "优惠券码": "coupon_code",
        "折扣详情": "discount_detail",
        "优惠金额": "discount_amount",
        "订单金额": "order_amount",
        "出货编码": "delivery_code",
    },
    "cashdetail": {
        "序号": "seq_no",
        "设备ID": "device_id",
        "设备名称": "device_name",
        "持有人": "holder",
        "交易类型": "transaction_type",
        "交易方式": "transaction_method",
        "金额": "amount",
        "交易时间": "transaction_time",
    },
    "essDetail": {
        "设备ID": "device_id",
        "设备名称": "device_name",
        "销售数量": "sales_qty",
        "销售总额": "total_sales",
        "微信": "wechat",
        "微信刷脸": "wechat_face",
        "微信刷掌": "wechat_palm",
        "支付宝": "alipay",
        "支付宝刷脸": "alipay_face",
        "支付宝NFC": "alipay_nfc",
        "现金": "cash",
        "微信会员": "wechat_member",
        "会员卡": "member_card",
        "扶贫网": "fupin",
        "GHL": "ghl",
    },
    "mtOrder": {
        "美团订单号": "meituan_order_no",
        "美团门店ID": "meituan_store_id",
        "设备号": "device_no",
        "商品名称": "product_name",
        "支付金额": "payment_amount",
        "订单状态": "order_status",
        "取货码": "pickup_code",
        "商品货道": "product_aisle",
        "出货详情": "delivery_detail",
        "创建时间": "created_time",
    },
    "orderThird": {
        "订单号": "order_no",
        "三方订单号": "third_order_no",
        "设备ID": "device_id",
        "商品名称": "product_name",
        "货道": "aisle",
        "支付方式": "payment_method",
        "订单金额": "order_amount",
        "商品单价": "unit_price",
        "数量": "quantity",
        "购买人": "buyer",
        "购买ID": "buyer_id",
        "应退款金额": "refund_amount",
        "出货状态": "delivery_status",
        "交易时间": "transaction_time",
        "创建时间": "created_time",
    },
    "orderThirdMachine": {
        "设备ID": "device_id",
        "设备名称": "device_name",
        "销售数量": "sales_qty",
        "销售总额": "total_sales",
    },
    "onlineOrderDetail": {
        "序号": "seq_no",
        "系统订单号": "system_order_no",
        "支付渠道流水号": "payment_channel_no",
        "设备ID": "device_id",
        "设备名称": "device_name",
        "商品名称": "product_name",
        "支付方式": "payment_method",
        "支付金额": "payment_amount",
        "购买数量": "purchase_qty",
        "商品进价": "cost_price",
        "支付状态": "payment_status",
        "出货状态": "delivery_status",
        "退款状态": "refund_status",
        "支付时间": "payment_time",
    },
}


class ClickHouseStorage:
    """Insert scraped data into ClickHouse tables."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        secure: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._database = database
        self._username = username
        self._password = password
        self._secure = secure
        self._client: Optional[clickhouse_connect.driver.Client] = None

    def connect(self) -> None:
        """Open ClickHouse connection. Call once before inserting."""
        self._client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            database=self._database,
            username=self._username,
            password=self._password,
            secure=self._secure,
            connect_timeout=10,
            send_receive_timeout=30,
        )
        logger.info(f"Connected to ClickHouse: {self._host}:{self._port}/{self._database}")

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def _ensure_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("ClickHouseStorage.connect() must be called before inserting")

    def delete_for_date_range(self, table: str, start_date: datetime, end_date: datetime) -> None:
        """
        Delete existing rows for the given date range before re-inserting.
        Prevents duplicates when the same date range is scraped more than once.
        """
        self._ensure_connected()
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        query = (
            f"ALTER TABLE {self._database}.{table} "
            f"DELETE WHERE scrape_date >= '{start_str}' AND scrape_date <= '{end_str}'"
        )
        self._client.command(query)
        logger.debug(f"Deleted existing rows from {table} for {start_str} → {end_str}")

    def insert_submenu(
        self,
        data: SalesStatisticData,
        start_date: datetime,
        end_date: datetime,
        force_overwrite: bool = False,
    ) -> int:
        """
        Insert all records from one SalesStatisticData into the matching ClickHouse table.
        Returns number of rows inserted.

        Args:
            data: Scraped data for one submenu/table.
            start_date: Start of date range (used for delete-before-insert).
            end_date: End of date range.
            force_overwrite: If True, bypass history lock and overwrite existing data.
                             Set this to True when running manual backfill/repair jobs
                             (e.g., python main.py --start-date 2026-07-01 --end-date 2026-07-01).
        """
        self._ensure_connected()

        submenu = data.submenu
        col_map = _COLUMN_MAP.get(submenu)
        if col_map is None:
            logger.warning(f"No column mapping for submenu '{submenu}', skipping")
            return 0

        if not data.records:
            logger.info(f"  {submenu}: 0 records, nothing to insert")
            return 0

        # Build column list: metadata first, then data columns in mapping order
        ch_columns = ["scrape_date", "scrape_timestamp"] + list(col_map.values())

        rows: list[list] = []
        for record in data.records:
            scrape_d = record.scrape_date
            ts: datetime = record.scrape_timestamp
            if ts.tzinfo is not None:
                ts = ts.astimezone(timezone.utc).replace(tzinfo=None)

            row = [scrape_d, ts]
            for cn_name, _en_name in col_map.items():
                row.append(record.data.get(cn_name) or None)
            rows.append(row)

        # HISTORY LOCK: never silently overwrite a day already loaded by normal daily cron.
        # Bypassed when force_overwrite=True (manual repair runs).
        if not force_overwrite:
            _locked = self._client.command(
                f"SELECT count() FROM {self._database}.{submenu} "
                f"WHERE scrape_date = '{data.scrape_date}'"
            )
            if int(_locked) > 0:
                logger.info(
                    f"  {submenu}: scrape_date {data.scrape_date} already has "
                    f"{_locked} rows - skipping (history lock). "
                    f"Use --force-overwrite to replace."
                )
                return 0
        else:
            logger.info(f"  {submenu}: force_overwrite=True, deleting existing rows for {data.scrape_date}")

        # Delete stale rows for this date before inserting (idempotent)
        from datetime import datetime as datetime_class
        scrape_date_as_datetime = datetime_class.combine(
            data.scrape_date, datetime_class.min.time()
        ).replace(tzinfo=timezone.utc)
        self.delete_for_date_range(submenu, scrape_date_as_datetime, scrape_date_as_datetime)

        self._client.insert(
            f"{self._database}.{submenu}",
            rows,
            column_names=ch_columns,
        )
        logger.info(f"  {submenu}: inserted {len(rows)} rows into ClickHouse")
        return len(rows)

    def insert_all(
        self,
        all_data: List[SalesStatisticData],
        start_date: datetime,
        end_date: datetime,
        force_overwrite: bool = False,
    ) -> int:
        """
        Insert data for all submenus. Returns total rows inserted.
        Raises on connection errors; per-table errors are logged and skipped.

        Args:
            force_overwrite: Bypass history lock, overwrite existing rows.
                             Pass True for manual repair/backfill runs.
        """
        self._ensure_connected()
        total = 0
        for data in all_data:
            try:
                total += self.insert_submenu(data, start_date, end_date, force_overwrite=force_overwrite)
            except Exception as exc:
                logger.error(f"Failed to insert {data.submenu} into ClickHouse: {exc}")
        return total

    def insert_machines(self, result: MachineScrapingResult) -> int:
        """
        Insert machine records into machine table.

        Machine data is real-time snapshots taken every 30 minutes.
        Each run appends new rows — no deletion, so full history is preserved.

        Returns number of rows inserted.
        """
        self._ensure_connected()

        if not result.records:
            logger.info("  machine: 0 records, nothing to insert")
            return 0

        ch_columns = [
            "scrape_date",
            "scrape_timestamp",
            "machine_code",
            "machine_name",
            "temperature",
            "temperature_unit",
        ]
        rows: list[list] = []
        for rec in result.records:
            ts = rec.scrape_timestamp
            if ts.tzinfo is not None:
                ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
            rows.append([
                ts.date(),
                ts,
                rec.machine_code,
                rec.machine_name,
                rec.temperature,
                rec.temperature_unit,
            ])

        self._client.insert(
            f"{self._database}.machine",
            rows,
            column_names=ch_columns,
        )
        logger.info(f"  machine: inserted {len(rows)} rows into ClickHouse")
        return len(rows)
