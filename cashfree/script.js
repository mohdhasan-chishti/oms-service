// Rozana Cashfree Payment Test Client JavaScript
class RozanaCashfreeClient {
    constructor() {
        this.currentOrder = null;
        this.cashfree = null;
        this.paymentSession = null;
        this.init();
    }

    async init() {
        try {
            // Initialize Cashfree SDK
            this.cashfree = new Cashfree({
                mode: "sandbox" // Change to "production" for live environment
            });
            
            this.setupEventListeners();
            this.paymentMethods = [];
            this.totalAmount = 0;
            this.addPaymentMethod(); // Add first payment method by default
            this.addItem(); // Add first item by default
            this.log('🚀 Rozana Cashfree Payment Test Client initialized');
            this.log('✅ Cashfree SDK initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Cashfree SDK:', error);
            this.log(`❌ Failed to initialize Cashfree SDK: ${error.message}`, 'error');
        }
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
                            <option value="cashfree">Cashfree</option>
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
    
    // Add a new item to the order
    addItem() {
        const container = document.getElementById('orderItems');
        if (!container) return;
        
        const itemId = `item-${Date.now()}`;
        const itemHtml = `
            <div class="item-card" id="${itemId}">
                <div class="item-header">
                    <div class="item-title">
                        <i class="fas fa-box"></i>
                        <span>Item Details</span>
                    </div>
                    <button type="button" class="remove-item">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="item-fields">
                    <div class="form-row">
                        <div class="form-group">
                            <label>SKU</label>
                            <input type="text" class="sku" value="SKU${container.children.length + 1}" required>
                        </div>
                        <div class="form-group">
                            <label>Item Name</label>
                            <input type="text" class="item-name" value="Test Item ${container.children.length + 1}" required>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Quantity</label>
                            <input type="number" class="quantity" min="1" value="1" required>
                        </div>
                        <div class="form-group">
                            <label>Unit Price (₹)</label>
                            <input type="number" class="unit-price" step="0.01" min="0" value="25.00" required>
                        </div>
                        <div class="form-group">
                            <label>Sale Price (₹)</label>
                            <input type="number" class="sale-price" step="0.01" min="0" value="28.50" required>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        const itemElement = document.createElement('div');
        itemElement.innerHTML = itemHtml;
        const newItem = itemElement.firstElementChild;
        container.appendChild(newItem);
        
        // Add click handler for the remove button
        const removeBtn = newItem.querySelector('.remove-item');
        if (removeBtn) {
            removeBtn.addEventListener('click', () => this.removeItem(newItem));
        }
        
        // Add input handlers for quantity and price changes
        const quantityInput = newItem.querySelector('.quantity');
        const priceInput = newItem.querySelector('.sale-price');
        
        const updateHandler = () => this.calculateOrderTotal();
        
        if (quantityInput) quantityInput.addEventListener('input', updateHandler);
        if (priceInput) priceInput.addEventListener('input', updateHandler);
        
        // Update the order total
        this.calculateOrderTotal();
        
        return newItem;
    }
    
    // Remove an item from the order
    removeItem(itemElement) {
        if (itemElement && itemElement.parentNode) {
            itemElement.remove();
            this.calculateOrderTotal();
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

    // Helper method to safely get element value
    getElementValue(id, defaultValue = '') {
        const element = document.getElementById(id);
        return element ? element.value : defaultValue;
    }

    // Get order form data including items and payment methods
    getOrderFormData() {
        try {
            // Set default values
            const defaultValues = {
                customerId: '2CN3aYJnaGXpaguuctWAubZnKKp1',
                customerName: 'Test Customer',
                facilityId: '1',
                facilityName: 'ROZANA_TEST_WH1',
                fullName: 'Test Customer',
                phoneNumber: '9123456789',
                addressLine1: '123 Main Street',
                city: 'Bangalore',
                state: 'Karnataka',
                postalCode: '560001',
                country: 'India',
                addressType: 'home'
            };

            // Collect order items with null checks
            const items = [];
            try {
                const itemCards = document.querySelectorAll('.item-card') || [];
                if (itemCards.length === 0) {
                    // Add a default item if none exist
                    items.push({
                        sku: 'DEFAULT_SKU',
                        name: 'Test Item',
                        quantity: 1,
                        unit_price: this.totalAmount || 100,
                        sale_price: this.totalAmount || 100
                    });
                } else {
                    itemCards.forEach((card, index) => {
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
                }
            } catch (error) {
                console.error('Error processing order items:', error);
                if (items.length === 0) {
                    items.push({
                        sku: 'ERROR_SKU',
                        name: 'Error Item',
                        quantity: 1,
                        unit_price: 0,
                        sale_price: 0
                    });
                }
            }

            // Collect payment methods with null checks
            const payment = [];
            try {
                const paymentMethods = document.querySelectorAll('.payment-method') || [];
                if (paymentMethods.length === 0) {
                    // Add default payment method if none exist
                    payment.push({
                        payment_mode: 'cashfree',
                        amount: this.totalAmount || 100,
                        create_payment_order: true
                    });
                } else {
                    paymentMethods.forEach(method => {
                        try {
                            const modeElement = method.querySelector('.payment-mode');
                            const amountElement = method.querySelector('.payment-amount');
                            
                            const mode = modeElement?.value || 'cashfree';
                            const amount = amountElement ? parseFloat(amountElement.value) || 0 : (this.totalAmount || 100);
                            
                            if (mode && amount > 0) {
                                payment.push({
                                    payment_mode: mode,
                                    amount: amount,
                                    create_payment_order: mode === 'cashfree' || mode === 'wallet'
                                });
                            }
                        } catch (error) {
                            console.error('Error processing payment method:', error);
                        }
                    });
                }
            } catch (error) {
                console.error('Error processing payment methods:', error);
                if (payment.length === 0) {
                    payment.push({
                        payment_mode: 'cashfree',
                        amount: this.totalAmount || 100,
                        create_payment_order: true
                    });
                }
            }

            // Calculate total amount if not set
            if (!this.totalAmount || this.totalAmount === 0) {
                this.totalAmount = items.reduce((sum, item) => {
                    return sum + (parseFloat(item.sale_price) * parseInt(item.quantity));
                }, 0);
            }

            // Basic order data with all required fields
            return {
                customer_id: this.getElementValue('customerId', defaultValues.customerId),
                customer_name: this.getElementValue('customerName', defaultValues.customerName),
                facility_id: this.getElementValue('facilityId', defaultValues.facilityId),
                facility_name: this.getElementValue('facilityName', defaultValues.facilityName),
                total_amount: this.totalAmount,
                items: items,
                address: {
                    full_name: this.getElementValue('fullName', defaultValues.fullName),
                    phone_number: this.getElementValue('phoneNumber', defaultValues.phoneNumber),
                    address_line1: this.getElementValue('addressLine1', defaultValues.addressLine1),
                    address_line2: this.getElementValue('addressLine2', ''),
                    city: this.getElementValue('city', defaultValues.city),
                    state: this.getElementValue('state', defaultValues.state),
                    postal_code: this.getElementValue('postalCode', defaultValues.postalCode),
                    country: this.getElementValue('country', defaultValues.country),
                    type_of_address: this.getElementValue('addressType', defaultValues.addressType),
                    longitude: parseFloat(this.getElementValue('longitude', '0')) || null,
                    latitude: parseFloat(this.getElementValue('latitude', '0')) || null
                },
                payment: payment,
                customer_email: 'test@example.com',
                customer_phone: this.getElementValue('phoneNumber', defaultValues.phoneNumber)
            };
        } catch (error) {
            console.error('Error in getOrderFormData:', error);
            // Return minimal valid order data to prevent complete failure
            return {
                customer_id: 'ERROR_USER',
                customer_name: 'Error User',
                facility_id: '1',
                facility_name: 'DEFAULT_FACILITY',
                total_amount: 100,
                items: [{
                    sku: 'ERROR_SKU',
                    name: 'Error Item',
                    quantity: 1,
                    unit_price: 100,
                    sale_price: 100
                }],
                address: {
                    full_name: 'Error User',
                    phone_number: '0000000000',
                    address_line1: 'Error Address',
                    address_line2: '',
                    city: 'Error City',
                    state: 'Error State',
                    postal_code: '000000',
                    country: 'India',
                    type_of_address: 'home',
                    longitude: null,
                    latitude: null
                },
                payment: [{
                    payment_mode: 'cashfree',
                    amount: 100,
                    create_payment_order: true
                }],
                customer_email: 'error@example.com',
                customer_phone: '0000000000'
            };
        }
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
            
            // Check if there's a Cashfree payment with payment order details
            const cashfreePayment = orderData.payment.find(p => p.payment_mode === 'cashfree');
            
            // Debug: Log the payment_order_details to see what we received
            console.log('DEBUG: payment_order_details =', result.payment_order_details);
            this.log(`Debug: payment_order_details count = ${result.payment_order_details ? result.payment_order_details.length : 0}`);
            
            if (cashfreePayment && result.payment_order_details) {
                // Debug: Show what payment modes we have
                const modes = result.payment_order_details.map(p => `${p.payment_mode} (${typeof p.payment_mode})`).join(', ');
                this.log(`Debug: Payment modes in response: [${modes}]`);
                
                // Find the Cashfree payment order from the response
                const cashfreeOrder = result.payment_order_details.find(p => p.payment_mode === 'cashfree');
                
                if (cashfreeOrder) {
                    this.log('✅ Payment order created in order creation');
                    this.initiateCashfreePayment(cashfreeOrder, result.order_id);
                } else {
                    this.log('❌ No Cashfree payment order found in response', 'error');
                    console.error('Full payment_order_details:', JSON.stringify(result.payment_order_details, null, 2));
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

    async initiateCashfreePayment(paymentOrder, orderId) {
        try {
            this.log('Initiating Cashfree payment...');
            this.log(`Payment Order Data: ${JSON.stringify(paymentOrder)}`);
            
            // Check if we have payment order data
            if (!paymentOrder) {
                throw new Error('Invalid payment order data received from server');
            }

            // Check for payment_session_id (could be null, undefined, or missing)
            const hasValidSessionId = paymentOrder.payment_session_id && 
                                     paymentOrder.payment_session_id !== 'null' && 
                                     paymentOrder.payment_session_id !== 'None';

            // CASE 1: No valid session ID - Use payment URL fallback
            if (!hasValidSessionId) {
                this.log('⚠️ No valid payment session ID available');
                
                if (paymentOrder.payment_url) {
                    this.log('✅ Payment URL found, redirecting to Cashfree payment page...');
                    this.log(`Payment URL: ${paymentOrder.payment_url}`);
                    
                    // Open payment page in new tab
                    const paymentWindow = window.open(paymentOrder.payment_url, '_blank');
                    
                    if (paymentWindow) {
                        this.log('✅ Cashfree payment page opened in new tab');
                        this.log('ℹ️ Complete the payment in the opened tab');
                        this.log('💡 For production: Add real Cashfree credentials to get modal payment (like Razorpay)');
                        
                        // Don't auto-show success, just inform user
                        alert('✅ Cashfree Payment Demo\n\nThe payment page has opened in a new tab.\n\n📝 Note: This is demo mode using mock credentials.\n\nTo get Razorpay-style payment modal:\n1. Add real Cashfree credentials to .env\n2. Restart services\n3. Real payment_session_id will be returned\n4. SDK will open payment modal');
                    } else {
                        throw new Error('Popup blocked! Please allow popups for this site.');
                    }
                    return;
                } else {
                    throw new Error('No payment session ID or payment URL available');
                }
            }

            // CASE 2: Valid session ID - Use Cashfree SDK
            this.log('✅ Valid payment session ID found, using Cashfree SDK...');
            this.log(`🚀 Opening Cashfree checkout with session: ${paymentOrder.payment_session_id}`);
            
            // Store the payment session
            this.paymentSession = paymentOrder.payment_session_id;
            
            // Check if Cashfree SDK is loaded
            if (!window.Cashfree) {
                throw new Error('Cashfree SDK not loaded. Please refresh the page.');
            }

            // Initialize Cashfree
            const cashfree = new window.Cashfree({
                mode: "sandbox" // Change to "production" for live
            });

            const checkoutOptions = {
                paymentSessionId: paymentOrder.payment_session_id,
                returnUrl: `${window.location.origin}/cashfree/return.html`,
                redirectTarget: "_modal"
            };
            
            // Open Cashfree checkout
            cashfree.checkout(checkoutOptions).then((result) => {
                this.log('Cashfree checkout completed');
                this.log(`Result: ${JSON.stringify(result)}`);
                
                if (result.error) {
                    this.log(`❌ Payment failed: ${result.error.message}`, 'error');
                    alert(`Payment failed: ${result.error.message}`);
                } else if (result.redirect) {
                    this.log('✅ Payment successful, redirecting...');
                    this.verifyPayment(result, orderId);
                } else if (result.paymentDetails) {
                    this.log('✅ Payment completed');
                    this.verifyPayment(result.paymentDetails, orderId);
                } else {
                    this.log('✅ Payment flow completed');
                    this.showSuccess({
                        order_id: orderId,
                        payment_status: 'SUCCESS',
                        message: 'Payment completed successfully'
                    });
                }
            }).catch(error => {
                console.error('Cashfree checkout error:', error);
                this.log(`❌ SDK Error: ${error.message}`, 'error');
                
                // SDK failed, fallback to URL if available
                if (paymentOrder.payment_url) {
                    this.log('SDK failed, falling back to payment URL...');
                    const userConfirm = confirm(`Cashfree SDK error. Open payment page in new tab instead?`);
                    if (userConfirm) {
                        window.open(paymentOrder.payment_url, '_blank');
                    }
                } else {
                    alert(`Payment initialization failed: ${error.message}`);
                }
            });

        } catch (error) {
            console.error('Payment initialization error:', error);
            this.log(`❌ Error: ${error.message}`, 'error');
            
            // Final fallback: try payment URL
            if (paymentOrder && paymentOrder.payment_url) {
                this.log('Exception caught, trying payment URL fallback...');
                const userConfirm = confirm(`${error.message}\n\nWould you like to open the payment page in a new tab?`);
                if (userConfirm) {
                    window.open(paymentOrder.payment_url, '_blank');
                    // Show success for demo
                    setTimeout(() => {
                        this.showSuccess({
                            order_id: orderId,
                            payment_status: 'PENDING',
                            message: 'Please complete payment in the opened tab'
                        });
                    }, 2000);
                }
            } else {
                alert(`Payment initialization failed: ${error.message}`);
            }
        }
    }

    async verifyPayment(paymentDetails, orderId) {
        try {
            this.log('🔍 Verifying payment...');
            
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const headers = this.getAuthHeaders();

            const verificationData = {
                order_id: orderId,
                payment_details: paymentDetails
            };

            const response = await fetch(`${apiBaseUrl}/app/v1/cashfree/verify_payment`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(verificationData)
            });

            if (!response.ok) {
                throw new Error(`Verification failed: ${response.status}`);
            }

            const result = await response.json();
            this.log('✅ Payment verified successfully');
            this.displayPaymentStatus(result);

        } catch (error) {
            this.log(`❌ Payment verification failed: ${error.message}`, 'error');
            // Still show success but with warning
            this.showSuccess(this.currentOrder, 'Payment completed but verification pending');
        }
    }

    displayPaymentStatus(statusData) {
        if (statusData.status === 'success' || statusData.payment_status === 'PAID') {
            this.showSuccess(statusData);
        } else {
            this.log(`❌ Payment failed: ${statusData.message || 'Unknown error'}`, 'error');
            alert('Payment failed. Please try again.');
        }
    }

    showSuccess(result, message = null) {
        // Move to success step
        document.getElementById('paymentStep').classList.remove('active');
        document.getElementById('successStep').classList.add('active');
        document.getElementById('step2').classList.remove('active');
        document.getElementById('step3').classList.add('active');

        // Populate success details
        const successDetails = document.getElementById('successDetails');
        successDetails.innerHTML = `
            <div class="success-info">
                <div class="info-row">
                    <span class="label">Order ID:</span>
                    <span class="value">${result.order_id || result.id}</span>
                </div>
                <div class="info-row">
                    <span class="label">Amount:</span>
                    <span class="value">₹${result.total_amount || result.amount}</span>
                </div>
                <div class="info-row">
                    <span class="label">Status:</span>
                    <span class="value success">${message || 'Payment Successful'}</span>
                </div>
                <div class="info-row">
                    <span class="label">Transaction Time:</span>
                    <span class="value">${new Date().toLocaleString()}</span>
                </div>
            </div>
        `;

        this.log('🎉 Payment journey completed successfully!');
    }

    setButtonLoading(buttonText, isLoading) {
        const submitButton = document.querySelector('button[type="submit"]');
        if (submitButton) {
            if (isLoading) {
                submitButton.disabled = true;
                submitButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${buttonText}...`;
            } else {
                submitButton.disabled = false;
                submitButton.innerHTML = `<i class="fas fa-arrow-right"></i> ${buttonText}`;
            }
        }
    }

    async initiatePayment() {
        if (!this.currentOrder) {
            this.log('❌ No order found. Please create an order first.', 'error');
            return;
        }

        // Check if there's a Cashfree payment in the order
        const cashfreePayment = this.currentOrder.payment_order_details?.find(p => p.payment_mode === 'cashfree');
        if (cashfreePayment) {
            await this.initiateCashfreePayment(cashfreePayment, this.currentOrder.order_id);
        } else {
            this.log('❌ No Cashfree payment found in order', 'error');
            if (window.paymentClient) {
                window.paymentClient.calculateOrderTotal();
            }
        }
    }

    addLog(message, type = 'info') {
        if (window.paymentClient) {
            window.paymentClient.log(message, type);
        }
    }

    clearLogs() {
        const logs = document.getElementById('logs');
        if (logs) {
            logs.textContent = '';
        }
    }
}

