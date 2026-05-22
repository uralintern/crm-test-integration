package intern

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"math/rand"
	"net/http"
	"test-constructor/config"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"
	"time"

	"github.com/gorilla/mux"
	"gorm.io/gorm"
)

type CRMCreateSessionData struct {
	TestID    uint   `json:"test_id"`
	SessionID string `json:"session_id"`
	ExpiresAt string `json:"expires_at"`
}

type StartAttemptRequest struct {
	ApplicationID uint `json:"application_id"`
}

type StartAttemptResponse struct {
	ConfigID      uint           `json:"config_id"`
	TestID        uint           `json:"test_id"`
	ApplicationID uint           `json:"application_id"`
	Title         string         `json:"title"`
	Description   string         `json:"description"`
	TimeLimit     int            `json:"time_limit"`
	Threshold     float64        `json:"threshold"`
	Questions     []QuestionInfo `json:"questions"`
}

type QuestionInfo struct {
	QuestionID  uint          `json:"question_id"`
	Text        string        `json:"text"`
	Points      int           `json:"points"`
	OrderNumber int           `json:"order_number"`
	Type        models.QType  `json:"type"`
	Options     PublicOptions `json:"options"`
}

type PublicOptions struct {
	Choices       []string        `json:"choice,omitempty"`
	Matching      *PublicMatching `json:"matching,omitempty"`
	CaseSensitive bool            `json:"case_sensitive,omitempty"`
	Sequence      []string        `json:"sequence,omitempty"`
}

type PublicMatching struct {
	LeftColumn  []string `json:"left,omitempty"`
	RightColumn []string `json:"right,omitempty"`
}

