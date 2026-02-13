# Market Analyzer Bot

## Overview

A Python-based market analysis bot that monitors financial assets (cryptocurrencies and stocks) using technical indicators and sends notifications via Telegram. The bot tracks assets like BTC, ETH, AAPL, TSLA, and S&P 500, analyzing price movements using SMA and RSI indicators on hourly intervals.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Pattern
- **Single-file application**: All logic contained in `main.py` for simplicity
- **Async architecture**: Uses asyncio for non-blocking Telegram notifications
- **Class-based structure**: `MarketAnalyzer` class encapsulates all functionality

### Data Pipeline
1. **Data Fetching**: Uses yfinance to pull historical price data (5-day window, 1-hour intervals)
2. **Technical Analysis**: Applies indicators via the `ta` library (SMA-20, RSI-14)
3. **Signal Generation**: Compares current prices against indicators to generate trading signals
4. **Notification Delivery**: Sends alerts through Telegram Bot API

### Configuration Approach
- Environment variables for sensitive data (Telegram credentials)
- Hardcoded constants for non-sensitive settings (assets, intervals, check periods)
- Graceful degradation: Falls back to console logging if Telegram not configured

## External Dependencies

### APIs and Services
- **yfinance**: Yahoo Finance API wrapper for market data (no API key required)
- **Telegram Bot API**: For sending notifications (requires `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` environment variables)
- **Anthropic AI**: Integrated via Replit AI Integrations for future signal analysis (no API key required, billed to credits)

### Python Libraries
- `pandas`: Data manipulation and analysis
- `yfinance`: Market data fetching
- `ta`: Technical analysis indicators library
- `python-telegram-bot`: Telegram Bot API wrapper
- `asyncio`: Asynchronous I/O support

### Environment Variables Required
| Variable | Purpose |
|----------|---------|
| `TELEGRAM_TOKEN` | Bot authentication token from BotFather |
| `TELEGRAM_CHAT_ID` | Target chat/channel for notifications |