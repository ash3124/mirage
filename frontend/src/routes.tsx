import { Route, Routes } from 'react-router-dom';
import Landing from './pages/Landing';
import Privacy from './pages/Privacy';
import SafetyKit from './pages/SafetyKit';
import Studio from './pages/Studio';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/studio" element={<Studio />} />
      <Route path="/safety-kit" element={<SafetyKit />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}
