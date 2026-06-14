package auth

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"test-constructor/config"
	"test-constructor/internal/database"
	"test-constructor/internal/models"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type SSOExchangeRequest struct {
	Ticket string `json:"ticket"`
}

type CRMSSOUser struct {
	ID                uint   `json:"id"`
	Email             string `json:"email"`
	FirstName         string `json:"first_name"`
	LastName          string `json:"last_name"`
	DisplayName       string `json:"display_name"`
	Role              string `json:"role"`
	ManagedEventIDs   []uint `json:"managed_event_ids"`
	IsGlobalOrganizer bool   `json:"is_global_organizer"`
	VK                string `json:"vk"`
	VKConfirmed       bool   `json:"vk_confirmed"`
	Course            *int   `json:"course"`
	Specialty         string `json:"specialty"`
	Specializations   any    `json:"specializations"`
}

type CRMContextApplication struct {
	ID int `json:"id"`
}

type CRMContextEvent struct {
	ID int `json:"id"`
}

type CRMContextSpecialization struct {
	ID int `json:"id"`
}

type CRMTestingContext struct {
	Application    CRMContextApplication     `json:"application"`
	Event          *CRMContextEvent          `json:"event"`
	Specialization *CRMContextSpecialization `json:"specialization"`
	AvailableTests any                       `json:"availableTests"`
	CurrentSession any                       `json:"currentSession"`
	LatestResult   any                       `json:"latestResult"`
}

type CRMSSOExchangeResponse struct {
	User        CRMSSOUser         `json:"user"`
	Application *CRMTestingContext `json:"application"`
	Next        string             `json:"next"`
}

type SSOExchangeResponse struct {
	Token       string             `json:"token"`
	UserID      uint               `json:"user_id"`
	Email       string             `json:"email"`
	Name        string             `json:"name"`
	Surname     string             `json:"surname"`
	Role        string             `json:"role"`
	Message     string             `json:"message"`
	Application *CRMTestingContext `json:"application,omitempty"`
	Next        string             `json:"next,omitempty"`
	TestLink    string             `json:"test_link,omitempty"`
}

type CRMExchangeError struct {
	StatusCode int
	Message    string
}

func (err *CRMExchangeError) Error() string {
	return err.Message
}

func SSOExchange(w http.ResponseWriter, r *http.Request) {
	var req SSOExchangeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	req.Ticket = strings.TrimSpace(req.Ticket)
	if req.Ticket == "" {
		http.Error(w, "Ticket is required", http.StatusBadRequest)
		return
	}

	crmPayload, err := exchangeTicketWithCRM(req.Ticket)
	if err != nil {
		log.Printf("CRM SSO exchange failed: %v", err)
		statusCode := http.StatusBadGateway
		var crmErr *CRMExchangeError
		if errors.As(err, &crmErr) {
			statusCode = crmErr.StatusCode
		}
		http.Error(w, err.Error(), statusCode)
		return
	}

	user, err := upsertCRMUser(crmPayload.User)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	if err := upsertUserEvent(user.ID, crmPayload.Application); err != nil {
		log.Printf("Failed to save CRM application context: %v", err)
	}

	token, err := GenerateJWTWithScope(
		user.ID,
		user.Email,
		user.Name,
		user.Surname,
		user.Role.Code,
		crmPayload.User.ManagedEventIDs,
		crmPayload.User.IsGlobalOrganizer,
	)
	if err != nil {
		http.Error(w, "Failed to create token", http.StatusInternalServerError)
		return
	}

	testLink := ""
	if crmPayload.Application != nil && user.Role.Code == "intern" {
		testLink = findTestLinkForApplication(crmPayload.Application, user.ID)
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	json.NewEncoder(w).Encode(SSOExchangeResponse{
		Token:       token,
		UserID:      user.ID,
		Email:       user.Email,
		Name:        user.Name,
		Surname:     user.Surname,
		Role:        user.Role.Code,
		Message:     "SSO login completed",
		Application: crmPayload.Application,
		Next:        crmPayload.Next,
		TestLink:    testLink,
	})
}

func upsertUserEvent(userID uint, application *CRMTestingContext) error {
	if application == nil || application.Event == nil || application.Application.ID == 0 {
		return nil
	}

	userEvent := models.UserEvent{
		UserID:        userID,
		EventID:       uint(application.Event.ID),
		ApplicationID: uint(application.Application.ID),
	}
	return database.DB.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "user_id"}, {Name: "event_id"}},
		DoUpdates: clause.AssignmentColumns([]string{"application_id"}),
	}).Create(&userEvent).Error
}

