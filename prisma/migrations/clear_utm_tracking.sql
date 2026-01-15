-- Clear UTM tracking data
-- This script removes all data from user_tracking and tracking_events tables

-- Clear tracking_events first (due to foreign key constraint)
DELETE FROM tracking_events;

-- Clear user_tracking
DELETE FROM user_tracking;

-- Verify tables are empty
SELECT COUNT(*) as tracking_events_count FROM tracking_events;
SELECT COUNT(*) as user_tracking_count FROM user_tracking;

