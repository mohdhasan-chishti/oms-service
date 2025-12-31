// Rozana Payment Test Client JavaScript
class RozanaPaymentClient {
    constructor() {
        this.currentOrder = null;
        this.razorpayInstance = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.paymentMethods = [];
        this.totalAmount = 0;
        this.addPaymentMethod(); // Add first payment method by default
        this.log('🚀 Rozana Payment Test Client initialized');
    }

    setupEventListeners() {
        // Remove existing listeners to prevent duplicates
        this.removeEventListeners();
        
        const orderForm = document.getElementById('orderForm');
        if (orderForm) {
            this.orderFormHandler = (e) => {
                e.preventDefault();
                this.createOrder();
            };
            orderForm.addEventListener('submit', this.orderFormHandler);
        }

        const payButton = document.getElementById('payButton');
        if (payButton) {
            this.payButtonHandler = () => {
                this.initiatePayment();
            };
            payButton.addEventListener('click', this.payButtonHandler);
        }

        // Add payment method button
        const addPaymentMethodBtn = document.getElementById('addPaymentMethod');
        if (addPaymentMethodBtn) {
            this.addPaymentMethodHandler = () => {
                this.addPaymentMethod();
            };
            addPaymentMethodBtn.addEventListener('click', this.addPaymentMethodHandler);
        }

        // Auto-calculate total from items
        const orderItems = document.getElementById('orderItems');
        if (orderItems) {
            this.orderItemsHandler = (e) => {
                if (e.target.classList.contains('quantity') || e.target.classList.contains('sale-price')) {
                    this.calculateOrderTotal();
                }
            };
            orderItems.addEventListener('input', this.orderItemsHandler);
        }
    }

