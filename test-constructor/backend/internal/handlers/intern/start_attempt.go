package intern

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"strconv"
	"strings"
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

type CRMTestingContextResponse struct {
	AvailableTests []CRMAvailableTest `json:"availableTests"`
}

type CRMAvailableTest struct {
	ID   uint   `json:"id"`
	Name string `json:"name"`
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
	Choices       []PublicChoice  `json:"choice,omitempty"`
	Matching      *PublicMatching `json:"matching,omitempty"`
	CaseSensitive bool            `json:"case_sensitive,omitempty"`
	Sequence      []string        `json:"sequence,omitempty"`
}

type PublicChoice struct {
	Text  string `json:"text"`
	Index int    `json:"index"`
}

type PublicMatching struct {
	LeftColumn  []string `json:"left,omitempty"`
	RightColumn []string `json:"right,omitempty"`
}

func syncTestingStartedStatus(applicationID uint) {
	if applicationID == 0 {
		return
	}
	if err := sendApplicationStatusToCRM(applicationID, crmStatusTestingStarted); err != nil {
		log.Printf("CRM testing status sync failed: %v", err)
	}
}

func StartAttempt(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "User is not authorized", http.StatusUnauthorized)
		return
	}

	vars := mux.Vars(r)
	link := vars["link"]

	req := readStartAttemptRequest(r)

	var eventConfig models.EventConfig
	err := database.DB.Preload("Test.Questions").
		Preload("ExtraThreshold.Test").
		Where("test_link = ?", link).
		First(&eventConfig).Error

	if errors.Is(err, gorm.ErrRecordNotFound) {
		http.Error(w, "Test was not found", http.StatusNotFound)
		return
	} else if err != nil {
		http.Error(w, "Database error: "+err.Error(), http.StatusInternalServerError)
		return
	}

	if !hasAccessToExtraConfig(claims.UserID, req.ApplicationID, eventConfig) {
		http.Error(w, "Дополнительный тест пока недоступен", http.StatusForbidden)
		return
	}

	var existingActiveAttempt models.Attempt
	resumeActiveAttempt := false
	if err := database.DB.Where("intern_id = ? AND end_time IS NULL", claims.UserID).
		First(&existingActiveAttempt).Error; err == nil {
		sameApplication := existingActiveAttempt.ApplicationID == req.ApplicationID
		sameConfig := existingActiveAttempt.ConfigID == eventConfig.ConfigID
		if sameConfig && sameApplication {
			resumeActiveAttempt = true
		} else {
			now := time.Now()
			existingActiveAttempt.EndTime = &now
			existingActiveAttempt.Passed = false
			existingActiveAttempt.Score = 0
			if err := database.DB.Save(&existingActiveAttempt).Error; err != nil {
				http.Error(w, "Failed to close previous active attempt: "+err.Error(), http.StatusInternalServerError)
				return
			}
		}
	} else if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
		http.Error(w, "Database error: "+err.Error(), http.StatusInternalServerError)
		return
	}

	if !resumeActiveAttempt {
		var existingAttempt models.Attempt
		existingAttemptQuery := database.DB.Where(
			"intern_id = ? AND config_id = ? AND end_time IS NOT NULL",
			claims.UserID,
			eventConfig.ConfigID,
		)
		if req.ApplicationID > 0 {
			existingAttemptQuery = existingAttemptQuery.Where("application_id = ?", req.ApplicationID)
		} else {
			existingAttemptQuery = existingAttemptQuery.Where("application_id = 0")
		}
		if err := existingAttemptQuery.First(&existingAttempt).Error; err == nil {
			http.Error(w, "You already passed this test for this application", http.StatusConflict)
			return
		} else if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
			http.Error(w, "Database error: "+err.Error(), http.StatusInternalServerError)
			return
		}
	}

	test := eventConfig.Test
	publicQuestions := make([]QuestionInfo, len(test.Questions))

	for i, q := range test.Questions {
		var options models.QuestionOptions
		if err := json.Unmarshal(q.Options, &options); err != nil {
			http.Error(w, "Question format error: "+err.Error(), http.StatusInternalServerError)
			return
		}

		var publicOptions PublicOptions
		switch q.Type {
		case models.SingleChoice, models.MultipleChoice:
			choices := make([]PublicChoice, len(options.Choices))
			for j, choice := range options.Choices {
				choices[j] = PublicChoice{Text: choice.Text, Index: j}
			}
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

	applicationIDForCRM := req.ApplicationID
	if resumeActiveAttempt && applicationIDForCRM == 0 {
		applicationIDForCRM = existingActiveAttempt.ApplicationID
	}
	syncTestingStartedStatus(applicationIDForCRM)

	if resumeActiveAttempt {
		response := StartAttemptResponse{
			ConfigID:      eventConfig.ConfigID,
			TestID:        eventConfig.TestID,
			ApplicationID: existingActiveAttempt.ApplicationID,
			Title:         test.Title,
			Description:   test.Description,
			TimeLimit:     eventConfig.TimeLimit,
			Threshold:     eventConfig.Threshold,
			Questions:     publicQuestions,
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
		return
	}

	crmTestID := uint(0)
	if req.ApplicationID > 0 {
		crmTestID = fetchCRMTestID(req.ApplicationID, eventConfig.Test.Title)
	}

	maxScore := 0
	for _, question := range eventConfig.Test.Questions {
		maxScore += question.Points
	}

	attempt := models.Attempt{
		ConfigID:      eventConfig.ConfigID,
		ApplicationID: req.ApplicationID,
		CRMTestID:     crmTestID,
		InternID:      claims.UserID,
		StartTime:     time.Now(),
		EndTime:       nil,
		MaxScore:      maxScore,
	}

	if err := database.DB.Create(&attempt).Error; err != nil {
		http.Error(w, "Failed to create attempt: "+err.Error(), http.StatusInternalServerError)
		return
	}

	if req.ApplicationID > 0 && crmTestID > 0 {
		expiresAt := attempt.StartTime.Add(time.Duration(eventConfig.TimeLimit) * time.Second)
		sessionID := fmt.Sprintf("%d", attempt.AttemptID)
		if err := createTestSession(req.ApplicationID, crmTestID, sessionID, expiresAt); err != nil {
			log.Printf("CRM test session sync failed: %v", err)
		}
	}

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

func readStartAttemptRequest(r *http.Request) StartAttemptRequest {
	var req StartAttemptRequest

	if raw := r.URL.Query().Get("application_id"); raw != "" {
		if parsed, err := strconv.ParseUint(raw, 10, 64); err == nil {
			req.ApplicationID = uint(parsed)
		}
	}

	if r.Body == nil {
		return req
	}
	defer r.Body.Close()

	body, err := io.ReadAll(r.Body)
	if err != nil || len(bytes.TrimSpace(body)) == 0 {
		return req
	}

	_ = json.Unmarshal(body, &req)
	return req
}

func fetchCRMTestID(applicationID uint, testTitle string) uint {
	cfg := config.Load()
	if cfg.CRMService == "" || cfg.CRMToken == "" {
		return 0
	}

	url := cfg.CRMService + fmt.Sprintf("/api/users/integration/applications/%d/testing-context/", applicationID)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		log.Printf("CRM testing context request creation failed: %v", err)
		return 0
	}
	req.Header.Set("X-Service-Token", cfg.CRMToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("CRM testing context request failed: %v", err)
		return 0
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		log.Printf("CRM testing context returned %d: %s", resp.StatusCode, string(body))
		return 0
	}

	var context CRMTestingContextResponse
	if err := json.Unmarshal(body, &context); err != nil {
		log.Printf("CRM testing context parse failed: %v", err)
		return 0
	}

	if len(context.AvailableTests) == 0 {
		return 0
	}

	normalizedTitle := strings.TrimSpace(testTitle)
	for _, availableTest := range context.AvailableTests {
		if strings.EqualFold(strings.TrimSpace(availableTest.Name), normalizedTitle) {
			return availableTest.ID
		}
	}

	return context.AvailableTests[0].ID
}
func createTestSession(applicationID uint, testID uint, sessionID string, expiresAt time.Time) error {
	cfg := config.Load()
	if cfg.CRMService == "" || cfg.CRMToken == "" {
		return fmt.Errorf("CRM integration is not configured")
	}

	url := cfg.CRMService + fmt.Sprintf("/api/users/integration/applications/%d/test-sessions/", applicationID)
	crmData := CRMCreateSessionData{
		TestID:    testID,
		SessionID: sessionID,
		ExpiresAt: expiresAt.Format("2006-01-02T15:04:05Z"),
	}

	crmDataJSON, err := json.Marshal(crmData)
	if err != nil {
		return fmt.Errorf("session data marshal failed: %v", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(crmDataJSON))
	if err != nil {
		return fmt.Errorf("request creation failed: %v", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Service-Token", cfg.CRMToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("CRM request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
		responseBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("CRM returned %d: %s", resp.StatusCode, string(responseBody))
	}

	return nil
}
