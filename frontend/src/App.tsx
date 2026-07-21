import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import NavSidebar from './components/NavSidebar';
import ErrorBoundary from './components/ErrorBoundary';
import SplashPage from './pages/SplashPage';
import DashboardPage from './pages/DashboardPage';
import CarersPage from './pages/CarersPage';
import PatientsPage from './pages/PatientsPage';
import SoftSkillsPage from './pages/SoftSkillsPage';
import ExceptionsPage from './pages/ExceptionsPage';
import ReportsPage from './pages/ReportsPage';
import ScenariosPage from './pages/ScenariosPage';
import ConfigPage from './pages/ConfigPage';
import VisitsPage from './pages/VisitsPage';

function App() {
  const [showSplash, setShowSplash] = useState(true);

  if (showSplash) {
    return <SplashPage onEnter={() => setShowSplash(false)} />;
  }

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
            <Route path="/soft-skills" element={<SoftSkillsPage />} />
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
