-- CostGPT Schema

-- Customers
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT,
    plan TEXT NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- API Keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix) WHERE revoked_at IS NULL;

-- Usage Events
CREATE TABLE events (
    id UUID DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT now() NOT NULL,
    model TEXT NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    input_cost DECIMAL(10, 6) NOT NULL,
    output_cost DECIMAL(10, 6) NOT NULL,
    total_cost DECIMAL(10, 6) NOT NULL,
    duration_ms INT,
    user_id TEXT,
    feature TEXT,
    metadata JSONB DEFAULT '{}',

    PRIMARY KEY (id, timestamp)
);

-- TimescaleDB hypertable for time-series queries
SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE);

-- Indexes for common queries
CREATE INDEX idx_events_customer_time ON events(customer_id, timestamp DESC);
CREATE INDEX idx_events_user ON events(customer_id, user_id, timestamp DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_events_feature ON events(customer_id, feature, timestamp DESC) WHERE feature IS NOT NULL;
CREATE INDEX idx_events_model ON events(customer_id, model, timestamp DESC);

-- Daily aggregates (materialized for fast dashboard queries)
CREATE TABLE daily_costs (
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    model TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    feature TEXT NOT NULL DEFAULT '',
    total_calls INT DEFAULT 0,
    total_input_tokens BIGINT DEFAULT 0,
    total_output_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(12, 6) DEFAULT 0,

    PRIMARY KEY (customer_id, date, model, user_id, feature)
);

-- Function to update daily aggregates
CREATE OR REPLACE FUNCTION update_daily_costs()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO daily_costs (customer_id, date, model, user_id, feature, total_calls, total_input_tokens, total_output_tokens, total_cost)
    VALUES (
        NEW.customer_id,
        DATE(NEW.timestamp),
        NEW.model,
        COALESCE(NEW.user_id, ''),
        COALESCE(NEW.feature, ''),
        1,
        NEW.input_tokens,
        NEW.output_tokens,
        NEW.total_cost
    )
    ON CONFLICT (customer_id, date, model, user_id, feature)
    DO UPDATE SET
        total_calls = daily_costs.total_calls + 1,
        total_input_tokens = daily_costs.total_input_tokens + NEW.input_tokens,
        total_output_tokens = daily_costs.total_output_tokens + NEW.output_tokens,
        total_cost = daily_costs.total_cost + NEW.total_cost;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_daily_costs
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_daily_costs();
