-- Add single berries balance to users and extend payments bookkeeping

-- Users: single balance field
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "berries" INTEGER NOT NULL DEFAULT 1;

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

-- Payments: store Telegram user id + charge id (for audit/refunds)
ALTER TABLE "payments" ADD COLUMN IF NOT EXISTS "tgId" BIGINT;
ALTER TABLE "payments" ADD COLUMN IF NOT EXISTS "telegramPaymentChargeId" TEXT;

-- Backfill payments.tgId from the user relation when possible
UPDATE "payments" p
SET "tgId" = u."tgId"
FROM "users" u
WHERE p."userId" = u."id"
  AND p."tgId" IS NULL;


