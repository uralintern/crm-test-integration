package database

import (
	"fmt"
	"log"
	"test-constructor/config"
	"test-constructor/internal/models"
	"test-constructor/migrations"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

var DB *gorm.DB

func Connect() {
	cfg := config.Load()
	dsn := cfg.DatabaseURL
	if dsn == "" {
		dsn = fmt.Sprintf(
			"host=%s user=%s password=%s dbname=%s port=%s sslmode=disable",
			cfg.DBHost,
			cfg.DBUser,
			cfg.DBPassword,
			cfg.DBName,
			cfg.DBPort,
		)
	}

	connection, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		DisableForeignKeyConstraintWhenMigrating: true,
	})
	if err != nil {
		log.Fatal("database connection failed: ", err)
	}

	DB = connection

	err = DB.AutoMigrate(
		&models.User{},
		&models.Test{},
		&models.Question{},
		&models.Answer{},
		&models.Role{},
		&models.EventConfig{},
		&models.ExtraThreshold{},
		&models.Attempt{},
		&models.UserEvent{},
	)
	if err != nil {
		log.Fatal("database migration failed: ", err)
	}

	fixLegacyConstraints()

	if err := migrations.SeedRoles(DB); err != nil {
		log.Fatal("failed to seed roles: ", err)
	}

	if err := migrations.SeedAdmin(DB); err != nil {
		log.Fatal("failed to seed admin: ", err)
	}

	log.Println("database connected")
}

func fixLegacyConstraints() {
	if err := DB.Exec(`ALTER TABLE event_configs DROP CONSTRAINT IF EXISTS fk_attempts_event_config`).Error; err != nil {
		log.Fatal("failed to drop legacy event config constraint: ", err)
	}

	if err := DB.Exec(`ALTER TABLE attempts DROP CONSTRAINT IF EXISTS fk_attempts_event_config`).Error; err != nil {
		log.Fatal("failed to drop attempts event config constraint: ", err)
	}

	if err := DB.Exec(`
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_attempts_event_config'
          AND conrelid = 'attempts'::regclass
    ) THEN
        ALTER TABLE attempts
        ADD CONSTRAINT fk_attempts_event_config
        FOREIGN KEY (config_id)
        REFERENCES event_configs(config_id)
        ON DELETE CASCADE;
    END IF;
END
$$;
`).Error; err != nil {
		log.Fatal("failed to create attempts event config constraint: ", err)
	}
}
