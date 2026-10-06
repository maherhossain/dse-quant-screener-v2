-- =====================================================================
-- DSE Quant Screener v2 — Initial Schema
-- =====================================================================
-- Module 0: Foundation
-- Created: 2026-10-06
-- Study start: 2013-01-28 (DSEX launch)
-- MySQL target: 8.0.30 (laptop) and 8.4.3 (office)
-- Storage: InnoDB, utf8mb4 / utf8mb4_0900_ai_ci
-- =====================================================================
-- ---------------------------------------------------------------------
-- Table 1: sectors
-- Source: endpoint #1 (stocknow.com.bd/api/v1/sectors), 23 rows + 1 synthetic (id 23 = Index)
-- ---------------------------------------------------------------------
CREATE TABLE sectors (
    id              INT             NOT NULL PRIMARY KEY,
    name            VARCHAR(64)     NOT NULL,
    is_index_bucket TINYINT(1)      NOT NULL DEFAULT 0,
    notes           VARCHAR(255)    NULL,
    CONSTRAINT uq_sectors_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 2: instruments
-- Source: endpoint #2 (bullbd /shares/get-names-tv) union endpoint #3 (stocknow /instruments)
-- Notes: type is NOT authoritative for equity classification — see audit entry 2.
--        category kept as filterable attribute; Z NOT excluded at load time.
-- ---------------------------------------------------------------------
CREATE TABLE instruments (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(32)     NOT NULL,
    name            VARCHAR(255)    NULL,
    sector_id       INT             NULL,
    type            VARCHAR(16)     NULL,
    category        VARCHAR(8)      NULL,
    is_sme          TINYINT(1)      NOT NULL DEFAULT 0,
    first_seen_date DATE            NULL,
    last_seen_date  DATE            NULL,
    source_primary  VARCHAR(32)     NOT NULL,
    source_notes    VARCHAR(255)    NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_instruments_code UNIQUE (code),
    CONSTRAINT fk_instruments_sector
        FOREIGN KEY (sector_id) REFERENCES sectors(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_instruments_type_cat (type, category),
    INDEX idx_instruments_sector (sector_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 3: daily_bars (equities)
-- Source: endpoint #7 (bullbd get-one-for-tv2) primary, endpoint #6 (stocknow history) gap-fill
-- Notes: prices are UNADJUSTED (as traded). Adjustment handled in Module 2 via corporate_actions.
--        volume = raw shares.
-- ---------------------------------------------------------------------
CREATE TABLE daily_bars (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    instrument_id   BIGINT UNSIGNED NOT NULL,
    trade_date      DATE            NOT NULL,
    open            DECIMAL(12,4)   NOT NULL,
    high            DECIMAL(12,4)   NOT NULL,
    low             DECIMAL(12,4)   NOT NULL,
    close           DECIMAL(12,4)   NOT NULL,
    volume          BIGINT UNSIGNED NOT NULL,
    price_adjusted  TINYINT(1)      NOT NULL DEFAULT 0,
    source          VARCHAR(16)     NOT NULL,
    source_ref      VARCHAR(64)     NULL,
    loaded_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_daily_bars_natkey UNIQUE (instrument_id, trade_date),
    CONSTRAINT fk_daily_bars_instrument
        FOREIGN KEY (instrument_id) REFERENCES instruments(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_daily_bars_ohlc
        CHECK (high >= low
               AND high >= open  AND high >= close
               AND low  <= open  AND low  <= close),
    CONSTRAINT chk_daily_bars_positive
        CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
    INDEX idx_daily_bars_date (trade_date),
    INDEX idx_daily_bars_inst_date (instrument_id, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 4a: indices (reference)
-- Broad indices: DSEX, DS30, DSES. Sector indices: 22 rows keyed by sector name.
-- valid_from filters pre-launch bars (DSEX pre-2013 is DGEN, not DSEX).
-- ---------------------------------------------------------------------
CREATE TABLE indices (
    id              INT             NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code            VARCHAR(32)     NOT NULL,
    name            VARCHAR(128)    NOT NULL,
    kind            VARCHAR(16)     NOT NULL,   -- 'broad' | 'sector'
    sector_id       INT             NULL,
    valid_from      DATE            NOT NULL,
    notes           VARCHAR(255)    NULL,
    CONSTRAINT uq_indices_code UNIQUE (code),
    CONSTRAINT fk_indices_sector
        FOREIGN KEY (sector_id) REFERENCES sectors(id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 4b: index_bars
-- Source: endpoint #7 for OHLC + volume_constituent, endpoint #6 for turnover_market_million
-- Notes: endpoint #6's DSEX 'v[4]' is turnover in BDT, NOT volume — divided by 1e6.
--        turnover_market_million populated only for broad indices.
-- ---------------------------------------------------------------------
CREATE TABLE index_bars (
    id                       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    index_id                 INT             NOT NULL,
    trade_date               DATE            NOT NULL,
    open                     DECIMAL(12,4)   NOT NULL,
    high                     DECIMAL(12,4)   NOT NULL,
    low                      DECIMAL(12,4)   NOT NULL,
    close                    DECIMAL(12,4)   NOT NULL,
    volume_constituent       BIGINT UNSIGNED NULL,
    turnover_market_million  DECIMAL(18,4)   NULL,
    source_ohlc              VARCHAR(16)     NOT NULL,
    source_volume            VARCHAR(16)     NULL,
    source_turnover          VARCHAR(16)     NULL,
    loaded_at                DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_index_bars_natkey UNIQUE (index_id, trade_date),
    CONSTRAINT fk_index_bars_index
        FOREIGN KEY (index_id) REFERENCES indices(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_index_bars_ohlc
        CHECK (high >= low
               AND high >= open  AND high >= close
               AND low  <= open  AND low  <= close),
    CONSTRAINT chk_index_bars_positive
        CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0),
    INDEX idx_index_bars_date (trade_date),
    INDEX idx_index_bars_idx_date (index_id, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 5: daily_snapshot
-- Source: endpoint #4 (bullbd get-once) primary, endpoint #3 (stocknow) fallback.
-- Forward-only. Fields not in historical bars: trades_count, turnover_million, halt_raw.
-- ---------------------------------------------------------------------
CREATE TABLE daily_snapshot (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    snapshot_date     DATE            NOT NULL,
    code              VARCHAR(32)     NOT NULL,
    instrument_id     BIGINT UNSIGNED NULL,
    category          VARCHAR(8)      NULL,
    type              VARCHAR(16)     NULL,
    open              DECIMAL(12,4)   NULL,
    high              DECIMAL(12,4)   NULL,
    low               DECIMAL(12,4)   NULL,
    close             DECIMAL(12,4)   NULL,
    ycp               DECIMAL(12,4)   NULL,
    trades_count      INT UNSIGNED    NULL,
    volume            BIGINT UNSIGNED NULL,
    turnover_million  DECIMAL(18,4)   NULL,
    halt_raw          VARCHAR(16)     NULL,
    source            VARCHAR(16)     NOT NULL,
    source_timestamp  DATETIME        NULL,
    source_ref        VARCHAR(64)     NULL,
    fetched_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_daily_snapshot_natkey UNIQUE (snapshot_date, code),
    CONSTRAINT fk_daily_snapshot_instrument
        FOREIGN KEY (instrument_id) REFERENCES instruments(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_daily_snapshot_date (snapshot_date),
    INDEX idx_daily_snapshot_code (code),
    INDEX idx_daily_snapshot_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 6: corporate_actions
-- Source: endpoint #8 (bullbd corporate-actions)
-- Notes: publish_date is a true timestamp; year_ended_on/agm_date/record_date shifted +1d
--        at load. agm_date sentinel '1969-12-31' filtered to NULL.
-- ---------------------------------------------------------------------
CREATE TABLE corporate_actions (
    id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code                   VARCHAR(32)     NOT NULL,
    instrument_id          BIGINT UNSIGNED NULL,
    news_id                VARCHAR(64)     NOT NULL,
    publish_date           DATE            NOT NULL,
    year_ended_on          DATE            NULL,
    agm_date               DATE            NULL,
    record_date            DATE            NULL,
    cash_pct               DECIMAL(12,4)   NULL,
    stock_pct              DECIMAL(12,4)   NULL,
    right_pct              DECIMAL(12,4)   NULL,
    premium                DECIMAL(12,4)   NULL,
    split_ratio            DECIMAL(12,4)   NULL,
    no_dividend            TINYINT(1)      NULL,
    record_date_confirmed  TINYINT(1)      NULL,
    source_provider        VARCHAR(16)     NOT NULL,
    source_ref             VARCHAR(64)     NULL,
    loaded_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_corporate_actions_natkey UNIQUE (instrument_id, news_id),
    CONSTRAINT fk_corporate_actions_instrument
        FOREIGN KEY (instrument_id) REFERENCES instruments(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_corporate_actions_code (code),
    INDEX idx_corporate_actions_record_date (record_date),
    INDEX idx_corporate_actions_publish_date (publish_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 7: block_trades
-- Source: endpoint #9 (bullbd get-block-share)
-- ⚠️ Coverage: 2023-06-21 onward. No historical data. H2 caveat documented.
-- ---------------------------------------------------------------------
CREATE TABLE block_trades (
    id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code                  VARCHAR(32)     NOT NULL,
    instrument_id         BIGINT UNSIGNED NULL,
    trade_date            DATE            NOT NULL,
    block_trade_count     INT UNSIGNED    NOT NULL,
    block_volume          BIGINT UNSIGNED NOT NULL,
    block_value_million   DECIMAL(18,4)   NOT NULL,
    block_min_price       DECIMAL(12,4)   NOT NULL,
    block_max_price       DECIMAL(12,4)   NOT NULL,
    source_provider       VARCHAR(16)     NOT NULL,
    source_ref            VARCHAR(64)     NULL,
    loaded_at             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_block_trades_natkey UNIQUE (instrument_id, trade_date),
    CONSTRAINT fk_block_trades_instrument
        FOREIGN KEY (instrument_id) REFERENCES instruments(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_block_trades_code (code),
    INDEX idx_block_trades_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 8: market_snapshot
-- Source: endpoint #10 (dse.com.bd/api/live/market)
-- Forward-only. Backfill partial rows from dailyTotals when available.
-- ---------------------------------------------------------------------
CREATE TABLE market_snapshot (
    id                     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    snapshot_date          DATE            NOT NULL,
    dsex_close             DECIMAL(12,4)   NULL,
    dsex_change            DECIMAL(12,4)   NULL,
    dsex_change_pct        DECIMAL(8,4)    NULL,
    ds30_close             DECIMAL(12,4)   NULL,
    ds30_change            DECIMAL(12,4)   NULL,
    ds30_change_pct        DECIMAL(8,4)    NULL,
    dses_close             DECIMAL(12,4)   NULL,
    dses_change            DECIMAL(12,4)   NULL,
    dses_change_pct        DECIMAL(8,4)    NULL,
    total_trades           INT UNSIGNED    NULL,
    total_volume           BIGINT UNSIGNED NULL,
    total_turnover_million DECIMAL(18,4)   NULL,
    market_cap_bdt         BIGINT UNSIGNED NULL,
    advanced               INT UNSIGNED    NULL,
    declined               INT UNSIGNED    NULL,
    unchanged              INT UNSIGNED    NULL,
    traded                 INT UNSIGNED    NULL,
    partial_row            TINYINT(1)      NOT NULL DEFAULT 0,
    source_provider        VARCHAR(16)     NOT NULL,
    source_ref             VARCHAR(64)     NULL,
    fetched_at             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_market_snapshot_date UNIQUE (snapshot_date),
    INDEX idx_market_snapshot_date (snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 9: trading_calendar
-- Derived from index_bars (DSEX) + market_snapshot presence.
-- Populated 2013-01-28 onward. Fri/Sat always non-trading.
-- ---------------------------------------------------------------------
CREATE TABLE trading_calendar (
    trade_date       DATE            NOT NULL PRIMARY KEY,
    is_trading_day   TINYINT(1)      NOT NULL,
    notes            VARCHAR(255)    NULL,
    created_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- ---------------------------------------------------------------------
-- Table 10: load_log
-- Audit trail for every load event. Written by Module 1 loaders.
-- ---------------------------------------------------------------------
CREATE TABLE load_log (
    id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id             VARCHAR(32)     NOT NULL,
    started_at         DATETIME        NOT NULL,
    finished_at        DATETIME        NULL,
    target_table       VARCHAR(64)     NOT NULL,
    source_provider    VARCHAR(32)     NOT NULL,
    source_endpoint    VARCHAR(255)    NULL,
    scope_date_from    DATE            NULL,
    scope_date_to      DATE            NULL,
    rows_inserted      INT UNSIGNED    NOT NULL DEFAULT 0,
    rows_skipped       INT UNSIGNED    NOT NULL DEFAULT 0,
    rows_failed        INT UNSIGNED    NOT NULL DEFAULT 0,
    status             VARCHAR(16)     NOT NULL,
    error_message      VARCHAR(1024)   NULL,
    git_commit_hash    CHAR(40)        NULL,
    hostname           VARCHAR(64)     NULL,
    raw_file_ref       VARCHAR(255)    NULL,
    notes              VARCHAR(255)    NULL,
    INDEX idx_load_log_started_at (started_at),
    INDEX idx_load_log_target_table_started (target_table, started_at),
    INDEX idx_load_log_status (status),
    INDEX idx_load_log_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- =====================================================================
-- End of schema
-- =====================================================================