    removeEventListeners() {
        const orderForm = document.getElementById('orderForm');
        if (orderForm && this.orderFormHandler) {
            orderForm.removeEventListener('submit', this.orderFormHandler);
        }

        const payButton = document.getElementById('payButton');
        if (payButton && this.payButtonHandler) {
            payButton.removeEventListener('click', this.payButtonHandler);
        }

        const addPaymentMethodBtn = document.getElementById('addPaymentMethod');
        if (addPaymentMethodBtn && this.addPaymentMethodHandler) {
            addPaymentMethodBtn.removeEventListener('click', this.addPaymentMethodHandler);
        }

        const orderItems = document.getElementById('orderItems');
        if (orderItems && this.orderItemsHandler) {
            orderItems.removeEventListener('input', this.orderItemsHandler);
        }
    }

    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logElement = document.getElementById('logs');
        if (logElement) {
            const logMessage = `[${timestamp}] ${type.toUpperCase()}: ${message}\n`;
            logElement.textContent += logMessage;
            logElement.scrollTop = logElement.scrollHeight;
        }
        console.log(`[${timestamp}] ${type.toUpperCase()}: ${message}`);
    }

    clearLogs() {
        document.getElementById('logs').textContent = '';
    }

    getAuthHeaders() {
        const firebaseToken = document.getElementById('firebaseToken').value;
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (firebaseToken) {
            headers['authorization'] = firebaseToken;
        }
        
        return headers;
    }

    validateAuth() {
        const firebaseToken = document.getElementById('firebaseToken').value;
        if (!firebaseToken) {
            this.log('❌ Firebase ID Token is required for authentication', 'error');
            alert('Please enter your Firebase ID Token in the configuration section');
            return false;
        }
        return true;
    }

    // Add a new payment method row
    addPaymentMethod() {
        const container = document.getElementById('paymentMethodsContainer');
        const methodId = `payment-method-${Date.now()}`;
        const methodHtml = `
            <div class="payment-method" id="${methodId}">
                <div class="payment-method-header">
                    <div class="payment-method-title">
                        <i class="fas fa-credit-card"></i>
                        <span>Payment Method</span>
                    </div>
                    <button type="button" class="remove-payment-method" data-method-id="${methodId}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="payment-method-fields">
                    <div class="form-group payment-method-select">
                        <select class="payment-mode" required>
                            <option value="">Select payment method</option>
                            <option value="razorpay">Razorpay</option>
                            <option value="cod">Cash on Delivery</option>
                            <option value="wallet">Wallet</option>
                            <option value="cash">Cash</option>
                        </select>
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="form-group payment-method-amount">
                        <label>Amount (₹)</label>
                        <input type="number" class="payment-amount" step="0.01" min="0" required>
                    </div>
                </div>
            </div>
        `;
        
        const methodElement = document.createElement('div');
        methodElement.innerHTML = methodHtml;
        container.appendChild(methodElement.firstElementChild);
        
        // Add event listeners
        const amountInput = document.querySelector(`#${methodId} .payment-amount`);
        amountInput.addEventListener('input', () => this.updatePaymentSummary());
        
        const removeButton = document.querySelector(`#${methodId} .remove-payment-method`);
        removeButton.addEventListener('click', (e) => {
            e.preventDefault();
            this.removePaymentMethod(methodId);
        });
        
        this.updatePaymentSummary();
        return methodId;
    }
    
    // Remove a payment method
    removePaymentMethod(methodId) {
        const method = document.getElementById(methodId);
        if (method) {
            method.remove();
            this.updatePaymentSummary();
        }
    }
    
    // Calculate order total from items
    calculateOrderTotal() {
        let total = 0;
        document.querySelectorAll('.item-card').forEach(card => {
            const quantity = parseFloat(card.querySelector('.quantity')?.value) || 0;
            const price = parseFloat(card.querySelector('.sale-price')?.value) || 0;
            total += quantity * price;
        });
        
        this.totalAmount = parseFloat(total.toFixed(2));
        const totalAmountInput = document.getElementById('totalAmount');
        if (totalAmountInput) {
            totalAmountInput.value = this.totalAmount.toFixed(2);
        }
        this.updatePaymentSummary();
        
        return this.totalAmount;
    }

    // Get order form data including items and payment methods
    getOrderFormData() {
        // Set default facility
        const facilityId = 'ROZANA_TEST_WH1';

        // Collect order items
        const items = [];
        document.querySelectorAll('.item-card').forEach((card, index) => {
            const getValue = (selector) => {
                const element = card.querySelector(selector);
                return element ? element.value : '';
            };

            items.push({
                sku: getValue('.sku') || `SKU${index + 1}`,
                name: getValue('.item-name') || `Item ${index + 1}`,
                quantity: parseInt(getValue('.quantity')) || 1,
                unit_price: parseFloat(getValue('.unit-price')) || 0,
                sale_price: parseFloat(getValue('.sale-price')) || 0
            });
        });

        // Collect payment methods
        const payment = [];
        document.querySelectorAll('.payment-method').forEach(method => {
            const mode = method.querySelector('.payment-mode').value;
            const amount = parseFloat(method.querySelector('.payment-amount').value) || 0;
            
            if (mode && amount > 0) {
                payment.push({
                    payment_mode: mode,
                    amount: amount,
                    create_payment_order: mode === 'razorpay' || mode === 'wallet'
                });
            }
        });

        // Basic order data - matching API schema
        return {
            customer_id: document.getElementById('customerId').value || '2CN3aYJnaGXpaguuctWAubZnKKp1',
            customer_name: document.getElementById('customerName').value || '',
            facility_id: document.getElementById('facilityId').value || '1',
            facility_name: document.getElementById('facilityName').value || 'ROZANA_TEST_WH1',
            total_amount: this.totalAmount,
            items: items,
            address: {
                full_name: document.getElementById('fullName').value || 'Test Customer',
                phone_number: document.getElementById('phoneNumber').value || '9123456789',
                address_line1: document.getElementById('addressLine1').value || '123 Main Street',
                address_line2: document.getElementById('addressLine2').value || '',
                city: document.getElementById('city').value || 'Bangalore',
                state: document.getElementById('state').value || 'Karnataka',
                postal_code: document.getElementById('postalCode').value || '56001',
                country: document.getElementById('country').value || 'INDIA',
                type_of_address: document.getElementById('addressType').value || 'work',
                longitude: parseFloat(document.getElementById('longitude').value) || null,
                latitude: parseFloat(document.getElementById('latitude').value) || null
            },
            payment: payment,
            customer_email: 'test@example.com',
            customer_phone: document.getElementById('phoneNumber').value || '9123456789'
        };
    }
    
    // Update payment summary with totals and remaining amount
    updatePaymentSummary() {
        let allocated = 0;
        
        // Calculate total allocated amount
        document.querySelectorAll('.payment-method').forEach(method => {
            const amount = parseFloat(method.querySelector('.payment-amount').value) || 0;
            allocated += amount;
        });
        
        // Get current total amount from input field if totalAmount is not set
        if (!this.totalAmount || this.totalAmount === 0) {
            const totalAmountInput = document.getElementById('totalAmount');
            this.totalAmount = parseFloat(totalAmountInput?.value) || 0;
        }
        
        // Update UI
        const remaining = this.totalAmount - allocated;
        document.getElementById('totalAllocated').textContent = `₹${allocated.toFixed(2)}`;
        document.getElementById('remainingAmount').textContent = `₹${remaining.toFixed(2)}`;
        
        // Show/hide error message
        const errorElement = document.getElementById('paymentError');
        if (Math.abs(remaining) > 0.01) {
            errorElement.style.display = 'block';
            errorElement.textContent = remaining > 0 
                ? `Add ₹${Math.abs(remaining).toFixed(2)} more to complete payment`
                : `Reduce payment by ₹${Math.abs(remaining).toFixed(2)}`;
        } else {
            errorElement.style.display = 'none';
        }
        
        // Update payment method amounts if there's only one method
        const paymentMethods = document.querySelectorAll('.payment-method');
        if (paymentMethods.length === 1 && remaining > 0) {
            paymentMethods[0].querySelector('.payment-amount').value = this.totalAmount.toFixed(2);
        }
    }
    
    async createOrder() {
        // Prevent duplicate calls
        if (this.isCreatingOrder) {
            this.log('⚠️ Order creation already in progress...', 'warning');
            return;
        }

        try {
            this.isCreatingOrder = true;
            this.log('📝 Creating order...');
            this.setButtonLoading('Create Order', true);
            
            // Recalculate total in case it wasn't updated
            this.calculateOrderTotal();
            
            // Validate payment methods
            const paymentMethods = document.querySelectorAll('.payment-method');
            if (paymentMethods.length === 0) {
                throw new Error('Please add at least one payment method');
            }
            
            // Validate Firebase token
            if (!this.validateAuth()) {
                return;
            }
            
            const orderData = this.getOrderFormData();
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const headers = this.getAuthHeaders();
            
            this.log('Sending order data:', 'debug');
            this.log(JSON.stringify(orderData, null, 2), 'debug');

            const response = await fetch(`${apiBaseUrl}/app/v1/create_order`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(orderData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log(`✅ Order created successfully: ID ${result.order_id}`);
            this.currentOrder = result;
            
            // Move to payment step
            document.getElementById('orderStep').classList.remove('active');
            document.getElementById('paymentStep').classList.add('active');
            document.getElementById('step1').classList.remove('active');
            document.getElementById('step2').classList.add('active');
            
            // Check if there's a Razorpay payment with payment order details
            const razorpayPayment = orderData.payment.find(p => p.payment_mode === 'razorpay');
            if (razorpayPayment && result.payment_order_details) {
                // Find the Razorpay payment order from the response
                const razorpayOrder = result.payment_order_details.find(p => p.payment_mode === 'razorpay');
                if (razorpayOrder) {
                    this.log('✅ Payment order created in order creation');
                    this.initiateRazorpayPayment(razorpayOrder, result.order_id);
                } else {
                    this.log('❌ No Razorpay payment order found in response', 'error');
                }
            } else if (orderData.payment.every(p => ['cod', 'cash'].includes(p.payment_mode))) {
                // For COD/Cash only orders, show success immediately
                this.log('✅ Order created with COD/Cash payment. No online payment required.');
                this.showSuccess(result);
            }

        } catch (error) {
            this.log(`❌ Error creating order: ${error.message}`, 'error');
            alert(`Error creating order: ${error.message}`);
        } finally {
            this.isCreatingOrder = false;
            this.setButtonLoading('Create Order', false);
        }
    }


    getAuthHeaders() {
        const firebaseToken = document.getElementById('firebaseToken').value;
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (firebaseToken) {
            headers['authorization'] = firebaseToken;
        }
        
        return headers;
    }

    validateAuth() {
        const firebaseToken = document.getElementById('firebaseToken').value;
        if (!firebaseToken) {
            this.log('❌ Firebase ID Token is required for authentication', 'error');
            alert('Please enter your Firebase ID Token in the configuration section');
            return false;
        }
        return true;
    }




initiateRazorpayPayment(paymentOrder, orderId) {
    const razorpayKeyId = paymentOrder.razorpay_key_id || document.getElementById('razorpayKeyId').value;
    const customerName = document.getElementById('customerName').value;
    
    const options = {
        key: razorpayKeyId,
        amount: paymentOrder.amount_paise, // Use amount in paise from response
        currency: paymentOrder.currency || 'INR',
        name: 'Rozana',
        description: `Payment for Order #${orderId}`,
        order_id: paymentOrder.payment_order_id, // Use payment_order_id from response
        handler: (response) => {
            this.log('Payment successful!', 'success');
            this.log(JSON.stringify(response), 'debug');
            this.verifyPayment(
                response.razorpay_payment_id, 
                response.razorpay_order_id, 
                response.razorpay_signature,
                orderId
            );
        },
        prefill: {
            name: customerName,
            email: 'customer@example.com',
            contact: '+919999999999'
        },
        theme: {
            color: '#1e40af'
        },
        modal: {
            ondismiss: () => {
                this.log('Payment window closed without completing payment', 'warning');
            }
        }
    };

    try {
        const rzp = new Razorpay(options);
        rzp.open();
    } catch (error) {
        this.log(`❌ Error initializing Razorpay: ${error.message}`, 'error');
        alert(`Error initializing payment: ${error.message}`);
    }
}

async verifyPayment(paymentId, orderId, signature, originalOrderId) {
    try {
        this.log('🔍 Verifying payment...');
        
        const apiBaseUrl = document.getElementById('apiBaseUrl').value;
        const response = await fetch(`${apiBaseUrl}/app/v1/verify_payment`, {
            method: 'POST',
            headers: this.getAuthHeaders(),
            body: JSON.stringify({
                razorpay_payment_id: paymentId,
                razorpay_order_id: orderId,
                razorpay_signature: signature,
                oms_order_id: originalOrderId // Fixed field name to match API schema
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        this.log('✅ Payment verified successfully');
        this.showSuccess(result);

    } catch (error) {
        this.log(`❌ Error verifying payment: ${error.message}`, 'error');
        alert(`Payment verification failed: ${error.message}`);
    }
}

displayPaymentStatus(statusData) {
    const statusElement = document.getElementById('paymentStatus');
    
    if (!statusData.success) {
            statusElement.innerHTML = `
                <div class="status-error">
                    <h3>❌ Error Loading Payment Status</h3>
                    <p>Unable to fetch payment information</p>
                </div>
            `;
            return;
        }

        const paymentSummary = statusData.payment_summary;
        let statusClass = 'status-pending';
        let statusIcon = '⏳';
        let statusText = 'Unknown';
        
        // Determine overall payment status
        if (paymentSummary.has_payments) {
            if (paymentSummary.completed_count > 0 && paymentSummary.pending_count === 0 && paymentSummary.failed_count === 0) {
                statusClass = 'status-success';
                statusIcon = '✅';
                statusText = 'Payment Completed';
            } else if (paymentSummary.pending_count > 0) {
                statusClass = 'status-pending';
                statusIcon = '⏳';
                statusText = 'Payment Pending';
            } else if (paymentSummary.failed_count > 0) {
                statusClass = 'status-error';
                statusIcon = '❌';
                statusText = 'Payment Failed';
            }
        } else {
            statusClass = 'status-pending';
            statusIcon = '⏳';
            statusText = 'No Payments Found';
        }

        // Build payment details HTML
        let paymentsHtml = '';
        if (paymentSummary.payments && paymentSummary.payments.length > 0) {
            paymentsHtml = paymentSummary.payments.map(payment => {
                const paymentStatusClass = payment.payment_status_display === 'Payment Completed' ? 'payment-success' : 'payment-pending';
                const paymentIcon = payment.payment_status_display === 'Payment Completed' ? '✅' : '⏳';
                
                return `
                    <div class="payment-item ${paymentStatusClass}">
                        <div class="payment-header">
                            <span class="payment-icon">${paymentIcon}</span>
                            <span class="payment-status">${payment.payment_status_display}</span>
                            <span class="payment-amount">₹${payment.payment_amount}</span>
                        </div>
                        <div class="payment-details">
                            <p><strong>Payment ID:</strong> ${payment.payment_id}</p>
                            <p><strong>Mode:</strong> ${payment.payment_mode.toUpperCase()}</p>
                            <p><strong>Cash Amount:</strong> ₹${payment.cash_amount}</p>
                            <p><strong>Online Amount:</strong> ₹${payment.online_amount}</p>
                            <p><strong>Created:</strong> ${new Date(payment.created_at).toLocaleString()}</p>
                            <p><strong>Updated:</strong> ${new Date(payment.updated_at).toLocaleString()}</p>
                        </div>
                    </div>
                `;
            }).join('');
        }

        statusElement.innerHTML = `
            <div class="${statusClass}">
                <div class="status-header">
                    <span class="status-icon">${statusIcon}</span>
                    <h3>${statusText}</h3>
                </div>
                <div class="status-summary">
                    <p><strong>Order ID:</strong> ${statusData.order_id}</p>
                    <p><strong>Order Status:</strong> ${statusData.order_status}</p>
                    <p><strong>Total Paid:</strong> ₹${paymentSummary.total_paid}</p>
                    <p><strong>Payment Count:</strong> ${paymentSummary.payment_count}</p>
                    <div class="payment-counts">
                        <span class="count-item completed">✅ Completed: ${paymentSummary.completed_count}</span>
                        <span class="count-item pending">⏳ Pending: ${paymentSummary.pending_count}</span>
                        <span class="count-item failed">❌ Failed: ${paymentSummary.failed_count}</span>
                    </div>
                </div>
                ${paymentsHtml ? `<div class="payments-list">${paymentsHtml}</div>` : ''}
            </div>
        `;
    }

    showSuccess(result) {
        // Move to completion step
        document.getElementById('paymentStep').classList.remove('active');
        document.getElementById('completionStep').classList.add('active');
        document.getElementById('step2').classList.remove('active');
        document.getElementById('step3').classList.add('active');
        
        this.log(`✅ Order completed successfully: ${result.order_id}`);
        
        // Display success information in payment status area
        const statusElement = document.getElementById('paymentStatus');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="success-content">
                    <h3>🎉 Order Created Successfully!</h3>
                    <p><strong>Order ID:</strong> ${result.order_id}</p>
                    <p><strong>Status:</strong> ${result.status || 'Created'}</p>
                    <p><strong>Total Amount:</strong> ₹${this.totalAmount}</p>
                </div>
            `;
        }
    }

    async checkPaymentStatus() {
        if (!this.currentOrder || !this.currentOrder.order_id) {
            this.log('❌ No active order found', 'error');
            return;
        }

        try {
            this.log('🔍 Checking payment status...');
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const response = await fetch(`${apiBaseUrl}/app/v1/order/${this.currentOrder.order_id}/payment_status`, {
                method: 'GET',
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log('✅ Payment status retrieved');
            this.displayPaymentStatus(result);

        } catch (error) {
            this.log(`❌ Error checking payment status: ${error.message}`, 'error');
            alert(`Error checking payment status: ${error.message}`);
        }
    }

    setButtonLoading(buttonText, isLoading) {
        const submitButton = document.querySelector('button[type="submit"]');
        if (isLoading) {
            submitButton.innerHTML = `<span class="loading"></span>${buttonText}...`;
            submitButton.disabled = true;
        } else {
            submitButton.innerHTML = buttonText;
            submitButton.disabled = false;
        }
    }
}

// Utility functions for managing order items
function addItem() {
    const container = document.getElementById('orderItems');
    const itemCount = container.children.length + 1;
    const newItem = document.createElement('div');
    newItem.className = 'item-card';
    newItem.innerHTML = `
        <div class="item-header">
            <i class="fas fa-cube"></i>
            <span>Item #${itemCount}</span>
            <button type="button" class="remove-item" onclick="removeItem(this)">
                <i class="fas fa-trash"></i>
            </button>
        </div>
        <div class="item-fields">
            <div class="form-group">
                <label><i class="fas fa-barcode"></i> SKU:</label>
                <input type="text" placeholder="SKU-000${itemCount}" class="sku" required>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label><i class="fas fa-sort-numeric-up"></i> Quantity:</label>
                    <input type="number" placeholder="1" value="1" class="quantity" required>
                </div>
                <div class="form-group">
                    <label><i class="fas fa-tag"></i> Unit Price:</label>
                    <input type="number" placeholder="0" step="0.01" class="unit-price" required>
                </div>
                <div class="form-group">
                    <label><i class="fas fa-money-bill"></i> Sale Price:</label>
                    <input type="number" placeholder="0" step="0.01" class="sale-price" required>
                </div>
            </div>
        </div>
    `;
    container.appendChild(newItem);
}

function removeItem(button) {
    const itemCard = button.closest('.item-card');
    const container = document.getElementById('orderItems');
    if (container.children.length > 1) {
        itemCard.remove();
        // Recalculate total after removing item
        if (window.paymentClient) {
            window.paymentClient.calculateOrderTotal();
        }
    } else {
        alert('At least one item is required');
    }
}

function addLog(message, type = 'info') {
    const logsElement = document.getElementById('logs');
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${type.toUpperCase()}: ${message}\n`;
    logsElement.textContent += logEntry;
    logsElement.scrollTop = logsElement.scrollHeight;
}

function clearLogs() {
    document.getElementById('logs').textContent = '';
    addLog('Debug logs cleared', 'info');
}

function checkPaymentStatus() {
    if (window.paymentClient && window.paymentClient.currentOrder) {
        window.paymentClient.checkPaymentStatus();
    } else {
        alert('No active order found. Please create an order first.');
    }
}

// Initialize the payment client when the page loads
document.addEventListener('DOMContentLoaded', function() {
    window.paymentClient = new RozanaPaymentClient();
});

// Utility functions for UI interactions
function toggleLogs() {
    const logsContent = document.getElementById('logsContent');
    const toggleIcon = document.getElementById('toggleIcon');
    
    if (logsContent.style.display === 'none') {
        logsContent.style.display = 'block';
        toggleIcon.classList.remove('fa-chevron-right');
        toggleIcon.classList.add('fa-chevron-down');
    } else {
        logsContent.style.display = 'none';
        toggleIcon.classList.remove('fa-chevron-down');
        toggleIcon.classList.add('fa-chevron-right');
    }
}

function resetJourney() {
    // Reset to step 1
    document.getElementById('orderStep').classList.add('active');
    document.getElementById('paymentStep').classList.remove('active');
    document.getElementById('completionStep').classList.remove('active');
    
    document.getElementById('step1').classList.add('active');
    document.getElementById('step2').classList.remove('active');
    document.getElementById('step3').classList.remove('active');
    
    // Clear current order
    if (window.paymentClient) {
        window.paymentClient.currentOrder = null;
        window.paymentClient.log('🔄 Journey reset - ready for new order');
    }
    
    // Clear payment status
    const paymentStatus = document.getElementById('paymentStatus');
    if (paymentStatus) {
        paymentStatus.innerHTML = '';
    }
}

// Settings modal functions
function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

function saveSettings() {
    // Save settings to localStorage
    localStorage.setItem('apiBaseUrl', document.getElementById('apiBaseUrl').value);
    localStorage.setItem('razorpayKeyId', document.getElementById('razorpayKeyId').value);
    localStorage.setItem('firebaseToken', document.getElementById('firebaseToken').value);
    
    closeSettings();
    
    // Show success message
    if (window.paymentClient) {
        window.paymentClient.log('✅ Configuration saved successfully!');
    }
}

function loadSettings() {
    // Load settings from localStorage
    const apiBaseUrl = localStorage.getItem('apiBaseUrl');
    const razorpayKeyId = localStorage.getItem('razorpayKeyId');
    const firebaseToken = localStorage.getItem('firebaseToken');
    
    if (apiBaseUrl) document.getElementById('apiBaseUrl').value = apiBaseUrl;
    if (razorpayKeyId) document.getElementById('razorpayKeyId').value = razorpayKeyId;
    if (firebaseToken) document.getElementById('firebaseToken').value = firebaseToken;
}

function toggleLogs() {
    const logsPanel = document.querySelector('.logs-panel');
    const toggleIcon = document.getElementById('toggleIcon');
    
    logsPanel.classList.toggle('collapsed');
    
    if (logsPanel.classList.contains('collapsed')) {
        toggleIcon.classList.remove('fa-chevron-right');
        toggleIcon.classList.add('fa-chevron-down');
    } else {
        toggleIcon.classList.remove('fa-chevron-down');
        toggleIcon.classList.add('fa-chevron-right');
    }
}

function resetJourney() {
    // Reset to step 1
    document.querySelectorAll('.journey-step').forEach(step => {
        step.classList.remove('active');
    });
    document.getElementById('orderStep').classList.add('active');
    
    // Reset progress
    if (window.paymentClient) {
        window.paymentClient.updateJourneyProgress(1);
        window.paymentClient.currentOrder = null;
    }
    
    // Clear form
    document.getElementById('orderForm').reset();
    
    // Scroll to top
    document.getElementById('orderStep').scrollIntoView({ behavior: 'smooth' });
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target === modal) {
        closeSettings();
    }
}

// Initialize the payment client when the page loads
function initializePaymentClient() {
    // Prevent multiple initializations
    if (window.paymentClient) {
        console.log('Payment client already initialized');
        return;
    }
    
    // First load settings
    loadSettings();
    
    // Then create the payment client
    window.paymentClient = new RozanaPaymentClient();
    
    // Add initial log to show debug panel is working
    if (window.paymentClient) {
        window.paymentClient.log('🚀 Rozana Payment Test Client initialized', 'info');
        window.paymentClient.log('📋 Debug logging is active', 'info');
        window.paymentClient.log('⚙️ Configure your API settings using the gear icon', 'info');
    }
    
    // Ensure logs panel is visible by default
    const logsPanel = document.querySelector('.logs-panel');
    const toggleIcon = document.getElementById('toggleIcon');
    if (logsPanel && toggleIcon) {
        logsPanel.classList.remove('collapsed');
        toggleIcon.classList.remove('fa-chevron-down');
        toggleIcon.classList.add('fa-chevron-right');
    }
}

// Wait for DOM to be fully loaded before initializing
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePaymentClient);
} else {
    initializePaymentClient();
}
