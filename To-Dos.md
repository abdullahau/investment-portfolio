## portfolio.py

The schematic idea is:
1) Take the transaction log and map the trade to a wide-form dataframe (symbols are columns, index is date, values are trades (quantity)
2) track holdings across time (full date range), account for splits (available in yfinanace but MAY not be available in user-provided data and if it is not provided, can be ignored), adjust holdings for splits
3) obtain closing prices for each symbol over the entire date range
4) compute value of adjusted holdings over time.
5) user-provided data can be of different lengths and different trading days. Ensure that all price data is forward filled from the last trading day and that not event data (dividends, splits, etc) are not forward filled.
6) information in the main notebook can be taken from the symbols_df
7) symbols which are user provided (missing from yfinance or marked as incorrect) price data should be found in config.MANUAL_DATA_DIR
8) All symbols and their price history will need to be converted to USD if they are in non-USD currency
9) the point of this class is not just to evaluate performance over time but also to look at the following:
    a) my current portfolio holdings
    b) total realized/unrealized gains for the portfolio and individual stock in my portfolio, split between capital gains and income earned for each holding and in aggregate (realized gain if the holding was sold and unrealized gains if unsold)
    c) my current holdings industry and sector concentration 
    d) geographic concentration (note that this metadata has not yet been added to `Symbols` and will be considered later.
    e) I would also like to look at total deposits and total return (gains/earnings) over the investment period.
    f) Then consider ways to evaluate returns that factor in cash outflows, inflows and unrealized earnings that accounts for time value of money
    
There are a few important facts to keep in mind about information inside the transaction/master logs

Firstly it is mandatory to structure all transaction logs with the following headers:

Date, Type, Symbol, Quantity, Price, Amount, Commission, Currency, Description, Exchange, Source

There are quite a few variations we can expect in "Type" of transactions. One this is for sure, this cannot be an empty field.

In my case, for example, I have the following Types: 'Net Deposit', 'buy', 'Net Dividend', 'sell', 'Qualified interest income reallocation for 2023', 'Credit/Margin Interest', 'Merger/Acquisition', 'Stock Split', 'High-Yield Cash Sweep'.

I have a small custom script to clean up data and removing useless entries like warrants and inter-account transfer of funds between equity and crypto.

But generally, I would like to enforce the following for all users:
1) Deposits and withdrawals should be Net deposits. If cash was deposited, ensure it is positive `Amount`. If cash was withdrawn, ensure it is negative `Amount`.
2) All dividend income should be net of taxes.
3)  `Credit/Margin Interest` income should be net of taxes too.
4) `buy`, `sell` should be separated for purchase Amount spent and commission paid.

Everything else is a bit of an accounting standard employed in the preperation.

My transactions log has two entries for a Stock Split event for any stock that has been split. On the same date there is a negative of quantity and positive of quantity to reflect the update in holdings. While this can be ignored entirely if the symbol has a prop data provider like yfinance or others where `get_history` call will return a price, dividend, and stock split history. But this may not be true for manually entered price histories. 

In my transaction log, I also have two entries of a single symbol of type 'Merger/Acquisition'. This is where the one symbol was acquired so one entry shows a reduction in the quantity of that symbol and another entry showing an inflow of 'Amount'. While this isn't "income", it is capital returned (either with some gain or with some loss), how should this amount be treated? Does it affect how we simulate benchmark? Or should it be ignored in benchmark simulation? How do we show gains and losses?

'High-Yield Cash Sweep' entries are just inflows and outflows of funds from cash account to a FIDIC insured cash pool.

'Qualified interest income reallocation for 2023' is just an accounting anomaly that can be ignored for all intents and purposes of this analysis. 

How can I work with a broad diversity of entry types? Can we abstract away and categorize entry types into ones that affect holdings, cash-flow, and income or some combination of the three?

Because these entry names won't be consistent, how can I also allow the user to categorize their unique entry names (or different cases) to what the basic operation needs to be taken while preparing the trade log or performing functions with this log?


## Working with Realized and Unrealized gains

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
