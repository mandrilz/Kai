-- Manual migration for referral system
-- Run this SQL directly on the database if prisma migrate dev fails

-- Create referrals table
CREATE TABLE IF NOT EXISTS "referrals" (
    "id" TEXT NOT NULL,
    "inviterId" TEXT NOT NULL,
    "inviteeId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdFrom" TEXT,
    "createdChatType" TEXT,

    CONSTRAINT "referrals_pkey" PRIMARY KEY ("id")
);

-- Create referral_rewards table
CREATE TABLE IF NOT EXISTS "referral_rewards" (
    "id" TEXT NOT NULL,
    "referralId" TEXT NOT NULL,
    "inviterId" TEXT NOT NULL,
    "berriesRewarded" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "referral_rewards_pkey" PRIMARY KEY ("id")
);

-- Create unique constraint on inviteeId (one inviter per invitee)
CREATE UNIQUE INDEX IF NOT EXISTS "referrals_inviteeId_key" ON "referrals"("inviteeId");

-- Create unique constraint on referralId (one reward per referral)
CREATE UNIQUE INDEX IF NOT EXISTS "referral_rewards_referralId_key" ON "referral_rewards"("referralId");

-- Create indexes
CREATE INDEX IF NOT EXISTS "referrals_inviterId_idx" ON "referrals"("inviterId");
CREATE INDEX IF NOT EXISTS "referrals_inviteeId_idx" ON "referrals"("inviteeId");
CREATE INDEX IF NOT EXISTS "referrals_createdAt_idx" ON "referrals"("createdAt");
CREATE INDEX IF NOT EXISTS "referral_rewards_inviterId_idx" ON "referral_rewards"("inviterId");
CREATE INDEX IF NOT EXISTS "referral_rewards_createdAt_idx" ON "referral_rewards"("createdAt");

-- Add foreign key constraints
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'referrals_inviterId_fkey'
    ) THEN
        ALTER TABLE "referrals" 
        ADD CONSTRAINT "referrals_inviterId_fkey" 
        FOREIGN KEY ("inviterId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'referrals_inviteeId_fkey'
    ) THEN
        ALTER TABLE "referrals" 
        ADD CONSTRAINT "referrals_inviteeId_fkey" 
        FOREIGN KEY ("inviteeId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'referral_rewards_referralId_fkey'
    ) THEN
        ALTER TABLE "referral_rewards" 
        ADD CONSTRAINT "referral_rewards_referralId_fkey" 
        FOREIGN KEY ("referralId") REFERENCES "referrals"("id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'referral_rewards_inviterId_fkey'
    ) THEN
        ALTER TABLE "referral_rewards" 
        ADD CONSTRAINT "referral_rewards_inviterId_fkey" 
        FOREIGN KEY ("inviterId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

