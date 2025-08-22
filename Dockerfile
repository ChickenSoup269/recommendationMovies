FROM python:3.10-slim

# Install Node.js and build tools
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python path
ENV PYTHON_PATH=/usr/bin/python3

# Set working directory
WORKDIR /app

# Copy and install Node.js dependencies
COPY package.json .
RUN npm install

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy project files
COPY . .

# Build TypeScript
RUN npm run build

# Expose port
EXPOSE 5000

# Start server
CMD ["node", "dist/server.js"]