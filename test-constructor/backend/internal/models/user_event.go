package models

type UserEvent struct {
	ID            uint `gorm:"primaryKey"`
	UserID        uint `gorm:"not null;uniqueIndex:idx_user_event"`
	EventID       uint `gorm:"not null;uniqueIndex:idx_user_event"`
	ApplicationID uint `gorm:"not null"`
	User          User `gorm:"foreignKey:UserID;constraint:OnDelete:CASCADE;OnUpdate:CASCADE"`
}
