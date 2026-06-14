package intern

import (
	"encoding/json"
	"net/http"
	"strconv"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"
)

type TestSelectionResponse struct {
	EventID          uint                `json:"event_id"`
	SpecializationID uint                `json:"specialization_id"`
	ApplicationID    uint                `json:"application_id"`
	Tests            []TestSelectionInfo `json:"tests"`
	AllCompleted     bool                `json:"all_completed"`
}

type TestSelectionInfo struct {
	ConfigID    uint    `json:"config_id"`
	TestID      uint    `json:"test_id"`
	TestLink    string  `json:"test_link"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	TimeLimit   int     `json:"time_limit"`
	Status      string  `json:"status"`
	Score       float64 `json:"score,omitempty"`
	MaxScore    int     `json:"max_score,omitempty"`
	Passed      bool    `json:"passed,omitempty"`
	AttemptID   uint    `json:"attempt_id,omitempty"`
	IsExtra     bool    `json:"is_extra"`
	Message     string  `json:"message,omitempty"`
}

type extraTestRule struct {
	SourceConfigID uint
	Threshold      float64
	Message        string
}

// GetTestSelection returns all main and additional tests available for an application.
// @Summary Получить список тестов мероприятия
// @Security ApiKeyAuth
// @Tags intern
// @Produce json
// @Param event_id query int true "Event ID"
// @Param specialization_id query int false "Specialization ID"
// @Param application_id query int false "Application ID"
// @Success 200 {object} TestSelectionResponse
// @Failure 400 {object} map[string]string
// @Failure 401 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/intern/tests/selection [get]
func GetTestSelection(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Пользователь не авторизован", http.StatusUnauthorized)
		return
	}

	eventID, err := parseRequiredUintQuery(r, "event_id")
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	specializationID := parseOptionalUintQuery(r, "specialization_id")
	applicationID := parseOptionalUintQuery(r, "application_id")

	var configs []models.EventConfig
	query := database.DB.
		Preload("Test").
		Preload("Test.Questions").
		Preload("ExtraThreshold").
		Where("event_id = ?", eventID).
		Order("config_id ASC")
	if specializationID > 0 {
		query = query.Where("specialization_id = ?", specializationID)
	}
	if err := query.Find(&configs).Error; err != nil {
		http.Error(w, "Не удалось получить тесты", http.StatusInternalServerError)
		return
	}

	configIDs := make([]uint, 0, len(configs))
	rulesByTestID := make(map[uint][]extraTestRule)
	for _, config := range configs {
		configIDs = append(configIDs, config.ConfigID)
		for _, rule := range config.ExtraThreshold {
			rulesByTestID[rule.TestID] = append(rulesByTestID[rule.TestID], extraTestRule{
				SourceConfigID: config.ConfigID,
				Threshold:      rule.Threshold,
				Message:        rule.Message,
			})
		}
	}

	attemptsByConfig := make(map[uint]models.Attempt)
	if len(configIDs) > 0 {
		var attempts []models.Attempt
		attemptQuery := database.DB.
			Where("intern_id = ? AND config_id IN ?", claims.UserID, configIDs).
			Order("start_time ASC")
		if applicationID > 0 {
			attemptQuery = attemptQuery.Where("application_id = ?", applicationID)
		}
		if err := attemptQuery.Find(&attempts).Error; err != nil {
			http.Error(w, "Не удалось получить попытки", http.StatusInternalServerError)
			return
		}
		for _, attempt := range attempts {
			attemptsByConfig[attempt.ConfigID] = attempt
		}
	}

	tests := make([]TestSelectionInfo, 0, len(configs))
	allCompleted := len(configs) > 0
	for _, config := range configs {
		rules := rulesByTestID[config.TestID]
		isExtra := len(rules) > 0
		status := "available"
		message := ""

		if isExtra {
			status = "locked"
			for _, rule := range rules {
				sourceAttempt, exists := attemptsByConfig[rule.SourceConfigID]
				if exists && sourceAttempt.EndTime != nil && !sourceAttempt.Passed && sourceAttempt.Score >= rule.Threshold {
					status = "available"
					message = rule.Message
					break
				}
			}
		}

		maxScore := 0
		for _, question := range config.Test.Questions {
			maxScore += question.Points
		}

		info := TestSelectionInfo{
			ConfigID:    config.ConfigID,
			TestID:      config.TestID,
			TestLink:    config.TestLink.String(),
			Title:       config.Test.Title,
			Description: config.Test.Description,
			TimeLimit:   config.TimeLimit,
			Status:      status,
			MaxScore:    maxScore,
			IsExtra:     isExtra,
			Message:     message,
		}

		if attempt, exists := attemptsByConfig[config.ConfigID]; exists {
			info.AttemptID = attempt.AttemptID
			info.Score = attempt.Score
			if attempt.MaxScore > 0 {
				info.MaxScore = attempt.MaxScore
			}
			info.Passed = attempt.Passed
			if attempt.EndTime == nil {
				info.Status = "in_progress"
			} else {
				info.Status = "completed"
			}
		}

		if !isExtra && info.Status != "completed" {
			allCompleted = false
		}
		if isExtra && info.Status != "locked" && info.Status != "completed" {
			allCompleted = false
		}
		tests = append(tests, info)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(TestSelectionResponse{
		EventID:          eventID,
		SpecializationID: specializationID,
		ApplicationID:    applicationID,
		Tests:            tests,
		AllCompleted:     allCompleted,
	})
}

func hasAccessToExtraConfig(userID, applicationID uint, config models.EventConfig) bool {
	var sourceConfigs []models.EventConfig
	query := database.DB.
		Preload("ExtraThreshold").
		Where("event_id = ? AND specialization_id = ?", config.EventID, config.SpecializationID)
	if err := query.Find(&sourceConfigs).Error; err != nil {
		return false
	}

	matchedRule := false
	for _, sourceConfig := range sourceConfigs {
		for _, rule := range sourceConfig.ExtraThreshold {
			if rule.TestID != config.TestID {
				continue
			}
			matchedRule = true
			var attempt models.Attempt
			attemptQuery := database.DB.
				Where("intern_id = ? AND config_id = ? AND end_time IS NOT NULL", userID, sourceConfig.ConfigID)
			if applicationID > 0 {
				attemptQuery = attemptQuery.Where("application_id = ?", applicationID)
			}
			if err := attemptQuery.Order("start_time DESC").First(&attempt).Error; err == nil && !attempt.Passed && attempt.Score >= rule.Threshold {
				return true
			}
		}
	}

	return !matchedRule
}

func parseRequiredUintQuery(r *http.Request, key string) (uint, error) {
	value := r.URL.Query().Get(key)
	parsed, err := strconv.ParseUint(value, 10, 32)
	if err != nil || parsed == 0 {
		return 0, &queryParameterError{key: key}
	}
	return uint(parsed), nil
}

func parseOptionalUintQuery(r *http.Request, key string) uint {
	value := r.URL.Query().Get(key)
	parsed, err := strconv.ParseUint(value, 10, 32)
	if err != nil {
		return 0
	}
	return uint(parsed)
}

type queryParameterError struct {
	key string
}

func (err *queryParameterError) Error() string {
	return err.key + " должен быть положительным числом"
}
