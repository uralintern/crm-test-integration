import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Registration from "./pages/Registration";
import Home from "./pages/Home.jsx";
import ProtectedRoutes from "./utils/ProtectedRoutes.jsx";
import Login from "./pages/Login.jsx";
import Tests from "./pages/Test.jsx";
import CreateTest from "./pages/CreateTest.jsx";
import MyTestStudent from "./pages/MyTestStudent.jsx";
import StudentHome from "./pages/StudentHome.jsx";
import TestPreviewPage from "./pages/TestPreviewPage.jsx";
import StatisticsTest from "./pages/StatisticsTest.jsx";
import PassingTestStudent from "./pages/PassingTestStudent.jsx";
import SSO from "./pages/SSO.jsx";
import Events from "./pages/Events.jsx";
import Candidates from "./pages/Candidates.jsx";
import CandidateDetails from "./pages/CandidateDetails.jsx";
import EventConfigPage from "./components/EventConfigPage";
import StatisticsEvent from "./pages/StatisticsEvent";

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Navigate to="/registration" replace />} />
                <Route path="/registration" element={<Registration />} />
                <Route path="/login" element={<Login />} />
                <Route path="/sso" element={<SSO />} />

                <Route path="/StudentHome" element={<StudentHome />} />
                <Route path="/student-home" element={<StudentHome />} />
                <Route path="/myTestStudent" element={<MyTestStudent />} />
                <Route path="/test-preview/:test_link" element={<TestPreviewPage />} />
                <Route path="/statisticsTest" element={<StatisticsTest />} />
                <Route path="/passingTestStudent" element={<PassingTestStudent />} />
                <Route path="/statistics/:testId" element={<StatisticsTest />} />
                <Route path="/test/:test_link" element={<PassingTestStudent />} />

                <Route element={<ProtectedRoutes />}>
                    <Route path="/home" element={<Home />} />
                    <Route path="/tests" element={<Tests />} />
                    <Route path="/create" element={<CreateTest />} />
                </Route>

                <Route path="/tests" element={<Tests />} />
                <Route path="/events" element={<Events />} />
                <Route path="/candidates" element={<Candidates />} />
                <Route path="/candidates/:candidateId" element={<CandidateDetails />} />
                <Route path="/event-config" element={<EventConfigPage />} />
                <Route path="/event-statistics/:eventId" element={<StatisticsEvent />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
