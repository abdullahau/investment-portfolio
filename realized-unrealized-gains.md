
### ✅ **1. How are realized and unrealized gains tracked over time?**

#### **Unrealized Gains**

* **Definition:** Gains/losses on holdings that you still own.
* **How it's tracked:**
  Unrealized gains are calculated continuously as:

  ```
  Unrealized Gain = (Current Market Price - Purchase Price) × Quantity Held
  ```
* **When it's updated:**

  * **Daily** (if you're marking to market — typical in dashboards).
  * Every time the market price changes.

#### **Realized Gains**

* **Definition:** Gains/losses from positions that have been sold.
* **How it's tracked:**

  ```
  Realized Gain = (Sale Price - Purchase Price) × Quantity Sold
  ```
* **When it's updated:**

  * At the **moment of sale**.
  * Stored as a cumulative total, or per-trade history, in many dashboards.

You can maintain a **running log** of both using:

* A transaction ledger (buy/sell history).
* Current prices (for unrealized).
* Historical prices at time of sale (for realized).

---

### ✅ **2. Are gains calculated only at the end of a time period?**

Not necessarily. It depends on **what you’re trying to measure**:

| Use Case            | Realized                                | Unrealized                                   |
| ------------------- | --------------------------------------- | -------------------------------------------- |
| **Daily dashboard** | Cumulative up to date of last trade     | MTM every day                                |
| **Monthly reports** | Gains/losses realized during that month | Unrealized as of end of month                |
| **Tax purposes**    | Realized gains in financial year        | Often ignored unless for tax-loss harvesting |

So for **dashboard tracking**, you'd typically track both continuously — not just at period-end.

---

### ✅ **3. What happens if proceeds from sales are reinvested?**

**Reinvestment doesn't "erase" gains** — here’s what happens:

#### a) **Realized gain is still recorded at time of sale.**

* You sold at a profit (or loss), so that’s locked in.
* **Even if** the cash is immediately reinvested in another stock.

#### b) **New investment creates a new cost basis.**

* The reinvested cash goes into a new position.
* This starts a **new unrealized gain/loss** trail.

#### Example:

| Date  | Action             | Cash Flow | Position       | Realized Gain | Unrealized Gain |
| ----- | ------------------ | --------- | -------------- | ------------- | --------------- |
| Jan 1 | Buy AAPL at \$100  | -\$1000   | 10 shares AAPL | \$0           | \$0             |
| Mar 1 | AAPL hits \$150    | —         | 10 shares AAPL | \$0           | \$500           |
| Mar 2 | Sell all AAPL      | +\$1500   | 0              | **\$500**     | \$0             |
| Mar 2 | Buy GOOG at \$1500 | -\$1500   | 1 share GOOG   | \$0           | \$0             |

So:

* AAPL gain = **realized**.
* GOOG investment = starts its own unrealized gain trail.

---

### 📊 **In your dashboard**, consider tracking:

1. **Cumulative Realized Gains** over time (line chart).
2. **Daily Unrealized Gains** (based on current holdings).
3. **Cumulative Contributions vs. Portfolio Value** (as you’re already doing).
4. Possibly a breakdown of **gains from price vs. income vs. dividends**.

Let me know if you want code snippets for this logic!


**Realized/Unrealized Gains**: To calculate gains and losses, you need to implement cost basis tracking. This involves tracking each purchase (a "lot") with its date and price. When you sell shares, you match the sale against a specific lot (usually First-In, First-Out or FIFO) to calculate the realized gain or loss. This is a significant feature that would require adding a new _calculate_cost_basis method to your Portfolio class.
