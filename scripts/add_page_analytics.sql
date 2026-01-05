-- Add page analytics tracking tables

-- Track page views and user interactions
CREATE TABLE IF NOT EXISTS page_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT NOT NULL,
    page_path TEXT NOT NULL,
    page_title TEXT,
    referrer TEXT,
    user_agent TEXT,
    ip_address INET,
    country_code VARCHAR(2),
    country_name TEXT,
    city TEXT,
    
    -- Visit tracking
    visit_duration_seconds INTEGER,
    max_scroll_depth_percent INTEGER,
    
    -- Engagement metrics
    clicks_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Track individual click events
CREATE TABLE IF NOT EXISTS click_events (
    id SERIAL PRIMARY KEY,
    page_analytics_id INTEGER REFERENCES page_analytics(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT NOT NULL,
    page_path TEXT NOT NULL,
    
    -- Click details
    element_type TEXT,  -- button, link, tab, etc.
    element_id TEXT,
    element_text TEXT,
    element_class TEXT,
    click_position_x INTEGER,
    click_position_y INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_page_analytics_user_id ON page_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_page_analytics_session_id ON page_analytics(session_id);
CREATE INDEX IF NOT EXISTS idx_page_analytics_page_path ON page_analytics(page_path);
CREATE INDEX IF NOT EXISTS idx_page_analytics_created_at ON page_analytics(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_click_events_page_analytics_id ON click_events(page_analytics_id);
CREATE INDEX IF NOT EXISTS idx_click_events_user_id ON click_events(user_id);
CREATE INDEX IF NOT EXISTS idx_click_events_session_id ON click_events(session_id);
CREATE INDEX IF NOT EXISTS idx_click_events_page_path ON click_events(page_path);
CREATE INDEX IF NOT EXISTS idx_click_events_element_type ON click_events(element_type);
CREATE INDEX IF NOT EXISTS idx_click_events_created_at ON click_events(created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE page_analytics IS 'Tracks page views and user interaction metrics';
COMMENT ON TABLE click_events IS 'Tracks individual click events for user behavior analysis';
COMMENT ON COLUMN page_analytics.max_scroll_depth_percent IS 'Maximum percentage of page scrolled (0-100)';
COMMENT ON COLUMN page_analytics.visit_duration_seconds IS 'How long user stayed on page in seconds';
