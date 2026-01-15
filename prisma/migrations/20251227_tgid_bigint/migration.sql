-- Ensure users.tgId is BIGINT for Telegram IDs

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


