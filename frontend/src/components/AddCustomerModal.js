import React, { useState } from 'react';
import axios from 'axios';

const AddCustomerModal = ({ apiUrl, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    name: '',
    people_count: ''
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

      await axios.post(`${apiUrl}/add_customer`, submitData, {
        withCredentials: true
      });
      onSuccess();
      alert('Customer added successfully');
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
          <h3>Add Customer to Queue</h3>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Customer Name:</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="people_count">Party Size:</label>
            <input
              type="number"
              id="people_count"
              name="people_count"
              value={formData.people_count}
              onChange={handleChange}
              required
              min="1"
              disabled={loading}
            />
          </div>

          <div className="modal-actions">
            <button 
              type="button" 
              className="btn btn-danger" 
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
              {loading ? 'Adding...' : 'Submit'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddCustomerModal;