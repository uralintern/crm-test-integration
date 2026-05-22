package models

import (
	"errors"

	"gorm.io/datatypes"
	"gorm.io/gorm"
)

type Question struct {
	gorm.Model
	TestID      uint
	Text        string
	Points      int
	Type        QType
	Options     datatypes.JSON
	OrderNumber int
	// Связи
	Test Test `gorm:"foreignKey:TestID;constraint:OnDelete:CASCADE;"`
}

type QType string

const (
	SingleChoice   QType = "single_choice"
	MultipleChoice QType = "multiple_choice"
	TextInput      QType = "text_input"
	Matching       QType = "matching"
	CorrectOrder   QType = "correct_order"
)

func ParseQType(s string) (QType, error) {
	qType := QType(s)
	switch qType {
	case SingleChoice, MultipleChoice, TextInput, Matching, CorrectOrder:
	default:
		return qType, errors.New("Неверный тип вопроса: " + s)
	}

	return qType, nil
}

type QuestionOptions struct {
	Choices       []ChoiceOption `json:"choice,omitempty"`
	MatchingPairs []MatchingPair `json:"matching,omitempty"`
	CorrectInput  []string       `json:"correct_input,omitempty"`
	CaseSensitive bool           `json:"case_sensitive,omitempty"`
	Sequence      []SequenceItem `json:"sequence,omitempty"`
}

type ChoiceOption struct {
	Text   string `json:"text"`
	IsTrue bool   `json:"is_true,omitempty"`
}

type MatchingPair struct {
	LeftColumn  string `json:"left"`
	RightColumn string `json:"right"`
}

type SequenceItem struct {
	Text  string `json:"text"`
	Order int    `json:"order"`
}
