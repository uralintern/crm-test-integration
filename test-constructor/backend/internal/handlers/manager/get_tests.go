package manager

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/database"
	"test-constructor/internal/models"

	"github.com/gorilla/mux"
)

type TestInfo struct {
	ID          uint   `json:"test_id"`
	CreatorID   uint   `json:"creator_id"`
	Title       string `json:"title"`
	Description string `json:"description"`
}

type TestsInfoResponse struct {
	Tests []TestInfo `json:"tests"`
}

// @Summary Получить тесты для организотора
// @Security ApiKeyAuth
// @Description Получить список тестов
// @Tags manager
// @Produce json
// @Success 200 {object} TestsInfoResponse
// @Failure 404 {object} map[string]string
// @Router /api/manager/tests [get]
func GetTests(w http.ResponseWriter, r *http.Request) {
	var tests []models.Test
	if err := database.DB.Preload("User").Find(&tests).Error; err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	var response TestsInfoResponse
	for _, t := range tests {
		response.Tests = append(response.Tests, TestInfo{
			ID:          t.ID,
			CreatorID:   t.CreatorID,
			Title:       t.Title,
			Description: t.Description,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// @Summary Удалить тест
// @Security ApiKeyAuth
// @Tags manager
// @Accept json
// @Produce json
// @Param id path int true "ID теста" minimum(1)
// @Success 200
// @Router /api/manager/tests/delete/{id} [post]
func DeleteTest(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	testID := vars["id"]
	if err := database.DB.Where("id = ?", testID).Delete(&models.Test{}).Error; err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}
