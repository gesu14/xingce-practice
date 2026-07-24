import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { PracticePage } from './pages/PracticePage';
import { QuizPage } from './pages/QuizPage';
import { WrongPage } from './pages/WrongPage';
import { SprintListPage, SprintPackPage } from './pages/SprintPage';
import { TipDetailPage, TipsPage } from './pages/TipsPage';
import './App.css';

export default function App() {
  return (
    <HashRouter>
      <div className="app-shell">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/practice" element={<PracticePage />} />
          <Route path="/quiz" element={<QuizPage />} />
          <Route path="/wrong" element={<WrongPage />} />
          <Route path="/sprint" element={<SprintListPage />} />
          <Route path="/sprint/:packId" element={<SprintPackPage />} />
          <Route path="/tips" element={<TipsPage />} />
          <Route path="/tips/:tipId" element={<TipDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </HashRouter>
  );
}
