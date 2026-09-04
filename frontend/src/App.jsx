import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import Layout from './components/layout/Layout';

import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import LiveCall from './pages/LiveCall';
import Incidents from './pages/Incidents';
import Investigation from './pages/Investigation';
import CallHistory from './pages/CallHistory';
import AuditLogs from './pages/AuditLogs';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import DemoSimulator from './pages/DemoSimulator';

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Enterprise Login Route */}
          <Route path="/login" element={<Login />} />

          {/* Authenticated SOC Enclave Routes wrapped with Persistent Shell */}
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/live-call" element={<LiveCall />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/investigation/:callId" element={<Investigation />} />
            <Route path="/investigation" element={<Investigation />} />
            <Route path="/call-history" element={<CallHistory />} />
            <Route path="/audit-logs" element={<AuditLogs />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/demo" element={<DemoSimulator />} />
          </Route>

          {/* Fallback to Dashboard */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
