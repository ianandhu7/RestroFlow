import React from 'react';

const CustomerQueue = ({ customers, onRemoveCustomer, onAddCustomer, onRefresh }) => {
  const formatWaitTime = (timestamp) => {
    if (!timestamp) return 'Unknown';
    
    const now = new Date();
    const customerTime = new Date(timestamp);
    const diffMinutes = Math.floor((now - customerTime) / (1000 * 60));
    
    if (diffMinutes < 1) return 'Just arrived';
    if (diffMinutes < 60) return `${diffMinutes} min`;
    
    const hours = Math.floor(diffMinutes / 60);
    const minutes = diffMinutes % 60;
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="card">
      <h2>👥 Customer Queue ({customers.length})</h2>
      
      <div className="customer-list">
        {customers.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '40px 20px', 
            color: '#6c757d',
            fontStyle: 'italic'
          }}>
            No customers in queue
          </div>
        ) : (
          customers.map(customer => (
            <div key={customer.id} className="customer-item">
              <div className="customer-info">
                <h4>{customer.name}</h4>
                <div className="customer-meta">
                  Party of {customer.people_count} • Waiting {formatWaitTime(customer.timestamp)}
                  {customer.phone_number && (
                    <span> • {customer.phone_number}</span>
                  )}
                </div>
              </div>
              <div className="customer-actions">
                <button 
                  className="btn btn-danger btn-sm"
                  onClick={() => onRemoveCustomer(customer.id)}
                  title="Remove from queue"
                >
                  Remove
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
        <button className="btn btn-success" onClick={onAddCustomer}>
          ➕ Add Customer
        </button>
        <button className="btn btn-secondary" onClick={onRefresh}>
          🔄 Refresh
        </button>
      </div>

      {customers.length > 0 && (
        <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#e7f3ff', borderRadius: '8px', fontSize: '14px' }}>
          <strong>Queue Summary:</strong>
          <div style={{ marginTop: '8px' }}>
            • Total customers: {customers.length}<br />
            • Average party size: {customers.length > 0 ? Math.round(customers.reduce((sum, c) => sum + c.people_count, 0) / customers.length) : 0}<br />
            • Longest wait: {customers.length > 0 ? formatWaitTime(Math.min(...customers.map(c => new Date(c.timestamp)))) : 'N/A'}
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerQueue;