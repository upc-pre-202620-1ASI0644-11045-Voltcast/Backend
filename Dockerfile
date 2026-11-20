FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Trust X-Forwarded-For only from App Service's internal proxy (link-local 169.254.x.x, as seen in the access logs);
# the rate limiter counts per client IP. shortcut: if Azure changes that range, the limiter goes back to one shared counter.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=169.254.0.0/16"]
