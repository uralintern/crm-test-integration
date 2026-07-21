import { lazy, Suspense, useContext } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Header from "../components/Header/Header";
import PageLoader from "../components/Loading/PageLoader";
import { AuthContext } from "../context/AuthContext";

const EventsPage = lazy(() => import("../features/events/pages/EventsPage"));
const DirectionsPage = lazy(() => import("../features/events/pages/DirectionsPage"));
const ProjectsPage = lazy(() => import("../features/events/pages/ProjectsPage"));
const RequestsPage = lazy(() => import("../features/requests/pages/RequestsPage"));
const InternshipsPage = lazy(() => import("../features/internships/pages/InternshipsPage"));
const InternshipsAdminPage = lazy(() => import("../features/internships/pages/InternshipsAdminPage"));
const PlannerPage = lazy(() => import("../features/planner/pages/PlannerPage"));
const ArchivePage = lazy(() => import("../features/events/pages/ArchivePage"));
const ProfilePage = lazy(() => import("../features/profile/ProfilePage"));
const LoginPage = lazy(() => import("../features/auth/Login"));
const RegisterPage = lazy(() => import("../features/auth/Register"));

export default function AppRouter() {
  const { user } = useContext(AuthContext);
  const isGuest = !user;

  return (
    <BrowserRouter>
      <Header />
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Navigate to="/events" replace />} />

          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route path="/events" element={<EventsPage />} />
          <Route path="/events/:eventId/directions" element={<DirectionsPage />} />
          <Route path="/events/:eventId/directions/:directionId/projects" element={<ProjectsPage />} />

          {isGuest ? (
            <Route path="*" element={<Navigate to="/events" replace />} />
          ) : (
            <>
              <Route path="/planner" element={<PlannerPage />} />
              <Route path="/automation" element={<ArchivePage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/requests" element={<RequestsPage />} />
              <Route path="/internships" element={<InternshipsPage />} />
              <Route path="/internships/admin" element={<InternshipsAdminPage />} />
              <Route path="*" element={<Navigate to="/events" replace />} />
            </>
          )}
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
