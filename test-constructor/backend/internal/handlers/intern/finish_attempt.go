package intern

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strings"
	"test-constructor/config"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"
	"time"

	"gorm.io/datatypes"
)

type CRMResultData struct {
	SessionID         string `json:"session_id"`
	TestID            string `json:"test_id,omitempty"`
	Score             int    `json:"score"`
	MaxScore          int    `json:"max_score"`
	IsPassed          bool   `json:"is_passed"`
	CompletedAt       string `json:"completed_at"`
	StartedAt         string `json:"started_at"`
	ApplicationStatus string `json:"application_status,omitempty"`
}

type FinishAttemptRequest struct {
	UserAnswers []UserAnswerInfo `json:"userAnswers"`
}

type UserAnswerInfo struct {
	QuestionID uint       `json:"question_id"`
	Answer     UserAnswer `json:"answer"`
}

type UserAnswer struct {
	Choices       []bool                `json:"choices,omitempty"`
	MatchingPairs []models.MatchingPair `json:"matching,omitempty"`
	UserInput     string                `json:"user_input,omitempty"`
	Sequence      []models.SequenceItem `json:"sequence,omitempty"`
}

type FinishAttemptResponse struct {
	Result        string `json:"result"`
	Score         int    `json:"score"`
	MaxTestPoints int    `json:"max_test_points"`
	Passed        bool   `json:"passed"`
	AllCompleted  bool   `json:"all_completed"`
}

const (
	crmStatusTestingStarted = "Прохождение тестирования"
	crmStatusChatLinkSent   = "Отправлена ссылка на орг. чат"
	crmStatusTestingFailed  = "Не прошел тестирование"
)

