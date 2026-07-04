package bot

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"giava/api"
	"giava/pkg/models"
)

type getUpdatesResponse struct {
	Ok     bool                    `json:"ok"`
	Result []models.TelegramUpdate `json:"result"`
}

// StartPolling begins a long-polling loop to fetch updates from Telegram
func StartPolling(botToken string) {
	if botToken == "" {
		fmt.Println("No TELEGRAM_BOT_TOKEN provided, polling disabled.")
		return
	}

	client := &http.Client{
		Timeout: 65 * time.Second, // slightly higher than the 60s long-polling timeout
	}

	offset := int64(0)
	fmt.Println("Starting Telegram Long-Polling engine...")

	for {
		url := fmt.Sprintf("https://api.telegram.org/bot%s/getUpdates?offset=%d&timeout=60", botToken, offset)
		resp, err := client.Get(url)
		if err != nil {
			fmt.Printf("Error polling Telegram: %v\n", err)
			time.Sleep(5 * time.Second)
			continue
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			fmt.Printf("Error reading Telegram response: %v\n", err)
			time.Sleep(5 * time.Second)
			continue
		}

		var updateResp getUpdatesResponse
		if err := json.Unmarshal(body, &updateResp); err != nil {
			fmt.Printf("Error parsing Telegram response: %v\n", err)
			time.Sleep(5 * time.Second)
			continue
		}

		if !updateResp.Ok {
			fmt.Printf("Telegram API error: %s\n", string(body))
			time.Sleep(5 * time.Second)
			continue
		}

		for _, update := range updateResp.Result {
			// Process each update synchronously or asynchronously
			api.ProcessUpdate(update)
			
			// Increment offset to acknowledge we've processed this update
			if update.UpdateID >= offset {
				offset = update.UpdateID + 1
			}
		}
	}
}
