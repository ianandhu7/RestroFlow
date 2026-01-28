import React, { useState, useEffect } from 'react';
import axios from 'axios';
import TableManagement from './TableManagement';
import CustomerQueue from './CustomerQueue';
import AddCustomerModal from './AddCustomerModal';
import AddWaiterModal from './AddWaiterModal';

const Dashboard = ({ onLogout, apiUrl }) => {
  const [dashboardData, setDashboardData] = useState({
    all_tables: [],
    customers: [],
    waiters: [],
    auto_allocator_status: 'OFF'
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddCustomer, setShowAddCustomer] = useState(false);
  const [showAddWaiter, setShowAddWaiter] = useState(false);

  const fetchDashboardData = async () => {
    try {
      const response = await axios.get(`${apiUrl}/api/dashboard_data`);
      setDashboardData(response.data);
      setError('');
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  const handleTableAction = async (action, tableId) => {
    try {
      const formData = new FormData();
      formData.append('table_id', tableId);
      
      await axios.post(`${apiUrl}/${action}`, formData);
      fetchDashboardData(); // Refresh data
    } catch (error) {
      console.error(`Error with ${action}:`, error);
      alert(`Error updating table`);
    }
  };

  const handleAddTable = async () => {
    const capacity = prompt('Enter table capacity (number of seats):');
    if (capacity && !isNaN(capacity) && capacity > 0) {
      try {
        const formData = new FormData();
        formData.append('capacity', capacity);
        
        await axios.post(`${apiUrl}/add_table`, formData);
        alert('Table added successfully');
        fetchDashboardData();
      } catch (error) {
        console.error('Error adding table:', error);
        alert('Error adding table');
      }
    }
  };

  const handleRemoveCustomer = async (customerId) => {
    if (window.confirm('Remove this customer from queue?')) {
      try {
        const formData = new FormData();
        formData.append('customer_id', customerId);
        
        await axios.post(`${apiUrl}/remove_customer`, formData);
        fetchDashboardData();
      } catch (error) {
        console.error('Error removing customer:', error);
        alert('Error removing customer');
      }
    }
  };

  const handleToggleAutoAllocator = async () => {
    try {
      await axios.post(`${apiUrl}/toggle_auto_allocator`);
      fetchDashboardData();
      alert('Auto-allocator toggled successfully');
    } catch (error) {
      console.error('Error toggling auto-allocator:', error);
      alert('Error toggling auto-allocator');
    }
  };

  const occupiedTables = dashboardData.all_tables.filter(table => table.status === 'occupied').length;
  const totalTables = dashboardData.all_tables.length;
  const queueCount = dashboardData.customers.length;
  const waiterCount = dashboardData.waiters.length;

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading">Loading RestroFlow Dashboard...</div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Header */}
      <div className="header">
        <h1>🍽️ RestroFlow Dashboard</h1>
        <div className="header-right">
          <span className="status-indicator"></span>
          <span>System Online</span>
          <button className="logout-btn" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="error" style={{ marginBottom: '24px' }}>
          {error}
        </div>
      )}

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number">{totalTables}</div>
          <div className="stat-label">Total Tables</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{occupiedTables}</div>
          <div className="stat-label">Occupied Tables</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{queueCount}</div>
          <div className="stat-label">Customers in Queue</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{waiterCount}</div>
          <div className="stat-label">Active Waiters</div>
        </div>
      </div>

      {/* Dashboard Grid */}
      <div className="dashboard-grid">
        {/* Table Management */}
        <div className="card">
          <h2>📋 Table Status</h2>
          <TableManagement 
            tables={dashboardData.all_tables}
            onTableAction={handleTableAction}
          />
          <div className="actions">
            <button className="btn" onClick={handleAddTable}>
              Add Table
            </button>
            <button className="btn btn-warning" onClick={fetchDashboardData}>
              Refresh
            </button>
          </div>
        </div>

        {/* Customer Queue */}
        <div className="card">
          <h2>👥 Customer Queue</h2>
          <CustomerQueue 
            customers={dashboardData.customers}
            onRemoveCustomer={handleRemoveCustomer}
          />
          <div className="actions">
            <button 
              className="btn btn-success" 
              onClick={() => setShowAddCustomer(true)}
            >
              Add Customer
            </button>
            <button className="btn btn-warning" onClick={fetchDashboardData}>
              Refresh
            </button>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="card">
          <h2>👨‍💼 Quick Actions</h2>
          <div className="actions">
            <button 
              className="btn" 
              onClick={() => setShowAddWaiter(true)}
            >
              Add Waiter
            </button>
            <button 
              className="btn btn-success" 
              onClick={handleToggleAutoAllocator}
            >
              Toggle Auto-Seat
            </button>
            <button 
              className="btn btn-warning" 
              onClick={() => window.open(`${apiUrl}/health`, '_blank')}
            >
              System Health
            </button>
          </div>
          
          <div className="system-status">
            <h3>System Status</h3>
            <p>✅ Database: Connected</p>
            <p>✅ Tables: {totalTables} configured</p>
            <p>✅ Waiters: {waiterCount} active</p>
            <p>✅ Auto-Allocator: {dashboardData.auto_allocator_status}</p>
          </div>
        </div>
      </div>

      {/* Modals */}
      {showAddCustomer && (
        <AddCustomerModal
          apiUrl={apiUrl}
          onClose={() => setShowAddCustomer(false)}
          onSuccess={() => {
            setShowAddCustomer(false);
            fetchDashboardData();
          }}
        />
      )}

      {showAddWaiter && (
        <AddWaiterModal
          apiUrl={apiUrl}
          onClose={() => setShowAddWaiter(false)}
          onSuccess={() => {
            setShowAddWaiter(false);
            fetchDashboardData();
          }}
        />
      )}
    </div>
  );
};

export default Dashboard;