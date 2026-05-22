package manager

import (
	"encoding/json"
	"net/http"
	"strconv"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"

	"github.com/gorilla/mux"
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

// @Summary Создать настройку мероприятия
// @Security ApiKeyAuth
// @Tags manager
// @Accept json
// @Produce json
// @Param test body EventCfgInfo true "EventCfg object"
// @Success 201 {object} map[string]interface{}
// @Router /api/manager/events [post]
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
	}

	userID := claims.UserID
	transaction := database.DB.Begin()
	if transaction.Error != nil {
		http.Error(w, "Ошибка базы данных", http.StatusInternalServerError)
		return
	}

	defer func() {
		if r := recover(); r != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка сервера", http.StatusInternalServerError)
			return
		}
	}()

	eventCFG := models.EventConfig{
		EventID:          req.EventID,
		SpecializationID: req.SpecializationID,
		TestID:           req.TestID,
		CreatorID:        userID,
		SuccessText:      req.SuccessText,
		FailText:         req.FailText,
		TimeLimit:        req.TimeLimit,
		Threshold:        req.Threshold,
	}

	if err := transaction.Create(&eventCFG).Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Ошибка создания настройки: "+err.Error(), http.StatusInternalServerError)
		return
	}

	for _, eThreshold := range req.ExtraThreshold {
		extraThreshold := models.ExtraThreshold{
			ConfigID:  eventCFG.ConfigID,
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

	w.WriteHeader(http.StatusCreated)
}

// @Summary Обновить настройку мероприятия
// @Security ApiKeyAuth
// @Tags manager
// @Accept json
// @Produce json
// @Param id path int true "Config ID"
// @Param test body EventCfgInfo true "EventCfg object"
// @Success 200 {object} map[string]interface{}
// @Router /api/manager/events/{id} [put]
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
		if r := recover(); r != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка сервера", http.StatusInternalServerError)
			return
		}
	}()

	var existingConfig models.EventConfig
	if err := transaction.Where("config_id = ? AND creator_id = ?", uint(configID), userID).First(&existingConfig).Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Конфигурация не найдена", http.StatusNotFound)
		return
	}

	updates := models.EventConfig{
		EventID:          req.EventID,
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
			ConfigID:  existingConfig.ConfigID,
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
