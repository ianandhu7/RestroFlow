import React from 'react';

const CustomerQueue = ({ customers, onRemoveCustomer }) => {
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
    <div className="customer-list">
      {customers.length === 0 ? (
        <div className="empty-state">
          No customers in queue
        </div>
      ) : (
        customers.map(customer => (
          <div key={customer.id} className="customer-item">
            <div className="customer-info">
              <div className="customer-name">{customer.name}</div>
              <div className="customer-meta">
                Party of {customer.people_count}
                {customer.timestamp && ` • Waiting ${formatWaitTime(customer.timestamp)}`}
              </div>
            </div>
            <button 
              className="btn btn-danger"
              onClick={() => onRemoveCustomer(customer.id)}
            >
              Remove
            </button>
          </div>
        ))
      )}
    </div>
  );
};

export default CustomerQueue;