function checkPaymentStatus() {
    if (window.paymentClient && window.paymentClient.currentOrder) {
        window.paymentClient.log('🔍 Checking payment status...');
        // Implementation for checking payment status
    }
}

// Utility functions for UI interactions
function toggleLogs() {
    const logsContent = document.querySelector('.logs-content');
    const toggleBtn = document.querySelector('.btn-toggle i');
    
    if (logsContent.style.display === 'none') {
        logsContent.style.display = 'block';
        toggleBtn.className = 'fas fa-eye';
    } else {
        logsContent.style.display = 'none';
        toggleBtn.className = 'fas fa-eye-slash';
    }
}

function resetJourney() {
    // Reset all steps
    document.querySelectorAll('.journey-step').forEach(step => {
        step.classList.remove('active');
    });
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });
    
    // Activate first step
    document.getElementById('orderStep').classList.add('active');
    document.getElementById('step1').classList.add('active');
    
    // Clear current order
    if (window.paymentClient) {
        window.paymentClient.currentOrder = null;
        window.paymentClient.log('🔄 Journey reset. Ready for new order.');
    }
}

// Settings modal functions
function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
    loadSettings();
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

function saveSettings() {
    const settings = {
        apiBaseUrl: document.getElementById('apiBaseUrl').value,
        cashfreeAppId: document.getElementById('cashfreeAppId').value,
        cashfreeSecretKey: document.getElementById('cashfreeSecretKey').value,
        firebaseToken: document.getElementById('firebaseToken').value
    };
    
    localStorage.setItem('cashfreeSettings', JSON.stringify(settings));
    alert('Settings saved successfully!');
    closeSettings();
}

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('cashfreeSettings') || '{}');
    
    if (settings.apiBaseUrl) document.getElementById('apiBaseUrl').value = settings.apiBaseUrl;
    if (settings.cashfreeAppId) document.getElementById('cashfreeAppId').value = settings.cashfreeAppId;
    if (settings.cashfreeSecretKey) document.getElementById('cashfreeSecretKey').value = settings.cashfreeSecretKey;
    if (settings.firebaseToken) document.getElementById('firebaseToken').value = settings.firebaseToken;
}

