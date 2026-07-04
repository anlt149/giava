# Giava Telegram Bot

A Telegram bot built in Go to automatically track and report Vietnam gold prices and stock market changes.

## Prerequisites
- Docker Desktop (or another Docker engine) installed on your system.

## Getting Started

1. **Configure the Environment**
   Before starting the application, you need to set up your Telegram credentials. Copy the provided template to create your `.env` file:
   ```bash
   cp .env.example .env
   ```

2. **Add your Secrets**
   Open the newly created `.env` file and insert your `TELEGRAM_BOT_TOKEN` and your `TELEGRAM_CHAT_ID`. You can also tweak the `CRON_SCHEDULE` if you want to change how frequently the bot checks prices.

3. **Start the Application**
   Run the bot in the background using Docker Compose:
   ```bash
   docker compose up -d --build
   ```

## Managing the Bot
- To stop the bot: `docker compose down`
- To view logs: `docker compose logs -f`
