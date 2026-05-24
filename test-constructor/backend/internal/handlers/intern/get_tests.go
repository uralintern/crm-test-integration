package intern

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"
	"time"
)

type AttemptInfo struct {
	ID            uint       `json:"id"`
	AttemptID     uint       `json:"attempt_id"`
	ApplicationID uint       `json:"application_id"`
	TestID        uint       `json:"test_id"`
	ConfigID      uint       `json:"config_id"`
	TestLink      string     `json:"test_link"`
	TestTitle     string     `json:"test_title"`
	Title         string     `json:"title"`
	ResultText    string     `json:"result_text"`
	Message       string     `json:"message"`
	Score         float64    `json:"score"`
	Passed        bool       `json:"passed"`
	Status        string     `json:"status"`
	StartedAt     time.Time  `json:"started_at"`
	FinishedAt    *time.Time `json:"finished_at"`
}

type InternAttemptResponse struct {
	AttemptsInfo []AttemptInfo `json:"attempts"`
	Tests        []AttemptInfo `json:"tests"`
}

func GetAttempts(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Пользователь не авторизован", http.StatusUnauthorized)
		return
	}

	var user models.User
	if err := database.DB.First(&user, claims.UserID).Error; err != nil {
		http.Error(w, "Пользователь не найден", http.StatusInternalServerError)
		return
	}

	var attempts []models.Attempt
	if err := database.DB.Preload("EventConfig").
		Preload("EventConfig.ExtraThreshold").
		Preload("EventConfig.Test").
		Where("intern_id = ?", claims.UserID).
		Order("start_time DESC").
		Find(&attempts).Error; err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	attemptsInfo := make([]AttemptInfo, 0, len(attempts))
	for _, attempt := range attempts {
		status := "in_progress"
		resultText := "Тест начат, но ещё не завершён"
		if attempt.EndTime != nil {
			if attempt.Passed {
				status = "passed"
				resultText = attempt.EventConfig.SuccessText
			} else {
				status = "failed"
				resultText = attempt.EventConfig.FailText
			}
		}

		attemptsInfo = append(attemptsInfo, AttemptInfo{
			ID:            attempt.AttemptID,
			AttemptID:     attempt.AttemptID,
			ApplicationID: attempt.ApplicationID,
			TestID:        attempt.EventConfig.TestID,
			ConfigID:      attempt.ConfigID,
			TestLink:      attempt.EventConfig.TestLink.String(),
			TestTitle:     attempt.EventConfig.Test.Title,
			Title:         attempt.EventConfig.Test.Title,
			ResultText:    resultText,
			Message:       resultText,
			Score:         attempt.Score,
			Passed:        attempt.Passed,
			Status:        status,
			StartedAt:     attempt.StartTime,
			FinishedAt:    attempt.EndTime,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(InternAttemptResponse{
		AttemptsInfo: attemptsInfo,
		Tests:        attemptsInfo,
	})
}
