import React from 'react';

const TableManagement = ({ tables, onTableAction, onAddTable, onRefresh }) => {
  const handleTableClick = (table) => {
    if (table.status === 'occupied') {
      if (window.confirm(`Free table ${table.table_number}?`)) {
        onTableAction('free', table.id);
      }
    } else if (table.status === 'free') {
      if (window.confirm(`Block table ${table.table_number}?`)) {
        onTableAction('block', table.id);
      }
    } else if (table.status === 'blocked') {
      if (window.confirm(`Make table ${table.table_number} available?`)) {
        onTableAction('free', table.id);
      }
    }
  };

  return (
    <div className="card">
      <h2>📋 Table Management</h2>
      
      <div className="tables-grid">
        {tables.map(table => (
          <div 
            key={table.id}
            className={`table-box ${table.status}`}
            onClick={() => handleTableClick(table)}
            title={`Click to ${table.status === 'occupied' ? 'free' : table.status === 'free' ? 'block' : 'make available'}`}
          >
            <div className="table-number">{table.table_number}</div>
            <div className="table-capacity">{table.capacity} seats</div>
            {table.status === 'occupied' && table.customer_name && (
              <div className="table-customer">{table.customer_name}</div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
        <button className="btn" onClick={onAddTable}>
          ➕ Add Table
        </button>
        <button className="btn btn-secondary" onClick={onRefresh}>
          🔄 Refresh
        </button>
      </div>

      <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '8px', fontSize: '14px' }}>
        <strong>Legend:</strong>
        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '12px', height: '12px', backgroundColor: '#d4edda', border: '1px solid #28a745', borderRadius: '2px' }}></div>
            Free
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '12px', height: '12px', backgroundColor: '#f8d7da', border: '1px solid #dc3545', borderRadius: '2px' }}></div>
            Occupied
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '12px', height: '12px', backgroundColor: '#fff3cd', border: '1px solid #ffc107', borderRadius: '2px' }}></div>
            Blocked
          </div>
        </div>
      </div>
    </div>
  );
};

export default TableManagement;