-- Complete migration script for referral system
-- Run this AFTER migrating credits to berries

-- Step 1: Create referrals table
CREATE TABLE IF NOT EXISTS "referrals" (
    "id" TEXT NOT NULL,
    "inviterId" TEXT NOT NULL,
    "inviteeId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdFrom" TEXT,
    "createdChatType" TEXT,

    CONSTRAINT "referrals_pkey" PRIMARY KEY ("id")
);

-- Step 2: Create referral_rewards table
CREATE TABLE IF NOT EXISTS "referral_rewards" (
    "id" TEXT NOT NULL,
    "referralId" TEXT NOT NULL,
    "inviterId" TEXT NOT NULL,
    "berriesRewarded" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "referral_rewards_pkey" PRIMARY KEY ("id")
);

-- Step 3: Create unique constraint on inviteeId (one inviter per invitee)
CREATE UNIQUE INDEX IF NOT EXISTS "referrals_inviteeId_key" ON "referrals"("inviteeId");

-- Step 4: Create unique constraint on referralId (one reward per referral)
CREATE UNIQUE INDEX IF NOT EXISTS "referral_rewards_referralId_key" ON "referral_rewards"("referralId");

-- Step 5: Create indexes
CREATE INDEX IF NOT EXISTS "referrals_inviterId_idx" ON "referrals"("inviterId");
CREATE INDEX IF NOT EXISTS "referrals_inviteeId_idx" ON "referrals"("inviteeId");
CREATE INDEX IF NOT EXISTS "referrals_createdAt_idx" ON "referrals"("createdAt");
CREATE INDEX IF NOT EXISTS "referral_rewards_inviterId_idx" ON "referral_rewards"("inviterId");
CREATE INDEX IF NOT EXISTS "referral_rewards_createdAt_idx" ON "referral_rewards"("createdAt");

-- Step 6: Add foreign key constraints
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

-- Step 7: Drop old columns (only if they exist and data is migrated)
DO $$ 
BEGIN
    -- Drop freeCreditsRemaining if exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'freeCreditsRemaining'
    ) THEN
        ALTER TABLE "users" DROP COLUMN "freeCreditsRemaining";
        RAISE NOTICE 'Dropped column freeCreditsRemaining';
    END IF;
    
    -- Drop paidCreditsRemaining if exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'paidCreditsRemaining'
    ) THEN
        ALTER TABLE "users" DROP COLUMN "paidCreditsRemaining";
        RAISE NOTICE 'Dropped column paidCreditsRemaining';
    END IF;
END $$;

