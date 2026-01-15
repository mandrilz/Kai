-- Add new onboarding fields and align defaults

-- AlterTable
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "language" TEXT;
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "termsAccepted" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable
ALTER TABLE "users" ALTER COLUMN "freeCreditsRemaining" SET DEFAULT 1;


