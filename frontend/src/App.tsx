import { Routes, Route } from 'react-router-dom';
import NavSidebar from './components/NavSidebar';
import ErrorBoundary from './components/ErrorBoundary';
import DashboardPage from './pages/DashboardPage';
import CarersPage from './pages/CarersPage';
import PatientsPage from './pages/PatientsPage';
import SkillsPage from './pages/SkillsPage';
import ConstraintsPage from './pages/ConstraintsPage';
import ExceptionsPage from './pages/ExceptionsPage';
import ReportsPage from './pages/ReportsPage';
import ScenariosPage from './pages/ScenariosPage';
import ConfigPage from './pages/ConfigPage';
import VisitsPage from './pages/VisitsPage';

function App() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <NavSidebar />
      <main className="flex-1 overflow-auto">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/carers" element={<CarersPage />} />
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/visits" element={<VisitsPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/constraints" element={<ConstraintsPage />} />
            <Route path="/exceptions" element={<ExceptionsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="/config" element={<ConfigPage />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default App;
