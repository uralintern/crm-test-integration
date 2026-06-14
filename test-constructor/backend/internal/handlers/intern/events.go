package intern

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"

	"gorm.io/gorm/clause"
)

type UserEventCreateInfo struct {
	EventID       uint `json:"event_id"`
	ApplicationID uint `json:"application_id"`
}

type UserEventInfo struct {
	EventID       uint `json:"event_id"`
	ApplicationID uint `json:"application_id"`
}

// CreateUserEvent stores the CRM application associated with an event for the current intern.
// @Summary Сохранить мероприятие пользователя
// @Security ApiKeyAuth
// @Tags intern
// @Accept json
// @Produce json
// @Param body body UserEventCreateInfo true "Event data"
// @Success 201 {object} UserEventInfo
// @Failure 400 {object} map[string]string
// @Failure 401 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/intern/users/events [post]
func CreateUserEvent(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Пользователь не авторизован", http.StatusUnauthorized)
		return
	}

	var request UserEventCreateInfo
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Неправильный формат запроса", http.StatusBadRequest)
		return
	}
	if request.EventID == 0 || request.ApplicationID == 0 {
		http.Error(w, "event_id и application_id обязательны", http.StatusBadRequest)
		return
	}

	userEvent := models.UserEvent{
		UserID:        claims.UserID,
		EventID:       request.EventID,
		ApplicationID: request.ApplicationID,
	}
	result := database.DB.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "user_id"}, {Name: "event_id"}},
		DoUpdates: clause.AssignmentColumns([]string{"application_id"}),
	}).Create(&userEvent)
	if result.Error != nil {
		http.Error(w, "Не удалось сохранить мероприятие: "+result.Error.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(UserEventInfo{
		EventID:       userEvent.EventID,
		ApplicationID: userEvent.ApplicationID,
	})
}

// GetUserEvents returns events associated with the current intern through CRM SSO.
// @Summary Получить мероприятия пользователя
// @Security ApiKeyAuth
// @Tags intern
// @Produce json
// @Success 200 {array} UserEventInfo
// @Failure 401 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /api/intern/users/events [get]
func GetUserEvents(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Пользователь не авторизован", http.StatusUnauthorized)
		return
	}

	var userEvents []models.UserEvent
	if err := database.DB.
		Where("user_id = ?", claims.UserID).
		Order("id DESC").
		Find(&userEvents).Error; err != nil {
		http.Error(w, "Не удалось получить мероприятия: "+err.Error(), http.StatusInternalServerError)
		return
	}

	response := make([]UserEventInfo, 0, len(userEvents))
	for _, userEvent := range userEvents {
		response = append(response, UserEventInfo{
			EventID:       userEvent.EventID,
			ApplicationID: userEvent.ApplicationID,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
