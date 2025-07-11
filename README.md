# Economic Development Snapshot Generator

A FastAPI-based application that generates comprehensive economic development snapshots using World Bank data and Large Language Models (LLMs).

## Features

- **World Bank Data Integration**: Fetches real-time economic indicators from the World Bank Open Data API
- **LLM-Powered Analysis**: Generates intelligent economic analysis using OpenAI GPT or local Mistral-7B via LM Studio
- **RESTful API**: Clean, documented API endpoints for easy integration
- **Web Dashboard**: Beautiful, responsive web interface for generating snapshots
- **Multiple LLM Support**: Choose between OpenAI GPT and local LM Studio for analysis
- **Comprehensive Testing**: Unit tests and integration tests included

## Tech Stack

- **Backend**: FastAPI (Python)
- **Data Processing**: Pandas, NumPy
- **LLM Integration**: OpenAI API, LM Studio (Mistral-7B-Instruct-v0.1)
- **Data Source**: World Bank Open Data API
- **Testing**: Pytest
- **Frontend**: HTML, CSS, JavaScript (Vanilla)

## Project Structure

```
economic_development_snapshot_generator/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── routes.py            # API route definitions
│   ├── utils.py             # Utility functions (data fetching, validation, etc.)
│   ├── templates/
│   │   └── dashboard.html   # Web dashboard template
│   └── static/              # Static assets
├── tests/                   # Unit and integration tests
│   ├── __init__.py
│   └── test_utils.py
├── requirements.txt         # Python dependencies
├── env.example             # Environment variables template
└── README.md               # This file
```

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- OpenAI API key (optional, for GPT analysis)
- LM Studio (optional, for local Mistral-7B analysis)

### Installation

1. **Clone the repository**
   ```cmd
   git clone <repository-url>
   cd EDSG
   ```

2. **Create a virtual environment**
   ```cmd
   python -m venv env
   env\Scripts\activate
   ```

3. **Install dependencies**
   ```cmd
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```cmd
   copy env.example .env
   ```
   
   Edit `.env` file and add your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   LM_STUDIO_URL=http://localhost:1234/v1
   ```

5. **Run the application**
   ```cmd
   uvicorn app.main:app --reload
   ```

6. **Access the application**
   - API Documentation: http://127.0.0.1:8000/docs
   - Web Dashboard: http://127.0.0.1:8000/
   - Health Check: http://127.0.0.1:8000/health

## API Endpoints

### Core Endpoints

- `GET /` - Root endpoint with basic information
- `GET /health` - Health check endpoint
- `GET /api/v1/health` - API health check

### Data Endpoints

- `GET /api/v1/countries` - Get available countries
- `GET /api/v1/indicators` - Get available economic indicators
- `GET /api/v1/data/{country_code}` - Get raw World Bank data for a country

### Snapshot Generation

- `POST /api/v1/generate-snapshot` - Generate economic development snapshot

#### Example Request:
```json
{
  "country_code": "USA",
  "indicator_codes": ["NY.GDP.MKTP.CD", "NY.GDP.MKTP.KD.ZG"],
  "year": 2022,
  "llm_provider": "openai"
}
```

#### Example Response:
```json
{
  "country_code": "USA",
  "country_name": "United States",
  "indicators": [
    {
      "code": "NY.GDP.MKTP.CD",
      "name": "GDP (current US$)",
      "values": [
        {
          "year": "2022",
          "value": 25462700000000,
          "unit": "",
          "obs_status": ""
        }
      ]
    }
  ],
  "snapshot_text": "The United States economy shows strong performance...",
  "generated_at": "2024-01-15T10:30:00",
  "metadata": {
    "llm_provider": "openai",
    "year": 2022,
    "indicator_count": 2
  }
}
```

## Available Economic Indicators

The application supports various World Bank economic indicators including:

- **GDP**: Current US$, Growth rate, Per capita
- **Inflation**: Consumer price index
- **Employment**: Unemployment rate
- **Trade**: Exports and imports as % of GDP
- **Government**: Central government debt
- **Social**: Literacy rate, Mortality rate

## LLM Configuration

### OpenAI GPT
1. Get an API key from [OpenAI](https://platform.openai.com/)
2. Add to `.env`: `OPENAI_API_KEY=your_key_here`
3. Use `"llm_provider": "openai"` in API requests

### LM Studio (Mistral-7B)
1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load the Mistral-7B-Instruct-v0.1 model
3. Start the local server (default: http://localhost:1234)
4. Use `"llm_provider": "lm_studio"` in API requests

## Testing

Run the test suite:

```cmd
pytest tests/
```

Run with coverage:
```cmd
pytest tests/ --cov=app --cov-report=html
```

## Development

### Code Formatting
```cmd
black app/ tests/
isort app/ tests/
```

### Linting
```cmd
flake8 app/ tests/
```

### Running in Development Mode
```cmd
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Deployment

### Production Considerations

1. **Environment Variables**: Set production values for all environment variables
2. **CORS**: Configure CORS settings for your domain
3. **Database**: Set up Supabase for data persistence (future feature)
4. **Logging**: Configure proper logging levels
5. **Security**: Use HTTPS and proper authentication

### Docker Deployment (Future)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Commit your changes: `git commit -am 'Add feature'`
7. Push to the branch: `git push origin feature-name`
8. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team

## Roadmap

- [ ] Supabase integration for data persistence
- [ ] User authentication and authorization
- [ ] Historical snapshot comparison
- [ ] Export functionality (PDF, Excel)
- [ ] Advanced analytics and visualizations
- [ ] Multi-language support
- [ ] Mobile application
