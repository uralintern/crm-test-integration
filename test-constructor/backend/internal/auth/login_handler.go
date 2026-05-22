package auth

import (
	"encoding/json"
	"net/http"
	"test-constructor/internal/database"
	"test-constructor/internal/models"
)

type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type LoginResponse struct {
	Token   string `json:"token"`
	UserID  uint   `json:"user_id"`
	Email   string `json:"email"`
	Name    string `json:"name"`
	Surname string `json:"surname"`
	Role    string `json:"role"`
	Message string `json:"message"`
}

// @Summary Вход
// @Description Логин
// @Tags users
// @Accept json
// @Produce json
// @Param user body LoginRequest true "User object"
// @Success 200 {object} LoginResponse
// @Router /login [post]
func Login(w http.ResponseWriter, r *http.Request) {
	var req LoginRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Неправильный JSON", http.StatusBadRequest)
		return
	}

	if req.Email == "" || req.Password == "" {
		http.Error(w, "Не все поля заполнены", http.StatusBadRequest)
		return
	}

	var user models.User
	if err := database.DB.Preload("Role").Where("email = ?", req.Email).First(&user).Error; err != nil {
		http.Error(w, "Неправильный логин или пароль", http.StatusUnauthorized)
		return
	}

	if err := user.CheckPassword(req.Password); err != nil {
		http.Error(w, "Неправильный логин или пароль", http.StatusUnauthorized)
		return
	}

	token, err := GenerateJWT(user.ID, user.Email, user.Name, user.Surname, user.Role.Code)
	if err != nil {
		http.Error(w, "Ошибка при создании токена", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(LoginResponse{
		Token:   token,
		UserID:  user.ID,
		Email:   user.Email,
		Name:    user.Name,
		Surname: user.Surname,
		Role:    user.Role.Code,
		Message: "Вы вошли",
	})
}
