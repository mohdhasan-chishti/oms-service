# Cart Service - Category-Based Promotions

The Cart Service provides advanced functionality for managing shopping cart promotions with **category-level targeting** and discount calculations in the OMS system.

## 🚀 Key Features

### 1. **Available Promotions API** - Category-Aware Filtering
- **APP Endpoint**: `POST /app/v1/cart/promotions/available`
- **POS Endpoint**: `POST /pos/v1/cart/promotions/available`
- **Purpose**: Returns promotions filtered by cart items and their categories
- **Innovation**: Uses `CategoryFilter` to validate promotions against actual cart contents

### 2. **Cart Discount Calculation API** - Intelligent Item Targeting
- **APP Endpoint**: `POST /app/v1/cart/discount/calculate`
- **POS Endpoint**: `POST /pos/v1/cart/discount/calculate`
- **Purpose**: Applies discounts only to eligible items based on category/SKU filters
- **Innovation**: Returns `offer_applied` flag for each item to show promotion targeting

## 🏗️ Architecture

```
├── cart/
│   ├── repository.py      # Typesense integration for promotions
│   ├── service.py         # Business logic for cart operations
│   └── README.md         # This comprehensive guide
├── core/
│   └── cart_functions.py  # Core business logic (channel-agnostic)
├── dto/
│   └── cart.py           # Enhanced models with category fields
├── promotions/
│   └── category_filter.py # Category-based filtering engine
├── routes/app/
│   └── cart.py           # APP channel cart endpoints
└── routes/pos/
    └── cart.py           # POS channel cart endpoints
```

## 🎯 Category-Based Promotion System

### **Core Concept**
Promotions can now target specific categories while excluding others, with intelligent item filtering and precise discount application.

### **Filter Priority (Highest to Lowest)**
1. **SKU Filters**: `applicable_skus`, `excluded_skus`
2. **Category Filters**: `applicable_categories`, `excluded_categories`
3. **Include/Exclude Logic**: Include first, then exclude

## 📊 Comprehensive Examples with Mathematical Calculations

### **Sample Cart Items**

| SKU | Name | Category | Sub Category | Sub-Sub Category | MRP | Sale Price | Qty | Total |
|-----|------|----------|--------------|------------------|-----|------------|-----|-------|
| GROC001 | Fresh Milk 1L | Groceries | Dairy Products | Milk & Cream | ₹120 | ₹100 | 2 | ₹200 |
| ELEC001 | Mobile Charger | Electronics | Mobile Accessories | Chargers | ₹600 | ₹500 | 1 | ₹500 |
| ORG001 | Organic Vegetables | Groceries | Organic | Organic Vegetables | ₹150 | ₹120 | 1 | ₹120 |
| SWEET001 | Traditional Sweets | Food | Sweets | Traditional Sweets | ₹250 | ₹200 | 2 | ₹400 |

**Total Cart Value**: ₹1,220

### **Sample Promotions**

| Code | Name | Type | Amount | Min Purchase | Applicable Categories | Excluded Categories |
|------|------|------|--------|--------------|----------------------|-------------------|
| GROCERY50 | 50% off Groceries | flat_discount | ₹50 | ₹150 | ["Groceries"] | ["Organic"] |
| ELECTRONICS100 | ₹100 off Electronics | flat_discount | ₹100 | ₹500 | ["Electronics"] | [] |
| FOOD25 | ₹25 off Food | flat_discount | ₹25 | ₹300 | ["Food"] | [] |

---

## 🔍 **Scenario 1: GROCERY50 Promotion**

### **Available Promotions API**

```bash
POST /app/v1/cart/promotions/available
Content-Type: application/json

{
    "total_amount": 1220,
    "user_id": "user123",
    "facility_name": "ROZANA_TEST_WH1",
    "items": [
        {
            "sku": "GROC001",
            "mrp": 120,
            "sale_price": 100,
            "quantity": 2,
            "category": "Groceries",
            "sub_category": "Dairy Products",
            "sub_sub_category": "Milk & Cream"
        },
        {
            "sku": "ELEC001",
            "mrp": 600,
            "sale_price": 500,
            "quantity": 1,
            "category": "Electronics",
            "sub_category": "Mobile Accessories",
            "sub_sub_category": "Chargers"
        },
        {
            "sku": "ORG001",
            "mrp": 150,
            "sale_price": 120,
            "quantity": 1,
            "category": "Groceries",
            "sub_category": "Organic",
            "sub_sub_category": "Organic Vegetables"
        },
        {
            "sku": "SWEET001",
            "mrp": 250,
            "sale_price": 200,
            "quantity": 2,
            "category": "Food",
            "sub_category": "Sweets",
            "sub_sub_category": "Traditional Sweets"
        }
    ]
}
```

