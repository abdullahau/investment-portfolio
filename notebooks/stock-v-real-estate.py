# start snippet imports
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.optimize import newton
import plotly.graph_objects as go
import itables

itables.init_notebook_mode()
itables.options.allow_html = True
# itables.options.searching = False
itables.options.warn_on_undocumented_option = False

# end snippet imports


# start snippet helper_functions
# Rate Periodicity Conversion
def equivRate(rate, from_freq=1, to_freq=1):
    return to_freq * ((1 + rate / from_freq) ** (from_freq / to_freq) - 1)


# Present Value Function
def pv(r, n, pmt, fv=0, beg=False):
    c = np.full(n, pmt)
    t = np.arange(1, n + 1)
    d = 1.0 / np.power((1 + r), t)
    B = np.sum(d * c)
    tv = fv / (1 + r) ** n

    return np.where(beg, (B + tv) * (1 + r), B + tv)


# Amortizing Loan Principal Outstanding Balance
def principal_out(P, r, N, n):
    d1 = (1 + r) ** N - (1 + r) ** (n - 1)
    d2 = (1 + r) ** N - 1
    return P * d1 / d2


# end snippet helper_functions

# start snippet inputs
fx_rate = 1 / 3.67
currency = "AED"

start_date = pd.to_datetime("2020-01-01")
end_date = pd.DateOffset(months=12 * 12) + start_date
eval_end_date = pd.to_datetime("2025-07-01")

# Real Estate Investment
property_val = 510_000
down_payment = property_val * 0.2
loan_amount = property_val - down_payment

emi = 3_500
n_period = 12 * 12

interest_rate = newton(
    lambda r: pv(r=r, n=n_period, pmt=emi, beg=False) - loan_amount, x0=0
)

annual_rent = 36_000
annual_rent_gwth = 0.05
annual_appreciation = 0.05
monthly_appreciation = equivRate(annual_appreciation, 1, 12) / 12

# Closing Costs Operating Costs
service_fee = 15 * 484
closing_costs = 28_000  # closing costs = DLD fees + mortgage fees + commissions

# Equity Market Investment
snp500 = yf.Ticker("VOO")  # Vanguard S&P 500 ETF (VOO) (consider tax-efficient UCITs)
snp500_hist = snp500.history(start=start_date, end=end_date)
snp500_hist.reset_index(inplace=True)
snp500_hist[["Open", "High", "Low", "Close", "Dividends"]] /= fx_rate

# end snippet inputs


# start snippet loan_amort_schd
months = np.arange(n_period + 1)
dates = pd.date_range(start=start_date, end=end_date, freq="MS")
emi_cf = np.insert(np.full(n_period, emi), 0, 0)
principal_bal = principal_out(loan_amount, interest_rate, n_period, months + 1)
interest_portion = np.roll(principal_bal, 1) * interest_rate
principal_portion = emi_cf - interest_portion
prop_value = property_val * (1 + monthly_appreciation) ** months
rental_income = np.zeros(months.shape)
rental_income[12::12] = (
    annual_rent * (1 + annual_rent_gwth) ** (months[12::12] / 12) - service_fee
)

home_investment_schedule = pd.DataFrame({
    "Date": dates,
    "Month": months,
    "Principal Balance": principal_bal,
    "Interest Portion": interest_portion,
    "Principal Portion": principal_portion,
    "EMI": emi_cf,
    "Property Value": prop_value,
    "Equity": prop_value - principal_bal,
    "Net Rental Income": rental_income,
})

home_investment_schedule["Cumulative Interest"] = home_investment_schedule[
    "Interest Portion"
].cumsum()
home_investment_schedule["Principal Paid"] = home_investment_schedule[
    "Principal Portion"
].cumsum()

home_investment_schedule.set_index("Date", inplace=True)

s = home_investment_schedule.style
s.format("{:,.2f}").format_index(formatter=lambda x: x.strftime("%Y-%m-%d"))

# end snippet loan_amort_schd


# start snippet loan_amort_plot
loan_amort_fig = go.Figure()

loan_amort_fig.add_trace(
    go.Scatter(
        x=home_investment_schedule["Date"],
        y=home_investment_schedule["Cumulative Interest"],
        mode="lines",
        name="Cumulative Interest",
        line=dict(color="black", dash="dashdot", width=0.75),
    )
)

loan_amort_fig.add_trace(
    go.Scatter(
        x=home_investment_schedule["Date"],
        y=home_investment_schedule["Principal Paid"],
        mode="lines",
        name="Principal Paid",
        line=dict(color="black", dash="dash", width=0.75),
    )
)

loan_amort_fig.add_trace(
    go.Scatter(
        x=home_investment_schedule["Date"],
        y=home_investment_schedule["Principal Balance"],
        mode="lines",
        name="Principal Balance",
        line=dict(color="black", width=0.75),
    )
)

loan_amort_fig.update_layout(
    title="Loan Amortization Chart",
    xaxis_title="Date",
    yaxis_title=f"{currency}",
    legend=dict(orientation="h"),
    template="plotly_white",
)

loan_amort_fig.update_yaxes(tickformat=",")

# end snippet loan_amort_plot


# start snippet home_equity
home_equity_fig = go.Figure()

home_equity_fig.add_trace(
    go.Scatter(
        x=home_investment_schedule["Date"],
        y=home_investment_schedule["Equity"],
        mode="lines",
        name="Equity",
        line=dict(color="black", width=0.75),
    )
)

home_equity_fig.add_trace(
    go.Scatter(
        x=home_investment_schedule["Date"],
        y=home_investment_schedule["Property Value"],
        mode="lines",
        name="Property Value",
        line=dict(color="black", dash="dash", width=0.75),
    )
)

