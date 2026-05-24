package manager

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"test-constructor/config"
	"test-constructor/internal/database"
	"test-constructor/internal/models"

	"github.com/gorilla/mux"
	"gorm.io/gorm"
)

type GetUsersResponse struct {
	Users []UserInfo `json:"users"`
}

type UserInfo struct {
	ID      uint   `json:"id"`
	Name    string `json:"name"`
	Surname string `json:"surname"`
	Email   string `json:"email"`
}

type UserStatisticsResponse struct {
	UserID    uint                `json:"user_id"`
	FirstName string              `json:"first_name"`
	LastName  string              `json:"last_name"`
	Email     string              `json:"email"`
	Attempts  []UserAttemptDetail `json:"attempts"`
}

type UserAttemptDetail struct {
	AttemptID uint               `json:"attempt_id"`
	TestTitle string             `json:"test_title"`
	EventName string             `json:"event_name"`
	IsExtra   bool               `json:"is_extra"`
	Score     float64            `json:"score"`
	MaxScore  int                `json:"max_score"`
	Passed    bool               `json:"passed"`
	Questions []QuestionStatInfo `json:"questions"`
}

type QuestionStatInfo struct {
	Text         string  `json:"text"`
	Points       float64 `json:"points_earned"`
	MaxPoints    int     `json:"max_points"`
	IsCorrect    bool    `json:"is_correct"`
	QuestionType string  `json:"question_type"`
	OrderNumber  int     `json:"order_number"`
}

type crmEventInfo struct {
	ID    uint   `json:"id"`
	Name  string `json:"name"`
	Title string `json:"title"`
}

func GetUsers(w http.ResponseWriter, r *http.Request) {
	var internRole models.Role
	if err := database.DB.Where("code = ?", "intern").First(&internRole).Error; err != nil {
		http.Error(w, "Роль стажера не найдена", http.StatusInternalServerError)
		return
	}

	var users []models.User
	if err := database.DB.Where("role_id = ?", internRole.ID).Order("surname, name").Find(&users).Error; err != nil {
		http.Error(w, "Ошибка получения пользователей: "+err.Error(), http.StatusInternalServerError)
		return
	}

	interns := make([]UserInfo, 0, len(users))
	for _, user := range users {
		interns = append(interns, UserInfo{
			ID:      user.ID,
			Name:    user.Name,
			Surname: user.Surname,
			Email:   user.Email,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(GetUsersResponse{Users: interns})
}

func GetUserStatistics(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	userID, err := strconv.ParseUint(vars["id"], 10, 32)
	if err != nil || userID == 0 {
		http.Error(w, "Неверный формат user_id", http.StatusBadRequest)
		return
	}

	stats, err := buildUserStatistics(uint(userID))
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			http.Error(w, "Пользователь не найден", http.StatusNotFound)
			return
		}
		http.Error(w, "Ошибка получения статистики: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func buildUserStatistics(userID uint) (*UserStatisticsResponse, error) {
	var user models.User
	if err := database.DB.First(&user, userID).Error; err != nil {
		return nil, err
	}

	var attempts []models.Attempt
	if err := database.DB.Where("intern_id = ? AND end_time IS NOT NULL", userID).
		Preload("EventConfig").
		Preload("EventConfig.Test").
		Preload("EventConfig.Test.Questions").
		Preload("Answers").
		Preload("Answers.Question").
		Order("end_time DESC").
		Find(&attempts).Error; err != nil {
		return nil, fmt.Errorf("ошибка получения попыток: %w", err)
	}

	eventNames := loadCRMEventNames()
	attemptDetails := make([]UserAttemptDetail, 0, len(attempts))
	for _, attempt := range attempts {
		cfg := attempt.EventConfig
		maxScore := 0
		for _, question := range cfg.Test.Questions {
			maxScore += question.Points
		}

		eventName := eventNames[cfg.EventID]
		if eventName == "" {
			eventName = fmt.Sprintf("Мероприятие #%d", cfg.EventID)
		}

		attemptDetails = append(attemptDetails, UserAttemptDetail{
			AttemptID: attempt.AttemptID,
			TestTitle: cfg.Test.Title,
			EventName: eventName,
			IsExtra:   false,
			Score:     attempt.Score,
			MaxScore:  maxScore,
			Passed:    attempt.Passed,
			Questions: buildQuestionStats(attempt.Answers),
		})
	}

	return &UserStatisticsResponse{
		UserID:    user.ID,
		FirstName: user.Name,
		LastName:  user.Surname,
		Email:     user.Email,
		Attempts:  attemptDetails,
	}, nil
}

func buildQuestionStats(answers []models.Answer) []QuestionStatInfo {
	stats := make([]QuestionStatInfo, 0, len(answers))
	for _, answer := range answers {
		stats = append(stats, QuestionStatInfo{
			Text:         answer.Question.Text,
			Points:       answer.Points,
			MaxPoints:    answer.Question.Points,
			IsCorrect:    answer.IsCorrect,
			QuestionType: string(answer.Question.Type),
			OrderNumber:  answer.Question.OrderNumber,
		})
	}

	sort.Slice(stats, func(i, j int) bool {
		return stats[i].OrderNumber < stats[j].OrderNumber
	})

	return stats
}

func loadCRMEventNames() map[uint]string {
	cfg := config.Load()
	eventNames := map[uint]string{}
	if cfg.CRMService == "" || cfg.CRMToken == "" {
		return eventNames
	}

	req, err := http.NewRequest("GET", cfg.CRMService+"/api/users/events/", nil)
	if err != nil {
		return eventNames
	}
	req.Header.Set("X-Service-Token", cfg.CRMToken)
	req.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return eventNames
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		io.Copy(io.Discard, resp.Body)
		return eventNames
	}

	var events []crmEventInfo
	if err := json.NewDecoder(resp.Body).Decode(&events); err != nil {
		return eventNames
	}

	for _, event := range events {
		name := event.Name
		if name == "" {
			name = event.Title
		}
		if event.ID > 0 && name != "" {
			eventNames[event.ID] = name
		}
	}

	return eventNames
}
