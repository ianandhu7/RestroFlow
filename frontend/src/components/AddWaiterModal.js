import React, { useState } from 'react';
import axios from 'axios';

const AddWaiterModal = ({ apiUrl, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
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
      submitData.append('username', formData.username);
      submitData.append('password', formData.password);

      const response = await axios.post(`${apiUrl}/admin/add_waiter`, submitData);

      if (response.data.status === 'success') {
        onSuccess();
        alert(response.data.message);
      } else {
        setError(response.data.message || 'Failed to add waiter');
      }
    } catch (error) {
      console.error('Error adding waiter:', error);
      if (error.response && error.response.data && error.response.data.message) {
        setError(error.response.data.message);
      } else {
        setError('Error adding waiter. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Waiter</h2>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username *</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Enter username"
              minLength="3"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password *</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Enter password"
              minLength="6"
            />
            <small style={{ color: '#6c757d', fontSize: '12px' }}>
              Password must be at least 6 characters long
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
              {loading ? 'Adding...' : 'Add Waiter'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddWaiterModal;