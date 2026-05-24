package manager

import (
	"encoding/json"
	"net/http"
	"strconv"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"gorm.io/gorm"
)

type EventCfgInfo struct {
	EventID          uint                 `json:"event_id"`
	SpecializationID uint                 `json:"specialization_id"`
	TestID           uint                 `json:"test_id"`
	SuccessText      string               `json:"success_text"`
	FailText         string               `json:"fail_text"`
	TimeLimit        int                  `json:"time_limit"`
	Threshold        float64              `json:"threshold"`
	ExtraThreshold   []ExtraThresholdInfo `json:"extra_threshold"`
}

type ExtraThresholdInfo struct {
	Threshold float64 `json:"threshold"`
	Message   string  `json:"message"`
	TestID    uint    `json:"test_id"`
}

type EventConfigResponse struct {
	ConfigID         uint                 `json:"config_id"`
	EventID          uint                 `json:"event_id"`
	SpecializationID uint                 `json:"specialization_id"`
	TestID           uint                 `json:"test_id"`
	SuccessText      string               `json:"success_text"`
	FailText         string               `json:"fail_text"`
	TimeLimit        int                  `json:"time_limit"`
	Threshold        float64              `json:"threshold"`
	TestLink         string               `json:"test_link"`
	ExtraThreshold   []ExtraThresholdInfo `json:"extra_threshold"`
}

type EventConfigsResponse struct {
	Configs []EventConfigResponse `json:"configs"`
}

func mapEventConfigResponse(config models.EventConfig) EventConfigResponse {
	extra := make([]ExtraThresholdInfo, 0, len(config.ExtraThreshold))
	for _, item := range config.ExtraThreshold {
		extra = append(extra, ExtraThresholdInfo{
			Threshold: item.Threshold,
			Message:   item.Message,
			TestID:    item.TestID,
		})
	}

	return EventConfigResponse{
		ConfigID:         config.ConfigID,
		EventID:          config.EventID,
		SpecializationID: config.SpecializationID,
		TestID:           config.TestID,
		SuccessText:      config.SuccessText,
		FailText:         config.FailText,
		TimeLimit:        config.TimeLimit,
		Threshold:        config.Threshold,
		TestLink:         config.TestLink.String(),
		ExtraThreshold:   extra,
	}
}