home_equity_fig.add_vline(
    x=eval_end_date,
    line=dict(color="black", dash="dash", width=0.75),
)


home_equity_fig.update_layout(
    title="Home Equity Over Time",
    xaxis_title="Date",
    yaxis_title=f"Home Equity ({currency})",
    legend=dict(orientation="h"),
    template="plotly_white",
)


home_equity_fig.update_yaxes(tickformat=",")
# end snippet home_equity

# start snippet property_performance_metrics
i = np.searchsorted(dates, eval_end_date)
t = (eval_end_date - start_date).total_seconds() / (60**2 * 24 * 365)
print(f"Home Value - Start ({currency}) = {property_val:,.2f}")
print(f"Home Value - Mid 2025 ({currency}) = {prop_value[i]:,.2f}")
print(f"% Increase in Home Value = {prop_value[i] / property_val - 1:.2%}")
print(
    f"Property Value Appreciation (CAGR) = {(prop_value[i] / property_val) ** (1 / t) - 1:,.2%}"
)
print()

total_investment = principal_portion[: i + 1].sum() + down_payment
current_home_equity = prop_value[i] - principal_bal[i]
print(f"Total Investment ({currency}) = {total_investment:,.2f}")
print(f"Home Equity Value ({currency}) = {current_home_equity:,.2f}")
print(f"Total Rental Income ({currency}) = {rental_income[: i + 1].sum():,.2f}")
print(f"Interest Cost ({currency}) = {interest_portion[: i + 1].sum():,.2f}")

hpr = (
    current_home_equity
    - total_investment
    + rental_income[: i + 1].sum()
    - interest_portion[: i + 1].sum()
    - closing_costs
) / total_investment
print(f"Holding Period Return = {hpr:,.2%}")
# end snippet property_performance_metrics


# start snippet benchmark_price_chart
snp_price_chart = go.Figure()

snp_price_chart.add_trace(
    go.Scatter(
        x=snp500_hist["Date"],
        y=snp500_hist["Close"],
        mode="lines",
        line=dict(color="black", width=1),
    )
)

snp_price_chart.update_layout(
    xaxis_title="Date",
    yaxis_title=f"Closing Price ({currency})",
    template="plotly_white",
)

snp_price_chart.update_yaxes(tickformat=",")
# end snippet benchmark_price_chart

# start snippet benchmark_cagr
years = (snp500_hist["Date"].iloc[-1] - snp500_hist["Date"].iloc[0]).total_seconds() / (
    60**2 * 24 * 365
)
cagr = (snp500_hist["Close"].iloc[-1] / snp500_hist["Close"].iloc[0]) ** (1 / years) - 1
print(f"S&P 500 CAGR = {cagr:.2%}")
# end snippet benchmark_cagr

# start snippet portfolio_performance
investment_dates = np.flatnonzero(
    np.diff(snp500_hist["Date"].dt.month, prepend=start_date.month)
)
monthly_investment = np.zeros(snp500_hist.shape[0])
monthly_investment[investment_dates] = emi  # principal_portion[1:i+1]
monthly_investment[0] = down_payment + closing_costs

trading_fees = monthly_investment * 0.0025
trading_fees = np.where(
    trading_fees < 1, np.where(trading_fees == 0, 0, 1), trading_fees
)

investment_df = pd.DataFrame()
investment_df["Date"] = snp500_hist["Date"].index
investment_df["Investments"] = monthly_investment
investment_df["Delta Shares"] = investment_df["Investments"] / snp500_hist["Open"]
investment_df["Trading Fees"] = trading_fees
investment_df["Total Shares"] = investment_df["Delta Shares"].cumsum()
investment_df["Portfolio Value"] = investment_df["Total Shares"] * snp500_hist["Close"]
investment_df["Avg Price"] = (
    investment_df["Investments"].cumsum() / investment_df["Total Shares"]
)
investment_df["Dividend Income"] = (
    investment_df["Total Shares"] * snp500_hist["Dividends"]
) * (1 - 0.3)  # Withholding Tax 30%

investment_df.set_index("Date", inplace=True)

s = investment_df.style.format("{:,.2f}").format_index(
    formatter=lambda x: x.strftime("%Y-%m-%d")
)
# end snippet portfolio_performance

# start snippet portfolio_performance_chart
portfolio_performance_chart = go.Figure()

portfolio_performance_chart.add_trace(
    go.Scatter(
        x=investment_df["Date"],
        y=investment_df["Portfolio Value"],
        mode="lines",
        line=dict(color="black", width=1),
    )
)

portfolio_performance_chart.update_layout(
    xaxis_title="Date",
    yaxis_title=f"Portfolio Value ({currency})",
    template="plotly_white",
)

portfolio_performance_chart.update_yaxes(tickformat=",")

portfolio_performance_chart.show()
# end snippet portfolio_performance_chart

# start snippet portfolio_performance_metrics
portfolio_value_end = investment_df["Portfolio Value"].to_numpy()[-1]
total_invested = investment_df["Investments"].sum()
total_dividends = investment_df["Dividend Income"].sum()
snp500_return = (
    portfolio_value_end + total_dividends - trading_fees.sum() - total_invested
) / total_invested

print(f"Total Investment ({currency}) = {total_invested:,.2f}")
print(f"Portfolio Value ({currency}) = {portfolio_value_end:,.2f}")
print(f"Dividend Income After Tax ({currency}) = {total_dividends:,.2f}")
print(f"Total Trading Cost = {investment_df['Trading Fees'].sum()}")

print(f"Holding Period Return = {snp500_return:.2%}")
# end snippet portfolio_performance_metrics
