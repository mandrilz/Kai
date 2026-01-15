-- Migrate data from freeCreditsRemaining/paidCreditsRemaining to berries
-- Run this BEFORE applying the schema changes

-- Check if old columns exist and migrate data
DO $$ 
BEGIN
    -- Check if freeCreditsRemaining column exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'freeCreditsRemaining'
    ) THEN
        -- Migrate: berries = freeCreditsRemaining + paidCreditsRemaining (if exists)
        -- If paidCreditsRemaining doesn't exist, just use freeCreditsRemaining
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'paidCreditsRemaining'
        ) THEN
            -- Both columns exist - sum them
            UPDATE "users" 
            SET "berries" = COALESCE("freeCreditsRemaining", 0) + COALESCE("paidCreditsRemaining", 0)
            WHERE "freeCreditsRemaining" IS NOT NULL OR "paidCreditsRemaining" IS NOT NULL;
            
            RAISE NOTICE 'Migrated data: berries = freeCreditsRemaining + paidCreditsRemaining';
        ELSE
            -- Only freeCreditsRemaining exists
            UPDATE "users" 
            SET "berries" = COALESCE("freeCreditsRemaining", 0)
            WHERE "freeCreditsRemaining" IS NOT NULL;
            
            RAISE NOTICE 'Migrated data: berries = freeCreditsRemaining';
        END IF;
    ELSE
        RAISE NOTICE 'Column freeCreditsRemaining does not exist, skipping data migration';
    END IF;
END $$;

-- Show migration summary
SELECT 
    COUNT(*) as total_users,
    SUM(CASE WHEN "berries" > 0 THEN 1 ELSE 0 END) as users_with_berries,
    SUM("berries") as total_berries
FROM "users";

