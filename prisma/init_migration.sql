-- Initial migration for A2E Telegram Bot
-- Run this SQL if Prisma migrations don't work

-- Create users table
CREATE TABLE IF NOT EXISTS "users" (
    "id" TEXT NOT NULL,
    "tgId" BIGINT NOT NULL,
    "berries" INTEGER NOT NULL DEFAULT 1,
    "language" TEXT,
    "termsAccepted" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- Ensure new columns exist for upgraded deployments
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "berries" INTEGER NOT NULL DEFAULT 1;
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "language" TEXT;
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "termsAccepted" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "users" ALTER COLUMN "berries" SET DEFAULT 1;

-- Backfill berries from legacy columns if they exist
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'freeCreditsRemaining'
    ) AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'paidCreditsRemaining'
    ) THEN
        UPDATE "users"
        SET "berries" = COALESCE("freeCreditsRemaining", 0) + COALESCE("paidCreditsRemaining", 0);
    END IF;
END $$;

-- Ensure tgId type is BIGINT (Telegram user IDs can exceed 32-bit int)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'tgId'
          AND data_type <> 'bigint'
    ) THEN
        ALTER TABLE "users" ALTER COLUMN "tgId" TYPE BIGINT;
    END IF;
END $$;

-- Create payments table
CREATE TABLE IF NOT EXISTS "payments" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "tgId" BIGINT,
    "telegramPaymentChargeId" TEXT,
    "provider" TEXT NOT NULL DEFAULT 'telegram',
    "sku" TEXT NOT NULL,
    "amountRub" INTEGER NOT NULL,
    "creditsAdded" INTEGER NOT NULL,
    "payloadJson" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
);

-- Ensure new columns exist for upgraded deployments
ALTER TABLE "payments" ADD COLUMN IF NOT EXISTS "tgId" BIGINT;
ALTER TABLE "payments" ADD COLUMN IF NOT EXISTS "telegramPaymentChargeId" TEXT;

-- Backfill payments.tgId from users (if possible)
UPDATE "payments" p
SET "tgId" = u."tgId"
FROM "users" u
WHERE p."userId" = u."id"
  AND p."tgId" IS NULL;

-- Create unique index on tgId
CREATE UNIQUE INDEX IF NOT EXISTS "users_tgId_key" ON "users"("tgId");

-- Create foreign key
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'payments_userId_fkey'
    ) THEN
        ALTER TABLE "payments" ADD CONSTRAINT "payments_userId_fkey" 
        FOREIGN KEY ("userId") REFERENCES "users"("id") 
        ON DELETE CASCADE ON UPDATE CASCADE;
    END IF;
END $$;

-- Create Prisma migrations table (if needed)
CREATE TABLE IF NOT EXISTS "_prisma_migrations" (
    "id" VARCHAR(36) NOT NULL,
    "checksum" VARCHAR(64) NOT NULL,
    "finished_at" TIMESTAMP(3),
    "migration_name" VARCHAR(255) NOT NULL,
    "logs" TEXT,
    "rolled_back_at" TIMESTAMP(3),
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "applied_steps_count" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "_prisma_migrations_pkey" PRIMARY KEY ("id")
);

