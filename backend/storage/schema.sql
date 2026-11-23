-- ============================================================
-- Schéma MVP - System Monitoring (Oracle XE 21c, PDB XEPDB1)
-- S'exécute dans le schéma applicatif MONITOR_APP.
-- Idempotent : chaque création est conditionnée par un contrôle
-- sur le dictionnaire de données utilisateur.
-- ============================================================

DECLARE
    n NUMBER;
BEGIN
    -- ---------- Table 1 : machines ----------
    SELECT COUNT(*) INTO n FROM user_tables WHERE table_name = 'MACHINES';
    IF n = 0 THEN
        EXECUTE IMMEDIATE q'[
            CREATE TABLE machines (
                machine_id    NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                hostname      VARCHAR2(64)  NOT NULL,
                ip_address    VARCHAR2(45),
                os_info       VARCHAR2(128),
                cpu_cores     NUMBER,
                total_ram_mb  NUMBER,
                is_local      NUMBER(1) DEFAULT 1,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                CONSTRAINT uq_machine_hostname UNIQUE (hostname)
            )]';
    END IF;

    -- ---------- Table 2 : métriques collectées ----------
    SELECT COUNT(*) INTO n FROM user_tables WHERE table_name = 'METRICS';
    IF n = 0 THEN
        EXECUTE IMMEDIATE q'[
            CREATE TABLE metrics (
                metric_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                machine_id    NUMBER NOT NULL REFERENCES machines(machine_id),
                collected_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                cpu_percent   NUMBER(5,2),
                cpu_per_core  CLOB,
                ram_total_mb  NUMBER,
                ram_used_mb   NUMBER,
                ram_avail_mb  NUMBER,
                ram_percent   NUMBER(5,2),
                disk_total_gb NUMBER(10,2),
                disk_used_gb  NUMBER(10,2),
                disk_free_gb  NUMBER(10,2),
                disk_percent  NUMBER(5,2)
            )]';
    END IF;

    SELECT COUNT(*) INTO n FROM user_indexes WHERE index_name = 'IDX_METRICS_MACHINE_TIME';
    IF n = 0 THEN
        EXECUTE IMMEDIATE 'CREATE INDEX idx_metrics_machine_time ON metrics (machine_id, collected_at DESC)';
    END IF;

    SELECT COUNT(*) INTO n FROM user_indexes WHERE index_name = 'IDX_METRICS_TIME';
    IF n = 0 THEN
        EXECUTE IMMEDIATE 'CREATE INDEX idx_metrics_time ON metrics (collected_at DESC)';
    END IF;

    -- ---------- Table 3 : alertes ----------
    SELECT COUNT(*) INTO n FROM user_tables WHERE table_name = 'ALERTS';
    IF n = 0 THEN
        EXECUTE IMMEDIATE q'[
            CREATE TABLE alerts (
                alert_id      NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                machine_id    NUMBER NOT NULL REFERENCES machines(machine_id),
                alert_resource VARCHAR2(20) NOT NULL,
                alert_level   VARCHAR2(10) NOT NULL,
                message       VARCHAR2(500),
                value_percent NUMBER(5,2),
                threshold     NUMBER(5,2),
                status        VARCHAR2(10) DEFAULT 'OPEN' NOT NULL,
                notified      NUMBER(1) DEFAULT 0,
                started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                resolved_at   TIMESTAMP,
                CONSTRAINT ck_alert_level CHECK (alert_level IN ('WARNING','CRITICAL','NORMAL')),
                CONSTRAINT ck_alert_status CHECK (status IN ('OPEN','RESOLVED'))
            )]';
    END IF;

    SELECT COUNT(*) INTO n FROM user_indexes WHERE index_name = 'IDX_ALERTS_OPEN';
    IF n = 0 THEN
        EXECUTE IMMEDIATE 'CREATE INDEX idx_alerts_open ON alerts (status, alert_resource)';
    END IF;

    SELECT COUNT(*) INTO n FROM user_indexes WHERE index_name = 'IDX_ALERTS_TIME';
    IF n = 0 THEN
        EXECUTE IMMEDIATE 'CREATE INDEX idx_alerts_time ON alerts (started_at DESC)';
    END IF;
END;
/
