package middleware

import (
	"net/http"
	"test-constructor/internal/auth"
)

func ManagerMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims, ok := r.Context().Value(UserContextKey).(*auth.JWTClaims)
		if !ok {
			http.Error(w, "Authentication failed", http.StatusUnauthorized)
			return
		}

		if claims.Role == "intern" {
			http.Error(w, "Forbidden", http.StatusForbidden)
			return
		}

		next.ServeHTTP(w, r)
	})
}
