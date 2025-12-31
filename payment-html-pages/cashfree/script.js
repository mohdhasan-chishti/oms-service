// Rozana Cashfree Multi-Facility Payment Test Client JavaScript
class RozanaCashfreeMultiFacilityClient {
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
            this.loadFormData(); // Load saved form data
            this.calculateOrderTotal(); // Calculate total from loaded items
            this.setupPreloadedItems(); // Set up event listeners for pre-loaded items
            this.log('🚀 Rozana Cashfree Multi-Facility Payment Test Client initialized');
            this.log('✅ Cashfree SDK initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Cashfree SDK:', error);
            this.log(`❌ Failed to initialize Cashfree SDK: ${error.message}`, 'error');
        }
    }

    // Set up event listeners for pre-loaded items
    setupPreloadedItems() {
        // Set up remove buttons for existing items
        document.querySelectorAll('.item-card .remove-item').forEach(button => {
            button.addEventListener('click', () => {
                const itemCard = button.closest('.item-card');
                if (itemCard) {
                    this.removeItem(itemCard);
                }
            });
        });

        // Set up input listeners for existing items
        document.querySelectorAll('.item-card').forEach(card => {
            const quantityInput = card.querySelector('.quantity');
            const priceInput = card.querySelector('.sale-price');

            const updateHandler = () => this.calculateOrderTotal();

            if (quantityInput) quantityInput.addEventListener('input', updateHandler);
            if (priceInput) priceInput.addEventListener('input', updateHandler);
        });
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

        // Add change listener for saving form data
        document.addEventListener('change', (e) => {
            if (e.target.matches('input, select')) {
                this.saveFormData();
            }
        });
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
        this.saveFormData(); // Save after adding payment method
        return methodId;
    }

    // Remove a payment method
    removePaymentMethod(methodId) {
        const method = document.getElementById(methodId);
        if (method) {
            method.remove();
            this.updatePaymentSummary();
            this.saveFormData(); // Save after removing payment method
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
                    <i class="fas fa-cube"></i>
                    <span>Item #${container.children.length + 1}</span>
                    <button type="button" class="remove-item">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="item-fields">
                    <div class="form-group">
                        <label><i class="fas fa-barcode"></i> SKU:</label>
                        <input type="text" class="sku" value="ROZ${Date.now().toString().slice(-6)}" required>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label><i class="fas fa-sort-numeric-up"></i> Quantity:</label>
                            <input type="number" class="quantity" min="1" value="1" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-tag"></i> Unit Price:</label>
                            <input type="number" class="unit-price" step="0.01" min="0" value="100.00" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-money-bill"></i> Sale Price:</label>
                            <input type="number" class="sale-price" step="0.01" min="0" value="95.00" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-building"></i> Facility Name:</label>
                        <input type="text" class="facility-name" value="ROZANA_WH1" required>
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

        this.saveFormData(); // Save after adding item

        return newItem;
    }

    // Remove an item from the order
    removeItem(itemElement) {
        if (itemElement && itemElement.parentNode) {
            itemElement.remove();
            this.calculateOrderTotal();
            this.saveFormData(); // Save after removing item
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
                customerId: 'hy5TTnmZoogh0LFKbag5Ac7RkUa2',
                customerName: 'Sameera',
                facilityId: '5883',
                facilityName: 'ROZANA_WH1',
                fullName: 'Sameera',
                phoneNumber: '9391961859',
                addressLine1: '123 Main Street',
                city: 'Mumbai',
                state: 'Maharashtra',
                postalCode: '400001',
                country: 'india',
                addressType: 'home'
            };

            // Collect order items with facility information
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
                        sale_price: this.totalAmount || 100,
                        facility_name: defaultValues.facilityName
                    });
                } else {
                    itemCards.forEach((card, index) => {
                        const getValue = (selector) => {
                            const element = card.querySelector(selector);
                            return element ? element.value : '';
                        };

                        items.push({
                            sku: getValue('.sku') || `ROZ${Date.now().toString().slice(-6)}`,
                            name: `Item ${index + 1}`,
                            quantity: parseInt(getValue('.quantity')) || 1,
                            unit_price: parseFloat(getValue('.unit-price')) || 0,
                            sale_price: parseFloat(getValue('.sale-price')) || 0,
                            facility_name: getValue('.facility-name') || defaultValues.facilityName
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
                        sale_price: 0,
                        facility_name: defaultValues.facilityName
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
                facility_id: '5883',
                facility_name: 'ROZANA_WH1',
                total_amount: 100,
                items: [{
                    sku: 'ERROR_SKU',
                    name: 'Error Item',
                    quantity: 1,
                    unit_price: 100,
                    sale_price: 100,
                    facility_name: 'ROZANA_WH1'
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

    // Save form data to localStorage
    saveFormData() {
        const data = {
            // Customer details
            customerId: this.getElementValue('customerId'),
            customerName: this.getElementValue('customerName'),
            facilityId: this.getElementValue('facilityId'),
            facilityName: this.getElementValue('facilityName'),
            
            // Address
            fullName: this.getElementValue('fullName'),
            phoneNumber: this.getElementValue('phoneNumber'),
            addressLine1: this.getElementValue('addressLine1'),
            addressLine2: this.getElementValue('addressLine2'),
            city: this.getElementValue('city'),
            state: this.getElementValue('state'),
            postalCode: this.getElementValue('postalCode'),
            country: this.getElementValue('country'),
            addressType: this.getElementValue('addressType'),
            longitude: this.getElementValue('longitude'),
            latitude: this.getElementValue('latitude'),
            
            // Items
            items: [],
            
            // Payment methods
            paymentMethods: []
        };

        // Collect items
        document.querySelectorAll('.item-card').forEach(card => {
            data.items.push({
                sku: card.querySelector('.sku')?.value || '',
                quantity: card.querySelector('.quantity')?.value || '',
                unitPrice: card.querySelector('.unit-price')?.value || '',
                salePrice: card.querySelector('.sale-price')?.value || '',
                facilityName: card.querySelector('.facility-name')?.value || ''
            });
        });

        // Collect payment methods
        document.querySelectorAll('.payment-method').forEach(method => {
            data.paymentMethods.push({
                mode: method.querySelector('.payment-mode')?.value || '',
                amount: method.querySelector('.payment-amount')?.value || ''
            });
        });

        localStorage.setItem('cashfreeFormData', JSON.stringify(data));
    }

    // Load form data from localStorage
    loadFormData() {
        const dataStr = localStorage.getItem('cashfreeFormData');
        if (!dataStr) {
            // No saved data, add default payment method
            this.addPaymentMethod();
            return;
        }

        const data = JSON.parse(dataStr);

        // Load customer details
        if (data.customerId) document.getElementById('customerId').value = data.customerId;
        if (data.customerName) document.getElementById('customerName').value = data.customerName;
        if (data.facilityId) document.getElementById('facilityId').value = data.facilityId;
        if (data.facilityName) document.getElementById('facilityName').value = data.facilityName;

        // Load address
        if (data.fullName) document.getElementById('fullName').value = data.fullName;
        if (data.phoneNumber) document.getElementById('phoneNumber').value = data.phoneNumber;
        if (data.addressLine1) document.getElementById('addressLine1').value = data.addressLine1;
        if (data.addressLine2) document.getElementById('addressLine2').value = data.addressLine2;
        if (data.city) document.getElementById('city').value = data.city;
        if (data.state) document.getElementById('state').value = data.state;
        if (data.postalCode) document.getElementById('postalCode').value = data.postalCode;
        if (data.country) document.getElementById('country').value = data.country;
        if (data.addressType) document.getElementById('addressType').value = data.addressType;
        if (data.longitude) document.getElementById('longitude').value = data.longitude;
        if (data.latitude) document.getElementById('latitude').value = data.latitude;

        // Load items - set values in existing item cards (assuming HTML has 3)
        const itemCards = document.querySelectorAll('.item-card');
        if (data.items && data.items.length > 0) {
            data.items.forEach((item, index) => {
                if (itemCards[index]) {
                    const card = itemCards[index];
                    if (item.sku) card.querySelector('.sku').value = item.sku;
                    if (item.quantity) card.querySelector('.quantity').value = item.quantity;
                    if (item.unitPrice) card.querySelector('.unit-price').value = item.unitPrice;
                    if (item.salePrice) card.querySelector('.sale-price').value = item.salePrice;
                    if (item.facilityName) card.querySelector('.facility-name').value = item.facilityName;
                } else {
                    // If more items than HTML has, add new ones
                    const newCard = this.addItem();
                    if (item.sku) newCard.querySelector('.sku').value = item.sku;
                    if (item.quantity) newCard.querySelector('.quantity').value = item.quantity;
                    if (item.unitPrice) newCard.querySelector('.unit-price').value = item.unitPrice;
                    if (item.salePrice) newCard.querySelector('.sale-price').value = item.salePrice;
                    if (item.facilityName) newCard.querySelector('.facility-name').value = item.facilityName;
                }
            });
        }

        // Load payment methods
        if (data.paymentMethods && data.paymentMethods.length > 0) {
            data.paymentMethods.forEach(pm => {
                const methodId = this.addPaymentMethod();
                const method = document.getElementById(methodId);
                if (pm.mode) method.querySelector('.payment-mode').value = pm.mode;
                if (pm.amount) method.querySelector('.payment-amount').value = pm.amount;
            });
        } else {
            // Add default payment method
            this.addPaymentMethod();
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
            this.log('📝 Creating multi-facility order...');
            this.setButtonLoading('Create Multi-Facility Order', true);

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

            this.log('📦 Multi-facility order data:', 'debug');
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
            this.log(`✅ Multi-facility order created successfully: Parent ID ${result.parent_order_id}`);
            this.log(`📋 Order IDs: ${result.all_order_ids ? result.all_order_ids.join(', ') : 'N/A'}`);
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
                    this.log('✅ Payment order created in multi-facility order creation');
                    this.initiateCashfreePayment(cashfreeOrder, result.parent_order_id);
                } else {
                    this.log('❌ No Cashfree payment order found in response', 'error');
                    console.error('Full payment_order_details:', JSON.stringify(result.payment_order_details, null, 2));
                }
            } else if (orderData.payment.every(p => ['cod', 'cash'].includes(p.payment_mode))) {
                // For COD/Cash only orders, show success immediately
                this.log('✅ Multi-facility order created with COD/Cash payment. No online payment required.');
                this.showSuccess(result);
            }

        } catch (error) {
            this.log(`❌ Error creating multi-facility order: ${error.message}`, 'error');
            alert(`Error creating order: ${error.message}`);
        } finally {
            this.isCreatingOrder = false;
            this.setButtonLoading('Create Multi-Facility Order', false);
        }
    }

    async initiateCashfreePayment(paymentOrder, parentOrderId) {
        try {
            this.log('💳 Initiating Cashfree payment for multi-facility order...');
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
                this.log('Cashfree checkout completed for multi-facility order');
                this.log(`Result: ${JSON.stringify(result)}`);

                if (result.error) {
                    this.log(`❌ Payment failed: ${result.error.message}`, 'error');
                    alert(`Payment failed: ${result.error.message}`);
                } else if (result.redirect) {
                    this.log('✅ Payment successful, redirecting...');
                    this.verifyPayment(result, parentOrderId);
                } else if (result.paymentDetails) {
                    this.log('✅ Payment completed');
                    this.verifyPayment(result.paymentDetails, parentOrderId);
                } else {
                    this.log('✅ Payment flow completed');
                    this.showSuccess({
                        parent_order_id: parentOrderId,
                        payment_status: 'SUCCESS',
                        message: 'Payment completed successfully for multi-facility order'
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
                            parent_order_id: parentOrderId,
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

    async verifyPayment(paymentDetails, parentOrderId) {
        try {
            this.log('🔍 Verifying payment for multi-facility order...');

            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const headers = this.getAuthHeaders();

            const verificationData = {
                order_id: parentOrderId,
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
            this.log('✅ Payment verified successfully for multi-facility order');
            this.displayPaymentStatus(result);

        } catch (error) {
            this.log(`❌ Payment verification failed: ${error.message}`, 'error');
        }
    }

    // Helper methods for UI updates
    setButtonLoading(text, loading) {
        const button = document.querySelector('#orderForm button[type="submit"]');
        if (button) {
            if (loading) {
                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
            } else {
                button.disabled = false;
                button.innerHTML = `<i class="fas fa-arrow-right"></i> ${text}`;
            }
        }
    }

    // Display order details in payment step
    displayOrderDetails(orderData) {
        const orderDetailsContainer = document.getElementById('orderDetails');
        if (!orderDetailsContainer || !orderData) return;

        let orderHtml = '<h3>Order Details</h3>';
        orderHtml += `<p><strong>Parent Order ID:</strong> ${orderData.parent_order_id || 'N/A'}</p>`;

        if (orderData.all_order_ids && orderData.all_order_ids.length > 0) {
            orderHtml += `<p><strong>Order IDs:</strong> ${orderData.all_order_ids.join(', ')}</p>`;
        }

        if (orderData.facilities && orderData.facilities.length > 0) {
            orderHtml += `<p><strong>Facilities:</strong> ${orderData.facilities.join(', ')}</p>`;
        }

        orderHtml += `<p><strong>Total Amount:</strong> ₹${orderData.total_amount || 0}</p>`;
        orderHtml += `<p><strong>Customer:</strong> ${orderData.customer_name || 'N/A'}</p>`;

        orderDetailsContainer.innerHTML = orderHtml;
    }

    // Show success message
    showSuccess(orderData) {
        // Move to completion step
        document.getElementById('paymentStep').classList.remove('active');
        document.getElementById('completionStep').classList.add('active');
        document.getElementById('step2').classList.remove('active');
        document.getElementById('step3').classList.add('active');

        const statusElement = document.getElementById('paymentStatus');
        if (statusElement) {
            let statusHtml = '<h3>🎉 Order Created Successfully!</h3>';
            statusHtml += `<p><strong>Parent Order ID:</strong> ${orderData.parent_order_id || orderData.order_id || 'N/A'}</p>`;

            if (orderData.all_order_ids && orderData.all_order_ids.length > 0) {
                statusHtml += `<p><strong>All Order IDs:</strong> ${orderData.all_order_ids.join(', ')}</p>`;
            }

            if (orderData.facilities && orderData.facilities.length > 0) {
                statusHtml += `<p><strong>Facilities:</strong> ${orderData.facilities.join(', ')}</p>`;
            }

            statusHtml += `<p><strong>Status:</strong> ${orderData.payment_status || 'COMPLETED'}</p>`;
            statusHtml += `<p><strong>Message:</strong> ${orderData.message || 'Your multi-facility order has been processed successfully!'}</p>`;

            statusElement.innerHTML = statusHtml;
        }

        this.log('✅ Multi-facility order process completed successfully!');
    }

    // Display payment status
    displayPaymentStatus(result) {
        const statusElement = document.getElementById('paymentStatus');
        if (statusElement) {
            let statusHtml = '<h3>💳 Payment Status</h3>';
            statusHtml += `<p><strong>Status:</strong> ${result.status || 'Unknown'}</p>`;
            statusHtml += `<p><strong>Order ID:</strong> ${result.order_id || 'N/A'}</p>`;
            statusHtml += `<p><strong>Amount:</strong> ₹${result.amount || 0}</p>`;
            statusHtml += `<p><strong>Payment ID:</strong> ${result.payment_id || 'N/A'}</p>`;

            statusElement.innerHTML = statusHtml;
        }
    }

    // Initiate payment (called from UI)
    initiatePayment() {
        if (!this.currentOrder) {
            this.log('❌ No order data available for payment', 'error');
            return;
        }

        // Display order details
        this.displayOrderDetails(this.currentOrder);

        // Check if payment is already completed
        if (this.currentOrder.payment_status === 'COMPLETED') {
            this.showSuccess(this.currentOrder);
            return;
        }

        // For Cashfree payments, the payment should already be initiated during order creation
        this.log('ℹ️ Payment flow should be handled during order creation for multi-facility orders');
    }

    // Reset journey for new order
    resetJourney() {
        this.currentOrder = null;
        this.paymentSession = null;

        // Reset steps
        document.getElementById('orderStep').classList.add('active');
        document.getElementById('paymentStep').classList.remove('active');
        document.getElementById('completionStep').classList.remove('active');

        document.getElementById('step1').classList.add('active');
        document.getElementById('step2').classList.remove('active');
        document.getElementById('step3').classList.remove('active');

        // Clear logs
        this.clearLogs();

        // Clear saved form data
        localStorage.removeItem('cashfreeFormData');

        // Reset form if needed
        const orderForm = document.getElementById('orderForm');
        if (orderForm) {
            orderForm.reset();
        }

        // Reinitialize
        this.totalAmount = 0;
        this.paymentMethods = [];
        this.addPaymentMethod();

        this.log('🔄 Journey reset for new multi-facility order');
    }
}

// Configuration functions
function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

function saveSettings() {
    const apiBaseUrl = document.getElementById('apiBaseUrl').value;
    const cashfreeAppId = document.getElementById('cashfreeAppId').value;
    const cashfreeSecretKey = document.getElementById('cashfreeSecretKey').value;
    const firebaseToken = document.getElementById('firebaseToken').value;

    // Save to localStorage
    localStorage.setItem('apiBaseUrl', apiBaseUrl);
    localStorage.setItem('cashfreeAppId', cashfreeAppId);
    localStorage.setItem('cashfreeSecretKey', cashfreeSecretKey);
    localStorage.setItem('firebaseToken', firebaseToken);

    closeSettings();
    alert('Settings saved successfully!');
}

// Load settings on page load
window.addEventListener('DOMContentLoaded', () => {
    // Load saved settings
    const apiBaseUrl = localStorage.getItem('apiBaseUrl') || 'http://localhost:8000';
    const cashfreeAppId = localStorage.getItem('cashfreeAppId') || '';
    const cashfreeSecretKey = localStorage.getItem('cashfreeSecretKey') || '';
    const firebaseToken = localStorage.getItem('firebaseToken') || '';

    document.getElementById('apiBaseUrl').value = apiBaseUrl;
    document.getElementById('cashfreeAppId').value = cashfreeAppId;
    document.getElementById('cashfreeSecretKey').value = cashfreeSecretKey;
    document.getElementById('firebaseToken').value = firebaseToken;

    // Initialize the client
    window.client = new RozanaCashfreeMultiFacilityClient();
});

// Utility functions
function clearLogs() {
    if (window.client) {
        window.client.clearLogs();
    }
}

function toggleLogs() {
    const logsContent = document.getElementById('logsContent');
    const toggleIcon = document.getElementById('toggleIcon');

    if (logsContent.style.display === 'none') {
        logsContent.style.display = 'block';
        toggleIcon.className = 'fas fa-chevron-down';
    } else {
        logsContent.style.display = 'none';
        toggleIcon.className = 'fas fa-chevron-right';
    }
}

// Remove item function (accessible globally)
function removeItem(button) {
    if (window.client) {
        const itemCard = button.closest('.item-card');
        if (itemCard) {
            window.client.removeItem(itemCard);
        }
    }
}

// Add item function (accessible globally)
function addItem() {
    if (window.client && typeof window.client.addItem === 'function') {
        window.client.addItem();
    } else {
        console.warn('Client not initialized yet. Please wait for the page to load completely.');
    }
}
