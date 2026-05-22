package models

import "github.com/google/uuid"

type EventConfig struct {
	ConfigID         uint `gorm:"primaryKey"`
	EventID          uint `gorm:"not null"`
	TestID           uint `gorm:"not null"`
	SpecializationID uint
	CreatorID        uint `gorm:"not null"`
	SuccessText      string
	FailText         string
	TimeLimit        int       `gorm:"default:0"`
	TestLink         uuid.UUID `gorm:"type:uuid;default:gen_random_uuid()"`
	Threshold        float64
	ExtraThreshold   []ExtraThreshold `gorm:"foreignKey:ConfigID;constraint:OnDelete:CASCADE;OnUpdate:CASCADE"`
	Test             Test             `gorm:"foreignKey:TestID;constraint:OnDelete:CASCADE;OnUpdate:CASCADE"`
	User             User             `gorm:"foreignKey:CreatorID;constraint:OnDelete:CASCADE;OnUpdate:CASCADE"`
}