func exchangeTicketWithCRM(ticket string) (*CRMSSOExchangeResponse, error) {
	cfg := config.Load()
	if strings.TrimSpace(cfg.CRMService) == "" || strings.TrimSpace(cfg.CRMToken) == "" {
		return nil, fmt.Errorf("CRM integration is not configured")
	}

	body, _ := json.Marshal(map[string]string{"ticket": ticket})
	url := strings.TrimRight(cfg.CRMService, "/") + "/api/users/integration/testing/sso-exchange/"
	request, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Accept", "application/json")
	request.Header.Set("X-Service-Token", cfg.CRMToken)

	client := &http.Client{Timeout: 15 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("CRM SSO request failed: %w", err)
	}
	defer response.Body.Close()

	responseBody, _ := io.ReadAll(response.Body)
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		statusCode := http.StatusBadGateway
		if response.StatusCode == http.StatusBadRequest || response.StatusCode == http.StatusForbidden {
			statusCode = response.StatusCode
		}
		return nil, &CRMExchangeError{
			StatusCode: statusCode,
			Message:    fmt.Sprintf("CRM SSO exchange failed with status %d: %s", response.StatusCode, string(responseBody)),
		}
	}

	var payload CRMSSOExchangeResponse
	if err := json.Unmarshal(responseBody, &payload); err != nil {
		return nil, fmt.Errorf("CRM SSO response parse failed: %w", err)
	}
	return &payload, nil
}

func upsertCRMUser(data CRMSSOUser) (*models.User, error) {
	email := strings.ToLower(strings.TrimSpace(data.Email))
	if email == "" {
		return nil, fmt.Errorf("CRM user email is empty")
	}

	roleCode := mapCRMRole(data.Role)
	var role models.Role
	if err := database.DB.Where("code = ?", roleCode).First(&role).Error; err != nil {
		return nil, fmt.Errorf("role %s was not found: %w", roleCode, err)
	}

	firstName := strings.TrimSpace(data.FirstName)
	lastName := strings.TrimSpace(data.LastName)
	if firstName == "" {
		firstName = strings.TrimSpace(data.DisplayName)
	}
	if lastName == "" {
		lastName = "-"
	}

	var user models.User
	err := database.DB.Preload("Role").Where("LOWER(email) = ?", email).First(&user).Error
	if err == nil {
		user.Email = email
		user.Name = firstName
		user.Surname = lastName
		user.RoleID = role.ID
		user.Role = role
		if err := database.DB.Save(&user).Error; err != nil {
			return nil, err
		}
		return &user, nil
	}
	if err != nil && err != gorm.ErrRecordNotFound {
		return nil, err
	}

	user = models.User{
		Email:   email,
		Name:    firstName,
		Surname: lastName,
		RoleID:  role.ID,
		Role:    role,
	}
	if err := user.HashPassword(uuid.NewString()); err != nil {
		return nil, err
	}
	if err := database.DB.Create(&user).Error; err != nil {
		return nil, err
	}
	return &user, nil
}

func mapCRMRole(role string) string {
	normalized := strings.ToLower(strings.TrimSpace(role))
	if normalized == "organizer" || strings.Contains(normalized, "admin") || strings.Contains(normalized, "curator") {
		return "manager"
	}
	return "intern"
}

func findTestLinkForApplication(application *CRMTestingContext, internID uint) string {
	if application == nil || application.Event == nil {
		return ""
	}

	eventID := uint(application.Event.ID)
	applicationID := uint(application.Application.ID)
	specializationID := uint(0)
	if application.Specialization != nil {
		specializationID = uint(application.Specialization.ID)
	}

	var eventConfigs []models.EventConfig
	query := database.DB.Where("event_id = ?", eventID).Order("config_id ASC")
	if specializationID > 0 {
		query = query.Where("specialization_id = ?", specializationID)
	}

	if err := query.Find(&eventConfigs).Error; err != nil || len(eventConfigs) == 0 {
		return ""
	}

	configIDs := make([]uint, 0, len(eventConfigs))
	for _, eventConfig := range eventConfigs {
		configIDs = append(configIDs, eventConfig.ConfigID)
	}

	var attempts []models.Attempt
	if err := database.DB.
		Where("intern_id = ? AND application_id = ? AND config_id IN ? AND end_time IS NOT NULL", internID, applicationID, configIDs).
		Find(&attempts).Error; err != nil {
		return eventConfigs[0].TestLink.String()
	}

	finishedConfigIDs := make(map[uint]struct{}, len(attempts))
	for _, attempt := range attempts {
		finishedConfigIDs[attempt.ConfigID] = struct{}{}
	}

	for _, eventConfig := range eventConfigs {
		if _, exists := finishedConfigIDs[eventConfig.ConfigID]; !exists {
			return eventConfig.TestLink.String()
		}
	}

	return ""
}
