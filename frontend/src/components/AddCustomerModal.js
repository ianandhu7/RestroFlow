import React, { useState } from 'react';
import axios from 'axios';

const AddCustomerModal = ({ apiUrl, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    name: '',
    people_count: '',
    phone_number: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const submitData = new FormData();
      submitData.append('name', formData.name);
      submitData.append('people_count', formData.people_count);
      if (formData.phone_number) {
        submitData.append('phone_number', formData.phone_number);
      }

      const response = await axios.post(`${apiUrl}/add_customer`, submitData);

      if (response.data.status === 'success') {
        onSuccess();
        alert(response.data.message);
      } else {
        setError(response.data.message || 'Failed to add customer');
      }
    } catch (error) {
      console.error('Error adding customer:', error);
      setError('Error adding customer. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add Customer to Queue</h2>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Customer Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Enter customer name"
            />
          </div>

          <div className="form-group">
            <label htmlFor="people_count">Party Size *</label>
            <input
              type="number"
              id="people_count"
              name="people_count"
              value={formData.people_count}
              onChange={handleChange}
              required
              min="1"
              max="20"
              disabled={loading}
              placeholder="Number of people"
            />
          </div>

          <div className="form-group">
            <label htmlFor="phone_number">Phone Number (Optional)</label>
            <input
              type="tel"
              id="phone_number"
              name="phone_number"
              value={formData.phone_number}
              onChange={handleChange}
              disabled={loading}
              placeholder="10-digit phone number"
              pattern="[0-9]{10}"
            />
            <small style={{ color: '#6c757d', fontSize: '12px' }}>
              Enter 10 digits only (without +91)
            </small>
          </div>

          <div className="modal-actions">
            <button 
              type="button" 
              className="btn btn-secondary" 
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-success"
              disabled={loading}
            >
              {loading ? 'Adding...' : 'Add Customer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddCustomerModal;