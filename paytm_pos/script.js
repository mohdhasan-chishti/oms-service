// Paytm POS Payment Test Client JavaScript
class PaytmPOSClient {
    constructor() {
        this.currentOrder = null;
        this.selectedTerminal = null;
        this.paymentData = null;
        this.statusCheckInterval = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.totalAmount = 0;
        this.paymentMethods = [];
        this.calculateOrderTotal();
        this.log('🚀 Paytm POS Payment Test Client initialized');
        loadSettings();
        // Load terminals on page load
        setTimeout(() => this.loadTerminalsForOrder(), 1000);
        // Setup payment methods
        this.setupPaymentMethods();
    }

    setupEventListeners() {
        const orderForm = document.getElementById('orderForm');
        if (orderForm) {
            orderForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createOrder();
            });
        }

        const orderItems = document.getElementById('orderItems');
        if (orderItems) {
            orderItems.addEventListener('input', (e) => {
                if (e.target.classList.contains('quantity') || e.target.classList.contains('sale-price')) {
                    this.calculateOrderTotal();
                }
            });
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
        
        return this.totalAmount;
    }

    getOrderFormData() {
        const items = [];
        document.querySelectorAll('.item-card').forEach((card, index) => {
            const getValue = (selector) => {
                const element = card.querySelector(selector);
                return element ? element.value : '';
            };

            items.push({
                sku: getValue('.sku') || `SKU${index + 1}`,
                name: getValue('.sku') || `Item ${index + 1}`,
                quantity: parseInt(getValue('.quantity')) || 1,
                unit_price: parseFloat(getValue('.unit-price')) || 0,
                sale_price: parseFloat(getValue('.sale-price')) || 0
            });
        });

        // Build payment array from payment methods
        const payment = [];
        this.paymentMethods.forEach(pm => {
            if (pm && pm.mode && pm.amount > 0) {
                const paymentItem = {
                    payment_mode: pm.mode,
                    amount: pm.amount
                };
                
                // Add terminal_id for Paytm POS payments
                if (pm.mode === 'paytm_pos' && this.selectedTerminal) {
                    paymentItem.terminal_id = this.selectedTerminal.terminal_id;
                }
                
                payment.push(paymentItem);
            }
        });

        return {
            customer_id: document.getElementById('customerId').value || '2CN3aYJnaGXpaguuctWAubZnKKp1',
            customer_name: document.getElementById('customerName').value || 'Test Customer',
            facility_id: "1",
            facility_name: document.getElementById('facilityName').value || 'ROZANA_WH1',
            total_amount: this.totalAmount,
            items: items,
            address: {
                full_name: document.getElementById('fullName').value || 'Test Customer',
                phone_number: document.getElementById('phoneNumber').value || '9123456789',
                address_line1: document.getElementById('addressLine1').value || '123 Main Street',
                address_line2: document.getElementById('addressLine2').value || '',
                city: document.getElementById('city').value || 'Bangalore',
                state: document.getElementById('state').value || 'Karnataka',
                postal_code: document.getElementById('postalCode').value || '560001',
                country: document.getElementById('country').value || 'INDIA',
                type_of_address: document.getElementById('addressType').value || 'work',
                longitude: null,
                latitude: null
            },
            payment: payment,
            payment_mode: 'paytm_pos',
            customer_email: 'test@example.com',
            customer_phone: document.getElementById('phoneNumber').value || '9123456789'
        };
    }

    async createOrder() {
        if (!this.validateAuth()) {
            return;
        }

        // Validate payment methods
        const validPayments = this.paymentMethods.filter(pm => pm && pm.mode && pm.amount > 0);
        if (validPayments.length === 0) {
            this.log('❌ Please add at least one payment method', 'error');
            alert('Please add at least one payment method before creating the order');
            return;
        }

        // Check if total matches
        const totalAllocated = validPayments.reduce((sum, pm) => sum + pm.amount, 0);
        if (Math.abs(totalAllocated - this.totalAmount) > 0.01) {
            this.log('❌ Payment total must match order total', 'error');
            alert(`Payment total (₹${totalAllocated.toFixed(2)}) must match order total (₹${this.totalAmount.toFixed(2)})`);
            return;
        }

        // Validate terminal selection for Paytm POS
        const hasPaytmPOS = validPayments.some(pm => pm.mode === 'paytm_pos');
        if (hasPaytmPOS && !this.selectedTerminal) {
            this.log('❌ Please select a Paytm POS terminal', 'error');
            alert('Please select a Paytm POS terminal for Paytm POS payment');
            return;
        }

        try {
            this.log('📝 Creating order...');
            this.setButtonLoading(true);
            
            this.calculateOrderTotal();
            
            const orderData = this.getOrderFormData();
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const headers = this.getAuthHeaders();
            
            this.log('Sending order data:', 'debug');
            this.log(JSON.stringify(orderData, null, 2), 'debug');

            const response = await fetch(`${apiBaseUrl}/pos/v1/create_order`, {
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
            this.log('Order creation response:', 'debug');
            this.log(JSON.stringify(result, null, 2), 'debug');
            
            this.currentOrder = result;
            
            // Check if Paytm POS payment exists in the response
            const paytmPayment = result.payment_order_details?.find(p => p.payment_mode === 'paytm_pos');
            
            if (paytmPayment && paytmPayment.paytm_txn_id) {
                // Extract transaction ID from order creation response
                this.paymentData = {
                    txn_id: paytmPayment.paytm_txn_id,
                    payment_id: paytmPayment.payment_id,
                    payment_order_id: paytmPayment.payment_order_id,
                    amount: paytmPayment.amount,
                    status: paytmPayment.status
                };
                
                // Ensure selectedTerminal is set (it should be from order creation)
                if (!this.selectedTerminal) {
                    this.log('⚠️ Warning: selectedTerminal not set, payment status polling may fail', 'warning');
                }
                
                this.log(`✅ Paytm POS payment created with txn_id: ${paytmPayment.paytm_txn_id}`, 'success');
                
                // Go to payment step and start polling
                this.goToStep(3);
                this.updatePaymentDisplay();
                this.startStatusPolling();
            } else {
                // No Paytm POS payment, go directly to completion
                this.log('✅ No Paytm POS payment - order completed', 'success');
                this.goToStep(4);
                this.showCompletion();
            }

        } catch (error) {
            this.log(`❌ Error creating order: ${error.message}`, 'error');
            alert(`Error creating order: ${error.message}`);
        } finally {
            this.setButtonLoading(false);
        }
    }

    async loadTerminalsForOrder() {
        try {
            this.log('🔍 Loading terminals for order page...');
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const facilityCode = document.getElementById('facilityCode').value || 'ROZANA_WH1';
            
            const response = await fetch(`${apiBaseUrl}/pos/v1/terminals?facility_code=${facilityCode}`, {
                method: 'GET',
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log(`✅ Loaded ${result.terminal_count} terminals for order page`);
            this.displayTerminalsForOrder(result.terminals);

        } catch (error) {
            this.log(`❌ Error loading terminals: ${error.message}`, 'error');
            const container = document.getElementById('terminalsListOrder');
            if (container) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #ef4444; grid-column: 1/-1;">
                        <i class="fas fa-exclamation-circle" style="font-size: 3rem; margin-bottom: 20px;"></i>
                        <h3>Error Loading Terminals</h3>
                        <p>${error.message}</p>
                    </div>
                `;
            }
        }
    }

    displayTerminalsForOrder(terminals) {
        const container = document.getElementById('terminalsListOrder');
        
        if (!terminals || terminals.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666; grid-column: 1/-1;">
                    <i class="fas fa-exclamation-circle" style="font-size: 3rem; margin-bottom: 20px;"></i>
                    <h3>No Terminals Found</h3>
                    <p>No active terminals found for this facility.</p>
                </div>
            `;
            return;
        }

        terminals.forEach(terminal => {
            const statusClass = terminal.status.toLowerCase();
            const card = document.createElement('div');
            card.className = 'terminal-card';
            card.innerHTML = `
                <div class="terminal-icon" style="color: ${terminal.color_hex};">
                    <i class="fas fa-desktop"></i>
                </div>
                <div class="terminal-name">${terminal.terminal_name}</div>
                <div class="terminal-id">ID: ${terminal.terminal_id}</div>
                <span class="terminal-status ${statusClass}">${terminal.status}</span>
            `;
            
            // Add click event listener properly
            card.addEventListener('click', () => {
                this.selectTerminalForOrder(terminal.terminal_id, terminal.terminal_name);
                // Highlight selected
                container.querySelectorAll('.terminal-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
            });
            
            container.appendChild(card);
        });
    }

    selectTerminalForOrder(terminalId, terminalName) {
        this.selectedTerminal = { terminal_id: terminalId, terminal_name: terminalName };
        this.log(`✅ Selected terminal: ${terminalName} (${terminalId})`);
    }

    async loadTerminals() {
        try {
            this.log('🔍 Loading terminals...');
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const facilityCode = document.getElementById('facilityCode').value || 'ROZANA_WH1';
            
            const response = await fetch(`${apiBaseUrl}/pos/v1/terminals?facility_code=${facilityCode}`, {
                method: 'GET',
                headers: this.getAuthHeaders()
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log(`✅ Loaded ${result.terminal_count} terminals`);
            this.displayTerminals(result.terminals);

        } catch (error) {
            this.log(`❌ Error loading terminals: ${error.message}`, 'error');
            alert(`Error loading terminals: ${error.message}`);
        }
    }

    displayTerminals(terminals) {
        const container = document.getElementById('terminalsList');
        
        if (!terminals || terminals.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #0369a1;">
                    <i class="fas fa-exclamation-circle" style="font-size: 3rem; margin-bottom: 20px;"></i>
                    <h3>No Terminals Found</h3>
                    <p>No active terminals found for this facility.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = terminals.map(terminal => {
            const statusClass = terminal.status.toLowerCase();
            return `
                <div class="terminal-card" onclick="window.paymentClient.selectTerminal('${terminal.terminal_id}', '${terminal.terminal_name}')">
                    <div class="terminal-icon" style="color: ${terminal.color_hex};">
                        <i class="fas fa-desktop"></i>
                    </div>
                    <div class="terminal-name">${terminal.terminal_name}</div>
                    <div class="terminal-id">ID: ${terminal.terminal_id}</div>
                    <span class="terminal-status ${statusClass}">${terminal.status}</span>
                </div>
            `;
        }).join('');
    }

    async selectTerminal(terminalId, terminalName) {
        this.selectedTerminal = { terminal_id: terminalId, terminal_name: terminalName };
        this.log(`✅ Selected terminal: ${terminalName} (${terminalId})`);
        
        // Highlight selected terminal
        document.querySelectorAll('.terminal-card').forEach(card => {
            card.classList.remove('selected');
        });
        event.target.closest('.terminal-card').classList.add('selected');
        
        // Initiate payment
        await this.initiatePayment();
    }

    async initiatePayment() {
        if (!this.currentOrder || !this.selectedTerminal) {
            this.log('❌ Order or terminal not selected', 'error');
            return;
        }

        try {
            this.log('💳 Initiating Paytm POS payment...');
            this.goToStep(3);
            
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const payload = {
                order_id: this.currentOrder.order_id,
                terminal_id: this.selectedTerminal.terminal_id,
                amount: this.totalAmount,
                facility_code: document.getElementById('facilityCode').value || 'ROZANA_WH1'
            };

            this.log('Payment initiation payload:', 'debug');
            this.log(JSON.stringify(payload, null, 2), 'debug');

            const response = await fetch(`${apiBaseUrl}/pos/v1/paytm/initiate_payment`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.message || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log('✅ Payment initiated successfully');
            this.log('Full payment initiation response:', 'debug');
            this.log(JSON.stringify(result, null, 2), 'debug');
            
            // Extract payment data - try different response structures
            if (result.data) {
                this.paymentData = result.data;
            } else if (result.payment_data) {
                this.paymentData = result.payment_data;
            } else if (result.txn_id || result.transaction_id) {
                this.paymentData = result;
            } else {
                this.paymentData = null;
            }
            
            this.log('Extracted paymentData:', 'debug');
            this.log(JSON.stringify(this.paymentData, null, 2), 'debug');
            
            // Check if we have transaction ID
            const txnId = this.paymentData?.txn_id || this.paymentData?.transaction_id;
            
            if (!txnId) {
                this.log('❌ ERROR: No transaction ID received from payment initiation!', 'error');
                this.log('Payment initiation response structure:', 'error');
                this.log(JSON.stringify(result, null, 2), 'error');
                this.showPaymentError('Payment initiated but no transaction ID received. Response: ' + JSON.stringify(result));
                return;
            }
            
            this.log(`✅ Transaction ID received: ${txnId}`, 'success');
            
            // Update payment info display
            this.updatePaymentDisplay();
            
            // Start polling for payment status
            this.startStatusPolling();

        } catch (error) {
            this.log(`❌ Error initiating payment: ${error.message}`, 'error');
            this.showPaymentError(error.message);
        }
    }

    updatePaymentDisplay() {
        const orderIdEl = document.getElementById('displayOrderId');
        const terminalIdEl = document.getElementById('displayTerminalId');
        const amountEl = document.getElementById('displayAmount');
        const txnIdEl = document.getElementById('displayTxnId');
        
        if (orderIdEl) orderIdEl.textContent = this.currentOrder.order_id;
        if (terminalIdEl && this.selectedTerminal) terminalIdEl.textContent = this.selectedTerminal.terminal_id;
        if (amountEl) amountEl.textContent = `₹${this.totalAmount.toFixed(2)}`;
        if (txnIdEl) txnIdEl.textContent = this.paymentData?.txn_id || this.paymentData?.transaction_id || '-';
    }

    startStatusPolling() {
        this.log('🔄 Starting payment status polling...');
        
        // Clear any existing interval
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
        }
        
        // Poll every 3 seconds
        this.statusCheckInterval = setInterval(() => {
            this.checkPaymentStatusSilent();
        }, 3000);
        
        // Also check immediately
        this.checkPaymentStatusSilent();
    }

    stopStatusPolling() {
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
            this.log('⏹️ Stopped payment status polling');
        }
    }

    async checkPaymentStatusSilent() {
        try {
            const txnId = this.paymentData?.txn_id || this.paymentData?.transaction_id;
            
            if (!txnId) {
                this.log('⚠️ No transaction ID available for status check - stopping polling', 'warning');
                this.stopStatusPolling();
                return;
            }
            
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const payload = {
                order_id: this.currentOrder.order_id,
                terminal_id: this.selectedTerminal.terminal_id,
                txn_id: txnId
            };

            const response = await fetch(`${apiBaseUrl}/pos/v1/paytm/payment_status`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                return; // Silently fail for polling
            }

            const result = await response.json();
            
            if (result.data) {
                const status = result.data.payment_status || result.data.status;
                
                if (status === 'SUCCESS' || status === 'COMPLETED') {
                    this.stopStatusPolling();
                    this.log('✅ Payment successful!', 'success');
                    this.showConfirmButton();
                } else if (status === 'FAILED' || status === 'FAILURE') {
                    this.stopStatusPolling();
                    this.log('❌ Payment failed', 'error');
                    this.showReinitiateButton();
                }
            }

        } catch (error) {
            // Silently fail for polling
        }
    }

    async checkPaymentStatus() {
        try {
            this.log('🔍 Checking payment status...');
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            const payload = {
                order_id: this.currentOrder.order_id,
                terminal_id: this.selectedTerminal.terminal_id,
                transaction_id: this.paymentData?.txn_id || this.paymentData?.transaction_id
            };

            const response = await fetch(`${apiBaseUrl}/pos/v1/paytm/payment_status`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log('✅ Payment status retrieved');
            this.log(JSON.stringify(result, null, 2), 'debug');
            
            const status = result.data?.payment_status || result.data?.status;
            
            if (status === 'SUCCESS' || status === 'COMPLETED') {
                this.stopStatusPolling();
                this.showConfirmButton();
            } else if (status === 'FAILED' || status === 'FAILURE') {
                this.stopStatusPolling();
                this.showReinitiateButton();
            } else {
                this.log(`⏳ Payment status: ${status}`, 'info');
            }

        } catch (error) {
            this.log(`❌ Error checking payment status: ${error.message}`, 'error');
            alert(`Error checking payment status: ${error.message}`);
        }
    }

    async confirmPayment() {
        try {
            this.log('✅ Confirming payment...');
            const apiBaseUrl = document.getElementById('apiBaseUrl').value;
            
            const txnId = this.paymentData?.txn_id || this.paymentData?.transaction_id;
            const paymentId = this.paymentData?.payment_id;
            
            if (!txnId) {
                throw new Error('Transaction ID is missing');
            }
            if (!paymentId) {
                throw new Error('Payment ID is missing');
            }
            
            const payload = {
                order_id: this.currentOrder.order_id,
                terminal_id: this.selectedTerminal?.terminal_id,
                txn_id: txnId,
                payment_id: paymentId
            };
            
            this.log('Confirm payment payload:', 'debug');
            this.log(JSON.stringify(payload, null, 2), 'debug');

            const response = await fetch(`${apiBaseUrl}/pos/v1/paytm/confirm_payment`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.log('✅ Payment confirmed successfully!');
            this.log(JSON.stringify(result, null, 2), 'debug');
            
            this.showCompletion(result);

        } catch (error) {
            this.log(`❌ Error confirming payment: ${error.message}`, 'error');
            alert(`Error confirming payment: ${error.message}`);
        }
    }

    async reinitiatePayment() {
        this.log('🔄 Reinitiating payment...');
        this.stopStatusPolling();
        
        // Reset payment data
        this.paymentData = null;
        
        // Hide buttons
        document.getElementById('confirmBtn').style.display = 'none';
        document.getElementById('reinitiateBtn').style.display = 'none';
        
        // Reset payment status display
        const statusDiv = document.getElementById('paymentStatus');
        statusDiv.innerHTML = `
            <div class="status-waiting">
                <div class="spinner"></div>
                <h3>Waiting for Payment...</h3>
                <p>Please complete the payment on the POS terminal</p>
                <div class="payment-info">
                    <div class="info-row">
                        <span>Order ID:</span>
                        <strong id="displayOrderId">-</strong>
                    </div>
                    <div class="info-row">
                        <span>Terminal ID:</span>
                        <strong id="displayTerminalId">-</strong>
                    </div>
                    <div class="info-row">
                        <span>Amount:</span>
                        <strong id="displayAmount">₹0.00</strong>
                    </div>
                    <div class="info-row">
                        <span>Transaction ID:</span>
                        <strong id="displayTxnId">-</strong>
                    </div>
                </div>
            </div>
        `;
        
        // Initiate payment again
        await this.initiatePayment();
    }

    showConfirmButton() {
        document.getElementById('confirmBtn').style.display = 'inline-flex';
        document.getElementById('reinitiateBtn').style.display = 'none';
        
        const statusDiv = document.getElementById('paymentStatus');
        statusDiv.innerHTML = `
            <div class="status-success">
                <i class="fas fa-check-circle" style="font-size: 4rem; color: #10b981; margin-bottom: 20px;"></i>
                <h3 style="color: #10b981;">Payment Successful!</h3>
                <p style="color: #0369a1;">Click confirm to complete the order</p>
            </div>
        `;
    }

    showReinitiateButton() {
        document.getElementById('confirmBtn').style.display = 'none';
        document.getElementById('reinitiateBtn').style.display = 'inline-flex';
        
        const statusDiv = document.getElementById('paymentStatus');
        statusDiv.innerHTML = `
            <div class="status-error">
                <i class="fas fa-times-circle" style="font-size: 4rem; color: #ef4444; margin-bottom: 20px;"></i>
                <h3 style="color: #ef4444;">Payment Failed</h3>
                <p style="color: #0369a1;">Click reinitiate to try again</p>
            </div>
        `;
    }

    showCompletion() {
        this.log('✅ Order completed successfully');
        
        const completionDiv = document.getElementById('completionDetails');
        if (completionDiv) {
            const paymentSummary = this.paymentMethods
                .filter(pm => pm && pm.mode && pm.amount > 0)
                .map(pm => `<p><strong>${pm.mode.toUpperCase()}:</strong> ₹${pm.amount.toFixed(2)}</p>`)
                .join('');
            
            completionDiv.innerHTML = `
                <div class="completion-details">
                    <h3>Order Details</h3>
                    <p><strong>Order ID:</strong> ${this.currentOrder.order_id}</p>
                    <p><strong>Total Amount:</strong> ₹${this.totalAmount.toFixed(2)}</p>
                    <p><strong>Status:</strong> ${this.currentOrder.status || 'Pending'}</p>
                    <h3 style="margin-top: 20px;">Payment Summary</h3>
                    ${paymentSummary}
                </div>
            `;
        }
    }

    showPaymentError(message) {
        const statusDiv = document.getElementById('paymentStatus');
        statusDiv.innerHTML = `
            <div class="status-error">
                <i class="fas fa-exclamation-circle" style="font-size: 4rem; color: #ef4444; margin-bottom: 20px;"></i>
                <h3 style="color: #ef4444;">Payment Error</h3>
                <p style="color: #0369a1;">${message}</p>
            </div>
        `;
        document.getElementById('reinitiateBtn').style.display = 'inline-flex';
    }

    showCompletion(result) {
        this.goToStep(4);
        
        const detailsDiv = document.getElementById('completionDetails');
        detailsDiv.innerHTML = `
            <div style="text-align: center;">
                <i class="fas fa-check-circle" style="font-size: 5rem; color: #10b981; margin-bottom: 30px;"></i>
                <h3 style="color: #0c4a6e; margin-bottom: 20px;">Order Completed Successfully!</h3>
                <div style="background: #f0f9ff; border: 2px solid #bae6fd; border-radius: 12px; padding: 25px; text-align: left;">
                    <p style="margin: 10px 0;"><strong>Order ID:</strong> ${this.currentOrder.order_id}</p>
                    <p style="margin: 10px 0;"><strong>Terminal:</strong> ${this.selectedTerminal.terminal_name}</p>
                    <p style="margin: 10px 0;"><strong>Amount:</strong> ₹${this.totalAmount.toFixed(2)}</p>
                    <p style="margin: 10px 0;"><strong>Status:</strong> <span style="color: #10b981; font-weight: 700;">COMPLETED</span></p>
                </div>
            </div>
        `;
    }

    goToStep(stepNumber) {
        // Hide all steps
        document.querySelectorAll('.journey-step').forEach(step => {
            step.classList.remove('active');
        });
        
        // Show current step
        const steps = ['orderStep', 'terminalStep', 'paymentStep', 'completionStep'];
        const targetStep = document.getElementById(steps[stepNumber - 1]);
        if (targetStep) {
            targetStep.classList.add('active');
        } else {
            this.log(`⚠️ Warning: Step element not found: ${steps[stepNumber - 1]}`, 'warning');
        }
        
        // Update progress indicators
        for (let i = 1; i <= 4; i++) {
            const stepEl = document.getElementById(`step${i}`);
            if (!stepEl) continue; // Skip if element doesn't exist
            
            if (i < stepNumber) {
                stepEl.classList.add('completed');
                stepEl.classList.remove('active');
            } else if (i === stepNumber) {
                stepEl.classList.add('active');
                stepEl.classList.remove('completed');
            } else {
                stepEl.classList.remove('active', 'completed');
            }
        }
    }

    setButtonLoading(isLoading) {
        const submitButton = document.querySelector('button[type="submit"]');
        if (submitButton) {
            if (isLoading) {
                submitButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Creating Order...`;
                submitButton.disabled = true;
            } else {
                submitButton.innerHTML = `<i class="fas fa-arrow-right"></i> Create Order & Pay`;
                submitButton.disabled = false;
            }
        }
    }

    setupPaymentMethods() {
        const addButton = document.getElementById('addPaymentMethod');
        if (addButton) {
            addButton.addEventListener('click', () => this.addPaymentMethod());
        }
    }

    addPaymentMethod() {
        const methodIndex = this.paymentMethods.length;
        const container = document.getElementById('paymentMethodsContainer');
        
        const methodCard = document.createElement('div');
        methodCard.className = 'payment-method-card';
        methodCard.dataset.index = methodIndex;
        methodCard.innerHTML = `
            <div class="payment-method-header">
                <h4><i class="fas fa-credit-card"></i> Payment Method #${methodIndex + 1}</h4>
                <button type="button" class="remove-payment" onclick="window.paymentClient.removePaymentMethod(${methodIndex})">
                    <i class="fas fa-trash"></i> Remove
                </button>
            </div>
            <div class="payment-method-fields">
                <div class="form-row">
                    <div class="form-group">
                        <label><i class="fas fa-wallet"></i> Payment Mode:</label>
                        <select class="payment-mode" data-index="${methodIndex}" onchange="window.paymentClient.handlePaymentModeChange(${methodIndex})">
                            <option value="">Select Payment Mode</option>
                            <option value="cod">💵 Cash on Delivery (COD)</option>
                            <option value="razorpay">💳 Razorpay</option>
                            <option value="paytm_pos">🖥️ Paytm POS</option>
                            <option value="wallet">👛 Wallet</option>
                            <option value="credit">🎫 Credit</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-money-bill"></i> Amount (₹):</label>
                        <input type="number" class="payment-amount" data-index="${methodIndex}" step="0.01" min="0" placeholder="0.00" oninput="window.paymentClient.updatePaymentSummary()">
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(methodCard);
        this.paymentMethods.push({ mode: '', amount: 0, terminal_id: null });
        this.updatePaymentSummary();
    }

    removePaymentMethod(index) {
        const card = document.querySelector(`.payment-method-card[data-index="${index}"]`);
        if (card) {
            card.remove();
            this.paymentMethods[index] = null;
            this.updatePaymentSummary();
            this.checkPaytmPOSSelection();
        }
    }

    handlePaymentModeChange(index) {
        const select = document.querySelector(`.payment-mode[data-index="${index}"]`);
        if (select) {
            this.paymentMethods[index].mode = select.value;
            this.checkPaytmPOSSelection();
        }
    }

    checkPaytmPOSSelection() {
        const hasPaytmPOS = this.paymentMethods.some(pm => pm && pm.mode === 'paytm_pos');
        const terminalSection = document.getElementById('terminalSelectionSection');
        
        if (hasPaytmPOS) {
            terminalSection.style.display = 'block';
        } else {
            terminalSection.style.display = 'none';
            this.selectedTerminal = null;
        }
    }

    updatePaymentSummary() {
        let totalAllocated = 0;
        
        document.querySelectorAll('.payment-amount').forEach((input, idx) => {
            const amount = parseFloat(input.value) || 0;
            if (this.paymentMethods[idx]) {
                this.paymentMethods[idx].amount = amount;
            }
            totalAllocated += amount;
        });
        
        const orderTotal = this.totalAmount;
        const remaining = orderTotal - totalAllocated;
        
        document.getElementById('totalAllocated').textContent = `₹${totalAllocated.toFixed(2)}`;
        document.getElementById('remainingAmount').textContent = `₹${remaining.toFixed(2)}`;
        
        const errorDiv = document.getElementById('paymentError');
        if (Math.abs(remaining) > 0.01 && totalAllocated > 0) {
            errorDiv.style.display = 'block';
        } else {
            errorDiv.style.display = 'none';
        }
    }
}

// Utility functions
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
    
    if (window.paymentClient) {
        window.paymentClient.calculateOrderTotal();
    }
}

function removeItem(button) {
    const itemCard = button.closest('.item-card');
    const container = document.getElementById('orderItems');
    if (container.children.length > 1) {
        itemCard.remove();
        if (window.paymentClient) {
            window.paymentClient.calculateOrderTotal();
        }
    } else {
        alert('At least one item is required');
    }
}

function clearLogs() {
    document.getElementById('logs').textContent = '';
    if (window.paymentClient) {
        window.paymentClient.log('Debug logs cleared', 'info');
    }
}

function checkPaymentStatus() {
    if (window.paymentClient) {
        window.paymentClient.checkPaymentStatus();
    }
}

function confirmPayment() {
    if (window.paymentClient) {
        window.paymentClient.confirmPayment();
    }
}

function reinitiatePayment() {
    if (window.paymentClient) {
        window.paymentClient.reinitiatePayment();
    }
}

function goBack(stepId) {
    const steps = ['orderStep', 'terminalStep', 'paymentStep', 'completionStep'];
    const targetIndex = steps.indexOf(stepId);
    
    if (targetIndex >= 0 && window.paymentClient) {
        window.paymentClient.goToStep(targetIndex + 1);
    }
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
    if (window.paymentClient) {
        window.paymentClient.stopStatusPolling();
        window.paymentClient.currentOrder = null;
        window.paymentClient.selectedTerminal = null;
        window.paymentClient.paymentData = null;
        window.paymentClient.goToStep(1);
        window.paymentClient.log('🔄 Journey reset - ready for new order');
    }
    
    // Reset form
    document.getElementById('orderForm').reset();
    document.getElementById('totalAmount').value = '0';
    
    // Reset buttons
    document.getElementById('confirmBtn').style.display = 'none';
    document.getElementById('reinitiateBtn').style.display = 'none';
}

// Settings modal functions
function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

function saveSettings() {
    localStorage.setItem('apiBaseUrl', document.getElementById('apiBaseUrl').value);
    localStorage.setItem('facilityCode', document.getElementById('facilityCode').value);
    localStorage.setItem('firebaseToken', document.getElementById('firebaseToken').value);
    
    closeSettings();
    
    if (window.paymentClient) {
        window.paymentClient.log('✅ Configuration saved successfully!');
    }
}

function loadSettings() {
    const apiBaseUrl = localStorage.getItem('apiBaseUrl');
    const facilityCode = localStorage.getItem('facilityCode');
    const firebaseToken = localStorage.getItem('firebaseToken');
    
    if (apiBaseUrl) document.getElementById('apiBaseUrl').value = apiBaseUrl;
    if (facilityCode) document.getElementById('facilityCode').value = facilityCode;
    if (firebaseToken) document.getElementById('firebaseToken').value = firebaseToken;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target === modal) {
        closeSettings();
    }
}

// Initialize the payment client when the page loads
document.addEventListener('DOMContentLoaded', function() {
    window.paymentClient = new PaytmPOSClient();
});