### **Category Filtering Logic for GROCERY50**

| Step | Filter | Items Processed | Result |
|------|--------|----------------|--------|
| 1 | **Include**: "Groceries" | GROC001 ✅, ELEC001 ❌, ORG001 ✅, SWEET001 ❌ | GROC001, ORG001 |
| 2 | **Exclude**: "Organic" | GROC001 ✅, ORG001 ❌ | GROC001 |
| 3 | **Eligible Items** | GROC001 only | ₹200 |
| 4 | **Min Purchase Check** | ₹200 ≥ ₹150 | ✅ **Applicable** |

### **Response:**
```json
[
    {
        "promotion_code": "GROCERY50",
        "title": "50% off Groceries",
        "description": "Get 50% discount on grocery items",
        "offer_type": "flat_discount",
        "discount_amount": 50,
        "min_purchase": 150,
        "is_applicable": true
    },
    {
        "promotion_code": "ELECTRONICS100",
        "title": "₹100 off Electronics",
        "description": "Flat ₹100 discount on electronics",
        "offer_type": "flat_discount",
        "discount_amount": 100,
        "min_purchase": 500,
        "is_applicable": true
    },
    {
        "promotion_code": "FOOD25",
        "title": "₹25 off Food",
        "description": "₹25 discount on food items",
        "offer_type": "flat_discount",
        "discount_amount": 25,
        "min_purchase": 300,
        "is_applicable": true
    }
]
```

---

## 💰 **Scenario 2: Calculate Discount with GROCERY50**

### **Discount Calculation API**

```bash
POST /app/v1/cart/discount/calculate
Content-Type: application/json

{
    "cart_value": 1220,
    "promo_code": "GROCERY50",
    "items": [
        {
            "sku": "GROC001",
            "mrp": 120,
            "sale_price": 100,
            "quantity": 2,
            "category": "Groceries",
            "sub_category": "Dairy Products",
            "sub_sub_category": "Milk & Cream"
        },
        {
            "sku": "ELEC001",
            "mrp": 600,
            "sale_price": 500,
            "quantity": 1,
            "category": "Electronics",
            "sub_category": "Mobile Accessories",
            "sub_sub_category": "Chargers"
        },
        {
            "sku": "ORG001",
            "mrp": 150,
            "sale_price": 120,
            "quantity": 1,
            "category": "Groceries",
            "sub_category": "Organic",
            "sub_sub_category": "Organic Vegetables"
        },
        {
            "sku": "SWEET001",
            "mrp": 250,
            "sale_price": 200,
            "quantity": 2,
            "category": "Food",
            "sub_category": "Sweets",
            "sub_sub_category": "Traditional Sweets"
        }
    ],
    "user_id": "user123",
    "facility_name": "ROZANA_TEST_WH1"
}
```

### **Mathematical Calculation for GROCERY50**

#### **Step 1: Category Filtering**
| SKU | Category Match | Organic Exclusion | Eligible | Item Total |
|-----|----------------|-------------------|----------|------------|
| GROC001 | ✅ Groceries | ✅ Not Organic | ✅ **Eligible** | ₹200 |
| ELEC001 | ❌ Electronics | N/A | ❌ Not Eligible | ₹500 |
| ORG001 | ✅ Groceries | ❌ Is Organic | ❌ Not Eligible | ₹120 |
| SWEET001 | ❌ Food | N/A | ❌ Not Eligible | ₹400 |

**Eligible Cart Value**: ₹200 (GROC001 only)

#### **Step 2: Discount Distribution**
- **Total Discount**: ₹50
- **Eligible Items**: Only GROC001 (₹200)
- **GROC001 Discount**: ₹50 (entire discount goes to eligible item)
- **Per Unit Discount**: ₹50 ÷ 2 units = ₹25 per unit

#### **Step 3: Final Calculations**
| SKU | Original Price | Discount | Final Price | Offer Applied |
|-----|----------------|----------|-------------|---------------|
| GROC001 | ₹100 | ₹25 | ₹75 | ✅ true |
| ELEC001 | ₹500 | ₹0 | ₹500 | ❌ false |
| ORG001 | ₹120 | ₹0 | ₹120 | ❌ false |
| SWEET001 | ₹200 | ₹0 | ₹200 | ❌ false |

