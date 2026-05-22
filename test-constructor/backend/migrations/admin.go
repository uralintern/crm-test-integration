package migrations

import (
	"errors"
	"log"
	"test-constructor/config"
	"test-constructor/internal/models"

	"gorm.io/gorm"
)

func SeedAdmin(db *gorm.DB) error {
	cfg := config.Load()

	var role models.Role
	if err := db.Where("code = ?", "admin").First(&role).Error; err != nil {
		return err
	}

	admin := models.User{
		Email:  cfg.AdminEmail,
		RoleID: role.ID,
		Role:   role,
	}

	err := admin.HashPassword(cfg.AdminPassword)
	if err != nil {
		return err
	}

	var existingAdmin models.User
	result := db.Where("email = ?", cfg.AdminEmail).First(&existingAdmin)
	if result.Error != nil && errors.Is(result.Error, gorm.ErrRecordNotFound) {
		if err := db.Create(&admin).Error; err != nil {
			return err
		}
		log.Printf("Админ создан")
	} else if result.Error == nil {
		log.Printf("Админ уже существует")
	} else {
		return result.Error
	}

	return nil
}
