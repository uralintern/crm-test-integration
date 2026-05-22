package models

import (
	"time"
)

type Attempt struct {
	AttemptID     uint      `gorm:"primaryKey"`
	InternID      uint      `gorm:"not null"`
	ApplicationID uint      `gorm:"not null"`
	ConfigID      uint      `gorm:"not null"`
	StartTime     time.Time `gorm:"not null"`
	EndTime       *time.Time
	Score         float64 `gorm:"default:0"`
	Passed        bool    `gorm:"default:false"`
	// Связи
	User        User        `gorm:"foreignKey:InternID;constraint:OnDelete:CASCADE;OnUpdate:CASCADE"`
	EventConfig EventConfig `gorm:"foreignKey:ConfigID;constraint:OnDelete:CASCADE;"`
	Answers     []Answer
}