### **Response:**
```json
{
    "original_cart_value": 1220,
    "total_discount_amount": 50,
    "final_cart_value": 1170,
    "promotion_code": "GROCERY50",
    "promotion_type": "flat_discount",
    "items": [
        {
            "sku": "GROC001",
            "mrp": 120,
            "sale_price": 100,
            "calculated_sale_price": 75,
            "discount_amount": 25,
            "quantity": 2,
            "offer_applied": true
        },
        {
            "sku": "ELEC001",
            "mrp": 600,
            "sale_price": 500,
            "calculated_sale_price": 500,
            "discount_amount": 0,
            "quantity": 1,
            "offer_applied": false
        },
        {
            "sku": "ORG001",
            "mrp": 150,
            "sale_price": 120,
            "calculated_sale_price": 120,
            "discount_amount": 0,
            "quantity": 1,
            "offer_applied": false
        },
        {
            "sku": "SWEET001",
            "mrp": 250,
            "sale_price": 200,
            "calculated_sale_price": 200,
            "discount_amount": 0,
            "quantity": 2,
            "offer_applied": false
        }
    ]
}
```

---

## 🔬 **Scenario 3: Multiple Eligible Items - ELECTRONICS100**

### **Mathematical Calculation for ELECTRONICS100**

#### **Step 1: Category Filtering**
| SKU | Category Match | Eligible | Item Total |
|-----|----------------|----------|------------|
| GROC001 | ❌ Groceries | ❌ Not Eligible | ₹200 |
| ELEC001 | ✅ Electronics | ✅ **Eligible** | ₹500 |
| ORG001 | ❌ Groceries | ❌ Not Eligible | ₹120 |
| SWEET001 | ❌ Food | ❌ Not Eligible | ₹400 |

**Eligible Cart Value**: ₹500 (ELEC001 only)

#### **Step 2: Discount Distribution**
- **Total Discount**: ₹100
- **ELEC001 Proportion**: ₹500 ÷ ₹500 = 100%
- **ELEC001 Discount**: ₹100 × 100% = ₹100
- **Per Unit Discount**: ₹100 ÷ 1 unit = ₹100 per unit

### **Response for ELECTRONICS100:**
```json
{
    "original_cart_value": 1220,
    "total_discount_amount": 100,
    "final_cart_value": 1120,
    "promotion_code": "ELECTRONICS100",
    "promotion_type": "flat_discount",
    "items": [
        {
            "sku": "GROC001",
            "offer_applied": false
        },
        {
            "sku": "ELEC001",
            "calculated_sale_price": 400,
            "discount_amount": 100,
            "offer_applied": true
        },
        {
            "sku": "ORG001",
            "offer_applied": false
        },
        {
            "sku": "SWEET001",
            "offer_applied": false
        }
    ]
}
```

---

## 🧮 **Category-Based Discount Logic**

### **Enhanced Proportional Distribution**

The category-aware discount calculation follows this advanced logic:

1. **Category Filtering**: Apply `CategoryFilter.get_eligible_items()`
2. **Eligible Cart Value**: Calculate total from eligible items only
3. **Promotion Validation**: Validate against eligible cart value (not total)
4. **Proportional Distribution**: Distribute discount among eligible items
5. **Per Unit Calculation**: Calculate per-unit discount for each eligible item
6. **Response Building**: Mark `offer_applied: true/false` for each item

### **Mathematical Formula**

```
For each eligible item:
item_proportion = item_total_value / eligible_cart_total
item_discount = total_discount × item_proportion
per_unit_discount = item_discount / quantity
final_price = original_price - per_unit_discount
```

---

## 🔧 **Technical Architecture**

### **Category Filter Engine**

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| `CategoryFilter` | Main filtering engine | `get_eligible_items()`, `item_matches_categories()` |
| **Priority Logic** | SKU > Category filters | Ensures precise targeting |
| **Hierarchy Matching** | Multi-level category support | Matches any level: category/sub_category/sub_sub_category |

### **Integration Points**

| Service | Integration | Purpose |
|---------|-------------|---------|
| **Typesense** | Promotion querying | Fast promotion lookup with filters |
| **PromotionEngine** | Validation & computation | Existing promotion logic |
| **CategoryFilter** | Item filtering | Category-based eligibility |
| **Strategy Pattern** | Discount calculation | Extensible discount types |

