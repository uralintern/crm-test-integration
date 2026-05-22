package intern

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"slices"
	"test-constructor/config"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"
	"time"

	"gorm.io/datatypes"
)

type CRMResultData struct {
	SessionID   string `json:"session_id"`
	TestID      string `json:"test_id"`
	Score       int    `json:"score"`
	MaxScore    int    `json:"max_score"`
	IsPassed    bool   `json:"is_passed"`
	CompletedAt string `json:"completed_at"`
	StartedAt   string `json:"started_at"`
}

type FinishAttemptRequest struct {
	UserAnswers []UserAnswerInfo
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
}

// @Summary Завершить тест
// @Security ApiKeyAuth
// @Description Получение ответов стажёра
// @Tags intern
// @Accept json
// @Produce json
// @Param answers body FinishAttemptRequest true "Answers object"
// @Success 201 {object} FinishAttemptResponse
// @Router /api/intern/attempt/finish [post]
func FinishAttempt(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Пользователь не авторизован", http.StatusUnauthorized)
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
		Where("intern_id = ? AND end_time IS NULL", claims.UserID).
		First(&attempt).Error; err != nil {
		http.Error(w, "Активная попытка не найдена", http.StatusNotFound)
		return
	}

	test := attempt.EventConfig.Test
	userPoints := 0
	maxPoints := 0
	for _, answerInfo := range req.UserAnswers {
		var question models.Question
		if err := database.DB.First(&question, answerInfo.QuestionID).Error; err != nil {
			http.Error(w, "Вопрос не найден", http.StatusNotFound)
			return
		}

		if question.TestID != test.ID {
			http.Error(w, "Тесты не совпадают", http.StatusBadRequest)
			return
		}

		answer := answerInfo.Answer
		maxPoints += question.Points
		var options models.QuestionOptions
		if err := json.Unmarshal(question.Options, &options); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		correct := true
		switch question.Type {
		case models.SingleChoice, models.MultipleChoice:
			for i, choice := range options.Choices {
				if choice.IsTrue != answer.Choices[i] {
					correct = false
				}
			}
		case models.Matching:
			pairs := options.MatchingPairs
			for i, pair := range pairs {
				if pair != answer.MatchingPairs[i] {
					correct = false
				}
			}
		case models.CorrectOrder:
			for i, item := range options.Sequence {
				if item != answer.Sequence[i] {
					correct = false
				}
			}
		case models.TextInput:
			if !slices.Contains(options.CorrectInput, answer.UserInput) {
				correct = false
			}
		}

		if correct {
			userPoints += question.Points
		}
		answerJSON, err := json.Marshal(answer)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		userAnswer := models.Answer{
			QuestionID:   question.ID,
			AttemptID:    attempt.AttemptID,
			InternAnswer: datatypes.JSON(answerJSON),
			IsCorrect:    correct,
		}

		if err := database.DB.Create(&userAnswer).Error; err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	now := time.Now()
	attempt.EndTime = &now
	attempt.Score = float64(userPoints)

	passed := float64(userPoints) > attempt.EventConfig.Threshold

	attempt.Passed = passed
	if err := database.DB.Save(&attempt).Error; err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	resultText := attempt.EventConfig.FailText
	if passed {
		resultText = attempt.EventConfig.SuccessText
	}

	crmResult := CRMResultData{
		SessionID:   fmt.Sprintf("%d", attempt.AttemptID),
		TestID:      fmt.Sprintf("%d", attempt.EventConfig.ConfigID),
		Score:       userPoints,
		MaxScore:    maxPoints,
		IsPassed:    passed,
		CompletedAt: now.Format("2006-01-02T15:04:05Z"),
		StartedAt:   attempt.StartTime.Format("2006-01-02T15:04:05Z"),
	}

	if err := sendResultsToCRM(crmResult, attempt.ApplicationID); err != nil {
		fmt.Printf("Ошибка отправки результатов в CRM: %v\n", err)
	}

	response := FinishAttemptResponse{
		Result:        resultText,
		Score:         userPoints,
		MaxTestPoints: maxPoints,
		Passed:        passed,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func sendResultsToCRM(result CRMResultData, applicationID uint) error {
	cfg := config.Load()
	crmService := cfg.CRMService
	crmToken := cfg.CRMToken
	url := crmService + fmt.Sprintf("/api/users/integration/applications/%d/test-results/", applicationID)

	resultJSON, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("ошибка маршалинга данных: %v", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(resultJSON))
	if err != nil {
		return fmt.Errorf("ошибка создания запроса: %v", err)
	}

	req.Header.Set("X-Service-Token", crmToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("ошибка отправки запроса: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		var errorResponse map[string]interface{}
		json.NewDecoder(resp.Body).Decode(&errorResponse)
		return fmt.Errorf("CRM вернул ошибку %d: %v", resp.StatusCode, errorResponse)
	}

	fmt.Println("Результаты успешно отправлены в Django")
	return nil
}
