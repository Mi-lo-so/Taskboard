FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt requirements.txt

# install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
# install dependencies from pyproject into the system interpreter
RUN uv pip install --system -r pyproject.toml

# Copy to the new folder
COPY . .

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]

# port in container for API access
EXPOSE 8000