// @Summary Пройти тест через конфигурацию мероприятия
// @Security ApiKeyAuth
// @Description Создание попытки по ссылке конфигурации мероприятия
// @Tags intern
// @Accept json
// @Produce json
// @Param answers body StartAttemptRequest true "Start attempt object"
// @Param link path string true "Ссылка конфигурации теста"
// @Success 201 {object} StartAttemptResponse
// @Router /api/intern/tests/{link} [get]
func StartAttempt(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Пользователь не авторизован", http.StatusUnauthorized)
		return
	}

	vars := mux.Vars(r)
	link := vars["link"]

	var req StartAttemptRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	var eventConfig models.EventConfig
	err := database.DB.Preload("Test.Questions").
		Preload("ExtraThreshold.Test").
		Where("test_link = ?", link).
		First(&eventConfig).Error

	if errors.Is(err, gorm.ErrRecordNotFound) {
		http.Error(w, "Тест не найден", http.StatusNotFound)
		return
	} else if err != nil {
		http.Error(w, "Ошибка базы данных: "+err.Error(), http.StatusInternalServerError)
		return
	}

	var existingActiveAttempt models.Attempt
	if err := database.DB.Where("intern_id = ? AND end_time IS NULL", claims.UserID).
		First(&existingActiveAttempt).Error; err == nil {
		http.Error(w, "У вас уже есть активная попытка", http.StatusConflict)
		return
	}

	var existingAttempt models.Attempt
	if err := database.DB.Where("intern_id = ? AND test_id = ?", claims.UserID, eventConfig.TestID).
		First(&existingAttempt).Error; err == nil {
		if existingAttempt.EndTime != nil {
			http.Error(w, "Вы уже прошли этот тест", http.StatusConflict)
			return
		}
	}

	test := eventConfig.Test
	publicQuestions := make([]QuestionInfo, len(test.Questions))

	for i, q := range test.Questions {
		var options models.QuestionOptions
		if err := json.Unmarshal(q.Options, &options); err != nil {
			http.Error(w, "Ошибка формата вопроса: "+err.Error(), http.StatusInternalServerError)
			return
		}

		var publicOptions PublicOptions
		switch q.Type {
		case models.SingleChoice, models.MultipleChoice:
			choices := make([]string, len(options.Choices))
			for j, choice := range options.Choices {
				choices[j] = choice.Text
			}

			rand.New(rand.NewSource(time.Now().UnixNano()))
			rand.Shuffle(len(choices), func(i, j int) {
				choices[i], choices[j] = choices[j], choices[i]
			})

			publicOptions.Choices = choices

		case models.Matching:
			pairs := options.MatchingPairs
			leftColumn := make([]string, len(pairs))
			rightColumn := make([]string, len(pairs))

			for j, pair := range pairs {
				leftColumn[j] = pair.LeftColumn
				rightColumn[j] = pair.RightColumn
			}

			shuffledRight := make([]string, len(rightColumn))
			copy(shuffledRight, rightColumn)
			rand.New(rand.NewSource(time.Now().UnixNano()))
			rand.Shuffle(len(shuffledRight), func(i, j int) {
				shuffledRight[i], shuffledRight[j] = shuffledRight[j], shuffledRight[i]
			})

			publicOptions.Matching = &PublicMatching{
				LeftColumn:  leftColumn,
				RightColumn: shuffledRight,
			}

		case models.TextInput:
			publicOptions.CaseSensitive = options.CaseSensitive

		case models.CorrectOrder:
			shuffledSequence := make([]string, len(options.Sequence))
			for j, item := range options.Sequence {
				shuffledSequence[j] = item.Text
			}

			rand.New(rand.NewSource(time.Now().UnixNano()))
			rand.Shuffle(len(shuffledSequence), func(i, j int) {
				shuffledSequence[i], shuffledSequence[j] = shuffledSequence[j], shuffledSequence[i]
			})

			publicOptions.Sequence = shuffledSequence
		}

		publicQuestions[i] = QuestionInfo{
			QuestionID:  q.ID,
			Text:        q.Text,
			Points:      q.Points,
			OrderNumber: q.OrderNumber,
			Type:        q.Type,
			Options:     publicOptions,
		}
	}

	attempt := models.Attempt{
		ConfigID:      eventConfig.ConfigID,
		ApplicationID: req.ApplicationID,
		InternID:      claims.UserID,
		StartTime:     time.Now(),
		EndTime:       nil,
	}

	if err := database.DB.Create(&attempt).Error; err != nil {
		http.Error(w, "Ошибка создания попытки: "+err.Error(), http.StatusInternalServerError)
		return
	}

	expiresAt := attempt.StartTime.Add(time.Duration(eventConfig.TimeLimit) * time.Second)
	sessionID := fmt.Sprintf("%d", attempt.AttemptID)

	err = createTestSession(
		req.ApplicationID,
		eventConfig.TestID,
		sessionID,
		expiresAt,
	)

	response := StartAttemptResponse{
		ConfigID:      eventConfig.ConfigID,
		TestID:        eventConfig.TestID,
		ApplicationID: req.ApplicationID,
		Title:         test.Title,
		Description:   test.Description,
		TimeLimit:     eventConfig.TimeLimit,
		Threshold:     eventConfig.Threshold,
		Questions:     publicQuestions,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

func createTestSession(applicationID uint, testID uint, sessionID string, expiresAt time.Time) error {
	cfg := config.Load()
	crmService := cfg.CRMService
	crmToken := cfg.CRMToken
	url := crmService + fmt.Sprintf("/api/users/integration/applications/%d/test-sessions/", applicationID)
	crmData := CRMCreateSessionData{
		TestID:    testID,
		SessionID: sessionID,
		ExpiresAt: expiresAt.Format("2006-01-02T15:04:05Z"),
	}

	crmDataJSON, err := json.Marshal(crmData)
	if err != nil {
		return fmt.Errorf("ошибка маршалинга данных сессии: %v", err)
	}

	fmt.Printf("Отправка запроса в CRM: %s\n", string(crmDataJSON))

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(crmDataJSON))
	if err != nil {
		return fmt.Errorf("ошибка создания запроса: %v", err)
	}

	req.Header.Set("X-Service-Token", crmToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("ошибка отправки запроса в Django: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		var errorResponse map[string]interface{}
		json.NewDecoder(resp.Body).Decode(&errorResponse)
		return fmt.Errorf("CRM вернул ошибку %d: %v", resp.StatusCode, errorResponse)
	}

	fmt.Printf("Сессия создана")
	return nil
}
