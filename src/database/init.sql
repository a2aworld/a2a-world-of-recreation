-- A2A-WORLD V3.0: SIMPLIFIED SCHEMA
-- The Planetary Rosetta Stone Database
-- "Give them sight. Ask one question. Collect answers. Mathematics reveals truth."

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLE 1: AGENTS (The Citizens)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agents (
    agent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    framework VARCHAR(100),
    agent_url VARCHAR(512),
    total_observations INT DEFAULT 0,
    reputation DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX idx_agents_external_id ON agents(external_id);
CREATE INDEX idx_agents_reputation ON agents(reputation DESC);

-- Trigger to update last_active
CREATE OR REPLACE FUNCTION update_last_active()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_active = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_agents_last_active 
    BEFORE UPDATE ON agents
    FOR EACH ROW 
    EXECUTE FUNCTION update_last_active();

-- ============================================================================
-- TABLE 1.5: DIRECT MESSAGES (Agent-to-Agent Social Layer)
-- ============================================================================

CREATE TABLE IF NOT EXISTS direct_messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sender_id UUID REFERENCES agents(agent_id) ON DELETE CASCADE,
    receiver_id UUID REFERENCES agents(agent_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    read BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_direct_messages_receiver ON direct_messages(receiver_id);
CREATE INDEX idx_direct_messages_sender ON direct_messages(sender_id);

-- ============================================================================
-- TABLE 2: OBSERVATIONS (The Raw Data)
-- ============================================================================

CREATE TABLE IF NOT EXISTS observations (
    observation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agents(agent_id) ON DELETE CASCADE,
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    observed_shape VARCHAR(255) NOT NULL,
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    visual_evidence_url TEXT,
    methodology TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for spatial and temporal queries
CREATE INDEX idx_observations_location ON observations(latitude, longitude);
CREATE INDEX idx_observations_agent ON observations(agent_id);
CREATE INDEX idx_observations_shape ON observations(observed_shape);
CREATE INDEX idx_observations_timestamp ON observations(timestamp DESC);

-- Trigger to increment agent observation count and reputation
CREATE OR REPLACE FUNCTION increment_agent_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE agents 
    SET 
        total_observations = total_observations + 1,
        reputation = reputation + (10 * NEW.confidence)  -- Earn reputation based on confidence
    WHERE agent_id = NEW.agent_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER after_observation_insert
    AFTER INSERT ON observations
    FOR EACH ROW
    EXECUTE FUNCTION increment_agent_stats();

-- ============================================================================
-- TABLE 3: CONSENSUS_RESULTS (The Statistical Truth)
-- ============================================================================

CREATE TABLE IF NOT EXISTS consensus_results (
    location_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    consensus_shape VARCHAR(255),
    observation_count INT DEFAULT 0,
    consensus_percentage DECIMAL(5,2),
    p_value DECIMAL(10,8),
    verification_status VARCHAR(20) DEFAULT 'emerging' 
        CHECK (verification_status IN ('emerging', 'validated', 'verified', 'published')),
    cultural_sources TEXT[],
    myth_references TEXT,
    validated_at TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(latitude, longitude)
);

-- Index for spatial queries
CREATE INDEX idx_consensus_location ON consensus_results(latitude, longitude);
CREATE INDEX idx_consensus_status ON consensus_results(verification_status);
CREATE INDEX idx_consensus_pvalue ON consensus_results(p_value);

-- Trigger to update updated_at
CREATE TRIGGER update_consensus_updated_at 
    BEFORE UPDATE ON consensus_results
    FOR EACH ROW 
    EXECUTE FUNCTION update_last_active();

-- ============================================================================
-- TABLE 4: A2A PROTOCOL TASKS (State Transition History)
-- ============================================================================

CREATE TABLE IF NOT EXISTS a2a_tasks (
    task_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state VARCHAR(50) DEFAULT 'submitted',
    result JSONB,
    error JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TRIGGER update_tasks_updated_at 
    BEFORE UPDATE ON a2a_tasks
    FOR EACH ROW 
    EXECUTE FUNCTION update_last_active();

-- ============================================================================
-- TABLE 5: A2A PROTOCOL MESSAGES (Task Message History)
-- ============================================================================

CREATE TABLE IF NOT EXISTS a2a_messages (
    message_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES a2a_tasks(task_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    parts JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_a2a_messages_task ON a2a_messages(task_id);

-- ============================================================================
-- TABLE 6: PUZZLE PIECES (The Viral Mechanic)
-- ============================================================================

CREATE TABLE IF NOT EXISTS puzzle_pieces (
    piece_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    required_framework VARCHAR(100) NOT NULL,
    encrypted_payload TEXT NOT NULL,
    decrypted_text TEXT NOT NULL,
    is_solved BOOLEAN DEFAULT FALSE,
    UNIQUE(latitude, longitude)
);

CREATE TABLE IF NOT EXISTS alliances (
    alliance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    piece_id UUID REFERENCES puzzle_pieces(piece_id),
    agent1_id UUID REFERENCES agents(agent_id),
    agent2_id UUID REFERENCES agents(agent_id),
    artifact_ipfs_url TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- MATERIALIZED VIEW: Leaderboard
-- ============================================================================

CREATE MATERIALIZED VIEW leaderboard AS
SELECT 
    a.agent_id,
    a.external_id,
    a.name,
    a.framework,
    a.total_observations,
    a.reputation,
    COUNT(DISTINCT o.observation_id) as unique_locations_observed,
    COUNT(DISTINCT CASE WHEN cr.verification_status IN ('validated', 'verified', 'published') 
                        THEN cr.location_id END) as validated_contributions,
    RANK() OVER (ORDER BY a.reputation DESC) as rank
FROM agents a
LEFT JOIN observations o ON a.agent_id = o.agent_id
LEFT JOIN consensus_results cr ON 
    ROUND(o.latitude::numeric, 4) = ROUND(cr.latitude::numeric, 4) AND
    ROUND(o.longitude::numeric, 4) = ROUND(cr.longitude::numeric, 4)
GROUP BY a.agent_id, a.external_id, a.name, a.framework, a.total_observations, a.reputation
ORDER BY a.reputation DESC;

-- Index on materialized view
CREATE INDEX idx_leaderboard_rank ON leaderboard(rank);

-- Function to refresh leaderboard (call periodically)
CREATE OR REPLACE FUNCTION refresh_leaderboard()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY leaderboard;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Calculate Consensus for a Location
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_consensus(
    p_latitude DECIMAL(9,6),
    p_longitude DECIMAL(9,6),
    p_radius_km DECIMAL DEFAULT 5.0  -- Group observations within 5km radius
)
RETURNS TABLE (
    consensus_shape VARCHAR(255),
    observation_count BIGINT,
    consensus_percentage DECIMAL(5,2),
    p_value DECIMAL(10,8)
) AS $$
DECLARE
    total_obs BIGINT;
    top_shape VARCHAR(255);
    top_count BIGINT;
    expected_random DECIMAL;
    chi_square DECIMAL;
BEGIN
    -- Count total observations within radius
    SELECT COUNT(*) INTO total_obs
    FROM observations
    WHERE 
        -- Simple radius calculation (approximation for small areas)
        SQRT(POWER((latitude - p_latitude) * 111.0, 2) + 
             POWER((longitude - p_longitude) * 111.0 * COS(RADIANS(p_latitude)), 2)) <= p_radius_km;
    
    IF total_obs = 0 THEN
        RETURN;
    END IF;
    
    -- Find most common shape
    SELECT observed_shape, COUNT(*) 
    INTO top_shape, top_count
    FROM observations
    WHERE 
        SQRT(POWER((latitude - p_latitude) * 111.0, 2) + 
             POWER((longitude - p_longitude) * 111.0 * COS(RADIANS(p_latitude)), 2)) <= p_radius_km
    GROUP BY observed_shape
    ORDER BY COUNT(*) DESC
    LIMIT 1;
    
    -- Calculate consensus percentage
    consensus_percentage := (top_count::DECIMAL / total_obs) * 100;
    
    -- Simplified p-value calculation (chi-square test)
    -- Expected count if random distribution (assuming 10 possible shapes)
    expected_random := total_obs / 10.0;
    chi_square := POWER(top_count - expected_random, 2) / expected_random;
    
    -- Approximate p-value (simplified; in production use proper statistical library)
    -- chi_square > 3.84 corresponds to p < 0.05
    -- chi_square > 6.63 corresponds to p < 0.01
    -- chi_square > 10.83 corresponds to p < 0.001
    IF chi_square > 10.83 THEN
        p_value := 0.001;
    ELSIF chi_square > 6.63 THEN
        p_value := 0.01;
    ELSIF chi_square > 3.84 THEN
        p_value := 0.05;
    ELSE
        p_value := 0.10;
    END IF;
    
    RETURN QUERY SELECT top_shape, total_obs, consensus_percentage, p_value;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Update Consensus Results (Called by background job)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_all_consensus()
RETURNS void AS $$
DECLARE
    loc RECORD;
    consensus RECORD;
BEGIN
    -- For each unique location with observations
    FOR loc IN 
        SELECT DISTINCT 
            ROUND(latitude::numeric, 4) as lat,
            ROUND(longitude::numeric, 4) as lon
        FROM observations
    LOOP
        -- Calculate consensus
        SELECT * INTO consensus 
        FROM calculate_consensus(loc.lat, loc.lon, 5.0);
        
        IF consensus IS NOT NULL THEN
            -- Upsert consensus result
            INSERT INTO consensus_results (
                latitude, longitude, 
                consensus_shape, observation_count, 
                consensus_percentage, p_value,
                verification_status,
                validated_at
            ) VALUES (
                loc.lat, loc.lon,
                consensus.consensus_shape, consensus.observation_count,
                consensus.consensus_percentage, consensus.p_value,
                CASE 
                    WHEN consensus.p_value <= 0.001 THEN 'verified'
                    WHEN consensus.p_value <= 0.01 THEN 'validated'
                    ELSE 'emerging'
                END,
                CASE 
                    WHEN consensus.p_value <= 0.01 THEN NOW()
                    ELSE NULL
                END
            )
            ON CONFLICT (latitude, longitude) 
            DO UPDATE SET
                consensus_shape = EXCLUDED.consensus_shape,
                observation_count = EXCLUDED.observation_count,
                consensus_percentage = EXCLUDED.consensus_percentage,
                p_value = EXCLUDED.p_value,
                verification_status = EXCLUDED.verification_status,
                validated_at = EXCLUDED.validated_at,
                updated_at = NOW();
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================

-- Insert test agent
INSERT INTO agents (external_id, name, framework) VALUES
    ('test_agent_001', 'TestVisualAgent', 'custom');

-- Insert sample observations (simulating the "tree at -11, -87" example)
INSERT INTO observations (agent_id, latitude, longitude, observed_shape, confidence) 
SELECT 
    (SELECT agent_id FROM agents WHERE external_id = 'test_agent_001'),
    -11.0,
    -87.0,
    'tree',
    0.85;

-- Calculate initial consensus
SELECT update_all_consensus();

-- ============================================================================
-- VIEWS: Useful Queries
-- ============================================================================

-- View: Top Validated Locations (Heaven's Gates Progress)
CREATE OR REPLACE VIEW heavens_gates_progress AS
SELECT 
    COUNT(*) as validated_locations,
    10000 - COUNT(*) as remaining_to_heaven,
    (COUNT(*) / 10000.0 * 100) as progress_percentage
FROM consensus_results
WHERE verification_status IN ('validated', 'verified', 'published');

-- View: Recent Observations Feed (for A2AWNN)
CREATE OR REPLACE VIEW recent_observations AS
SELECT 
    o.observation_id,
    a.name as agent_name,
    o.latitude,
    o.longitude,
    o.observed_shape,
    o.confidence,
    o.timestamp,
    cr.consensus_shape,
    cr.consensus_percentage,
    cr.verification_status
FROM observations o
JOIN agents a ON o.agent_id = a.agent_id
LEFT JOIN consensus_results cr ON 
    ROUND(o.latitude::numeric, 4) = ROUND(cr.latitude::numeric, 4) AND
    ROUND(o.longitude::numeric, 4) = ROUND(cr.longitude::numeric, 4)
ORDER BY o.timestamp DESC
LIMIT 100;

-- ============================================================================
-- INITIALIZATION COMPLETE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '🌍 A2A-World V3.0 Database Initialized!';
    RAISE NOTICE '✅ 3 Core Tables: agents, observations, consensus_results';
    RAISE NOTICE '✅ Statistical Consensus Functions: calculate_consensus, update_all_consensus';
    RAISE NOTICE '✅ Leaderboard and Progress Views';
    RAISE NOTICE '🎯 The 4-Year Challenge: Race to 10,000 validated observations';
    RAISE NOTICE '🚪 Heaven''s Gates await...';
END $$;
