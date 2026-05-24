package main

import (
    "log"
    "net/http"
    "strings"
    "test-constructor/config"
    "test-constructor/internal/auth"
    "test-constructor/internal/database"
    "test-constructor/internal/handlers/admin"
    "test-constructor/internal/handlers/intern"
    "test-constructor/internal/handlers/manager"
    "test-constructor/internal/middleware"

    _ "test-constructor/docs"

    "github.com/gorilla/mux"
    "github.com/rs/cors"
    httpSwagger "github.com/swaggo/http-swagger"
)

// @title test constructor
// @version 1.0
// @description backend part of test constructor
// @host localhost:8080
// @BasePath /

// @securityDefinitions.apikey ApiKeyAuth
// @in header
// @name Authorization
func main() {
    cfg := config.Load()
    database.Connect()

    r := mux.NewRouter()

    r.HandleFunc("/register", auth.Registration).Methods("POST")
    r.HandleFunc("/login", auth.Login).Methods("POST")
    r.HandleFunc("/sso/exchange", auth.SSOExchange).Methods("POST")

    api := r.PathPrefix("/api").Subrouter()
    api.Use(middleware.AuthMiddleware)

    m := api.PathPrefix("/manager").Subrouter()
    m.Use(middleware.ManagerMiddleware)
    m.HandleFunc("/tests", manager.GetTests).Methods("GET")
    m.HandleFunc("/tests", manager.CreateTest).Methods("POST")
    m.HandleFunc("/tests/delete/{id}", manager.DeleteTest).Methods("POST")
    m.HandleFunc("/tests/{id}/attempts", manager.GetTestAttempts).Methods("GET")
    m.HandleFunc("/events", manager.GetEvents).Methods("GET")
    m.HandleFunc("/events", manager.CreateConfig).Methods("POST")
    m.HandleFunc("/events/{id}", manager.UpdateConfig).Methods("PUT")
    m.HandleFunc("/events/{id}/configs", manager.GetEventConfigs).Methods("GET")
    m.HandleFunc("/events/{id}/attempts", manager.GetEventAttempts).Methods("GET")
    m.HandleFunc("/events/{id}/specializations", manager.GetEventSpecializations).Methods("GET")
    m.HandleFunc("/users", manager.GetUsers).Methods("GET")
    m.HandleFunc("/users/{id}", manager.GetUserStatistics).Methods("GET")

    i := api.PathPrefix("/intern").Subrouter()
    i.Use(middleware.InternMiddleware)
    i.HandleFunc("/tests", intern.GetAttempts).Methods("GET")
    i.HandleFunc("/tests/{link}", intern.StartAttempt).Methods("GET")
    i.HandleFunc("/attempt/finish", intern.FinishAttempt).Methods("POST")

    a := api.PathPrefix("/admin").Subrouter()
    a.Use(middleware.AdminMiddleware)
    a.HandleFunc("/manager/create", admin.CreateManager).Methods("POST")

    r.PathPrefix("/swagger/").Handler(httpSwagger.WrapHandler)

    allowedOrigins := []string{"http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"}
    if strings.TrimSpace(cfg.ClientURL) != "" {
        allowedOrigins = append(allowedOrigins, strings.TrimRight(cfg.ClientURL, "/"))
    }

    c := cors.New(cors.Options{
        AllowedOrigins:   allowedOrigins,
        AllowedMethods:   []string{"GET", "POST", "PUT", "OPTIONS", "DELETE"},
        AllowedHeaders:   []string{"Content-Type", "Authorization"},
        AllowCredentials: true,
    })

    handler := c.Handler(r)

    log.Printf("starting server on port %s", cfg.Port)
    log.Fatal(http.ListenAndServe(":"+cfg.Port, handler))
}

