# 📈 Long-Term Investment & Target Tracker

A desktop stock market terminal developed using Python and PyQt6 that allows you to track your long-term stock investments on a **USD basis**. 

The application fetches real-time stock and exchange rate data via TradingView, calculates your costs, determines your Annual Percentage Rate (APR), and alerts you with a Windows desktop notification when your specified USD target is reached.

## 🚀 Features

* **Real-Time Data Feed:** Fetches instant prices of BIST stocks and the USD/TRY exchange rate without delay using the `tradingview-ta` infrastructure.
* **USD-Based Tracking:** Automatically converts all your investments to USD; clearly displays your entry cost, current value, and USD-based profit/loss ratio.
* **APR Calculation:** Calculates and displays your annualized return (APR) based on the number of days the position has been held.
* **Smart Notification System:** Runs in the background and sends a Windows system notification (System Tray) when a stock price hits your predefined USD target.
* **Trade History:** Moves closed positions from the `Active Positions` tab and permanently archives them along with their profit/loss status in the `Trade History` tab.
* **Data Privacy:** All portfolio data is stored locally in a `portfolio.json` file. No data is uploaded to the cloud.

## 🛠️ Technologies Used

* **Language:** Python 3
* **GUI:** PyQt6
* **Data Provider:** tradingview-ta
* **Notifications:** plyer
* **Packaging:** PyInstaller (for generating .exe)

## 💻 Installation and Execution

To run or develop the project on your local machine, follow these steps:

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/omerfk261/Long-Term-Investment-Tracker.git](https://github.com/omerfk261/Long-Term-Investment-Tracker.git)
   cd Long-Term-Investment-Tracker
