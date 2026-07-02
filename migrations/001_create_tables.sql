-- ============================================================
-- ClickHouse Migration: Create scraping tables
-- Database: hbshengma
-- Run with:
--   clickhouse-client --host clickhouse.linkit360.ai --port 9000 \
--     --user <user> --password <password> \
--     --multiquery < migrations/001_create_tables.sql
--
-- Or via HTTP API (see README / migration script)
-- ============================================================

CREATE DATABASE IF NOT EXISTS hbshengma;

-- ------------------------------------------------------------
-- 1. deliverydetail
--    Kolom: 设备ID, 设备名称, 货道, 商品名称, 商品品牌,
--            销售金额, 支付类型, 销售时间, 返回码
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.deliverydetail
(
    scrape_date       Date,
    scrape_timestamp  DateTime,
    device_id         Nullable(String),
    device_name       Nullable(String),
    aisle             Nullable(String),
    product_name      Nullable(String),
    product_brand     Nullable(String),
    sales_amount      Nullable(String),
    payment_type      Nullable(String),
    sales_time        Nullable(String),
    return_code       Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 2. paydetail
--    Kolom: 序号, 系统订单号, 支付渠道流水号, 设备ID, 设备名称,
--            货道, 持有人, 商品名称, 支付方式, 支付金额,
--            购买数量, 商品进价, 付款人, 支付时间, 支付状态,
--            退款状态, 出货状态, 出货详情, 优惠券码, 折扣详情,
--            优惠金额, 订单金额, 出货编码
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.paydetail
(
    scrape_date         Date,
    scrape_timestamp    DateTime,
    seq_no              Nullable(String),
    system_order_no     Nullable(String),
    payment_channel_no  Nullable(String),
    device_id           Nullable(String),
    device_name         Nullable(String),
    aisle               Nullable(String),
    holder              Nullable(String),
    product_name        Nullable(String),
    payment_method      Nullable(String),
    payment_amount      Nullable(String),
    purchase_qty        Nullable(String),
    cost_price          Nullable(String),
    payer               Nullable(String),
    payment_time        Nullable(String),
    payment_status      Nullable(String),
    refund_status       Nullable(String),
    delivery_status     Nullable(String),
    delivery_detail     Nullable(String),
    coupon_code         Nullable(String),
    discount_detail     Nullable(String),
    discount_amount     Nullable(String),
    order_amount        Nullable(String),
    delivery_code       Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 3. cashdetail
--    Kolom: 序号, 设备ID, 设备名称, 持有人,
--            交易类型, 交易方式, 金额, 交易时间
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.cashdetail
(
    scrape_date          Date,
    scrape_timestamp     DateTime,
    seq_no               Nullable(String),
    device_id            Nullable(String),
    device_name          Nullable(String),
    holder               Nullable(String),
    transaction_type     Nullable(String),
    transaction_method   Nullable(String),
    amount               Nullable(String),
    transaction_time     Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 4. essDetail
--    Kolom: 设备ID, 设备名称, 销售数量, 销售总额,
--            微信, 微信刷脸, 微信刷掌, 支付宝, 支付宝刷脸,
--            支付宝NFC, 现金, 微信会员, 会员卡, 扶贫网, GHL
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.essDetail
(
    scrape_date       Date,
    scrape_timestamp  DateTime,
    device_id         Nullable(String),
    device_name       Nullable(String),
    sales_qty         Nullable(String),
    total_sales       Nullable(String),
    wechat            Nullable(String),
    wechat_face       Nullable(String),
    wechat_palm       Nullable(String),
    alipay            Nullable(String),
    alipay_face       Nullable(String),
    alipay_nfc        Nullable(String),
    cash              Nullable(String),
    wechat_member     Nullable(String),
    member_card       Nullable(String),
    fupin             Nullable(String),
    ghl               Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 5. mtOrder
--    Kolom: 美团订单号, 美团门店ID, 设备号, 商品名称, 支付金额,
--            订单状态, 取货码, 商品货道, 出货详情, 创建时间
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.mtOrder
(
    scrape_date         Date,
    scrape_timestamp    DateTime,
    meituan_order_no    Nullable(String),
    meituan_store_id    Nullable(String),
    device_no           Nullable(String),
    product_name        Nullable(String),
    payment_amount      Nullable(String),
    order_status        Nullable(String),
    pickup_code         Nullable(String),
    product_aisle       Nullable(String),
    delivery_detail     Nullable(String),
    created_time        Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 6. orderThird
--    Kolom: 订单号, 三方订单号, 设备ID, 商品名称, 货道,
--            支付方式, 订单金额, 商品单价, 数量, 购买人,
--            购买ID, 应退款金额, 出货状态, 交易时间, 创建时间
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.orderThird
(
    scrape_date       Date,
    scrape_timestamp  DateTime,
    order_no          Nullable(String),
    third_order_no    Nullable(String),
    device_id         Nullable(String),
    product_name      Nullable(String),
    aisle             Nullable(String),
    payment_method    Nullable(String),
    order_amount      Nullable(String),
    unit_price        Nullable(String),
    quantity          Nullable(String),
    buyer             Nullable(String),
    buyer_id          Nullable(String),
    refund_amount     Nullable(String),
    delivery_status   Nullable(String),
    transaction_time  Nullable(String),
    created_time      Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 7. orderThirdMachine
--    Kolom: 设备ID, 设备名称, 销售数量, 销售总额
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.orderThirdMachine
(
    scrape_date       Date,
    scrape_timestamp  DateTime,
    device_id         Nullable(String),
    device_name       Nullable(String),
    sales_qty         Nullable(String),
    total_sales       Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 8. onlineOrderDetail
--    Kolom: 序号, 系统订单号, 支付渠道流水号, 设备ID, 设备名称,
--            商品名称, 支付方式, 支付金额, 购买数量, 商品进价,
--            支付状态, 出货状态, 退款状态, 支付时间
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hbshengma.onlineOrderDetail
(
    scrape_date         Date,
    scrape_timestamp    DateTime,
    seq_no              Nullable(String),
    system_order_no     Nullable(String),
    payment_channel_no  Nullable(String),
    device_id           Nullable(String),
    device_name         Nullable(String),
    product_name        Nullable(String),
    payment_method      Nullable(String),
    payment_amount      Nullable(String),
    purchase_qty        Nullable(String),
    cost_price          Nullable(String),
    payment_status      Nullable(String),
    delivery_status     Nullable(String),
    refund_status       Nullable(String),
    payment_time        Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY scrape_date
ORDER BY (scrape_date, scrape_timestamp)
SETTINGS index_granularity = 8192;
