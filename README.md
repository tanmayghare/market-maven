# MarketMaven

A production-grade AI-powered market intelligence agent built with Google's Agent Development Kit (ADK) and Gemini 2.0 Flash. This agent provides comprehensive stock analysis, investment recommendations, and automated trading capabilities with enterprise-level monitoring and risk management.

## 🚀 Features

### Core Capabilities
- **Comprehensive Stock Analysis**: Technical, fundamental, and sentiment analysis
- **AI-Powered Recommendations**: Investment advice with confidence scoring
- **Automated Trading**: Execute trades with proper risk management
- **Real-time Data**: Live market data and historical analysis
- **Risk Management**: Stop-loss, take-profit, and position sizing
- **Portfolio Management**: Track positions and performance

### Production Features
- **Google ADK Integration**: Built on Google's Agent Development Kit
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Metrics & Monitoring**: Prometheus metrics and health checks
- **Rate Limiting**: API rate limiting and retry logic
- **Caching**: Intelligent data caching for performance
- **Error Handling**: Comprehensive error handling and recovery
- **Configuration Management**: Environment-based configuration
- **CLI Interface**: Rich command-line interface with progress indicators

## 🏗️ Architecture

```
market-maven/
├── market_maven/
│   ├── agents/           # ADK agents
│   │   └── market_maven.py
│   ├── tools/            # ADK tools
│   │   ├── data_fetcher_tool.py
│   │   ├── analyzer_tool.py
│   │   └── trader_tool.py
│   ├── core/             # Core utilities
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── metrics.py
│   ├── config/           # Configuration
│   │   └── settings.py
│   ├── models/           # Data models
│   │   └── schemas.py
│   └── cli.py           # CLI interface
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 🛠️ Installation

### Prerequisites
- Python 3.9+
- Alpha Vantage API key
- Google AI API key
- Interactive Brokers TWS (for live trading)
- Docker and Docker Compose (optional, for containerized deployment)

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd market-maven
   ```

2. **Quick setup with Make**:
   ```bash
   make quickstart
   ```

3. **Manual setup**:
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up environment
   cp env.example .env
   # Edit .env with your API keys and settings
   
   # Create necessary directories
   mkdir -p logs data
   ```

### Development Setup

For development with all tools and pre-commit hooks:

```bash
make install-dev
make setup
```

### Docker Setup

For containerized deployment:

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f stock-agent

# Stop services
docker-compose down
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API key | - | ✅ |
| `GOOGLE_API_KEY` | Google AI API key | - | ✅ |
| `ENVIRONMENT` | Environment (development/staging/production) | development | ❌ |
| `ENABLE_DRY_RUN` | Enable dry-run mode for trading | true | ❌ |
| `MAX_POSITION_SIZE` | Maximum shares per position | 100 | ❌ |
| `LOG_LEVEL` | Logging level | INFO | ❌ |
| `METRICS_PORT` | Prometheus metrics port | 8000 | ❌ |

### Interactive Brokers Setup

For live trading, configure Interactive Brokers TWS:

1. Install and configure TWS
2. Enable API connections in TWS settings
3. Set the correct host, port, and client ID in your `.env` file

## 🚀 Usage

### Command Line Interface

The agent provides a comprehensive CLI with multiple commands:

#### Stock Analysis
```bash
# Comprehensive analysis
python -m market_maven.cli analyze AAPL

# Technical analysis only
python -m market_maven.cli analyze AAPL --analysis-type technical

# Quick analysis
python -m market_maven.cli quick AAPL

# Custom risk tolerance and horizon
python -m market_maven.cli analyze AAPL --risk-tolerance aggressive --investment-horizon long_term
```

#### Trading
```bash
# Market order (dry-run by default)
python -m market_maven.cli trade AAPL BUY 10

# Limit order with stop-loss
python -m market_maven.cli trade AAPL BUY 10 --order-type LIMIT --limit-price 150.00 --stop-loss 140.00

# Live trading (requires proper setup)
python -m market_maven.cli trade AAPL BUY 10 --force
```

#### Portfolio Management
```bash
# View portfolio summary
python -m market_maven.cli portfolio

# View specific position
python -m market_maven.cli position AAPL

# View all positions
python -m market_maven.cli position
```

#### Interactive Mode
```bash
# Start interactive session
python -m market_maven.cli interactive
```

#### System Commands
```bash
# Health check
python -m market_maven.cli health

# View configuration
python -m market_maven.cli config

# Debug mode
python -m market_maven.cli --debug analyze AAPL
```

### Python API

```python
from market_maven import market_maven

# Analyze a stock
result = market_maven.analyze_stock(
    symbol="AAPL",
    analysis_type="comprehensive",
    risk_tolerance="moderate",
    investment_horizon="medium_term"
)

# Execute a trade
trade_result = market_maven.execute_trade(
    symbol="AAPL",
    action="BUY",
    quantity=10,
    order_type="MARKET",
    dry_run=True
)

# Get portfolio summary
portfolio = market_maven.get_portfolio_summary()

# Health check
health = market_maven.health_check()
```

## 📊 Monitoring

### Metrics

The agent exposes Prometheus metrics on port 8000 (configurable):

- Tool execution metrics
- Data fetch performance
- Analysis confidence scores
- Trading volume and success rates
- Cache hit/miss ratios
- System health indicators

Access metrics at: `http://localhost:8000/metrics`

### Logging

Structured JSON logging with:
- Correlation IDs for request tracing
- Performance metrics
- Error tracking
- Audit trails for trading operations

### Health Checks

```bash
# Check agent health
python -m market_maven.cli health
```

Returns status of:
- Agent components
- Tool availability
- API connectivity
- Configuration validity

## 🔒 Security

### Risk Management
- Position size limits
- Stop-loss and take-profit automation
- Portfolio risk assessment
- Dry-run mode for testing

### Data Security
- API key encryption
- Sensitive data masking in logs
- Secure configuration management
- Rate limiting and abuse prevention

## 🧪 Testing

### Dry-Run Mode
All trading operations default to dry-run mode in development:

```bash
# This will simulate the trade
python -m market_maven.cli trade AAPL BUY 10
```

### Development Environment
```bash
# Set development environment
export ENVIRONMENT=development
export ENABLE_DRY_RUN=true
```

## 📈 Analysis Types

### Comprehensive Analysis
- Technical indicators (RSI, MACD, SMA, EMA, Bollinger Bands)
- Fundamental metrics (P/E, EPS, market cap, growth rates)
- Market sentiment and news analysis
- Risk assessment and price targets

### Technical Analysis
- Chart patterns and trends
- Technical indicators and signals
- Support and resistance levels
- Momentum analysis

### Fundamental Analysis
- Financial statement analysis
- Valuation metrics
- Industry comparison
- Growth prospects

### Quick Analysis
- Rapid assessment for immediate decisions
- Key metrics and signals
- Simple buy/hold/sell recommendation

## 🚨 Risk Disclaimers

**IMPORTANT**: This software is for educational and research purposes only.

- **Not Financial Advice**: This agent does not provide financial advice
- **Trading Risks**: All trading involves risk of loss
- **No Guarantees**: Past performance does not guarantee future results
- **Use at Your Own Risk**: Users are responsible for their trading decisions
- **Test Thoroughly**: Always test in dry-run mode before live trading

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the health check output
- Enable debug logging for troubleshooting

## 🔄 Version History

### v1.0.0
- Initial production release
- Google ADK integration
- Comprehensive analysis capabilities
- Production-grade monitoring
- CLI interface
- Risk management features 