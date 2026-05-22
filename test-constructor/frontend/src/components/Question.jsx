import ManualInputQuestion from "./questions/ManualInputQuestion";
import SingleChoiceQuestion from "./questions/SingleChoiceQuestion";
import MultipleChoiceQuestion from "./questions/MultipleChoiceQuestion";
import MatchingQuestion from "./questions/MatchingQuestion";
import OrderingQuestion from "./questions/OrderingQuestion";

function SortableQuestion({ question, updateQuestion, deleteQuestion }) {
    switch (question.type) {
        case "shortText":
            return <ManualInputQuestion
                question={question}
                updateQuestion={updateQuestion}
                deleteQuestion={deleteQuestion}
            />;
        case "singleChoice":
            return <SingleChoiceQuestion
                question={question}
                updateQuestion={updateQuestion}
                deleteQuestion={deleteQuestion}
            />;
        case "multipleChoice":
            return <MultipleChoiceQuestion
                question={question}
                updateQuestion={updateQuestion}
                deleteQuestion={deleteQuestion}
            />;
        case "matching":
            return <MatchingQuestion
                question={question}
                updateQuestion={updateQuestion}
                deleteQuestion={deleteQuestion}
            />;
        case "ordering":
            return <OrderingQuestion
                question={question}
                updateQuestion={updateQuestion}
                deleteQuestion={deleteQuestion}
            />;
        default:
            return <div>Неизвестный тип вопроса</div>;
    }
}

export default SortableQuestion;