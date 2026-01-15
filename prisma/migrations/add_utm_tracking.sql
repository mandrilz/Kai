-- Migration: Add UTM tracking tables
-- This migration adds UserTracking and TrackingEvent models for UTM source attribution

-- Create user_tracking table
CREATE TABLE IF NOT EXISTS "user_tracking" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "tgId" BIGINT NOT NULL,
    "firstSource" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "user_tracking_pkey" PRIMARY KEY ("id")
);

-- Create tracking_events table
CREATE TABLE IF NOT EXISTS "tracking_events" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "trackingId" TEXT,
    "eventType" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "metadata" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "tracking_events_pkey" PRIMARY KEY ("id")
);

-- Create unique constraints
CREATE UNIQUE INDEX IF NOT EXISTS "user_tracking_userId_key" ON "user_tracking"("userId");
CREATE UNIQUE INDEX IF NOT EXISTS "user_tracking_tgId_key" ON "user_tracking"("tgId");
CREATE UNIQUE INDEX IF NOT EXISTS "tracking_events_userId_eventType_key" ON "tracking_events"("userId", "eventType");

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS "user_tracking_firstSource_idx" ON "user_tracking"("firstSource");
CREATE INDEX IF NOT EXISTS "user_tracking_createdAt_idx" ON "user_tracking"("createdAt");
CREATE INDEX IF NOT EXISTS "tracking_events_eventType_idx" ON "tracking_events"("eventType");
CREATE INDEX IF NOT EXISTS "tracking_events_source_idx" ON "tracking_events"("source");
CREATE INDEX IF NOT EXISTS "tracking_events_createdAt_idx" ON "tracking_events"("createdAt");

-- Add foreign key constraints
ALTER TABLE "user_tracking" ADD CONSTRAINT "user_tracking_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "tracking_events" ADD CONSTRAINT "tracking_events_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "tracking_events" ADD CONSTRAINT "tracking_events_trackingId_fkey" FOREIGN KEY ("trackingId") REFERENCES "user_tracking"("id") ON DELETE SET NULL ON UPDATE CASCADE;

