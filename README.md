# MarketMaven

An AI-powered stock market agent that provides intelligent stock analysis, investment recommendations, and automated trading capabilities using Google's Gemini 2.0 Flash model.

## ✨ Features

- **Smart Stock Analysis**: Technical, fundamental, and sentiment analysis
- **AI Investment Recommendations**: Get investment advice with confidence scoring
- **Automated Trading**: Execute trades with built-in risk management
- **Real-time Market Data**: Access live and historical market data
- **Portfolio Management**: Track your positions and performance
- **Risk Management**: Automatic stop-loss and take-profit controls

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Alpha Vantage API key ([Get one free](https://www.alphavantage.co/support/#api-key))
- Google AI API key ([Get started](https://ai.google.dev/))
- Interactive Brokers account (for live trading)

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd market-maven
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

3. **Start using**:
   ```bash
   # Analyze a stock
   python -m market_maven.cli analyze AAPL

   # Quick analysis
   python -m market_maven.cli quick-analysis AAPL

   # Interactive mode
   python -m market_maven.cli interactive
   ```

## 📊 Usage Examples

### Stock Analysis
```bash
# Comprehensive analysis with custom parameters
python -m market_maven.cli analyze AAPL --analysis-type comprehensive --risk-tolerance moderate

# Technical analysis only
python -m market_maven.cli analyze AAPL --analysis-type technical

# Quick decision-making analysis
python -m market_maven.cli quick-analysis TSLA
```

### Trading (Simulation Mode)
```bash
# Simulate a market buy order
python -m market_maven.cli trade AAPL BUY 10 --dry-run

# Simulate limit order with stop-loss
python -m market_maven.cli trade AAPL BUY 10 --order-type LIMIT --limit-price 150.00 --stop-loss 140.00 --dry-run
```

### Portfolio Management
```bash
# View portfolio summary
python -m market_maven.cli portfolio

# Check position for specific stock
python -m market_maven.cli position AAPL
```

## ⚙️ Configuration

### Required Environment Variables

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `ALPHA_VANTAGE_API_KEY` | Stock market data API key | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| `GOOGLE_API_KEY` | Google AI API key | [ai.google.dev](https://ai.google.dev/) |

### Optional Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_DRY_RUN` | Safe simulation mode | `true` |
| `MAX_POSITION_SIZE` | Maximum shares per trade | `100` |
| `LOG_LEVEL` | Logging detail level | `INFO` |

## 🛡️ Safety Features

- **Dry-run mode**: All trades are simulated by default
- **Position limits**: Maximum position size controls
- **Risk management**: Automatic stop-loss and take-profit
- **Rate limiting**: API request throttling
- **Error handling**: Comprehensive error recovery

## 🐳 Docker Support

```bash
# Run with Docker
docker-compose up -d

# View logs
docker-compose logs -f stock-agent
```

## 📚 Development

```bash
# Install development dependencies
make install-dev

# Run tests
make test

# Format code
make format
```

## ⚠️ Important Disclaimers

- **Not Financial Advice**: This tool is for educational and research purposes only
- **Risk Warning**: All investments carry risk of loss
- **Paper Trading**: Start with simulation mode before live trading
- **Your Responsibility**: Always verify recommendations before acting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

For issues and questions:
1. Check the documentation in the code comments
2. Review the configuration settings
3. Enable debug mode: `python -m market_maven.cli --debug`

---

**Remember**: Past performance does not guarantee future results. Always do your own research before making investment decisions.