function toggleLogs() {
    const logsContent = document.querySelector('.logs-content');
    const toggleBtn = document.querySelector('.btn-toggle i');
    
    if (logsContent.style.display === 'none') {
        logsContent.style.display = 'block';
        toggleBtn.className = 'fas fa-eye';
    } else {
        logsContent.style.display = 'none';
        toggleBtn.className = 'fas fa-eye-slash';
    }
}

function resetJourney() {
    // Reset all steps
    document.querySelectorAll('.journey-step').forEach(step => {
        step.classList.remove('active');
    });
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });
    
    // Activate first step
    document.getElementById('orderStep').classList.add('active');
    document.getElementById('step1').classList.add('active');
    
    // Clear current order
    if (window.paymentClient) {
        window.paymentClient.currentOrder = null;
        window.paymentClient.log('🔄 Journey reset. Ready for new order.');
    }
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
    try {
        window.paymentClient = new RozanaCashfreeClient();
        
        // Load saved settings
        loadSettings();
        
        // Add initial item if none exists
        const orderItems = document.getElementById('orderItems');
        if (orderItems && orderItems.children.length === 0) {
            addItem();
        }
        
        console.log('✅ Cashfree Payment Client initialized successfully');
    } catch (error) {
        console.error('❌ Failed to initialize payment client:', error);
        alert('Failed to initialize payment client. Please refresh the page.');
    }
}

// Wait for DOM to be fully loaded before initializing
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePaymentClient);
} else {
    initializePaymentClient();
}