### **Data Flow**

```
Cart Items → Category Filter → Eligible Items → Promotion Engine → Discount Calculation → Response
```

---

## 🚨 **Error Handling & Validation**

### **Common Error Scenarios**

| Error Code | Scenario | HTTP Status | Description |
|------------|----------|-------------|-------------|
| `PROMOTION_NOT_FOUND` | Invalid promo code | 404 | Promotion doesn't exist |
| `INVALID_PROMOTION` | Not applicable | 400 | Promotion criteria not met |
| `INSUFFICIENT_ELIGIBLE_ITEMS` | Category mismatch | 400 | No eligible items for promotion |
| `PRICE_MISMATCH` | Order validation | 400 | Discount calculation mismatch |

### **Validation Layers**

1. **Request Validation**: Pydantic model validation
2. **Category Validation**: Item category requirements
3. **Promotion Validation**: Business rule validation
4. **Price Validation**: Mathematical consistency checks

---

## 📊 **Performance & Monitoring**

### **Logging Strategy**

All operations include structured logging:

```json
{
  "operation": "calculate_discount",
  "promotion_code": "GROCERY50",
  "total_items": 4,
  "eligible_items": 1,
  "eligible_cart_value": 200,
  "total_discount": 50,
  "execution_time_ms": 45
}
```

### **Key Metrics**

- **Category Filter Performance**: Item filtering execution time
- **Promotion Applicability Rate**: % of promotions applicable to carts
- **Discount Distribution Accuracy**: Mathematical precision validation
- **Error Rate by Category**: Category-specific error tracking

---

## 🔮 **Advanced Features**

### **Multi-Level Category Matching**

```python
# Matches items at ANY hierarchy level
"Groceries" matches:
- category: "Groceries"
- sub_category: "Groceries" 
- sub_sub_category: "Groceries"
```

### **Smart Exclusion Logic**

```python
# Include first, then exclude (exclude takes precedence)
applicable_categories: ["Groceries", "Food"]
excluded_categories: ["Organic"]

# Result: All Groceries & Food EXCEPT Organic items
```

### **Precision Financial Calculations**

- **Decimal Type**: All monetary calculations use `Decimal`
- **Rounding Strategy**: Banker's rounding for fairness
- **Currency Precision**: 2 decimal places for INR
- **Validation Tolerance**: ±₹0.01 for rounding differences

---

## 🎯 **Best Practices**

### **Frontend Integration**

1. **Always send all 3 category levels** for each item
2. **Handle `offer_applied` flag** to show promotion targeting
3. **Display eligible cart value** for transparency
4. **Show category-specific messaging** for promotions

### **Backend Configuration**

1. **Use `applicable_categories`** instead of `included_categories`
2. **Set appropriate `min_purchase`** based on eligible items
3. **Configure exclusions carefully** to avoid conflicts
4. **Test with mixed category carts** for validation

### **Promotion Design**

1. **Clear category targeting** for better user experience
2. **Reasonable minimum purchase** thresholds
3. **Avoid complex exclusion rules** for simplicity
4. **Test edge cases** with single-item carts

---

## 📚 **Quick Reference**

### **API Endpoints**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/app/v1/cart/promotions/available` | Get applicable promotions |
| POST | `/app/v1/cart/discount/calculate` | Calculate item-level discounts |
| POST | `/pos/v1/cart/promotions/available` | POS promotion listing |
| POST | `/pos/v1/cart/discount/calculate` | POS discount calculation |

### **Required Fields**

| Field | Purpose | Example |
|-------|---------|---------|
| `facility_name` | Promotion targeting | `"ROZANA_TEST_WH1"` |
| `items[].category` | Category filtering | `"Groceries"` |
| `items[].sub_category` | Sub-category matching | `"Dairy Products"` |
| `items[].sub_sub_category` | Granular targeting | `"Milk & Cream"` |

### **Response Indicators**

| Field | Purpose | Values |
|-------|---------|--------|
| `is_applicable` | Promotion eligibility | `true`/`false` |
| `offer_applied` | Item-level targeting | `true`/`false` |
| `discount_amount` | Per-unit discount | `25.0` (₹25) |
| `calculated_sale_price` | Final item price | `75.0` (₹75) |

This comprehensive guide covers all aspects of the category-based promotions system with clear examples, mathematical calculations, and practical implementation details. 🚀
