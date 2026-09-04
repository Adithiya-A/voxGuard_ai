import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AppContext = createContext();

export function AppProvider({ children }) {
  const [user, setUser] = useState({
    name: 'C. Vance, CISSP',
    role: 'Lead Incident Commander',
    badgeId: 'DEF-8821-SOC',
    organization: 'FinSecure Global Core // Enclave Alpha',
    isAuthenticated: true,
  });

  const [activeCallId, setActiveCallId] = useState('VS-2026-00081');
  const [activeCallData, setActiveCallData] = useState(null);
  const [incidentsCount, setIncidentsCount] = useState(14);
  const [notifications, setNotifications] = useState([]);
  const [systemAlert, setSystemAlert] = useState(null);

  // Load initial call data
  useEffect(() => {
    loadCall(activeCallId);
  }, [activeCallId]);

  const loadCall = async (id) => {
    try {
      const data = await api.getCallById(id);
      setActiveCallData(data);
    } catch (e) {
      console.warn("Using fallback local call data");
    }
  };

  const addNotification = (notif) => {
    const id = Date.now();
    const item = { id, ...notif };
    setNotifications((prev) => [item, ...prev.slice(0, 4)]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 5000);
  };

  const triggerSecurityAction = async (callId, action, reason) => {
    try {
      // Find incident if exists
      const incs = await api.getIncidents();
      const inc = incs.find((i) => i.call_id === callId);
      if (inc) {
        await api.incidentAction(inc.incident_id, action, reason);
      }
    } catch (e) {
      console.log("Applied action in local state:", action);
    }

    // Update active call status
    if (activeCallData && activeCallData.call_id === callId) {
      setActiveCallData((prev) => ({
        ...prev,
        status: action === 'BLOCK_TRANSACTION' ? 'BLOCKED' : action,
        action: action,
        timeline: [
          ...(prev.timeline || []),
          {
            time: "00:21",
            score: prev.trust_score,
            label: `SECURITY ACTION TRIGGERED: ${action} (${reason})`,
            type: action === 'BLOCK_TRANSACTION' ? 'block' : 'warning'
          }
        ]
      }));
    }

    addNotification({
      type: action === 'BLOCK_TRANSACTION' ? 'critical' : 'warning',
      title: action === 'BLOCK_TRANSACTION' ? 'TRANSACTION BLOCKED' : 'ACTION ENFORCED',
      message: `Enforced ${action} on ${callId}. Reason: ${reason}`
    });
  };

  return (
    <AppContext.Provider
      value={{
        user,
        setUser,
        activeCallId,
        setActiveCallId,
        activeCallData,
        setActiveCallData,
        incidentsCount,
        setIncidentsCount,
        notifications,
        addNotification,
        systemAlert,
        setSystemAlert,
        triggerSecurityAction,
        loadCall,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
