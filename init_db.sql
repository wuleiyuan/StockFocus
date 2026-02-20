-- 创建market_scan_results表
CREATE TABLE IF NOT EXISTS market_scan_results (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    current_price DECIMAL(10,2) DEFAULT 0,
    fair_price DECIMAL(10,2) DEFAULT 0,
    bias DECIMAL(8,2) DEFAULT 0,
    roe_5y DECIMAL(5,2) DEFAULT 0,
    mkt_cap BIGINT DEFAULT 0,
    industry VARCHAR(50),
    quality_score INTEGER DEFAULT 0,
    scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_bias ON market_scan_results(bias);
CREATE INDEX IF NOT EXISTS idx_roe_5y ON market_scan_results(roe_5y);
CREATE INDEX IF NOT EXISTS idx_industry ON market_scan_results(industry);
CREATE INDEX IF NOT EXISTS idx_quality_score ON market_scan_results(quality_score DESC);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_market_scan_results_updated_at 
    BEFORE UPDATE ON market_scan_results 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 插入一些示例数据（可选）
INSERT INTO market_scan_results (symbol, name, fair_price, roe_5y) VALUES
('600519', '贵州茅台', 1700.00, 25.5),
('000858', '五粮液', 180.00, 23.8),
('603288', '海天味业', 85.00, 28.2)
ON CONFLICT (symbol) DO NOTHING;