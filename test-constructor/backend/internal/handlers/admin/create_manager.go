package admin

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/database"
	"test-constructor/internal/models"
)

type CreateManagerRequest struct {
	Name     string `json:"name"`
	Surname  string `json:"surname"`
	Email    string `json:"email"`
	Password string `json:"password"`
}

type CreateManagerResponse struct {
	UserID  uint   `json:"user_id"`
	Email   string `json:"email"`
	Name    string `json:"name"`
	Surname string `json:"surname"`
	Role    string `json:"role"`
	Message string `json:"message"`
}

// @Summary Создать организатора
// @Security ApiKeyAuth
// @Description Создать нового организатора
// @Tags admin
// @Accept json
// @Produce json
// @Param test body CreateManagerRequest true "Manager object"
// @Success 201 {object} CreateManagerResponse
// @Router /api/admin/manager/create [post]
func CreateManager(w http.ResponseWriter, r *http.Request) {
	var req CreateManagerRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Неправильный JSON", http.StatusBadRequest)
		return
	}

	if req.Email == "" || req.Password == "" || req.Name == "" || req.Surname == "" {
		http.Error(w, "Не все поля заполнены", http.StatusBadRequest)
		return
	}

	var role models.Role
	if err := database.DB.Where("code = ?", "manager").First(&role).Error; err != nil {
		http.Error(w, "Ошибка при запросе роли", http.StatusInternalServerError)
	}

	user := models.User{
		Email:   req.Email,
		Name:    req.Name,
		Surname: req.Surname,
		RoleID:  role.ID,
		Role:    role,
	}

	if err := user.HashPassword(req.Password); err != nil {
		http.Error(w, "Ошибка при создании организатора", http.StatusInternalServerError)
		return
	}

	result := database.DB.Create(&user)
	if result.Error != nil {
		http.Error(w, "Пользователь с такой почтой уже существует", http.StatusConflict)
		return
	}

	w.WriteHeader(http.StatusCreated)
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(CreateManagerResponse{
		UserID:  user.ID,
		Email:   user.Email,
		Name:    user.Name,
		Surname: user.Surname,
		Role:    user.Role.Code,
		Message: "Организатор создан",
	})
}
