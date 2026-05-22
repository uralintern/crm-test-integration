package manager

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/auth"
	"test-constructor/internal/database"
	"test-constructor/internal/middleware"
	"test-constructor/internal/models"

	"gorm.io/datatypes"
)

type CreateTestInfo struct {
	Title       string               `json:"title"`
	Description string               `json:"description"`
	IsExtra     bool                 `json:"is_extra"`
	Questions   []CreateQuestionInfo `json:"questions"`
}

type CreateQuestionInfo struct {
	Text        string                 `json:"text"`
	Points      int                    `json:"points"`
	Type        string                 `json:"type"`
	OrderNumber int                    `json:"order_number"`
	Options     models.QuestionOptions `json:"options"`
}

// @Summary Создать тест
// @Security ApiKeyAuth
// @Description Создать новый тест
// @Tags manager
// @Accept json
// @Produce json
// @Param test body CreateTestInfo true "Test object"
// @Success 201 {object} map[string]interface{}
// @Router /api/manager/tests [post]
func CreateTest(w http.ResponseWriter, r *http.Request) {
	claims, ok := r.Context().Value(middleware.UserContextKey).(*auth.JWTClaims)
	if !ok {
		http.Error(w, "Вы не авторизованы", http.StatusUnauthorized)
		return
	}

	var req CreateTestInfo

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Неправильный JSON", http.StatusBadRequest)
		return
	}

	if req.Title == "" {
		http.Error(w, "Название теста обязательно", http.StatusBadRequest)
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

	test := models.Test{
		Title:       req.Title,
		Description: req.Description,
		IsExtra:     req.IsExtra,
		CreatorID:   userID,
	}

	if err := transaction.Create(&test).Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Ошибка создания теста: "+err.Error(), http.StatusInternalServerError)
		return
	}

	for _, qReq := range req.Questions {
		qType, err := models.ParseQType(qReq.Type)
		if err != nil {
			transaction.Rollback()
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		optionsJSON, err := json.Marshal(qReq.Options)
		if err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка преобразования опций вопроса: "+err.Error(), http.StatusBadRequest)
			return
		}

		question := models.Question{
			TestID:      test.ID,
			Text:        qReq.Text,
			Points:      qReq.Points,
			Type:        qType,
			OrderNumber: qReq.OrderNumber,
			Options:     datatypes.JSON(optionsJSON),
		}

		if err := transaction.Create(&question).Error; err != nil {
			transaction.Rollback()
			http.Error(w, "Ошибка создания вопроса: "+err.Error(), http.StatusInternalServerError)
			return
		}
	}

	if err := transaction.Commit().Error; err != nil {
		transaction.Rollback()
		http.Error(w, "Ошибка сохранения: "+err.Error(), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"id":      test.ID,
		"message": "Тест создан успешно",
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}