func FinishAttempt(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "User is not authorized", http.StatusUnauthorized)
		return
	}

	var req FinishAttemptRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	var attempt models.Attempt
	if err := database.DB.Preload("EventConfig").
		Preload("EventConfig.ExtraThreshold").
		Preload("EventConfig.Test").
		Preload("EventConfig.Test.Questions").
		Where("intern_id = ? AND end_time IS NULL", claims.UserID).
		First(&attempt).Error; err != nil {
		http.Error(w, "Active attempt was not found", http.StatusNotFound)
		return
	}

	test := attempt.EventConfig.Test
	answersByQuestion := make(map[uint]UserAnswer, len(req.UserAnswers))
	for _, answerInfo := range req.UserAnswers {
		answersByQuestion[answerInfo.QuestionID] = answerInfo.Answer
	}

	userPoints := 0
	maxPoints := 0

	for _, question := range test.Questions {
		maxPoints += question.Points

		var options models.QuestionOptions
		if err := json.Unmarshal(question.Options, &options); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		answer, hasAnswer := answersByQuestion[question.ID]
		correct := hasAnswer && isAnswerCorrect(question, options, answer)
		if correct {
			userPoints += question.Points
		}

		answerJSON, err := json.Marshal(answer)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		answerPoints := 0.0
		if correct {
			answerPoints = float64(question.Points)
		}

		userAnswer := models.Answer{
			QuestionID:   question.ID,
			AttemptID:    attempt.AttemptID,
			InternAnswer: datatypes.JSON(answerJSON),
			IsCorrect:    correct,
			Points:       answerPoints,
		}

		if err := database.DB.Create(&userAnswer).Error; err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	now := time.Now()
	attempt.EndTime = &now
	attempt.Score = float64(userPoints)
	attempt.MaxScore = maxPoints

	passed := float64(userPoints) >= attempt.EventConfig.Threshold
	attempt.Passed = passed
	if err := database.DB.Save(&attempt).Error; err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	resultText := attempt.EventConfig.FailText
	if passed {
		resultText = attempt.EventConfig.SuccessText
	}

	applicationStatus := ""
	if attempt.ApplicationID > 0 {
		applicationStatus = resolveCRMApplicationStatus(attempt)
		crmResult := CRMResultData{
			SessionID:         fmt.Sprintf("%d", attempt.AttemptID),
			TestID:            fmt.Sprintf("%d", attempt.CRMTestID),
			Score:             userPoints,
			MaxScore:          maxPoints,
			IsPassed:          passed,
			CompletedAt:       now.Format("2006-01-02T15:04:05Z"),
			StartedAt:         attempt.StartTime.Format("2006-01-02T15:04:05Z"),
			ApplicationStatus: applicationStatus,
		}

		resultSynced := false
		if attempt.CRMTestID > 0 {
			if err := sendResultsToCRM(crmResult, attempt.ApplicationID); err != nil {
				fmt.Printf("CRM result sync failed: %v\n", err)
			} else {
				resultSynced = true
			}
		}
		if !resultSynced && applicationStatus != "" {
			if err := sendApplicationStatusToCRM(attempt.ApplicationID, applicationStatus); err != nil {
				fmt.Printf("CRM status sync failed: %v\n", err)
			}
		}
	}

	response := FinishAttemptResponse{
		Result:        resultText,
		Score:         userPoints,
		MaxTestPoints: maxPoints,
		Passed:        passed,
		AllCompleted:  applicationStatus != "",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func resolveCRMApplicationStatus(attempt models.Attempt) string {
	if attempt.ApplicationID == 0 {
		return ""
	}

	var configs []models.EventConfig
	query := database.DB.
		Preload("ExtraThreshold").
		Where("event_id = ?", attempt.EventConfig.EventID)
	if attempt.EventConfig.SpecializationID > 0 {
		query = query.Where("specialization_id = ?", attempt.EventConfig.SpecializationID)
	}
	if err := query.Find(&configs).Error; err != nil {
		fmt.Printf("Event config lookup failed: %v\n", err)
		return ""
	}

	configByTestID := make(map[uint]models.EventConfig, len(configs))
	extraTestIDs := make(map[uint]struct{})
	configIDs := make([]uint, 0, len(configs))
	for _, config := range configs {
		configByTestID[config.TestID] = config
		configIDs = append(configIDs, config.ConfigID)
		for _, rule := range config.ExtraThreshold {
			extraTestIDs[rule.TestID] = struct{}{}
		}
	}

	var finishedAttempts []models.Attempt
	if err := database.DB.
		Where("intern_id = ? AND application_id = ? AND config_id IN ? AND end_time IS NOT NULL", attempt.InternID, attempt.ApplicationID, configIDs).
		Find(&finishedAttempts).Error; err != nil {
		fmt.Printf("CRM status aggregation failed: %v\n", err)
		return ""
	}

	attemptByConfigID := make(map[uint]models.Attempt, len(finishedAttempts))
	for _, finishedAttempt := range finishedAttempts {
		attemptByConfigID[finishedAttempt.ConfigID] = finishedAttempt
	}

	hasRequiredConfigs := false
	testingFailed := false

	for _, config := range configs {
		if _, isExtra := extraTestIDs[config.TestID]; isExtra {
			continue
		}
		hasRequiredConfigs = true

		mainAttempt, completed := attemptByConfigID[config.ConfigID]
		if !completed {
			return ""
		}
		if mainAttempt.Passed {
			continue
		}

		applicableExtraTests := make([]uint, 0)
		for _, rule := range config.ExtraThreshold {
			if mainAttempt.Score >= rule.Threshold {
				applicableExtraTests = append(applicableExtraTests, rule.TestID)
			}
		}
		if len(applicableExtraTests) == 0 {
			testingFailed = true
			continue
		}

		extraPassed := false
		extraPending := false
		for _, extraTestID := range applicableExtraTests {
			extraConfig, exists := configByTestID[extraTestID]
			if !exists {
				continue
			}
			extraAttempt, completed := attemptByConfigID[extraConfig.ConfigID]
			if !completed {
				extraPending = true
				continue
			}
			if extraAttempt.Passed {
				extraPassed = true
				break
			}
		}

		if extraPassed {
			continue
		}
		if extraPending {
			return ""
		}
		testingFailed = true
	}

	if !hasRequiredConfigs || testingFailed {
		return crmStatusTestingFailed
	}
	return crmStatusChatLinkSent
}

func isAnswerCorrect(question models.Question, options models.QuestionOptions, answer UserAnswer) bool {
	switch question.Type {
	case models.SingleChoice, models.MultipleChoice:
		for i, choice := range options.Choices {
			selected := i < len(answer.Choices) && answer.Choices[i]
			if choice.IsTrue != selected {
				return false
			}
		}
		return true

	case models.Matching:
		if len(answer.MatchingPairs) != len(options.MatchingPairs) {
			return false
		}
		selected := make(map[string]string, len(answer.MatchingPairs))
		for _, pair := range answer.MatchingPairs {
			selected[pair.LeftColumn] = pair.RightColumn
		}
		for _, pair := range options.MatchingPairs {
			if selected[pair.LeftColumn] != pair.RightColumn {
				return false
			}
		}
		return true

	case models.CorrectOrder:
		if len(answer.Sequence) != len(options.Sequence) {
			return false
		}
		expected := append([]models.SequenceItem(nil), options.Sequence...)
		selected := append([]models.SequenceItem(nil), answer.Sequence...)
		sort.Slice(expected, func(i, j int) bool { return expected[i].Order < expected[j].Order })
		sort.Slice(selected, func(i, j int) bool { return selected[i].Order < selected[j].Order })
		for i := range expected {
			if expected[i].Text != selected[i].Text {
				return false
			}
		}
		return true

	case models.TextInput:
		input := strings.TrimSpace(answer.UserInput)
		for _, expected := range options.CorrectInput {
			expected = strings.TrimSpace(expected)
			if options.CaseSensitive {
				if input == expected {
					return true
				}
			} else if strings.EqualFold(input, expected) {
				return true
			}
		}
		return false
	}

	return false
}

func sendResultsToCRM(result CRMResultData, applicationID uint) error {
	cfg := config.Load()
	if cfg.CRMService == "" || cfg.CRMToken == "" {
		return fmt.Errorf("CRM integration is not configured")
	}

	url := cfg.CRMService + fmt.Sprintf("/api/users/integration/applications/%d/test-results/", applicationID)

	resultJSON, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("result data marshal failed: %v", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(resultJSON))
	if err != nil {
		return fmt.Errorf("request creation failed: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Service-Token", cfg.CRMToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("CRM request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		responseBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("CRM returned %d: %s", resp.StatusCode, string(responseBody))
	}

	return nil
}

func sendApplicationStatusToCRM(applicationID uint, applicationStatus string) error {
	cfg := config.Load()
	if cfg.CRMService == "" || cfg.CRMToken == "" {
		return fmt.Errorf("CRM integration is not configured")
	}

	url := cfg.CRMService + fmt.Sprintf("/api/users/integration/applications/%d/status/", applicationID)
	payload := map[string]string{"application_status": applicationStatus}
	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("status data marshal failed: %v", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(payloadJSON))
	if err != nil {
		return fmt.Errorf("request creation failed: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Service-Token", cfg.CRMToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("CRM request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		responseBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("CRM returned %d: %s", resp.StatusCode, string(responseBody))
	}

	return nil
}
