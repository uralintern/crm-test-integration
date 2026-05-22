package models

import (
	"gorm.io/datatypes"
)

type Answer struct {
	AnswerID     uint           `gorm:"primary_key"`
	AttemptID    uint           `gorm:"not null"`
	QuestionID   uint           `gorm:"not null"`
	InternAnswer datatypes.JSON `gorm:"not null"`
	IsCorrect    bool           `gorm:"not null"`
	Points       float64        `gorm:"not null"`
	// Связи
	Question Question
	Attempt  Attempt
}