func GetEventConfigs(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	eventID, err := strconv.ParseUint(vars["id"], 10, 32)
	if err != nil || eventID == 0 {
		http.Error(w, "Неверный ID мероприятия", http.StatusBadRequest)
		return
	}

	var configs []models.EventConfig
	if err := database.DB.
		Preload("ExtraThreshold").
		Where("event_id = ?", uint(eventID)).
		Order("config_id").
		Find(&configs).Error; err != nil {
		http.Error(w, "Ошибка загрузки настроек: "+err.Error(), http.StatusInternalServerError)
		return
	}

	response := EventConfigsResponse{Configs: make([]EventConfigResponse, 0, len(configs))}
	for _, config := range configs {
		response.Configs = append(response.Configs, mapEventConfigResponse(config))
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(response)
}

func CreateConfig(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Вы не авторизованы", http.StatusUnauthorized)
		return
	}

	var req EventCfgInfo
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Неправильный JSON", http.StatusBadRequest)
		return
	}

	if req.EventID < 1 || req.SpecializationID < 1 || req.TestID < 1 {
		http.Error(w, "ID должен быть положительным", http.StatusBadRequest)
		return
	}

	if req.Threshold < 1 {
		http.Error(w, "Пороговое значение должно быть положительным", http.StatusBadRequest)
		return
	}

	userID := claims.UserID
	transaction := database.DB.Begin()
	if transaction.Error != nil {
		http.Error(w, "Ошибка базы данных", http.StatusInternalServerError)
		return
	}

	defer func() {
		if recovered := recover(); recovered != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка сервера", http.StatusInternalServerError)
		}
	}()

	var eventCFG models.EventConfig
	err := transaction.Where(
		"event_id = ? AND specialization_id = ? AND test_id = ?",
		req.EventID,
		req.SpecializationID,
		req.TestID,
	).First(&eventCFG).Error
	created := false

	if err == nil {
		updates := models.EventConfig{
			CreatorID:   userID,
			SuccessText: req.SuccessText,
			FailText:    req.FailText,
			TimeLimit:   req.TimeLimit,
			Threshold:   req.Threshold,
		}
		if err := transaction.Model(&eventCFG).Updates(updates).Error; err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка обновления настройки: "+err.Error(), http.StatusInternalServerError)
			return
		}
		if err := transaction.Where("config_id = ?", eventCFG.ConfigID).Delete(&models.ExtraThreshold{}).Error; err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка удаления старых порогов: "+err.Error(), http.StatusInternalServerError)
			return
		}
	} else if err == gorm.ErrRecordNotFound {
		eventCFG = models.EventConfig{
			EventID:          req.EventID,
			SpecializationID: req.SpecializationID,
			TestID:           req.TestID,
			CreatorID:        userID,
			SuccessText:      req.SuccessText,
			FailText:         req.FailText,
			TimeLimit:        req.TimeLimit,
			TestLink:         uuid.New(),
			Threshold:        req.Threshold,
		}
		if err := transaction.Create(&eventCFG).Error; err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка создания настройки: "+err.Error(), http.StatusInternalServerError)
			return
		}
		created = true
	} else {
		transaction.Rollback()
		http.Error(w, "Ошибка поиска настройки: "+err.Error(), http.StatusInternalServerError)
		return
	}

	for _, eThreshold := range req.ExtraThreshold {
		extraThreshold := models.ExtraThreshold{
			ConfigID:   eventCFG.ConfigID,
			Threshold: eThreshold.Threshold,
			Message:   eThreshold.Message,
			TestID:    eThreshold.TestID,
		}

		if err := transaction.Create(&extraThreshold).Error; err != nil {
			transaction.Rollback()
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
	}

	if eventCFG.TestLink == uuid.Nil {
		eventCFG.TestLink = uuid.New()
		if err := transaction.Model(&eventCFG).Update("test_link", eventCFG.TestLink).Error; err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка создания ссылки на тест: "+err.Error(), http.StatusInternalServerError)
			return
		}
	}

	if err := transaction.Commit().Error; err != nil {
		http.Error(w, "Ошибка сохранения изменений", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if created {
		w.WriteHeader(http.StatusCreated)
	} else {
		w.WriteHeader(http.StatusOK)
	}
	json.NewEncoder(w).Encode(map[string]any{
		"config_id": eventCFG.ConfigID,
		"test_link": eventCFG.TestLink.String(),
		"created":   created,
	})
}

func UpdateConfig(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Вы не авторизованы", http.StatusUnauthorized)
		return
	}

	vars := mux.Vars(r)
	configID, err := strconv.ParseUint(vars["id"], 10, 32)
	if err != nil {
		http.Error(w, "Неверный ID конфигурации", http.StatusBadRequest)
		return
	}

	var req EventCfgInfo
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Неправильный JSON", http.StatusBadRequest)
		return
	}

	if req.EventID < 1 || req.SpecializationID < 1 || req.TestID < 1 {
		http.Error(w, "ID должен быть положительным", http.StatusBadRequest)
		return
	}

	if req.Threshold < 1 {
		http.Error(w, "Пороговое значение должно быть положительным", http.StatusBadRequest)
		return
	}

	userID := claims.UserID
	transaction := database.DB.Begin()
	if transaction.Error != nil {
		http.Error(w, "Ошибка базы данных", http.StatusInternalServerError)
		return
	}

	defer func() {
		if recovered := recover(); recovered != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка сервера", http.StatusInternalServerError)
		}
	}()

	var existingConfig models.EventConfig
	if err := transaction.Where("config_id = ?", uint(configID)).First(&existingConfig).Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Конфигурация не найдена", http.StatusNotFound)
		return
	}

	updates := models.EventConfig{
		EventID:          req.EventID,
		CreatorID:        userID,
		SpecializationID: req.SpecializationID,
		TestID:           req.TestID,
		SuccessText:      req.SuccessText,
		FailText:         req.FailText,
		TimeLimit:        req.TimeLimit,
		Threshold:        req.Threshold,
	}

	if err := transaction.Model(&existingConfig).Updates(updates).Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Ошибка обновления настройки: "+err.Error(), http.StatusInternalServerError)
		return
	}

	if err := transaction.Where("config_id = ?", existingConfig.ConfigID).Delete(&models.ExtraThreshold{}).Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Ошибка удаления старых порогов: "+err.Error(), http.StatusInternalServerError)
		return
	}

	for _, eThreshold := range req.ExtraThreshold {
		extraThreshold := models.ExtraThreshold{
			ConfigID:   existingConfig.ConfigID,
			Threshold: eThreshold.Threshold,
			Message:   eThreshold.Message,
			TestID:    eThreshold.TestID,
		}

		if err := transaction.Create(&extraThreshold).Error; err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка создания порога: "+err.Error(), http.StatusInternalServerError)
			return
		}
	}

	if err := transaction.Commit().Error; err != nil {
		http.Error(w, "Ошибка сохранения изменений", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}
