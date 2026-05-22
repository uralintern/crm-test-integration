package models

type ExtraThreshold struct {
	ExtraThresholdID uint `gorm:"primaryKey"`
	ConfigID         uint
	TestID           uint
	Threshold        float64 `gorm:"not null"`
	Message          string
	Test             Test `gorm:"foreignKey:TestID;constraint:OnDelete:CASCADE;"`
}
