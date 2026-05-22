package main

import (
	"log"
	"net/http"
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

const clientURL = "http://localhost:5173"

// @title test constructor
// @version 1.0
// @description backend part of test constructor
// @host localhost:8080
// @BasePath /

// @securityDefinitions.apikey ApiKeyAuth
// @in header
// @name Authorization
func main() {
	database.Connect()

	r := mux.NewRouter()

	r.HandleFunc("/register", auth.Registration).Methods("POST")
	r.HandleFunc("/login", auth.Login).Methods("POST")

	api := r.PathPrefix("/api").Subrouter()
	api.Use(middleware.AuthMiddleware)

	m := api.PathPrefix("/manager").Subrouter()
	//m.Use(middleware.ManagerMiddleware)
	m.HandleFunc("/tests", manager.GetTests).Methods("GET")
	m.HandleFunc("/tests", manager.CreateTest).Methods("POST")
	m.HandleFunc("/tests/delete/{id}", manager.DeleteTest).Methods("POST")
	m.HandleFunc("/events", manager.GetEvents).Methods("GET")
	m.HandleFunc("/events", manager.CreateConfig).Methods("POST")
	m.HandleFunc("/events/{id}", manager.UpdateConfig).Methods("PUT")
	m.HandleFunc("/events/{id}/specializations", manager.GetEventSpecializations).Methods("GET")

	i := api.PathPrefix("/intern").Subrouter()
	i.Use(middleware.InternMiddleware)
	i.HandleFunc("/tests", intern.GetAttempts).Methods("GET")
	i.HandleFunc("/tests/{link}", intern.StartAttempt).Methods("GET")
	i.HandleFunc("/attempt/finish", intern.FinishAttempt).Methods("POST")

	a := api.PathPrefix("/admin").Subrouter()
	a.Use(middleware.AdminMiddleware)
	a.HandleFunc("/manager/create", admin.CreateManager).Methods("POST")

	r.PathPrefix("/swagger/").Handler(httpSwagger.WrapHandler)

	c := cors.New(cors.Options{
		AllowedOrigins:   []string{clientURL, "http://127.0.0.1:8080"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "OPTIONS", "DELETE"},
		AllowedHeaders:   []string{"Content-Type", "Authorization"},
		AllowCredentials: true,
		Debug:            true,
	})

	handler := c.Handler(r)

	log.Println("Starting server on port 8080")
	log.Fatal(http.ListenAndServe(":8080", handler))
}
