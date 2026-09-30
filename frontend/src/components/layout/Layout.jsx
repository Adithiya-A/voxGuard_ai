import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import AlertBanner from '../security/AlertBanner';

export default function Layout() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-container-lowest text-on-surface">
      {/* Persistent Docked Sidebar */}
      <Sidebar />

      {/* Main Viewport (Pushed right by w-64 sidebar) */}
      <div className="pl-64 flex flex-col flex-1 h-screen overflow-hidden min-w-0">
        <Header />
        
        {/* Scrollable Content Container */}
        <main className="flex-1 overflow-y-auto bg-surface-dim bg-grid-cyber min-h-0 relative">
          <Outlet />
        </main>

        {/* Global Floating Alert Notification Toasts */}
        <AlertBanner />
      </div>
    </div>
  );
}
