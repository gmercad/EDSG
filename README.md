# Economic Development Snapshot Generator

> **Note:** This project requires **Python 3.12** and uses [Poetry](https://python-poetry.org/) for dependency management.

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
- **LLM Integration**: OpenAI API, LM Studio (Mistral-7B-Instruct-v0.1), Ollama
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
├── pyproject.toml           # Poetry project configuration
├── env.example              # Environment variables template
└── README.md                # This file
```

## Quick Start

### Prerequisites

- Python 3.12
- [Poetry](https://python-poetry.org/) (install with `pip install poetry`)
- OpenAI API key (optional, for GPT analysis)
- LM Studio (optional, for local Mistral-7B analysis)
- Ollama (optional, for local LLM analysis)

### Installation

1. **Clone the repository**
   ```cmd
   git clone <repository-url>
   cd EDSG
   ```

2. **Install dependencies with Poetry**
   ```cmd
   poetry install
   ```

3. **Set up environment variables**
   - Create a `.env` file in the project root. Example:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     LM_STUDIO_URL=http://localhost:1234
     OLLAMA_URL=http://localhost:11434
     ```
   - Replace the placeholder values with your actual API keys and URLs as needed.

4. **Run the application**
   ```cmd
   poetry run uvicorn app.main:app --reload
   ```

5. **Access the application**
   - API Documentation: http://127.0.0.1:8000/docs
   - Web Dashboard: http://127.0.0.1:8000/
   - Health Check: http://127.0.0.1:8000/health

## LLM Setup: OpenAI, LM Studio & Ollama

You can use a local or cloud LLM backend for analysis. This project supports **OpenAI**, **LM Studio**, and **Ollama** as LLM providers.

### OpenAI GPT
1. Get an API key from [OpenAI](https://platform.openai.com/)
2. Add to `.env`: `OPENAI_API_KEY=your_key_here`
3. Use `"llm_provider": "openai"` in API requests

### LM Studio (Mistral-7B)
1. Download and install [LM Studio](https://lmstudio.ai/)
2. Download a model (e.g., `mistral-7b-instruct-v0.1`)
3. Start the LM Studio API server:
   - Open LM Studio
   - Go to the "API" tab and click "Enable API Server"
   - Default server URL: `http://localhost:1234`
4. Add to `.env`: `LM_STUDIO_URL=http://localhost:1234`
5. Use `"llm_provider": "lm_studio"` in API requests and specify the model name (e.g., `mistral-7b-instruct-v0.1`)

### Ollama
1. Download and install [Ollama](https://ollama.com/download)
2. Pull a model:
   ```cmd
   ollama pull mistral:latest
   # or another supported model, e.g., llama2, codellama, etc.
   ```
3. Start the Ollama server (default: `http://localhost:11434`)
4. Add to `.env`: `OLLAMA_URL=http://localhost:11434`
5. Use `"llm_provider": "ollama"` in API requests and specify the model name (e.g., `mistral`)

**Note:**
- Make sure the model name you use matches exactly what is available in your LM Studio or Ollama instance.
- You can check available models in LM Studio via the UI, and in Ollama with:
  ```cmd
  ollama list
  ```

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

## Testing

Run the test suite:

```cmd
poetry run pytest tests/
```

Run with coverage:
```cmd
poetry run pytest tests/ --cov=app --cov-report=html
```

## Development

### Code Formatting
```cmd
poetry run black app/ tests/
poetry run isort app/ tests/
```

### Linting
```cmd
poetry run flake8 app/ tests/
```

### Running in Development Mode
```cmd
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install poetry && poetry install --no-root

COPY . .
EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
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
