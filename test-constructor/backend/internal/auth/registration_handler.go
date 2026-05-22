package auth

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/database"
	"test-constructor/internal/models"
)

type RegisterRequest struct {
	Email    string `json:"email"`
	Name     string `json:"name"`
	Surname  string `json:"surname"`
	Password string `json:"password"`
}

type RegisterResponse struct {
	Token   string `json:"token"`
	UserID  uint   `json:"user_id"`
	Email   string `json:"email"`
	Name    string `json:"name"`
	Surname string `json:"surname"`
	Role    string `json:"role"`
	Message string `json:"message"`
}

// @Summary Создать пользователя
// @Description Создать нового пользователя
// @Tags users
// @Accept json
// @Produce json
// @Param user body RegisterRequest true "User object"
// @Success 201 {object} RegisterResponse
// @Router /register [post]
func Registration(w http.ResponseWriter, r *http.Request) {
	var req RegisterRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Неправильный JSON", http.StatusBadRequest)
		return
	}

	if req.Email == "" || req.Password == "" || req.Name == "" || req.Surname == "" {
		http.Error(w, "Не все поля заполнены", http.StatusBadRequest)
		return
	}

	var role models.Role
	if err := database.DB.Where("code = ?", "intern").First(&role).Error; err != nil {
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
		http.Error(w, "Ошибка при создании пользователя", http.StatusInternalServerError)
		return
	}

	result := database.DB.Create(&user)
	if result.Error != nil {
		http.Error(w, "Пользователь с такой почтой уже существует", http.StatusConflict)
		return
	}

	token, err := GenerateJWT(user.ID, user.Email, user.Name, user.Surname, user.Role.Code)
	if err != nil {
		http.Error(w, "Ошибка при создании токена", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusCreated)
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(RegisterResponse{
		Token:   token,
		UserID:  user.ID,
		Email:   user.Email,
		Name:    user.Name,
		Surname: user.Surname,
		Role:    user.Role.Code,
		Message: "Пользователь создан",
	})
}
