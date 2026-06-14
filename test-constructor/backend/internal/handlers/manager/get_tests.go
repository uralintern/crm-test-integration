package manager

import (
    "encoding/json"
    "net/http"
    "strconv"
    "test-constructor/internal/database"
    "test-constructor/internal/models"

    "github.com/gorilla/mux"
    "gorm.io/gorm"
)

type TestQuestionInfo struct {
    ID          uint                   `json:"id"`
    QuestionID  uint                   `json:"question_id"`
    Text        string                 `json:"text"`
    Points      int                    `json:"points"`
    Type        string                 `json:"type"`
    OrderNumber int                    `json:"order_number"`
    Options     models.QuestionOptions `json:"options"`
}

type TestInfo struct {
    ID           uint               `json:"test_id"`
    TestID       uint               `json:"id"`
    CreatorID    uint               `json:"creator_id"`
    Title        string             `json:"title"`
    Description  string             `json:"description"`
    IsExtra      bool               `json:"is_extra"`
    IsPercentage bool               `json:"is_percentage"`
    Threshold    float64            `json:"threshold"`
    SuccessText  string             `json:"success_text"`
    FailText     string             `json:"fail_text"`
    CompleteTime int                `json:"complete_time"`
    MaxScore     int                `json:"max_score"`
    Questions    []TestQuestionInfo `json:"questions,omitempty"`
}

type TestsInfoResponse struct {
    Tests []TestInfo `json:"tests"`
}

func GetTests(w http.ResponseWriter, r *http.Request) {
    var tests []models.Test
    if err := database.DB.Preload("Questions").Find(&tests).Error; err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    response := TestsInfoResponse{Tests: make([]TestInfo, 0, len(tests))}
    for _, test := range tests {
        response.Tests = append(response.Tests, buildTestInfo(test, nil))
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
}

func GetTest(w http.ResponseWriter, r *http.Request) {
    testID, err := strconv.ParseUint(mux.Vars(r)["id"], 10, 64)
    if err != nil || testID == 0 {
        http.Error(w, "Invalid test id", http.StatusBadRequest)
        return
    }

    var test models.Test
    if err := database.DB.Preload("Questions", func(db *gorm.DB) *gorm.DB {
        return db.Order("order_number ASC, id ASC")
    }).First(&test, uint(testID)).Error; err != nil {
        if err == gorm.ErrRecordNotFound {
            http.Error(w, "Test not found", http.StatusNotFound)
        } else {
            http.Error(w, err.Error(), http.StatusInternalServerError)
        }
        return
    }

    questions := make([]TestQuestionInfo, 0, len(test.Questions))
    for _, question := range test.Questions {
        questions = append(questions, buildQuestionInfo(question))
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(buildTestInfo(test, questions))
}

func DeleteTest(w http.ResponseWriter, r *http.Request) {
    testID := mux.Vars(r)["id"]
    if err := database.DB.Where("id = ?", testID).Delete(&models.Test{}).Error; err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }

    w.WriteHeader(http.StatusOK)
}

func buildTestInfo(test models.Test, questions []TestQuestionInfo) TestInfo {
    maxScore := 0
    for _, question := range test.Questions {
        maxScore += question.Points
    }

    return TestInfo{
        ID:           test.ID,
        TestID:       test.ID,
        CreatorID:    test.CreatorID,
        Title:        test.Title,
        Description:  test.Description,
        IsExtra:      test.IsExtra,
        IsPercentage: test.IsPercentage,
        Threshold:    test.Threshold,
        SuccessText:  test.SuccessText,
        FailText:     test.FailText,
        CompleteTime: test.CompleteTime,
        MaxScore:     maxScore,
        Questions:    questions,
    }
}

func buildQuestionInfo(question models.Question) TestQuestionInfo {
    var options models.QuestionOptions
    _ = json.Unmarshal(question.Options, &options)
    return TestQuestionInfo{
        ID:          question.ID,
        QuestionID:  question.ID,
        Text:        question.Text,
        Points:      question.Points,
        Type:        string(question.Type),
        OrderNumber: question.OrderNumber,
        Options:     options,
    }
}
