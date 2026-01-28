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
    analytics: {
      avg_wait_time: 0,
      longest_wait_time: 0,
      seated_today: 0
    },
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
      
      const endpoint = action === 'free' ? '/free_table' : '/block_table';
      const response = await axios.post(`${apiUrl}${endpoint}`, formData);
      
      if (response.data.status === 'success') {
        fetchDashboardData(); // Refresh data
      }
    } catch (error) {
      console.error('Error updating table:', error);
      alert('Error updating table status');
    }
  };

  const handleAddTable = async () => {
    const capacity = prompt('Enter table capacity (number of seats):');
    if (capacity && !isNaN(capacity) && capacity > 0) {
      try {
        const formData = new FormData();
        formData.append('capacity', capacity);
        
        const response = await axios.post(`${apiUrl}/add_table`, formData);
        
        if (response.data.status === 'success') {
          fetchDashboardData();
          alert(response.data.message);
        }
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
        
        const response = await axios.post(`${apiUrl}/remove_customer`, formData);
        
        if (response.data.status === 'success') {
          fetchDashboardData();
        }
      } catch (error) {
        console.error('Error removing customer:', error);
        alert('Error removing customer');
      }
    }
  };

  const handleToggleAutoAllocator = async () => {
    try {
      const response = await axios.post(`${apiUrl}/toggle_auto_allocator`);
      
      if (response.data.status === 'success') {
        fetchDashboardData();
        alert(response.data.message);
      }
    } catch (error) {
      console.error('Error toggling auto-allocator:', error);
      alert('Error toggling auto-allocator');
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  const occupiedTables = dashboardData.all_tables.filter(table => table.status === 'occupied').length;
  const freeTables = dashboardData.all_tables.filter(table => table.status === 'free').length;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="header-content">
          <h1>🍽️ RestroFlow Dashboard</h1>
          <div className="header-actions">
            <div className="status-indicator">
              <div className="status-dot"></div>
              System Online
            </div>
            <button className="btn btn-danger" onClick={onLogout}>
              Logout
            </button>
          </div>
        </div>
      </div>

      <div className="container">
        {error && <div className="error">{error}</div>}

        {/* Stats Grid */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-number">{dashboardData.all_tables.length}</div>
            <div className="stat-label">Total Tables</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{occupiedTables}</div>
            <div className="stat-label">Occupied Tables</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{dashboardData.customers.length}</div>
            <div className="stat-label">Customers in Queue</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{freeTables}</div>
            <div className="stat-label">Available Tables</div>
          </div>
        </div>

        {/* Main Dashboard Grid */}
        <div className="dashboard-grid">
          <div>
            <TableManagement 
              tables={dashboardData.all_tables}
              onTableAction={handleTableAction}
              onAddTable={handleAddTable}
              onRefresh={fetchDashboardData}
            />
          </div>
          
          <div>
            <CustomerQueue 
              customers={dashboardData.customers}
              onRemoveCustomer={handleRemoveCustomer}
              onAddCustomer={() => setShowAddCustomer(true)}
              onRefresh={fetchDashboardData}
            />
            
            <div className="card" style={{ marginTop: '24px' }}>
              <h2>⚙️ Quick Actions</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <button 
                  className="btn btn-success" 
                  onClick={() => setShowAddWaiter(true)}
                >
                  👨‍💼 Add Waiter
                </button>
                <button 
                  className="btn btn-warning" 
                  onClick={handleToggleAutoAllocator}
                >
                  🔄 Toggle Auto-Seat ({dashboardData.auto_allocator_status})
                </button>
                <button 
                  className="btn btn-secondary" 
                  onClick={() => window.open(`${apiUrl}/health`, '_blank')}
                >
                  🔍 System Health
                </button>
              </div>
              
              <div style={{ marginTop: '20px', padding: '16px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>System Status</h3>
                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                  <div>✅ Database: Connected</div>
                  <div>✅ Tables: {dashboardData.all_tables.length} configured</div>
                  <div>✅ Waiters: {dashboardData.waiters.length} active</div>
                  <div>✅ Auto-Allocator: {dashboardData.auto_allocator_status}</div>
                </div>
              </div>
            </div>
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