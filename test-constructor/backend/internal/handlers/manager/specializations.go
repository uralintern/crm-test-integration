package manager

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"test-constructor/config"

	"github.com/gorilla/mux"
)

type CRMEventResponse struct {
	Specializations []Specialization `json:"specializations"`
}

type Specialization struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
}

type EventSpecializationsResponse struct {
	Specializations []Specialization `json:"specializations"`
}

// @Summary Получить специализации мероприятия
// @Security ApiKeyAuth
// @Description Получение списка специализаций конкретного мероприятия
// @Tags manager
// @Accept json
// @Produce json
// @Param id path int true "Event ID"
// @Success 200 {object} EventSpecializationsResponse
// @Failure 400 {object} map[string]string
// @Failure 404 {object} map[string]string
// @Router /api/manager/events/{id}/specializations [get]
func GetEventSpecializations(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	eventIDStr := vars["id"]

	eventID, err := strconv.Atoi(eventIDStr)
	if err != nil {
		http.Error(w, "Неверный формат id", http.StatusBadRequest)
		return
	}

	eventData, err := getEventFromCRM(eventID)
	if err != nil {
		if err.Error() == "event not found" {
			http.Error(w, "Мероприятие не найдено", http.StatusNotFound)
			return
		}
		http.Error(w, "Ошибка получения данных мероприятия: "+err.Error(), http.StatusInternalServerError)
		return
	}

	response := EventSpecializationsResponse{
		Specializations: eventData.Specializations,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

func getEventFromCRM(eventID int) (*CRMEventResponse, error) {
	cfg := config.Load()
	crmService := cfg.CRMService
	crmToken := cfg.CRMToken
	url := crmService + fmt.Sprintf("/api/users/events/%d/", eventID)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("ошибка создания запроса: %v", err)
	}

	req.Header.Set("X-Service-Token", crmToken)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("ошибка запроса к CRM: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("event not found")
	}

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("CRM вернул ошибку %d: %s", resp.StatusCode, string(body))
	}

	var eventData CRMEventResponse
	if err := json.NewDecoder(resp.Body).Decode(&eventData); err != nil {
		return nil, fmt.Errorf("ошибка декодирования ответа: %v", err)
	}

	return &eventData, nil
}
