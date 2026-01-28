import React from 'react';

const TableManagement = ({ tables, onTableAction }) => {
  const handleTableClick = (table) => {
    if (table.status === 'occupied') {
      if (window.confirm(`Free table ${table.table_number}?`)) {
        onTableAction('free_table', table.id);
      }
    } else if (table.status === 'free') {
      if (window.confirm(`Block table ${table.table_number}?`)) {
        onTableAction('block_table', table.id);
      }
    } else if (table.status === 'blocked') {
      if (window.confirm(`Make table ${table.table_number} available?`)) {
        onTableAction('free_table', table.id);
      }
    }
  };

  return (
    <div className="table-grid">
      {tables.map(table => (
        <div 
          key={table.id}
          className={`table-box ${table.status}`}
          onClick={() => handleTableClick(table)}
        >
          <div className="table-number">{table.table_number}</div>
          <div className="table-capacity">{table.capacity} seats</div>
          {table.status === 'occupied' && table.customer_name && (
            <div className="table-customer">{table.customer_name}</div>
          )}
        </div>
      ))}
    </div>
  );
};

export default TableManagement;